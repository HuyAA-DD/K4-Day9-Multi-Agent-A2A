"""Model-driven EC_POLICY_V2 specialist."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import PolicyDecision, PrimaryPolicySelection

from .base import AgentSpec, BaseAgent


def compact_policy_facts(state: CaseState) -> dict[str, object]:
    """Expose only validated facts needed for the semantic policy decision."""
    assert state.customer_facts is not None
    assert state.order_product_facts is not None
    assert state.payment_facts is not None
    assert state.delivery_facts is not None
    customer = state.customer_facts
    order = state.order_product_facts
    payment = state.payment_facts
    delivery = state.delivery_facts
    return {
        "order_status": order.order_status,
        "seller_ids": order.seller_ids,
        "item_total_brl": order.item_total_brl,
        "freight_total_brl": order.freight_total_brl,
        "payment_total_brl": payment.payment_total_brl,
        "payment_row_count": len(payment.payments),
        "reconciled": payment.reconciled,
        "split_payment": payment.split_payment,
        "delivery_variance_hours": delivery.delivery_variance_hours,
        "delivered_late": delivery.delivered_late,
        "late_handoff_seller_ids": delivery.late_handoff_seller_ids,
        "multi_item_order": order.multi_item_order,
        "multi_seller_order": order.multi_seller_order,
        "repeat_customer": customer.repeat_customer,
        "multiple_categories": order.multiple_categories,
    }


def policy_decision_is_source_grounded(
    decision: PolicyDecision,
    facts: dict[str, object],
) -> bool:
    """Reject invented identifiers/amounts without selecting a business outcome in code."""
    seller_ids = {str(value) for value in facts["seller_ids"]}
    allowed_party_ids = seller_ids | {"OLIST_PLATFORM", "LOGISTICS_PROVIDER"}
    if any(party.party_id not in allowed_party_ids for party in decision.responsible_parties):
        return False
    source_amounts = {
        0.0,
        round(float(facts["payment_total_brl"]), 2),
        round(float(facts["freight_total_brl"] or 0.0), 2),
    }
    if round(decision.recommended_refund_brl, 2) not in source_amounts:
        return False
    collections = (
        decision.secondary_issues,
        decision.root_cause_codes,
        decision.resolution_actions,
        [(party.party_type, party.party_id) for party in decision.responsible_parties],
    )
    return all(len(values) == len(set(values)) for values in collections)


class PolicyAgent(BaseAgent):
    spec = AgentSpec(
        name="policy_agent",
        prompt_file=BaseAgent.prompt_path("policy_agent.md"),
        allowed_tools=("inspect_validated_facts",),
    )

    async def run(
        self,
        state: CaseState,
        correction_feedback: list[dict[str, object]] | None = None,
    ) -> PolicyDecision:
        case_id = state.case_input.case_id
        if not state.all_investigation_facts_ready():
            raise RuntimeError("Policy Agent requires all investigation facts")
        self.trace("started", case_id, policy_version=state.case_input.policy_version)
        facts = compact_policy_facts(state)
        primary = await self.decide(
            case_id,
            {
                "task": "Select only the first matching EC_POLICY_V2 primary issue.",
                "facts": facts,
                "verifier_correction": correction_feedback or [],
            },
            PrimaryPolicySelection,
            max_new_tokens=64,
        )
        decision = await self.decide(
            case_id,
            {
                "task": (
                    "Complete every PolicyDecision field for the already selected primary issue."
                ),
                "selected_primary_issue": primary.primary_issue,
                "facts": facts,
                "verifier_correction": correction_feedback or [],
            },
            PolicyDecision,
            accept=lambda value: (
                value.primary_issue == primary.primary_issue
                and policy_decision_is_source_grounded(value, facts)
            ),
            rejection_message=(
                "primary_issue must copy selected_primary_issue; every party ID and refund "
                "must come from supplied facts; arrays must not contain duplicates"
            ),
            max_new_tokens=320,
        )
        self.trace("handoff", case_id, recipient="output_builder", payload_type="PolicyDecision")
        return decision
