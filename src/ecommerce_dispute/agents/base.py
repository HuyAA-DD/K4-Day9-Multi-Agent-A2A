"""Common interface for model-driven agents with strict structured outputs."""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ecommerce_dispute.config import MODEL_NAME, PROJECT_ROOT
from ecommerce_dispute.llm import LocalModelClient
from ecommerce_dispute.tracing import TraceWriter

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class AgentDecisionError(RuntimeError):
    """Raised when an agent cannot produce an accepted structured decision."""


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    prompt_file: Path
    allowed_tools: tuple[str, ...]
    model_name: str = MODEL_NAME


class BaseAgent(ABC):
    """Base contract implemented by every model-backed agent."""

    spec: AgentSpec

    def __init__(
        self,
        model_client: LocalModelClient,
        trace_writer: TraceWriter,
        run_id: str,
    ) -> None:
        self.model_client = model_client
        self.trace_writer = trace_writer
        self.run_id = run_id

    @classmethod
    def prompt_path(cls, filename: str) -> Path:
        return PROJECT_ROOT / "prompts" / filename

    async def decide(
        self,
        case_id: str,
        payload: dict[str, Any],
        response_type: type[StructuredResult],
        *,
        accept: Callable[[StructuredResult], bool] | None = None,
        rejection_message: str = "Decision was not accepted",
        max_new_tokens: int | None = None,
    ) -> StructuredResult:
        """Require a schema-valid model decision; invalid decisions are retried then fail."""
        schema = response_type.model_json_schema()
        system_prompt = self.spec.prompt_file.read_text(encoding="utf-8") + (
            "\n\nReturn one JSON object only. No markdown and no explanation outside JSON. "
            "The runtime constrains decoding to the required JSON Schema."
        )
        feedback: str | None = None
        last_error = "unknown model decision error"
        for attempt in range(1, self.model_client.settings.max_agent_attempts + 1):
            request = dict(payload)
            raw: dict[str, Any] | None = None
            if feedback:
                request["correction"] = feedback
            try:
                raw = await self.model_client.complete_json(
                    system_prompt,
                    json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                    max_new_tokens=max_new_tokens,
                    response_schema=schema,
                )
                decision = response_type.model_validate(raw)
                if accept is not None and not accept(decision):
                    raise AgentDecisionError(rejection_message)
                self.trace(
                    "model_decision",
                    case_id,
                    attempt=attempt,
                    response_type=response_type.__name__,
                    model_output=decision.model_dump(mode="json"),
                )
                return decision
            except (AgentDecisionError, ValidationError, ValueError) as exc:
                last_error = str(exc)
            except Exception as exc:  # noqa: BLE001  # bounded model backend boundary
                last_error = f"{type(exc).__name__}: {exc}"
            self.trace(
                "model_decision_retry",
                case_id,
                attempt=attempt,
                response_type=response_type.__name__,
                error=last_error[:500],
                model_output=raw,
            )
            feedback = (
                f"Your previous response was invalid: {last_error}. "
                "Return a corrected JSON object matching the schema exactly."
            )
        raise AgentDecisionError(
            f"{self.spec.name} failed to produce {response_type.__name__}: {last_error}"
        )

    def trace(self, event: str, case_id: str, **details: Any) -> None:
        self.trace_writer.write(
            {
                "run_id": self.run_id,
                "case_id": case_id,
                "agent": self.spec.name,
                "model": self.spec.model_name,
                "event": event,
                **details,
            }
        )

    @abstractmethod
    async def run(self, state: Any) -> Any:
        """Process validated state and return a typed handoff payload."""
