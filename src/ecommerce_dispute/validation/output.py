"""Mechanical projection and cross-field validation for final CaseOutput."""

from typing import Any

from ecommerce_dispute.orchestration.output_builder import expected_evidence_ids
from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas import MechanicalReport, ValidationIssue
from ecommerce_dispute.schemas.output import CaseOutput
from ecommerce_dispute.validation.policy import outcome_consistency_issues


def _issue(field: str, code: str, message: str, owner: str) -> ValidationIssue:
    return ValidationIssue(
        field=field,
        code=code,
        message=message,
        owner_component=owner,
        retryable=False,
    )


def _compare(
    issues: list[ValidationIssue],
    field: str,
    actual: Any,
    expected: Any,
    owner: str,
) -> None:
    if actual != expected:
        issues.append(
            _issue(field, "PROJECTION_MISMATCH", f"Expected {expected!r}, got {actual!r}", owner)
        )


def validate_case_output(state: CaseState, output: CaseOutput) -> MechanicalReport:
    if not state.facts_ready() or state.policy_decision is None or state.policy_facts is None:
        return MechanicalReport(
            status="fail",
            issues=[_issue("state", "MISSING_FACTS", "Required facts are not ready", "orchestrator")],
        )
    assert state.customer_handoff is not None
    assert state.order_handoff is not None
    assert state.payment_handoff is not None
    assert state.delivery_handoff is not None
    customer = state.customer_handoff.payload
    order = state.order_handoff.payload
    payment = state.payment_handoff.payload
    delivery = state.delivery_handoff.payload
    outcome = state.policy_decision.outcome
    issues = [
        _issue(field, "OUTCOME_CONSISTENCY", message, "policy")
        for field, message in outcome_consistency_issues(outcome)
    ]
    checks = (
        ("case_id", output.case_id, state.case_input.case_id, "output_builder"),
        ("affected_entities.order_ids", output.affected_entities.order_ids, [order.order_id], "order"),
        (
            "affected_entities.item_ids",
            output.affected_entities.item_ids,
            [item.item_id for item in order.items[:5]],
            "order",
        ),
        (
            "affected_entities.seller_ids",
            output.affected_entities.seller_ids,
            list(order.seller_ids[:3]),
            "order",
        ),
        (
            "affected_entities.payment_ids",
            output.affected_entities.payment_ids,
            [row.payment_id for row in payment.payments[:5]],
            "payment",
        ),
        (
            "customer_context.customer_unique_id",
            output.customer_context.customer_unique_id,
            customer.customer_unique_id,
            "customer",
        ),
        (
            "customer_context.related_order_ids",
            output.customer_context.related_order_ids,
            list(customer.related_order_ids[:5]),
            "customer",
        ),
        (
            "product_context.product_ids",
            output.product_context.product_ids,
            list(order.product_ids[:5]),
            "order",
        ),
        (
            "product_context.category_names",
            output.product_context.category_names,
            list(order.category_names[:5]),
            "order",
        ),
        ("evidence_ids", output.evidence_ids, expected_evidence_ids(state), "output_builder"),
    )
    for check in checks:
        _compare(issues, *check)
    for field in (
        "delivered_at",
        "estimated_delivery_at",
        "carrier_handoff_at",
        "delivery_variance_hours",
        "seller_handoff_analysis",
        "late_handoff_seller_ids",
    ):
        expected = getattr(delivery, field)
        if isinstance(expected, tuple):
            expected = list(expected[:3])
        _compare(
            issues,
            f"delivery_analysis.{field}",
            getattr(output.delivery_analysis, field),
            expected,
            "delivery",
        )
    for field in (
        "item_total_brl",
        "freight_total_brl",
        "expected_total_brl",
        "payment_total_brl",
        "difference_brl",
        "reconciled",
        "payment_types",
    ):
        expected = getattr(payment, field)
        if isinstance(expected, tuple):
            expected = list(expected)
        _compare(
            issues,
            f"payment_reconciliation.{field}",
            getattr(output.payment_reconciliation, field),
            expected,
            "payment",
        )
    decision_checks = (
        ("case_assessment.primary_issue", output.case_assessment.primary_issue, outcome.primary_issue),
        (
            "case_assessment.secondary_issues",
            output.case_assessment.secondary_issues,
            outcome.secondary_issues,
        ),
        ("case_assessment.case_status", output.case_assessment.case_status, outcome.case_status),
        ("case_assessment.confidence", output.case_assessment.confidence, outcome.confidence),
        (
            "root_cause_analysis.ranked_causes",
            [
                (row.cause_code, row.rank)
                for row in output.root_cause_analysis.ranked_causes
            ],
            [(code, index) for index, code in enumerate(outcome.root_cause_codes[:3], start=1)],
        ),
        (
            "root_cause_analysis.responsible_parties",
            output.root_cause_analysis.responsible_parties,
            outcome.responsible_parties[:3],
        ),
        (
            "financial_resolution.recommended_refund_brl",
            output.financial_resolution.recommended_refund_brl,
            outcome.recommended_refund_brl,
        ),
        ("resolution_actions", output.resolution_actions, outcome.resolution_actions),
    )
    for field, actual, expected in decision_checks:
        _compare(issues, field, actual, expected, "policy")
    if set(output.customer_context.related_order_ids) & set(output.affected_entities.order_ids):
        issues.append(
            _issue(
                "customer_context.related_order_ids",
                "HISTORY_IN_AFFECTED_ENTITIES",
                "Historical orders must not appear in affected_entities",
                "customer",
            )
        )
    return MechanicalReport(status="fail" if issues else "pass", issues=issues)
