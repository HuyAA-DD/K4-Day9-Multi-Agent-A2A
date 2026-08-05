"""Build a final CaseOutput from validated facts without model-generated arithmetic."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.output import CaseOutput


def build_case_output(state: CaseState) -> CaseOutput:
    raise NotImplementedError("Detailed output assembly will be implemented next")

