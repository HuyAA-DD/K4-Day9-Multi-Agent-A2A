import pytest
from conftest import load_case

from ecommerce_dispute.orchestration.state import CasePhase, CaseState
from ecommerce_dispute.orchestration.workflow import InvalidTransitionError, WorkflowOrchestrator


def test_workflow_accepts_only_declared_transitions() -> None:
    state = CaseState(run_id="test-run-123", case_input=load_case("EC_001"))
    workflow = WorkflowOrchestrator()
    workflow.transition(state, CasePhase.INVESTIGATING)
    workflow.transition(state, CasePhase.FACTS_READY)
    assert state.transition_history == ["received", "investigating", "facts_ready"]

    with pytest.raises(InvalidTransitionError):
        workflow.transition(state, CasePhase.WRITTEN)
