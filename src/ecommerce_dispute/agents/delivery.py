"""Delivery and seller-handoff specialist."""

from typing import Any

from .base import AgentSpec, BaseAgent


class DeliveryAgent(BaseAgent):
    spec = AgentSpec(
        name="delivery_agent",
        prompt_file=BaseAgent.prompt_path("delivery_agent.md"),
        allowed_tools=("calculate_delivery_variance", "calculate_handoff_variance"),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Delivery Agent runtime will be implemented next")

