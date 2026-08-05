"""Common agent interface and immutable role specification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecommerce_dispute.config import MODEL_NAME, PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    prompt_file: Path
    allowed_tools: tuple[str, ...]
    model_name: str = MODEL_NAME


class BaseAgent(ABC):
    """Base contract implemented by every model-backed agent."""

    spec: AgentSpec

    @classmethod
    def prompt_path(cls, filename: str) -> Path:
        return PROJECT_ROOT / "prompts" / filename

    @abstractmethod
    async def run(self, state: Any) -> Any:
        """Process validated state and return a typed handoff payload."""

