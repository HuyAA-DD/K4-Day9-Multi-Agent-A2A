"""Application configuration.

The model name is deliberately defined in source code because the assignment
requires it to be visible to graders. Credentials and endpoint configuration
remain environment variables.
"""

from dataclasses import dataclass
import os
from pathlib import Path


MODEL_NAME = "Qwen/Qwen3.5-9B"
MODEL_PARAMETER_SIZE = "9B"
POLICY_VERSION = "EC_POLICY_V2"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
TRACE_PATH = PROJECT_ROOT / "logging" / "trace.jsonl"
METADATA_PATH = PROJECT_ROOT / "logging" / "metadata.json"


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings that may vary between local and provider execution."""

    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    temperature: float = 0.0
    max_agent_attempts: int = 2

    @classmethod
    def from_environment(cls) -> "Settings":
        defaults = cls()
        return cls(
            base_url=os.getenv("OPENAI_BASE_URL", defaults.base_url),
            api_key=os.getenv("OPENAI_API_KEY", defaults.api_key),
        )
