from pathlib import Path

import pytest
from conftest import OracleModelClient, load_case

from ecommerce_dispute.orchestration.runner import DisputeRunner
from ecommerce_dispute.schemas import CaseOutput


@pytest.mark.asyncio
async def test_all_50_cases_pass_golden_policy_and_output_schema(
    tmp_path: Path,
    repository,
    test_settings,
) -> None:
    run_id = "golden-run-050"
    runner = DisputeRunner(
        repository,
        OracleModelClient(test_settings),
        settings=test_settings,
        output_root=tmp_path / "output",
        logging_root=tmp_path / "logging",
        run_id=run_id,
    )
    cases = [load_case(f"EC_{index:03}") for index in range(1, 51)]
    results = await runner.run_cases(cases)
    assert all(result.status == "success" for result in results), [
        result for result in results if result.status != "success"
    ]
    output_dir = tmp_path / "output" / run_id
    output_paths = sorted(output_dir.glob("EC_*.json"))
    assert [path.name for path in output_paths] == [f"EC_{index:03}.json" for index in range(1, 51)]
    for path in output_paths:
        output = CaseOutput.model_validate_json(path.read_text(encoding="utf-8"))
        assert output.case_id == path.stem
