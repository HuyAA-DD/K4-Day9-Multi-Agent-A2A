"""Deterministic verification gates applied before Output Writer."""

from ecommerce_dispute.schemas.handoffs import PolicyDecision, VerificationIssue
from ecommerce_dispute.schemas.output import CaseOutput


def validate_refund_status(decision: PolicyDecision) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    should_require_action = decision.recommended_refund_brl > 0
    actual_requires_action = decision.case_status == "action_required"
    if should_require_action != actual_requires_action:
        issues.append(
            VerificationIssue(
                field="case_assessment.case_status",
                code="REFUND_STATUS_MISMATCH",
                message="case_status must be action_required exactly when refund is greater than 0",
                owner_agent="policy_agent",
                retryable=True,
            )
        )
    return issues


def validate_array_limits(output: CaseOutput) -> list[VerificationIssue]:
    """Validate limits after nested output schemas are finalized."""
    raise NotImplementedError

