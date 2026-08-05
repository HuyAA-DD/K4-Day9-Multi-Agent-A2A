"""Central supervisor responsible for DAG routing and retry decisions."""

from typing import Any

from .base import AgentSpec, BaseAgent


class SupervisorAgent(BaseAgent):
    spec = AgentSpec(
        name="supervisor_agent",
        prompt_file=BaseAgent.prompt_path("supervisor_agent.md"),
        allowed_tools=("inspect_case_state", "dispatch_agent", "request_correction"),
    )

    async def run(self, state: Any) -> Any:
        raise NotImplementedError("Supervisor Agent runtime will be implemented next")

