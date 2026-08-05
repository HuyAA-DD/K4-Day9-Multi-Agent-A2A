"""End-to-end execution of the deterministic workflow for one or many cases."""

import asyncio
import platform
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ecommerce_dispute.agents import (
    AdjudicatorAgent,
    IndependentPolicyEvaluator,
    PolicyAgent,
)
from ecommerce_dispute.config import LOGGING_ROOT, MODEL_PROVIDER, OUTPUT_ROOT, PROMPT_DIR, Settings
from ecommerce_dispute.data import OlistRepository
from ecommerce_dispute.llm import StructuredModelClient
from ecommerce_dispute.orchestration.comparator import compare_policy_decisions
from ecommerce_dispute.orchestration.output_builder import build_case_output
from ecommerce_dispute.orchestration.output_writer import write_verified_output
from ecommerce_dispute.orchestration.state import CasePhase, CaseState
from ecommerce_dispute.orchestration.workflow import WorkflowOrchestrator
from ecommerce_dispute.schemas import CaseInput, VerificationReport
from ecommerce_dispute.schemas.reports import CaseManifestEntry, RunManifest
from ecommerce_dispute.tools import CustomerTools, OrderProductTools, PaymentTools
from ecommerce_dispute.tracing import TraceWriter
from ecommerce_dispute.validation import (
    compact_policy_facts,
    policy_fact_hash,
    validate_case_output,
    validate_fact_handoffs,
)
from ecommerce_dispute.workers import (
    CustomerFactsWorker,
    DeliveryAnalysisWorker,
    OrderProductFactsWorker,
    PaymentReconciliationWorker,
)


@dataclass(frozen=True, slots=True)
class CaseRunResult:
    case_id: str
    status: str
    phase: str
    output_path: Path | None = None
    error: str | None = None


ProgressCallback = Callable[[int, int, CaseRunResult], None]


class DisputeRunner:
    def __init__(
        self,
        repository: OlistRepository,
        model_client: StructuredModelClient,
        *,
        settings: Settings | None = None,
        output_root: Path = OUTPUT_ROOT,
        logging_root: Path = LOGGING_ROOT,
        run_id: str | None = None,
        write_outputs: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.repository = repository
        self.model_client = model_client
        self.settings = settings or model_client.settings
        self.output_root = output_root
        self.run_id = run_id or uuid4().hex
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,63}", self.run_id) is None:
            raise ValueError(
                "run_id must be 8-64 characters using only letters, digits, '.', '_' or '-'"
            )
        self.write_outputs = write_outputs
        self.progress_callback = progress_callback
        self.trace_writer = TraceWriter(logging_root, self.run_id)
        self.workflow = WorkflowOrchestrator()

        self.customer_worker = CustomerFactsWorker(
            CustomerTools(repository), trace_writer=self.trace_writer
        )
        self.order_worker = OrderProductFactsWorker(
            OrderProductTools(repository), trace_writer=self.trace_writer
        )
        self.payment_worker = PaymentReconciliationWorker(
            PaymentTools(repository), trace_writer=self.trace_writer
        )
        self.delivery_worker = DeliveryAnalysisWorker(trace_writer=self.trace_writer)
        self.policy_agent = PolicyAgent(
            model_client,
            self.trace_writer,
            self.settings.policy_model,
            PROMPT_DIR,
        )
        self.evaluator = IndependentPolicyEvaluator(
            model_client,
            self.trace_writer,
            self.settings.evaluator_model,
            PROMPT_DIR,
        )
        self.adjudicator = (
            AdjudicatorAgent(
                model_client,
                self.trace_writer,
                self.settings.adjudicator_model,
                PROMPT_DIR,
            )
            if self.settings.adjudicator_model
            else None
        )

    async def _execute_case(self, state: CaseState) -> CaseRunResult:
        case = state.case_input
        case_id = case.case_id
        self.workflow.transition(state, CasePhase.INVESTIGATING)
        customer_handoff, order_handoff = await asyncio.gather(
            self.customer_worker.run(self.run_id, case),
            self.order_worker.run(self.run_id, case),
        )
        state.customer_handoff = customer_handoff
        state.order_handoff = order_handoff

        payment_handoff, delivery_handoff = await asyncio.gather(
            self.payment_worker.run(self.run_id, case, order_handoff.payload),
            self.delivery_worker.run(self.run_id, case, order_handoff.payload),
        )
        state.payment_handoff = payment_handoff
        state.delivery_handoff = delivery_handoff
        fact_report = validate_fact_handoffs(
            self.run_id,
            case,
            customer_handoff,
            order_handoff,
            payment_handoff,
            delivery_handoff,
        )
        if fact_report.status == "fail":
            detail = "; ".join(issue.message for issue in fact_report.issues)
            raise RuntimeError(f"Fact validation failed: {detail}")
        self.workflow.transition(state, CasePhase.FACTS_READY)

        state.policy_facts = compact_policy_facts(
            case,
            customer_handoff.payload,
            order_handoff.payload,
            payment_handoff.payload,
            delivery_handoff.payload,
        )
        state.source_fact_hash = policy_fact_hash(state.policy_facts)
        disputed_fields: tuple[str, ...] = ()

        for semantic_round in range(self.settings.semantic_retry_rounds + 1):
            self.workflow.transition(state, CasePhase.DECIDING)
            state.attempts["semantic_round"] = semantic_round + 1
            policy, expected = await asyncio.gather(
                self.policy_agent.run(
                    run_id=self.run_id,
                    case_id=case_id,
                    facts=state.policy_facts,
                    source_fact_hash=state.source_fact_hash,
                    disputed_fields=disputed_fields,
                ),
                self.evaluator.run(
                    run_id=self.run_id,
                    case_id=case_id,
                    facts=state.policy_facts,
                    source_fact_hash=state.source_fact_hash,
                    disputed_fields=disputed_fields,
                ),
            )
            state.policy_decision = policy
            state.expected_decision = expected
            state.draft_output = build_case_output(state)
            state.mechanical_report = validate_case_output(state, state.draft_output)
            if state.mechanical_report.status == "fail":
                detail = "; ".join(issue.message for issue in state.mechanical_report.issues)
                raise RuntimeError(f"Mechanical validation failed: {detail}")
            self.workflow.transition(state, CasePhase.MECHANICALLY_VALIDATED)
            self.workflow.transition(state, CasePhase.COMPARING)
            state.verification_report = compare_policy_decisions(policy, expected)
            self.trace_writer.write(
                {
                    "case_id": case_id,
                    "component": "deterministic_comparator",
                    "event": "comparison_completed",
                    "semantic_round": semantic_round + 1,
                    "status": state.verification_report.status,
                    "disputed_fields": [
                        issue.field for issue in state.verification_report.issues
                    ],
                }
            )
            if state.verification_report.status == "pass":
                self.workflow.transition(state, CasePhase.VERIFIED)
                break
            disputed_fields = tuple(issue.field for issue in state.verification_report.issues)
            if semantic_round < self.settings.semantic_retry_rounds:
                continue

            if self.adjudicator is None:
                self.workflow.transition(state, CasePhase.NEEDS_REVIEW)
                state.error = "Persistent semantic disagreement requires review"
                return CaseRunResult(
                    case_id=case_id,
                    status="needs_review",
                    phase=state.phase.value,
                    error=state.error,
                )

            self.workflow.transition(state, CasePhase.DECIDING)
            state.policy_decision = await self.adjudicator.run(
                run_id=self.run_id,
                case_id=case_id,
                facts=state.policy_facts,
                source_fact_hash=state.source_fact_hash,
                policy=policy,
                expected=expected,
                report=state.verification_report,
            )
            state.draft_output = build_case_output(state)
            state.mechanical_report = validate_case_output(state, state.draft_output)
            if state.mechanical_report.status == "fail":
                detail = "; ".join(issue.message for issue in state.mechanical_report.issues)
                raise RuntimeError(f"Adjudicated output failed validation: {detail}")
            self.workflow.transition(state, CasePhase.MECHANICALLY_VALIDATED)
            self.workflow.transition(state, CasePhase.COMPARING)
            state.verification_report = VerificationReport(status="pass", issues=[])
            self.trace_writer.write(
                {
                    "case_id": case_id,
                    "component": "adjudicator",
                    "event": "adjudication_approved",
                    "source_fact_hash": state.source_fact_hash,
                }
            )
            self.workflow.transition(state, CasePhase.VERIFIED)
            break
        else:  # pragma: no cover - the bounded loop always returns, breaks or raises
            raise RuntimeError("Semantic decision loop exhausted unexpectedly")

        assert state.draft_output is not None
        assert state.mechanical_report is not None
        assert state.verification_report is not None
        output_path = None
        if self.write_outputs:
            output_path = write_verified_output(
                state.draft_output,
                self.output_root,
                self.run_id,
                state.mechanical_report,
                state.verification_report,
            )
            self.workflow.transition(state, CasePhase.WRITTEN)
        self.trace_writer.write(
            {
                "case_id": case_id,
                "event": "case_completed",
                "status": "success",
                "phase": state.phase.value,
                "primary_issue": state.draft_output.case_assessment.primary_issue,
            }
        )
        return CaseRunResult(
            case_id=case_id,
            status="success",
            phase=state.phase.value,
            output_path=output_path,
        )

    async def run_case(self, case: CaseInput) -> CaseRunResult:
        state = CaseState(run_id=self.run_id, case_input=case)
        self.trace_writer.write(
            {
                "case_id": case.case_id,
                "event": "case_started",
                "status": "running",
            }
        )
        try:
            async with asyncio.timeout(self.settings.case_timeout_seconds):
                return await self._execute_case(state)
        except Exception as exc:  # noqa: BLE001  # case boundary records terminal failure
            self.workflow.fail(state, str(exc))
            self.trace_writer.write(
                {
                    "case_id": case.case_id,
                    "event": "case_completed",
                    "status": "failed",
                    "phase": state.phase.value,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )
            return CaseRunResult(
                case_id=case.case_id,
                status="failed",
                phase=state.phase.value,
                error=str(exc),
            )

    async def run_cases(self, cases: Iterable[CaseInput]) -> list[CaseRunResult]:
        case_list = list(cases)
        output_run_dir = self.output_root / self.run_id
        if self.write_outputs and output_run_dir.exists() and any(output_run_dir.iterdir()):
            raise FileExistsError(
                f"Output namespace already exists and is not empty: {output_run_dir}"
            )
        self.trace_writer.start_run()
        started_at = datetime.now(UTC)
        self.trace_writer.write(
            {
                "event": "run_started",
                "status": "running",
                "case_count": len(case_list),
                "configured_models": {
                    "policy": self.settings.policy_model,
                    "evaluator": self.settings.evaluator_model,
                    "adjudicator": self.settings.adjudicator_model,
                },
            }
        )
        semaphore = asyncio.Semaphore(self.settings.max_case_concurrency)
        progress_lock = asyncio.Lock()
        completed = 0

        async def bounded_run(case: CaseInput) -> CaseRunResult:
            nonlocal completed
            async with semaphore:
                result = await self.run_case(case)
            async with progress_lock:
                completed += 1
                if self.progress_callback is not None:
                    self.progress_callback(completed, len(case_list), result)
            return result

        results = await asyncio.gather(*(bounded_run(case) for case in case_list))
        succeeded = sum(result.status == "success" for result in results)
        failed = sum(result.status == "failed" for result in results)
        needs_review = sum(result.status == "needs_review" for result in results)
        if failed:
            run_status = "partial_failure"
        elif needs_review:
            run_status = "needs_review"
        else:
            run_status = "success"
        manifest = RunManifest(
            run_id=self.run_id,
            status=run_status,
            cases_total=len(results),
            cases_succeeded=succeeded,
            cases_failed=failed,
            cases_needing_review=needs_review,
            cases=[
                CaseManifestEntry(
                    case_id=result.case_id,
                    status=result.status,  # type: ignore[arg-type]
                    phase=result.phase,
                    output_path=str(result.output_path) if result.output_path else None,
                    error=result.error,
                )
                for result in results
            ],
        )
        self.trace_writer.write_manifest(manifest.model_dump(mode="json"))
        completed_at = datetime.now(UTC)
        self.trace_writer.write_metadata(
            {
                "run_id": self.run_id,
                "model_provider": MODEL_PROVIDER,
                "parameter_count": "not_disclosed",
                "configured_models": {
                    "policy": self.settings.policy_model,
                    "evaluator": self.settings.evaluator_model,
                    "adjudicator": self.settings.adjudicator_model,
                },
                "resolved_models": {
                    "policy": sorted(self.policy_agent.resolved_model_ids),
                    "evaluator": sorted(self.evaluator.resolved_model_ids),
                    "adjudicator": (
                        sorted(self.adjudicator.resolved_model_ids)
                        if self.adjudicator is not None
                        else []
                    ),
                },
                "framework": "deterministic-dag-with-model-policy-roles",
                "runtime": {
                    "device": self.model_client.device_name,
                    "python": sys.version.split()[0],
                    "platform": platform.platform(),
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
                    "max_case_concurrency": self.settings.max_case_concurrency,
                },
                "counts": {
                    "total": len(results),
                    "succeeded": succeeded,
                    "failed": failed,
                    "needs_review": needs_review,
                },
                "status": run_status,
            }
        )
        self.trace_writer.write(
            {
                "event": "run_completed",
                "status": run_status,
                "succeeded": succeeded,
                "failed": failed,
                "needs_review": needs_review,
            }
        )
        return results
