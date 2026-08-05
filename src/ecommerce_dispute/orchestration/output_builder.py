"""Pure projection from validated facts and a model-created decision to final schema."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.output import (
    AffectedEntities,
    CaseAssessment,
    CaseOutput,
    CustomerContext,
    DeliveryAnalysis,
    FinancialResolution,
    PaymentReconciliation,
    ProductContext,
    RankedCause,
    RootCauseAnalysis,
)
from ecommerce_dispute.tools import stable_unique


def expected_evidence_ids(state: CaseState) -> list[str]:
    if state.order_handoff is None or state.payment_handoff is None:
        raise RuntimeError("Evidence requires order and payment facts")
    if state.policy_decision is None:
        raise RuntimeError("Evidence requires a policy decision")
    order = state.order_handoff.payload
    payment = state.payment_handoff.payload
    outcome = state.policy_decision.outcome
    evidence = [f"order:{order.order_id}"]
    evidence.extend(f"item:{item.item_id}" for item in order.items[:5])
    evidence.extend(f"payment:{row.payment_id}" for row in payment.payments[:5])
    evidence.extend(
        f"seller:{party.party_id}"
        for party in outcome.responsible_parties
        if party.party_type == "seller"
    )
    evidence.extend(f"policy:{code}" for code in outcome.root_cause_codes[:3])
    return stable_unique(evidence)[:20]


def build_case_output(state: CaseState) -> CaseOutput:
    if not state.facts_ready() or state.policy_decision is None:
        raise RuntimeError("Cannot build output before facts and policy decision are ready")
    assert state.customer_handoff is not None
    assert state.order_handoff is not None
    assert state.payment_handoff is not None
    assert state.delivery_handoff is not None
    customer = state.customer_handoff.payload
    order = state.order_handoff.payload
    payment = state.payment_handoff.payload
    delivery = state.delivery_handoff.payload
    outcome = state.policy_decision.outcome
    return CaseOutput(
        case_id=state.case_input.case_id,
        case_assessment=CaseAssessment(
            primary_issue=outcome.primary_issue,
            secondary_issues=outcome.secondary_issues,
            case_status=outcome.case_status,
            confidence=outcome.confidence,
        ),
        affected_entities=AffectedEntities(
            order_ids=[order.order_id],
            item_ids=[item.item_id for item in order.items[:5]],
            seller_ids=list(order.seller_ids[:3]),
            payment_ids=[row.payment_id for row in payment.payments[:5]],
        ),
        customer_context=CustomerContext(
            customer_unique_id=customer.customer_unique_id,
            related_order_ids=list(customer.related_order_ids[:5]),
        ),
        product_context=ProductContext(
            product_ids=list(order.product_ids[:5]),
            category_names=list(order.category_names[:5]),
        ),
        delivery_analysis=DeliveryAnalysis(
            delivered_at=delivery.delivered_at,
            estimated_delivery_at=delivery.estimated_delivery_at,
            carrier_handoff_at=delivery.carrier_handoff_at,
            delivery_variance_hours=delivery.delivery_variance_hours,
            seller_handoff_analysis=list(delivery.seller_handoff_analysis[:3]),
            late_handoff_seller_ids=list(delivery.late_handoff_seller_ids[:3]),
        ),
        payment_reconciliation=PaymentReconciliation(
            item_total_brl=payment.item_total_brl,
            freight_total_brl=payment.freight_total_brl,
            expected_total_brl=payment.expected_total_brl,
            payment_total_brl=payment.payment_total_brl,
            difference_brl=payment.difference_brl,
            reconciled=payment.reconciled,
            payment_types=list(payment.payment_types),
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[
                RankedCause(cause_code=code, rank=index)
                for index, code in enumerate(outcome.root_cause_codes[:3], start=1)
            ],
            responsible_parties=outcome.responsible_parties[:3],
        ),
        evidence_ids=expected_evidence_ids(state),
        financial_resolution=FinancialResolution(
            recommended_refund_brl=outcome.recommended_refund_brl
        ),
        resolution_actions=outcome.resolution_actions,
    )
