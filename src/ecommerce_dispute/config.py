"""Application configuration for the local model-driven Supervisor DAG."""

import os
from dataclasses import dataclass
from pathlib import Path

MODEL_NAME = "Qwen/Qwen3-1.7B-GGUF"
MODEL_FILE = "Qwen3-1.7B-Q8_0.gguf"
MODEL_PARAMETER_SIZE = "1.7B"
MODEL_QUANTIZATION = "Q8_0"
POLICY_VERSION = "EC_POLICY_V2"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
TRACE_PATH = PROJECT_ROOT / "logging" / "trace.jsonl"
METADATA_PATH = PROJECT_ROOT / "logging" / "metadata.json"


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the cached GGUF model."""

    model_gpu_layers: int = 0
    model_context_tokens: int = 4096
    model_threads: int = max(1, (os.cpu_count() or 4) // 2)
    max_output_tokens: int = 384
    max_agent_attempts: int = 3

    @classmethod
    def from_environment(cls) -> "Settings":
        defaults = cls()
        return cls(
            model_gpu_layers=int(os.getenv("MODEL_GPU_LAYERS", defaults.model_gpu_layers)),
            model_context_tokens=int(
                os.getenv("MODEL_CONTEXT_TOKENS", defaults.model_context_tokens)
            ),
            model_threads=int(os.getenv("MODEL_THREADS", defaults.model_threads)),
        )
