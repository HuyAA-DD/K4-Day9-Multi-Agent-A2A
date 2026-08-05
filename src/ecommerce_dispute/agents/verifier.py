"""Final consistency and source-grounding specialist."""

from typing import Any

from .base import AgentSpec, BaseAgent


class VerifierAgent(BaseAgent):
    spec = AgentSpec(
        name="verifier_agent",
        prompt_file=BaseAgent.prompt_path("verifier_agent.md"),
        allowed_tools=(
            "validate_output_schema",
            "verify_arithmetic",
            "verify_evidence",
            "verify_policy_decision",
        ),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Verifier Agent runtime will be implemented next")

