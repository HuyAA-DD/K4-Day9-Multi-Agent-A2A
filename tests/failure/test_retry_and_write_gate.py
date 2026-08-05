import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from conftest import OracleModelClient, complete_outcome, load_case, select_primary_issue

from ecommerce_dispute.llm import ModelCompletion
from ecommerce_dispute.orchestration.runner import DisputeRunner


class InvalidThenValidClient(OracleModelClient):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.outcome_calls: defaultdict[str, int] = defaultdict(int)

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        *,
        model: str,
        response_schema: dict[str, Any],
        max_output_tokens: int | None = None,
    ) -> ModelCompletion:
        del system_prompt, max_output_tokens
        self.calls[model] += 1
        request = json.loads(user_payload)
        facts = request["facts"]
        primary = select_primary_issue(facts)
        if response_schema.get("title") == "PrimarySelection":
            return ModelCompletion(
                content={"primary_issue": primary, "confidence": 0.95},
                model_id=model,
                request_id=f"{model}-primary",
            )
        self.outcome_calls[model] += 1
        outcome = complete_outcome(primary, facts)
        if self.outcome_calls[model] == 1:
            outcome["recommended_refund_brl"] = 999999
        return ModelCompletion(content=outcome, model_id=model, request_id=f"{model}-retry")


class AlwaysInvalidClient(InvalidThenValidClient):
    async def complete_json(self, *args, **kwargs) -> ModelCompletion:
        result = await super().complete_json(*args, **kwargs)
        result.content["recommended_refund_brl"] = 999999
        return result


@pytest.mark.asyncio
async def test_agent_retries_its_own_invalid_grounding(
    tmp_path: Path,
    repository,
    test_settings,
) -> None:
    client = InvalidThenValidClient(test_settings)
    runner = DisputeRunner(
        repository,
        client,
        settings=test_settings,
        output_root=tmp_path / "output",
        logging_root=tmp_path / "logging",
        run_id="retry-run-001",
    )
    result = (await runner.run_cases([load_case("EC_001")]))[0]
    assert result.status == "success"
    assert client.calls["policy-test-model"] == 3
    assert client.calls["evaluator-test-model"] == 3


@pytest.mark.asyncio
async def test_failed_model_decision_creates_no_output(
    tmp_path: Path,
    repository,
    test_settings,
) -> None:
    runner = DisputeRunner(
        repository,
        AlwaysInvalidClient(test_settings),
        settings=test_settings,
        output_root=tmp_path / "output",
        logging_root=tmp_path / "logging",
        run_id="failed-run-001",
    )
    result = (await runner.run_cases([load_case("EC_001")]))[0]
    assert result.status == "failed"
    assert not (tmp_path / "output" / "failed-run-001" / "EC_001.json").exists()
