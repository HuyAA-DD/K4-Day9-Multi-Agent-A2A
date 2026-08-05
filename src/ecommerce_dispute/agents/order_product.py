"""Order, item, seller, product and category specialist."""

from typing import Any

from .base import AgentSpec, BaseAgent


class OrderProductAgent(BaseAgent):
    spec = AgentSpec(
        name="order_product_agent",
        prompt_file=BaseAgent.prompt_path("order_product_agent.md"),
        allowed_tools=("get_order", "get_order_items", "get_products", "get_sellers"),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Order & Product Agent runtime will be implemented next")

