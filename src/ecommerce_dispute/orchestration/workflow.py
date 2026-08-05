"""Declarative safety boundary for routes proposed by the Supervisor model."""

from typing import ClassVar

from ecommerce_dispute.orchestration.state import CasePhase, CaseState


class SupervisorDag:
    """Expose legal graph edges without deciding which edge the model selects."""

    ROUTE_GUARDS: ClassVar[dict[CasePhase, tuple[str, tuple[str, ...]]]] = {
        CasePhase.RECEIVED: (
            "investigate_customer_order",
            ("customer_agent", "order_product_agent"),
        ),
        CasePhase.INVESTIGATING: (
            "investigate_payment_delivery",
            ("payment_agent", "delivery_agent"),
        ),
        CasePhase.POLICY_READY: ("apply_policy", ("policy_agent",)),
        CasePhase.DECIDED: ("verify_output", ("verifier_agent",)),
        CasePhase.VERIFYING: ("verify_output", ("verifier_agent",)),
    }

    def allowed_route(self, state: CaseState) -> tuple[str, tuple[str, ...]]:
        return self.ROUTE_GUARDS.get(state.phase, ("", ()))
