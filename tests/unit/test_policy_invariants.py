from ecommerce_dispute.schemas import PolicyOutcome, ValidatedPolicyFacts
from ecommerce_dispute.validation import policy_invariant_issues


def test_validator_rejects_lower_priority_model_choice() -> None:
    facts = ValidatedPolicyFacts(
        policy_version="EC_POLICY_V2",
        order_status="canceled",
        order_is_canceled=True,
        order_is_unavailable=False,
        seller_ids=[],
        item_total_brl=10,
        freight_total_brl=2,
        payment_total_brl=12,
        has_positive_payment=True,
        payment_row_count=2,
        reconciled=True,
        split_payment=True,
        delivery_variance_hours=-1,
        delivered_late=False,
        late_handoff_seller_ids=[],
        multi_item_order=False,
        multi_seller_order=False,
        repeat_customer=False,
        multiple_categories=False,
    )
    lower_priority = PolicyOutcome(
        primary_issue="valid_split_payment",
        secondary_issues=["split_payment"],
        case_status="no_action",
        root_cause_codes=["MULTIPLE_PAYMENTS_RECONCILED"],
        responsible_parties=[],
        recommended_refund_brl=0,
        resolution_actions=["explain_valid_split_payment"],
        confidence=0.95,
    )
    issues = policy_invariant_issues(lower_priority, facts)
    assert issues[0][0] == "primary_issue"
