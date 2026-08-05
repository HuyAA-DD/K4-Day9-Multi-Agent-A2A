import json
from pathlib import Path

import pytest
from conftest import OracleModelClient, load_case

from ecommerce_dispute.orchestration.runner import DisputeRunner
from ecommerce_dispute.schemas import CaseOutput


@pytest.mark.asyncio
async def test_ec001_full_workflow_writes_verified_run_namespace(
    tmp_path: Path,
    repository,
    test_settings,
) -> None:
    run_id = "integration-run-001"
    runner = DisputeRunner(
        repository,
        OracleModelClient(test_settings),
        settings=test_settings,
        output_root=tmp_path / "output",
        logging_root=tmp_path / "logging",
        run_id=run_id,
    )
    results = await runner.run_cases([load_case("EC_001")])
    assert results[0].status == "success"
    output_path = tmp_path / "output" / run_id / "EC_001.json"
    output = CaseOutput.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert output.case_assessment.primary_issue == "unsupported_late_claim"
    assert output.payment_reconciliation.reconciled is True
    assert output.delivery_analysis.delivery_variance_hours == -166.52

    log_dir = tmp_path / "logging" / run_id
    manifest = json.loads((log_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    trace = (log_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert "deterministic_comparator" in trace
    assert "policy-test-model" in trace
    assert "evaluator-test-model" in trace
    assert "OPENAI_API_KEY" not in trace
