"""Outcome grounding and generic safety checks without a business-rule oracle."""

from decimal import Decimal

from ecommerce_dispute.schemas import PolicyOutcome, ValidatedPolicyFacts


def outcome_grounding_issues(
    outcome: PolicyOutcome,
    facts: ValidatedPolicyFacts,
) -> list[str]:
    """Reject invented source values without deciding which policy outcome is correct."""

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
        Decimal("0.00"),
        Decimal(str(facts.payment_total_brl)).quantize(Decimal("0.01")),
        Decimal(str(facts.freight_total_brl or 0.0)).quantize(Decimal("0.01")),
    }
    refund = Decimal(str(outcome.recommended_refund_brl))
    if refund.quantize(Decimal("0.01")) not in allowed_amounts:
        issues.append("recommended_refund_brl is not a source-backed amount")
    return issues


def outcome_consistency_issues(outcome: PolicyOutcome) -> list[tuple[str, str]]:
    """Check generic contradictions only; never derive an EC_POLICY_V2 answer."""

    issues: list[tuple[str, str]] = []
    refund = Decimal(str(outcome.recommended_refund_brl))
    if refund != refund.quantize(Decimal("0.01")):
        issues.append(
            (
                "recommended_refund_brl",
                "Monetary outcomes must have no more than two decimal places",
            )
        )
    if outcome.case_status == "no_action" and refund != Decimal("0.00"):
        issues.append(
            (
                "case_status",
                "no_action cannot contain a positive recommended refund",
            )
        )
    if outcome.case_status == "action_required" and refund <= Decimal("0.00"):
        issues.append(
            (
                "case_status",
                "action_required requires a positive recommended refund",
            )
        )
    if refund == Decimal("0.00") and "verify_refund_completion" in outcome.resolution_actions:
        issues.append(
            (
                "resolution_actions",
                "A zero-refund outcome cannot verify refund completion",
            )
        )
    return issues
