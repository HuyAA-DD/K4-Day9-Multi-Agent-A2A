"""Payment reconciliation specialist."""

from typing import Any

from .base import AgentSpec, BaseAgent


class PaymentAgent(BaseAgent):
    spec = AgentSpec(
        name="payment_agent",
        prompt_file=BaseAgent.prompt_path("payment_agent.md"),
        allowed_tools=("get_order_payments", "reconcile_payment"),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Payment Agent runtime will be implemented next")

