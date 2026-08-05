from pathlib import Path

from ecommerce_dispute.agents.policy import policy_decision_is_source_grounded
from ecommerce_dispute.config import PROJECT_ROOT
from ecommerce_dispute.schemas.handoffs import PolicyDecision, ResponsibleParty

FACTS = {
    "seller_ids": ["seller-1"],
    "payment_total_brl": 237.34,
    "freight_total_brl": 16.70,
}


def test_policy_decision_normalizes_percentage_confidence() -> None:
    decision = PolicyDecision(
        primary_issue="unsupported_late_claim",
        secondary_issues=["multi_item_order", "repeat_customer"],
        case_status="no_action",
        root_cause_codes=["DELIVERY_WITHIN_ESTIMATE"],
        responsible_parties=[],
        recommended_refund_brl=0,
        resolution_actions=["reject_late_refund"],
        confidence=95,
    )

    assert decision.confidence == 0.95
    assert policy_decision_is_source_grounded(decision, FACTS)


def test_source_grounding_rejects_invented_party_or_amount() -> None:
    invented_party = PolicyDecision(
        primary_issue="late_delivery_seller",
        secondary_issues=[],
        case_status="action_required",
        root_cause_codes=["SELLER_HANDOFF_AFTER_LIMIT"],
        responsible_parties=[ResponsibleParty(party_type="seller", party_id="invented")],
        recommended_refund_brl=16.70,
        resolution_actions=["refund_freight"],
        confidence=0.95,
    )
    invented_amount = invented_party.model_copy(
        update={
            "responsible_parties": [
                ResponsibleParty(party_type="seller", party_id="seller-1")
            ],
            "recommended_refund_brl": 999.0,
        }
    )

    assert not policy_decision_is_source_grounded(invented_party, FACTS)
    assert not policy_decision_is_source_grounded(invented_amount, FACTS)


def test_production_rule_engine_is_absent() -> None:
    policy_module = PROJECT_ROOT / "src" / "ecommerce_dispute" / "policies" / "ec_policy_v2.py"
    assert not Path(policy_module).exists()
