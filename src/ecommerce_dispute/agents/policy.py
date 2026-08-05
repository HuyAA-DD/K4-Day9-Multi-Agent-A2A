"""Policy specialist restricted to the deterministic EC_POLICY_V2 tool."""

from typing import Any

from .base import AgentSpec, BaseAgent


class PolicyAgent(BaseAgent):
    spec = AgentSpec(
        name="policy_agent",
        prompt_file=BaseAgent.prompt_path("policy_agent.md"),
        allowed_tools=("evaluate_ec_policy_v2",),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Policy Agent runtime will be implemented next")

