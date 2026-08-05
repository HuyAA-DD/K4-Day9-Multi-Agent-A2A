"""Optional model-backed adjudicator for persistent semantic disagreement."""

from ecommerce_dispute.schemas import (
    ExpectedPolicyDecision,
    PolicyDecision,
    ValidatedPolicyFacts,
    VerificationReport,
)

from .base import ModelPolicyRole


class AdjudicatorAgent(ModelPolicyRole):
    role = "adjudicator"
    prompt_filename = "adjudicator.md"
    prompt_version = "ec-policy-v2-adjudicator-1"

    async def run(
        self,
        *,
        run_id: str,
        case_id: str,
        facts: ValidatedPolicyFacts,
        source_fact_hash: str,
        policy: PolicyDecision,
        expected: ExpectedPolicyDecision,
        report: VerificationReport,
    ) -> PolicyDecision:
        outcome, metadata = await self.complete_outcome(
            run_id=run_id,
            case_id=case_id,
            facts=facts,
            source_fact_hash=source_fact_hash,
            task="Adjudicate a persistent disagreement and return the final EC_POLICY_V2 outcome.",
            additional_payload={
                "candidate_policy_outcome": policy.outcome.model_dump(mode="json"),
                "candidate_evaluator_outcome": expected.outcome.model_dump(mode="json"),
                "disputed_fields": [issue.field for issue in report.issues],
            },
        )
        return PolicyDecision(metadata=metadata, outcome=outcome)
