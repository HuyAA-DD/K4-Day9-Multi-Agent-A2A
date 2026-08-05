"""Deterministic routing layer around model-backed agents."""

from ecommerce_dispute.orchestration.state import CasePhase, CaseState


class SupervisorDag:
    """Computes ready nodes; execution and model calls are added in the next stage."""

    def ready_agents(self, state: CaseState) -> tuple[str, ...]:
        if state.phase == CasePhase.RECEIVED:
            return ("customer_agent", "order_product_agent")

        if state.phase == CasePhase.INVESTIGATING:
            ready: list[str] = []
            if state.order_product_facts is not None:
                if state.payment_facts is None:
                    ready.append("payment_agent")
                if state.delivery_facts is None:
                    ready.append("delivery_agent")
            if state.all_investigation_facts_ready() and state.policy_decision is None:
                ready.append("policy_agent")
            return tuple(ready)

        if state.phase in {CasePhase.DECIDED, CasePhase.VERIFYING}:
            return ("verifier_agent",)

        return ()

