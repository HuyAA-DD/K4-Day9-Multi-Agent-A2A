"""Final output contract.

The detailed nested models will be implemented together with the deterministic
output builder. Keeping a dedicated module prevents agents from writing ad-hoc
JSON dictionaries directly to the output directory.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class CaseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_assessment: dict[str, Any]
    affected_entities: dict[str, Any]
    customer_context: dict[str, Any]
    product_context: dict[str, Any]
    delivery_analysis: dict[str, Any]
    payment_reconciliation: dict[str, Any]
    root_cause_analysis: dict[str, Any]
    evidence_ids: list[str]
    financial_resolution: dict[str, Any]
    resolution_actions: list[str]

