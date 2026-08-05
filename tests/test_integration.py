import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ecommerce_dispute.config import DATA_DIR, INPUT_DIR
from ecommerce_dispute.data import OlistRepository
from ecommerce_dispute.orchestration.runner import DisputeRunner
from ecommerce_dispute.schemas.case import CaseInput
from ecommerce_dispute.schemas.output import CaseOutput
from ecommerce_dispute.tracing import TraceWriter

EC001_DECISION = {
    "primary_issue": "unsupported_late_claim",
    "secondary_issues": ["multi_item_order", "repeat_customer"],
    "case_status": "no_action",
    "root_cause_codes": ["DELIVERY_WITHIN_ESTIMATE"],
    "responsible_parties": [],
    "recommended_refund_brl": 0.0,
    "resolution_actions": ["reject_late_refund"],
    "confidence": 0.95,
}


class ScriptedModelClient:
    """Schema-aware test double; production always uses the local GGUF client."""

    settings = SimpleNamespace(max_agent_attempts=1)
    device_name = "scripted-local"

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        max_new_tokens: int | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del system_prompt, max_new_tokens
        request = json.loads(user_payload)
        title = (response_schema or {}).get("title")
        if title == "SupervisorDecision":
            return {"route": request["allowed_route"]}
        if title == "HandoffDecision":
            return {"action": "handoff", "confidence": 0.95}
        if title == "PrimaryPolicySelection":
            return {"primary_issue": "unsupported_late_claim", "confidence": 0.95}
        if title == "PolicyDecision":
            return dict(EC001_DECISION)
        raise AssertionError(f"Unexpected response schema: {title}")


def load_input(case_id: str) -> CaseInput:
    path = INPUT_DIR / f"{case_id}.json"
    return CaseInput.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_ec001_end_to_end_with_causal_structured_model(tmp_path: Path) -> None:
    repository = OlistRepository(DATA_DIR)
    repository.load()
    runner = DisputeRunner(
        repository=repository,
        trace_writer=TraceWriter(tmp_path / "trace.jsonl"),
        model_client=ScriptedModelClient(),  # type: ignore[arg-type]
        output_dir=tmp_path / "output",
        metadata_path=tmp_path / "metadata.json",
    )

    results = await runner.run_cases([load_input("EC_001")])

    assert results[0].status == "success"
    output = CaseOutput.model_validate_json(
        (tmp_path / "output" / "EC_001.json").read_text(encoding="utf-8")
    )
    assert output.case_assessment.primary_issue == "unsupported_late_claim"
    assert output.case_assessment.secondary_issues == ["multi_item_order", "repeat_customer"]
    assert output.financial_resolution.recommended_refund_brl == 0.0
    assert output.payment_reconciliation.reconciled is True
    assert output.delivery_analysis.delivery_variance_hours == -166.52

    trace_rows = [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert trace_rows[0]["event"] == "run_started"
    assert trace_rows[-1]["event"] == "run_completed"
    assert any(row.get("agent") == "policy_agent" for row in trace_rows)
    assert any(row.get("agent") == "verifier_agent" for row in trace_rows)


def test_input_inventory_contains_exactly_50_valid_cases() -> None:
    paths = sorted(INPUT_DIR.glob("EC_*.json"))

    assert [path.name for path in paths] == [f"EC_{index:03}.json" for index in range(1, 51)]
    for path in paths:
        case = CaseInput.model_validate_json(path.read_text(encoding="utf-8"))
        assert case.case_id == path.stem
