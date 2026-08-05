"""Deterministic field-by-field comparison of independent policy decisions."""

from ecommerce_dispute.schemas import (
    SEMANTIC_FIELDS,
    ExpectedPolicyDecision,
    PolicyDecision,
    ValidationIssue,
    VerificationReport,
)


def compare_policy_decisions(
    policy: PolicyDecision,
    expected: ExpectedPolicyDecision,
) -> VerificationReport:
    issues: list[ValidationIssue] = []
    if policy.metadata.source_fact_hash != expected.metadata.source_fact_hash:
        issues.append(
            ValidationIssue(
                field="metadata.source_fact_hash",
                code="FACT_SNAPSHOT_MISMATCH",
                message="Policy and evaluator did not use the same validated fact snapshot",
                owner_component="workflow_orchestrator",
                retryable=False,
            )
        )
    policy_values = policy.outcome.model_dump(mode="json")
    expected_values = expected.outcome.model_dump(mode="json")
    for field in SEMANTIC_FIELDS:
        if policy_values[field] != expected_values[field]:
            issues.append(
                ValidationIssue(
                    field=field,
                    code="SEMANTIC_DISAGREEMENT",
                    message="Policy Agent and Independent Evaluator disagree on this field",
                    owner_component="semantic_agents",
                    retryable=True,
                )
            )
    return VerificationReport(status="disagree" if issues else "pass", issues=issues)
