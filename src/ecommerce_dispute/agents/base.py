"""Shared runtime for model-driven policy roles."""

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from ecommerce_dispute.llm import StructuredModelClient
from ecommerce_dispute.schemas import (
    DecisionMetadata,
    PolicyOutcome,
    PrimarySelection,
    ValidatedPolicyFacts,
)
from ecommerce_dispute.tracing import TraceWriter
from ecommerce_dispute.validation import (
    outcome_grounding_issues,
    policy_invariant_issues,
    primary_selection_issue,
)


class AgentDecisionError(RuntimeError):
    """Raised after a model-backed role exhausts its bounded correction budget."""


class ModelPolicyRole:
    role: str
    prompt_filename: str
    prompt_version: str

    def __init__(
        self,
        model_client: StructuredModelClient,
        trace_writer: TraceWriter,
        model_name: str,
        prompt_dir: Path,
    ) -> None:
        self.model_client = model_client
        self.trace_writer = trace_writer
        self.model_name = model_name
        self.prompt_path = prompt_dir / self.prompt_filename
        self.system_prompt = self.prompt_path.read_text(encoding="utf-8") + (
            "\n\nReturn exactly one JSON object matching the supplied JSON Schema. "
            "Do not return markdown or prose outside JSON."
        )
        self.prompt_hash = sha256(self.system_prompt.encode("utf-8")).hexdigest()
        self.resolved_model_ids: set[str] = set()

    async def complete_primary_selection(
        self,
        *,
        run_id: str,
        case_id: str,
        facts: ValidatedPolicyFacts,
        source_fact_hash: str,
    ) -> PrimarySelection:
        payload = {
            "task": "Select only the first eligible EC_POLICY_V2 primary issue.",
            "policy_version": facts.policy_version,
            "facts": facts.model_dump(mode="json"),
        }
        correction: str | None = None
        last_error = "unknown primary selection error"
        settings = self.model_client.settings
        for attempt in range(1, settings.max_agent_attempts + 1):
            request = dict(payload)
            if correction:
                request["correction"] = correction
            started = perf_counter()
            try:
                completion = await self.model_client.complete_json(
                    self.system_prompt,
                    json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                    model=self.model_name,
                    response_schema=PrimarySelection.model_json_schema(),
                    max_output_tokens=96,
                )
                selection = PrimarySelection.model_validate(completion.content)
                issue = primary_selection_issue(selection.primary_issue, facts)
                if issue:
                    raise AgentDecisionError(issue)
                self.resolved_model_ids.add(completion.model_id)
                self.trace_writer.write(
                    {
                        "run_id": run_id,
                        "case_id": case_id,
                        "agent": self.role,
                        "event": "model_primary_selection",
                        "attempt": attempt,
                        "model": completion.model_id,
                        "provider_request_id": completion.request_id,
                        "prompt_version": self.prompt_version,
                        "prompt_hash": self.prompt_hash,
                        "source_fact_hash": source_fact_hash,
                        "latency_ms": round((perf_counter() - started) * 1000, 2),
                        "usage": completion.usage,
                        "primary_issue": selection.primary_issue,
                    }
                )
                return selection
            except (AgentDecisionError, ValidationError, ValueError) as exc:
                last_error = str(exc)
            except Exception as exc:  # noqa: BLE001  # bounded external model boundary
                last_error = f"{type(exc).__name__}: {exc}"
            self.trace_writer.write(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "agent": self.role,
                    "event": "model_primary_selection_retry",
                    "attempt": attempt,
                    "model": self.model_name,
                    "source_fact_hash": source_fact_hash,
                    "error": last_error[:500],
                }
            )
            correction = (
                f"The previous primary selection was invalid: {last_error}. "
                "Re-read the priority order and choose the first eligible outcome from facts."
            )
            if attempt < settings.max_agent_attempts and settings.retry_backoff_seconds > 0:
                await asyncio.sleep(settings.retry_backoff_seconds * (2 ** (attempt - 1)))
        raise AgentDecisionError(
            f"{self.role} failed primary selection after "
            f"{settings.max_agent_attempts} attempts: {last_error}"
        )

    async def complete_outcome(
        self,
        *,
        run_id: str,
        case_id: str,
        facts: ValidatedPolicyFacts,
        source_fact_hash: str,
        task: str,
        additional_payload: dict[str, Any] | None = None,
        disputed_fields: tuple[str, ...] = (),
    ) -> tuple[PolicyOutcome, DecisionMetadata]:
        primary = await self.complete_primary_selection(
            run_id=run_id,
            case_id=case_id,
            facts=facts,
            source_fact_hash=source_fact_hash,
        )
        payload: dict[str, Any] = {
            "task": task,
            "policy_version": facts.policy_version,
            "selected_primary_issue": primary.primary_issue,
            "facts": facts.model_dump(mode="json"),
        }
        if additional_payload:
            payload.update(additional_payload)
        if disputed_fields:
            payload["self_correction"] = {
                "fields_to_recheck": list(disputed_fields),
                "instruction": "Re-evaluate from facts; no other agent answer is provided.",
            }

        correction: str | None = None
        last_error = "unknown model decision error"
        settings = self.model_client.settings
        for attempt in range(1, settings.max_agent_attempts + 1):
            request = dict(payload)
            if correction:
                request["correction"] = correction
            started = perf_counter()
            try:
                completion = await self.model_client.complete_json(
                    self.system_prompt,
                    json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                    model=self.model_name,
                    response_schema=PolicyOutcome.model_json_schema(),
                    max_output_tokens=settings.max_output_tokens,
                )
                outcome = PolicyOutcome.model_validate(completion.content)
                if outcome.primary_issue != primary.primary_issue:
                    raise AgentDecisionError(
                        "primary_issue must exactly copy selected_primary_issue "
                        f"{primary.primary_issue!r}"
                    )
                grounding = outcome_grounding_issues(outcome, facts)
                invariants = policy_invariant_issues(outcome, facts)
                if grounding or invariants:
                    errors = grounding + [message for _, message in invariants]
                    raise AgentDecisionError("; ".join(errors))
                latency_ms = round((perf_counter() - started) * 1000, 2)
                self.resolved_model_ids.add(completion.model_id)
                self.trace_writer.write(
                    {
                        "run_id": run_id,
                        "case_id": case_id,
                        "agent": self.role,
                        "event": "model_decision",
                        "attempt": attempt,
                        "model": completion.model_id,
                        "provider_request_id": completion.request_id,
                        "prompt_version": self.prompt_version,
                        "prompt_hash": self.prompt_hash,
                        "source_fact_hash": source_fact_hash,
                        "latency_ms": latency_ms,
                        "usage": completion.usage,
                        "decision_summary": {
                            "primary_issue": outcome.primary_issue,
                            "secondary_issue_count": len(outcome.secondary_issues),
                            "responsible_party_count": len(outcome.responsible_parties),
                            "recommended_refund_brl": outcome.recommended_refund_brl,
                        },
                    }
                )
                metadata = DecisionMetadata(
                    policy_version=facts.policy_version,
                    prompt_version=self.prompt_version,
                    prompt_hash=self.prompt_hash,
                    source_fact_hash=source_fact_hash,
                    model_id=completion.model_id,
                    provider_request_id=completion.request_id,
                    agent_role=self.role,  # type: ignore[arg-type]
                )
                return outcome, metadata
            except (AgentDecisionError, ValidationError, ValueError) as exc:
                last_error = str(exc)
            except Exception as exc:  # noqa: BLE001  # bounded external model boundary
                last_error = f"{type(exc).__name__}: {exc}"
            self.trace_writer.write(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "agent": self.role,
                    "event": "model_decision_retry",
                    "attempt": attempt,
                    "model": self.model_name,
                    "prompt_version": self.prompt_version,
                    "source_fact_hash": source_fact_hash,
                    "error": last_error[:500],
                }
            )
            correction = (
                f"Your previous response failed validation: {last_error}. "
                "Re-evaluate only from the supplied facts and return a corrected object."
            )
            if attempt < settings.max_agent_attempts and settings.retry_backoff_seconds > 0:
                await asyncio.sleep(settings.retry_backoff_seconds * (2 ** (attempt - 1)))
        raise AgentDecisionError(
            f"{self.role} failed after {settings.max_agent_attempts} attempts: {last_error}"
        )
