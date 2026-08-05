"""Mechanical source, schema and transport gates applied before semantic verification."""

from typing import Any

from ecommerce_dispute.orchestration.output_builder import expected_evidence_ids
from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import (
    VerificationIssue,
    VerificationReport,
)
from ecommerce_dispute.schemas.output import CaseOutput


def _issue(
    field: str,
    code: str,
    message: str,
    owner: str | None = None,
    retryable: bool = False,
) -> VerificationIssue:
    return VerificationIssue(
        field=field,
        code=code,
        message=message,
        owner_agent=owner,
        retryable=retryable,
    )


def validate_array_limits(output: CaseOutput) -> list[VerificationIssue]:
    checks = {
        "affected_entities.order_ids": (output.affected_entities.order_ids, 5),
        "affected_entities.item_ids": (output.affected_entities.item_ids, 5),
        "affected_entities.seller_ids": (output.affected_entities.seller_ids, 3),
        "affected_entities.payment_ids": (output.affected_entities.payment_ids, 5),
        "customer_context.related_order_ids": (output.customer_context.related_order_ids, 5),
        "product_context.product_ids": (output.product_context.product_ids, 5),
        "product_context.category_names": (output.product_context.category_names, 5),
        "root_cause_analysis.ranked_causes": (output.root_cause_analysis.ranked_causes, 3),
        "root_cause_analysis.responsible_parties": (
            output.root_cause_analysis.responsible_parties,
            3,
        ),
        "evidence_ids": (output.evidence_ids, 20),
        "resolution_actions": (output.resolution_actions, 5),
    }
    issues: list[VerificationIssue] = []
    for field, (values, limit) in checks.items():
        if len(values) > limit:
            issues.append(_issue(field, "ARRAY_LIMIT", f"Array exceeds limit {limit}"))
    return issues


def _compare(
    issues: list[VerificationIssue],
    field: str,
    actual: Any,
    expected: Any,
    owner: str,
) -> None:
    if actual != expected:
        issues.append(
            _issue(
                field,
                "VALUE_MISMATCH",
                f"Expected {expected!r}, got {actual!r}",
                owner,
                True,
            )
        )


def verify_case_output(state: CaseState, output: CaseOutput) -> VerificationReport:
    if not state.all_investigation_facts_ready() or state.policy_decision is None:
        return VerificationReport(
            status="fail",
            issues=[_issue("state", "MISSING_FACTS", "Required facts are not ready")],
        )
    assert state.customer_facts is not None
    assert state.order_product_facts is not None
    assert state.payment_facts is not None
    assert state.delivery_facts is not None

    issues = validate_array_limits(output)
    order = state.order_product_facts
    payment = state.payment_facts
    delivery = state.delivery_facts

    _compare(issues, "case_id", output.case_id, state.case_input.case_id, "supervisor_agent")
    _compare(
        issues,
        "affected_entities.order_ids",
        output.affected_entities.order_ids,
        [order.order_id],
        "order_product_agent",
    )
    _compare(
        issues,
        "affected_entities.item_ids",
        output.affected_entities.item_ids,
        [item.item_id for item in order.items[:5]],
        "order_product_agent",
    )
    _compare(
        issues,
        "affected_entities.payment_ids",
        output.affected_entities.payment_ids,
        [row.payment_id for row in payment.payments[:5]],
        "payment_agent",
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
        _compare(
            issues,
            f"payment_reconciliation.{field}",
            getattr(output.payment_reconciliation, field),
            getattr(payment, field),
            "payment_agent",
        )
    for field in (
        "delivered_at",
        "estimated_delivery_at",
        "carrier_handoff_at",
        "delivery_variance_hours",
    ):
        _compare(
            issues,
            f"delivery_analysis.{field}",
            getattr(output.delivery_analysis, field),
            getattr(delivery, field),
            "delivery_agent",
        )

    expected_decision = state.policy_decision
    _compare(
        issues,
        "case_assessment.primary_issue",
        output.case_assessment.primary_issue,
        expected_decision.primary_issue,
        "policy_agent",
    )
    _compare(
        issues,
        "case_assessment.secondary_issues",
        output.case_assessment.secondary_issues,
        expected_decision.secondary_issues,
        "policy_agent",
    )
    _compare(
        issues,
        "case_assessment.case_status",
        output.case_assessment.case_status,
        expected_decision.case_status,
        "output_builder",
    )
    _compare(
        issues,
        "root_cause_analysis.responsible_parties",
        output.root_cause_analysis.responsible_parties,
        expected_decision.responsible_parties,
        "output_builder",
    )
    _compare(
        issues,
        "financial_resolution.recommended_refund_brl",
        output.financial_resolution.recommended_refund_brl,
        expected_decision.recommended_refund_brl,
        "policy_agent",
    )
    _compare(
        issues,
        "resolution_actions",
        output.resolution_actions,
        expected_decision.resolution_actions,
        "policy_agent",
    )
    _compare(
        issues,
        "evidence_ids",
        output.evidence_ids,
        expected_evidence_ids(state),
        "output_builder",
    )

    related = set(output.customer_context.related_order_ids)
    affected = set(output.affected_entities.order_ids)
    if related & affected:
        issues.append(
            _issue(
                "customer_context.related_order_ids",
                "HISTORY_IN_AFFECTED_ENTITIES",
                "Historical orders must not appear in affected_entities",
                "customer_agent",
            )
        )
    return VerificationReport(status="fail" if issues else "pass", issues=issues)
