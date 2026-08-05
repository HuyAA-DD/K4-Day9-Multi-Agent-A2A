"""Central supervisor responsible for DAG routing and retry decisions."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.orchestration.workflow import SupervisorDag
from ecommerce_dispute.schemas.handoffs import SupervisorDecision

from .base import AgentSpec, BaseAgent


class SupervisorAgent(BaseAgent):
    spec = AgentSpec(
        name="supervisor_agent",
        prompt_file=BaseAgent.prompt_path("supervisor_agent.md"),
        allowed_tools=("inspect_case_state", "dispatch_agent", "request_correction"),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dag = SupervisorDag()

    async def run(self, state: CaseState) -> tuple[str, ...]:
        case_id = state.case_input.case_id
        route_name, allowed_agents = self.dag.allowed_route(state)
        payload = {
            "task": "Select all agents that should run next for the current DAG phase.",
            "phase": state.phase.value,
            "allowed_route": route_name,
            "completed_handoffs": {
                "customer": state.customer_facts is not None,
                "order_product": state.order_product_facts is not None,
                "payment": state.payment_facts is not None,
                "delivery": state.delivery_facts is not None,
                "policy": state.policy_decision is not None,
            },
        }
        await self.decide(
            case_id,
            payload,
            SupervisorDecision,
            accept=lambda value: value.route == route_name,
            rejection_message="Route must equal the single allowed_route for this phase",
            max_new_tokens=96,
        )
        selected = allowed_agents
        self.trace("dispatch", case_id, ready_agents=list(selected), phase=state.phase.value)
        return selected
