"""Model-driven EC_POLICY_V2 decision agent."""

from ecommerce_dispute.schemas import PolicyDecision, ValidatedPolicyFacts

from .base import ModelPolicyRole


class PolicyAgent(ModelPolicyRole):
    role = "policy"
    prompt_filename = "policy_agent.md"
    prompt_version = "ec-policy-v2-policy-2"

    async def run(
        self,
        *,
        run_id: str,
        case_id: str,
        facts: ValidatedPolicyFacts,
        source_fact_hash: str,
        disputed_fields: tuple[str, ...] = (),
    ) -> PolicyDecision:
        outcome, metadata = await self.complete_outcome(
            run_id=run_id,
            case_id=case_id,
            facts=facts,
            source_fact_hash=source_fact_hash,
            task="Derive the complete EC_POLICY_V2 outcome from validated facts.",
            disputed_fields=disputed_fields,
        )
        return PolicyDecision(metadata=metadata, outcome=outcome)
