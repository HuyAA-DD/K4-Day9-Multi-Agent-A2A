"""Mechanically project validated model handoffs into the final output schema."""

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
from ecommerce_dispute.tools.evidence import (
    policy_evidence_id,
    seller_evidence_id,
)


def expected_evidence_ids(state: CaseState) -> list[str]:
    if state.order_product_facts is None or state.payment_facts is None:
        raise RuntimeError("Evidence requires order and payment facts")
    if state.policy_decision is None:
        raise RuntimeError("Evidence requires a policy decision")

    order = state.order_product_facts
    payment = state.payment_facts
    decision = state.policy_decision
    evidence = [f"order:{order.order_id}"]
    evidence.extend(f"item:{item.item_id}" for item in order.items[:5])
    evidence.extend(f"payment:{row.payment_id}" for row in payment.payments[:5])
    evidence.extend(
        seller_evidence_id(party.party_id)
        for party in decision.responsible_parties
        if party.party_type == "seller"
    )
    evidence.extend(policy_evidence_id(code) for code in decision.root_cause_codes[:3])
    return stable_unique(evidence)[:20]


def build_case_output(state: CaseState) -> CaseOutput:
    if not state.all_investigation_facts_ready() or state.policy_decision is None:
        raise RuntimeError("Cannot build output before facts and policy decision are ready")
    assert state.customer_facts is not None
    assert state.order_product_facts is not None
    assert state.payment_facts is not None
    assert state.delivery_facts is not None

    customer = state.customer_facts
    order = state.order_product_facts
    payment = state.payment_facts
    delivery = state.delivery_facts
    decision = state.policy_decision

    return CaseOutput(
        case_id=state.case_input.case_id,
        case_assessment=CaseAssessment(
            primary_issue=decision.primary_issue,
            secondary_issues=decision.secondary_issues,
            case_status=decision.case_status,
            confidence=decision.confidence,
        ),
        affected_entities=AffectedEntities(
            order_ids=[order.order_id],
            item_ids=[item.item_id for item in order.items[:5]],
            seller_ids=order.seller_ids[:3],
            payment_ids=[row.payment_id for row in payment.payments[:5]],
        ),
        customer_context=CustomerContext(
            customer_unique_id=customer.customer_unique_id,
            related_order_ids=customer.related_order_ids[:5],
        ),
        product_context=ProductContext(
            product_ids=order.product_ids[:5],
            category_names=order.category_names[:5],
        ),
        delivery_analysis=DeliveryAnalysis(
            delivered_at=delivery.delivered_at,
            estimated_delivery_at=delivery.estimated_delivery_at,
            carrier_handoff_at=delivery.carrier_handoff_at,
            delivery_variance_hours=delivery.delivery_variance_hours,
            seller_handoff_analysis=delivery.seller_handoff_analysis[:3],
            late_handoff_seller_ids=delivery.late_handoff_seller_ids[:3],
        ),
        payment_reconciliation=PaymentReconciliation(
            item_total_brl=payment.item_total_brl,
            freight_total_brl=payment.freight_total_brl,
            expected_total_brl=payment.expected_total_brl,
            payment_total_brl=payment.payment_total_brl,
            difference_brl=payment.difference_brl,
            reconciled=payment.reconciled,
            payment_types=payment.payment_types,
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[
                RankedCause(cause_code=code, rank=index)
                for index, code in enumerate(decision.root_cause_codes[:3], start=1)
            ],
            responsible_parties=decision.responsible_parties[:3],
        ),
        evidence_ids=expected_evidence_ids(state),
        financial_resolution=FinancialResolution(
            recommended_refund_brl=decision.recommended_refund_brl,
        ),
        resolution_actions=decision.resolution_actions,
    )
