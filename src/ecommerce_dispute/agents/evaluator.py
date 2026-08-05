"""Draft-blind independent model evaluation of EC_POLICY_V2."""

from ecommerce_dispute.schemas import ExpectedPolicyDecision, ValidatedPolicyFacts

from .base import ModelPolicyRole


class IndependentPolicyEvaluator(ModelPolicyRole):
    role = "evaluator"
    prompt_filename = "independent_evaluator.md"
    prompt_version = "ec-policy-v2-evaluator-2"

    async def run(
        self,
        *,
        run_id: str,
        case_id: str,
        facts: ValidatedPolicyFacts,
        source_fact_hash: str,
        disputed_fields: tuple[str, ...] = (),
    ) -> ExpectedPolicyDecision:
        outcome, metadata = await self.complete_outcome(
            run_id=run_id,
            case_id=case_id,
            facts=facts,
            source_fact_hash=source_fact_hash,
            task="Independently audit EC_POLICY_V2 and derive the expected complete outcome.",
            disputed_fields=disputed_fields,
        )
        return ExpectedPolicyDecision(metadata=metadata, outcome=outcome)
