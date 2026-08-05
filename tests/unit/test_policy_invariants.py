from ecommerce_dispute.schemas import PolicyOutcome, ValidatedPolicyFacts
from ecommerce_dispute.validation import outcome_consistency_issues, outcome_grounding_issues


def test_generic_consistency_rejects_no_action_with_positive_refund() -> None:
    outcome = PolicyOutcome(
        primary_issue="unsupported_late_claim",
        secondary_issues=[],
        case_status="no_action",
        root_cause_codes=["DELIVERY_WITHIN_ESTIMATE"],
        responsible_parties=[],
        recommended_refund_brl=10,
        resolution_actions=["reject_late_refund"],
        confidence=0.95,
    )
    issues = outcome_consistency_issues(outcome)
    assert issues == [("case_status", "no_action cannot contain a positive recommended refund")]


def test_validator_does_not_select_or_reject_a_primary_issue() -> None:
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
    outcome = PolicyOutcome(
        primary_issue="valid_split_payment",
        secondary_issues=["split_payment"],
        case_status="no_action",
        root_cause_codes=["MULTIPLE_PAYMENTS_RECONCILED"],
        responsible_parties=[],
        recommended_refund_brl=0,
        resolution_actions=["explain_valid_split_payment"],
        confidence=0.95,
    )
    assert outcome_grounding_issues(outcome, facts) == []
    assert outcome_consistency_issues(outcome) == []
