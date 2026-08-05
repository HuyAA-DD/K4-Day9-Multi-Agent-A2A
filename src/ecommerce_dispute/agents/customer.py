"""Customer identity and order-history specialist."""

from ecommerce_dispute.data import DataIntegrityError
from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import CustomerFacts, HandoffDecision
from ecommerce_dispute.tools import CustomerTools

from .base import AgentSpec, BaseAgent


class CustomerAgent(BaseAgent):
    spec = AgentSpec(
        name="customer_agent",
        prompt_file=BaseAgent.prompt_path("customer_agent.md"),
        allowed_tools=("get_order_customer", "get_related_orders"),
    )

    def __init__(self, tools: CustomerTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(self, state: CaseState) -> CustomerFacts:
        case_id = state.case_input.case_id
        order_id = state.case_input.customer_request.claimed_order_id
        self.trace("started", case_id, order_id=order_id)
        customer = self.tools.get_order_customer(order_id)
        if customer is None:
            raise DataIntegrityError(f"No customer row for claimed order {order_id}")
        unique_id = customer.get("customer_unique_id") or None
        related = (
            self.tools.get_related_orders(unique_id, order_id)
            if unique_id and state.case_input.investigation_scope.include_customer_history
            else []
        )
        await self.decide(
            case_id,
            {
                "task": "Decide whether the customer observation is ready for handoff.",
                "observation": {
                    "customer_unique_id": unique_id,
                    "related_order_ids": related,
                    "related_order_count": len(related),
                },
            },
            HandoffDecision,
            accept=lambda value: value.action == "handoff",
            rejection_message="Customer observation must be handed off when source fields are present",
            max_new_tokens=96,
        )
        facts = CustomerFacts(
            customer_unique_id=unique_id,
            related_order_ids=related,
            repeat_customer=bool(related),
        )
        self.trace("handoff", case_id, recipient="supervisor_agent", payload_type="CustomerFacts")
        return facts
