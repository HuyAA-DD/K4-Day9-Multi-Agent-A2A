"""Customer identity and order-history specialist."""

from typing import Any

from .base import AgentSpec, BaseAgent


class CustomerAgent(BaseAgent):
    spec = AgentSpec(
        name="customer_agent",
        prompt_file=BaseAgent.prompt_path("customer_agent.md"),
        allowed_tools=("get_order_customer", "get_related_orders"),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Customer Agent runtime will be implemented next")

