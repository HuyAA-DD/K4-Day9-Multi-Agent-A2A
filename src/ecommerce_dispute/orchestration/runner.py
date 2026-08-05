"""End-to-end execution of the Supervisor DAG for one or many cases."""

import asyncio
import json
import platform
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ecommerce_dispute.agents import (
    CustomerAgent,
    DeliveryAgent,
    OrderProductAgent,
    PaymentAgent,
    PolicyAgent,
    SupervisorAgent,
    VerifierAgent,
)
from ecommerce_dispute.config import (
    METADATA_PATH,
    MODEL_FILE,
    MODEL_NAME,
    MODEL_PARAMETER_SIZE,
    MODEL_QUANTIZATION,
    OUTPUT_DIR,
)
from ecommerce_dispute.data import OlistRepository
from ecommerce_dispute.llm import LocalModelClient
from ecommerce_dispute.orchestration.output_builder import build_case_output
from ecommerce_dispute.orchestration.output_writer import write_verified_output
from ecommerce_dispute.orchestration.state import CasePhase, CaseState
from ecommerce_dispute.schemas.case import CaseInput
from ecommerce_dispute.tools import CustomerTools, OrderProductTools, PaymentTools
from ecommerce_dispute.tracing import TraceWriter


@dataclass(frozen=True, slots=True)
class CaseRunResult:
    case_id: str
    status: str
    output_path: Path | None = None
    error: str | None = None


ProgressCallback = Callable[[int, int, CaseRunResult], None]


class DisputeRunner:
    def __init__(
        self,
        repository: OlistRepository,
        trace_writer: TraceWriter,
        model_client: LocalModelClient,
        output_dir: Path = OUTPUT_DIR,
        metadata_path: Path = METADATA_PATH,
        write_outputs: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.repository = repository
        self.trace_writer = trace_writer
        self.model_client = model_client
        self.output_dir = output_dir
        self.metadata_path = metadata_path
        self.write_outputs = write_outputs
        self.progress_callback = progress_callback
        self.run_id = uuid4().hex
        common = (model_client, trace_writer, self.run_id)
        self.supervisor = SupervisorAgent(*common)
        self.customer = CustomerAgent(CustomerTools(repository), *common)
        self.order_product = OrderProductAgent(OrderProductTools(repository), *common)
        self.payment = PaymentAgent(PaymentTools(repository), *common)
        self.delivery = DeliveryAgent(*common)
        self.policy = PolicyAgent(*common)
        self.verifier = VerifierAgent(*common)

    async def run_case(self, case_input: CaseInput) -> CaseRunResult:
        state = CaseState(case_input=case_input)
        case_id = case_input.case_id
        self.trace_writer.write(
            {
                "run_id": self.run_id,
                "case_id": case_id,
                "event": "case_started",
                "status": "running",
            }
        )
        try:
            initial = await self.supervisor.run(state)
            if set(initial) != {"customer_agent", "order_product_agent"}:
                raise RuntimeError(f"Unexpected initial routing: {initial}")
            state.phase = CasePhase.INVESTIGATING
            state.customer_facts, state.order_product_facts = await asyncio.gather(
                self.customer.run(state),
                self.order_product.run(state),
            )

            domain_route = await self.supervisor.run(state)
            if set(domain_route) != {"payment_agent", "delivery_agent"}:
                raise RuntimeError(f"Unexpected domain routing: {domain_route}")
            state.payment_facts, state.delivery_facts = await asyncio.gather(
                self.payment.run(state),
                self.delivery.run(state),
            )

            correction_feedback: list[dict[str, object]] | None = None
            for policy_attempt in range(1, 3):
                state.phase = CasePhase.POLICY_READY
                policy_route = await self.supervisor.run(state)
                if policy_route != ("policy_agent",):
                    raise RuntimeError(f"Unexpected policy routing: {policy_route}")
                state.policy_decision = await self.policy.run(state, correction_feedback)
                state.phase = CasePhase.DECIDED
                state.draft_output = build_case_output(state)

                verify_route = await self.supervisor.run(state)
                if verify_route != ("verifier_agent",):
                    raise RuntimeError(f"Unexpected verifier routing: {verify_route}")
                state.phase = CasePhase.VERIFYING
                state.verification = await self.verifier.run(state)
                if state.verification.status == "pass":
                    break
                retryable = [
                    issue
                    for issue in state.verification.issues
                    if issue.retryable and issue.owner_agent == "policy_agent"
                ]
                if policy_attempt == 2 or not retryable:
                    errors = "; ".join(issue.message for issue in state.verification.issues)
                    raise RuntimeError(f"Verification failed: {errors}")
                correction_feedback = [issue.model_dump(mode="json") for issue in retryable]
                self.trace_writer.write(
                    {
                        "run_id": self.run_id,
                        "case_id": case_id,
                        "event": "correction_requested",
                        "owner_agent": "policy_agent",
                        "issues": correction_feedback,
                    }
                )
            else:
                raise RuntimeError("Policy correction loop exhausted")
            state.phase = CasePhase.VERIFIED

            output_path = None
            if self.write_outputs:
                output_path = write_verified_output(state.draft_output, self.output_dir)
                state.phase = CasePhase.WRITTEN
            self.trace_writer.write(
                {
                    "run_id": self.run_id,
                    "case_id": case_id,
                    "event": "case_completed",
                    "status": "success",
                    "primary_issue": state.draft_output.case_assessment.primary_issue,
                }
            )
            return CaseRunResult(case_id=case_id, status="success", output_path=output_path)
        except Exception as exc:  # noqa: BLE001  # case boundary must record every failure
            state.phase = CasePhase.FAILED
            self.trace_writer.write(
                {
                    "run_id": self.run_id,
                    "case_id": case_id,
                    "event": "case_completed",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return CaseRunResult(case_id=case_id, status="failed", error=str(exc))

    async def run_cases(self, cases: Iterable[CaseInput]) -> list[CaseRunResult]:
        case_list = list(cases)
        self.trace_writer.start_run()
        self.trace_writer.write(
            {
                "run_id": self.run_id,
                "event": "run_started",
                "status": "running",
                "case_count": len(case_list),
                "model": MODEL_NAME,
                "model_enabled": True,
            }
        )
        results: list[CaseRunResult] = []
        for index, case in enumerate(case_list, start=1):
            result = await self.run_case(case)
            results.append(result)
            if self.progress_callback is not None:
                self.progress_callback(index, len(case_list), result)
        succeeded = sum(result.status == "success" for result in results)
        self.trace_writer.write(
            {
                "run_id": self.run_id,
                "event": "run_completed",
                "status": "success" if succeeded == len(results) else "partial_failure",
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
            }
        )
        self.write_metadata(len(results), succeeded)
        return results

    def write_metadata(self, total: int, succeeded: int) -> None:
        metadata = {
            "model": {
                "name": MODEL_NAME,
                "parameter_size": MODEL_PARAMETER_SIZE,
                "file": MODEL_FILE,
                "quantization": MODEL_QUANTIZATION,
                "shared_across_agents": True,
                "enabled": True,
                "decision_mode": "causal_structured_outputs",
            },
            "framework": {
                "name": "custom-supervisor-dag",
                "language": "Python",
            },
            "runtime": {
                "llm_runtime": "llama.cpp-local-offline",
                "model_device": self.model_client.device_name,
                "execution": "async DAG",
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "run_id": self.run_id,
                "completed_at": datetime.now(UTC).isoformat(),
                "cases_total": total,
                "cases_succeeded": succeeded,
                "cases_failed": total - succeeded,
                "status": "completed" if total == succeeded else "partial_failure",
            },
        }
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
