"""Source grounding and cross-field invariants for model-created policy outcomes."""

from dataclasses import dataclass
from decimal import Decimal

from ecommerce_dispute.schemas import PolicyOutcome, ResponsibleParty, ValidatedPolicyFacts


@dataclass(frozen=True, slots=True)
class RequiredOutcome:
    status: str
    root: str
    parties: tuple[ResponsibleParty, ...]
    refund: float
    first_action: str


def outcome_grounding_issues(
    outcome: PolicyOutcome,
    facts: ValidatedPolicyFacts,
) -> list[str]:
    """Reject invented IDs and amounts without selecting a policy outcome."""

    seller_ids = set(facts.seller_ids)
    allowed_parties = {
        ("platform", "OLIST_PLATFORM"),
        ("logistics_provider", "LOGISTICS_PROVIDER"),
        *(("seller", seller_id) for seller_id in seller_ids),
    }
    issues: list[str] = []
    for party in outcome.responsible_parties:
        if (party.party_type, party.party_id) not in allowed_parties:
            issues.append("responsible_parties contains an ID outside validated facts")
    allowed_amounts = {
        0.0,
        round(facts.payment_total_brl, 2),
        round(facts.freight_total_brl or 0.0, 2),
    }
    if round(outcome.recommended_refund_brl, 2) not in allowed_amounts:
        issues.append("recommended_refund_brl is not a source-backed amount")
    return issues


def _required_outcome(
    primary_issue: str,
    facts: ValidatedPolicyFacts,
) -> RequiredOutcome | None:
    """Return invariants for the model-selected primary; this function never selects it."""

    canceled_paid = facts.order_is_canceled and facts.has_positive_payment
    unavailable_paid = facts.order_is_unavailable and facts.has_positive_payment
    late_seller = facts.delivered_late and bool(facts.late_handoff_seller_ids)
    late_logistics = facts.delivered_late and not facts.late_handoff_seller_ids
    valid_split = facts.split_payment and facts.reconciled is True
    supported_within_estimate = facts.delivered_late is False and facts.reconciled is True

    if primary_issue == "canceled_order_paid":
        if not canceled_paid:
            return None
        return RequiredOutcome(
            "action_required",
            "ORDER_CANCELED_AFTER_PAYMENT",
            (ResponsibleParty(party_type="platform", party_id="OLIST_PLATFORM"),),
            facts.payment_total_brl,
            "issue_full_refund",
        )
    if primary_issue == "unavailable_order_paid":
        if canceled_paid or not unavailable_paid:
            return None
        return RequiredOutcome(
            "action_required",
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            (ResponsibleParty(party_type="platform", party_id="OLIST_PLATFORM"),),
            facts.payment_total_brl,
            "issue_full_refund",
        )
    if primary_issue == "late_delivery_seller":
        if canceled_paid or unavailable_paid or not late_seller:
            return None
        parties = tuple(
            ResponsibleParty(party_type="seller", party_id=seller_id)
            for seller_id in facts.late_handoff_seller_ids[:3]
        )
        return RequiredOutcome(
            "action_required",
            "SELLER_HANDOFF_AFTER_LIMIT",
            parties,
            facts.freight_total_brl or 0.0,
            "refund_freight",
        )
    if primary_issue == "late_delivery_logistics":
        if canceled_paid or unavailable_paid or late_seller or not late_logistics:
            return None
        return RequiredOutcome(
            "action_required",
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            (
                ResponsibleParty(
                    party_type="logistics_provider",
                    party_id="LOGISTICS_PROVIDER",
                ),
            ),
            facts.freight_total_brl or 0.0,
            "refund_freight",
        )
    if primary_issue == "valid_split_payment":
        if canceled_paid or unavailable_paid or late_seller or late_logistics or not valid_split:
            return None
        return RequiredOutcome(
            "no_action",
            "MULTIPLE_PAYMENTS_RECONCILED",
            (),
            0.0,
            "explain_valid_split_payment",
        )
    if primary_issue == "unsupported_late_claim":
        if (
            canceled_paid
            or unavailable_paid
            or late_seller
            or late_logistics
            or valid_split
            or not supported_within_estimate
        ):
            return None
        return RequiredOutcome(
            "no_action",
            "DELIVERY_WITHIN_ESTIMATE",
            (),
            0.0,
            "reject_late_refund",
        )
    return None


def primary_selection_issue(primary_issue: str, facts: ValidatedPolicyFacts) -> str | None:
    if _required_outcome(primary_issue, facts) is None:
        return "Selected primary issue is not the first eligible EC_POLICY_V2 outcome"
    return None


def policy_invariant_issues(
    outcome: PolicyOutcome,
    facts: ValidatedPolicyFacts,
) -> list[tuple[str, str]]:
    """Validate the selected outcome; no code path chooses a primary issue for the agent."""

    issues: list[tuple[str, str]] = []
    refund_decimal = Decimal(str(outcome.recommended_refund_brl))
    if refund_decimal != refund_decimal.quantize(Decimal("0.01")):
        issues.append(
            (
                "recommended_refund_brl",
                "Monetary outcomes must have no more than two decimal places",
            )
        )
    required = _required_outcome(outcome.primary_issue, facts)
    if required is None:
        return [
            (
                "primary_issue",
                "The model-selected primary issue is not eligible for the validated facts",
            )
        ]

    expected_secondary = [
        name
        for name, enabled in (
            ("multi_item_order", facts.multi_item_order),
            ("multi_seller_order", facts.multi_seller_order),
            ("split_payment", facts.split_payment),
            ("repeat_customer", facts.repeat_customer),
            ("multiple_categories", facts.multiple_categories),
        )
        if enabled
    ]
    expected_actions = [required.first_action]
    if outcome.primary_issue == "late_delivery_seller":
        expected_actions.append("review_seller_handoff")
    elif outcome.primary_issue == "late_delivery_logistics":
        expected_actions.append("review_carrier_delay")
    if required.refund > 0:
        expected_actions.append("verify_refund_completion")
    if facts.multi_seller_order:
        expected_actions.append("coordinate_multi_seller_case")
    if facts.split_payment and outcome.primary_issue != "valid_split_payment":
        expected_actions.append("verify_payment_allocation")

    checks = (
        ("secondary_issues", outcome.secondary_issues, expected_secondary),
        ("case_status", outcome.case_status, required.status),
        ("root_cause_codes", outcome.root_cause_codes, [required.root]),
        ("responsible_parties", outcome.responsible_parties, list(required.parties)),
        (
            "recommended_refund_brl",
            round(outcome.recommended_refund_brl, 2),
            round(required.refund, 2),
        ),
        ("resolution_actions", outcome.resolution_actions, expected_actions),
    )
    for field, actual, expected in checks:
        if actual != expected:
            issues.append((field, f"Expected {expected!r}, got {actual!r}"))
    return issues
