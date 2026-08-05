"""Deterministic DAG transitions; no model is involved in routing."""

from typing import ClassVar

from ecommerce_dispute.orchestration.state import CasePhase, CaseState


class InvalidTransitionError(RuntimeError):
    pass


class WorkflowOrchestrator:
    ALLOWED_TRANSITIONS: ClassVar[dict[CasePhase, set[CasePhase]]] = {
        CasePhase.RECEIVED: {CasePhase.INVESTIGATING, CasePhase.FAILED},
        CasePhase.INVESTIGATING: {CasePhase.FACTS_READY, CasePhase.FAILED},
        CasePhase.FACTS_READY: {CasePhase.DECIDING, CasePhase.FAILED},
        CasePhase.DECIDING: {CasePhase.MECHANICALLY_VALIDATED, CasePhase.FAILED},
        CasePhase.MECHANICALLY_VALIDATED: {CasePhase.COMPARING, CasePhase.FAILED},
        CasePhase.COMPARING: {
            CasePhase.DECIDING,
            CasePhase.VERIFIED,
            CasePhase.NEEDS_REVIEW,
            CasePhase.FAILED,
        },
        CasePhase.VERIFIED: {CasePhase.WRITTEN, CasePhase.FAILED},
        CasePhase.NEEDS_REVIEW: set(),
        CasePhase.FAILED: set(),
        CasePhase.WRITTEN: set(),
    }

    def transition(self, state: CaseState, target: CasePhase) -> None:
        if target not in self.ALLOWED_TRANSITIONS[state.phase]:
            raise InvalidTransitionError(f"Illegal transition {state.phase.value} -> {target.value}")
        state.phase = target
        state.transition_history.append(target.value)

    def fail(self, state: CaseState, error: str) -> None:
        if state.phase not in {CasePhase.FAILED, CasePhase.NEEDS_REVIEW, CasePhase.WRITTEN}:
            self.transition(state, CasePhase.FAILED)
        state.error = error
