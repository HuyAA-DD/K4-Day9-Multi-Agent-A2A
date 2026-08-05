import pytest
from pydantic import ValidationError

from ecommerce_dispute.schemas import CaseOutput


def test_output_schema_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CaseOutput.model_validate({"case_id": "EC_001", "unknown": True})


def test_output_json_schema_preserves_required_top_level_shape() -> None:
    schema = CaseOutput.model_json_schema()
    assert set(schema["required"]) == {
        "case_id",
        "case_assessment",
        "affected_entities",
        "customer_context",
        "product_context",
        "delivery_analysis",
        "payment_reconciliation",
        "root_cause_analysis",
        "evidence_ids",
        "financial_resolution",
        "resolution_actions",
    }
    assert schema["additionalProperties"] is False
