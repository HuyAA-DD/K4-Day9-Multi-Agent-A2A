"""Runtime configuration for the deterministic workflow and model-backed policy roles."""

import os
from dataclasses import dataclass
from pathlib import Path

POLICY_VERSION = "EC_POLICY_V2"
MODEL_PROVIDER = "OpenAI API"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_ROOT = PROJECT_ROOT / "output"
LOGGING_ROOT = PROJECT_ROOT / "logging"
PROMPT_DIR = PROJECT_ROOT / "prompts"


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings without credentials in serialized metadata."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    policy_model: str = "gpt-4o-mini"
    evaluator_model: str = "gpt-4o-mini"
    adjudicator_model: str | None = None
    temperature: float = 0.0
    max_output_tokens: int = 512
    max_agent_attempts: int = 3
    semantic_retry_rounds: int = 1
    request_timeout_seconds: float = 60.0
    case_timeout_seconds: float = 300.0
    max_case_concurrency: int = 4
    retry_backoff_seconds: float = 0.25

    @classmethod
    def from_environment(cls) -> "Settings":
        defaults = cls()
        adjudicator = os.getenv("ADJUDICATOR_MODEL", "").strip() or None
        result = cls(
            base_url=os.getenv("OPENAI_BASE_URL", defaults.base_url).rstrip("/"),
            api_key=os.getenv("OPENAI_API_KEY", defaults.api_key),
            policy_model=os.getenv("POLICY_MODEL", defaults.policy_model),
            evaluator_model=os.getenv("EVALUATOR_MODEL", defaults.evaluator_model),
            adjudicator_model=adjudicator,
            request_timeout_seconds=float(
                os.getenv("OPENAI_TIMEOUT_SECONDS", defaults.request_timeout_seconds)
            ),
            case_timeout_seconds=float(
                os.getenv("CASE_TIMEOUT_SECONDS", defaults.case_timeout_seconds)
            ),
            max_case_concurrency=int(
                os.getenv("MAX_CASE_CONCURRENCY", defaults.max_case_concurrency)
            ),
        )
        if result.max_case_concurrency < 1:
            raise ValueError("MAX_CASE_CONCURRENCY must be at least 1")
        if result.request_timeout_seconds <= 0 or result.case_timeout_seconds <= 0:
            raise ValueError("Timeout values must be positive")
        return result
