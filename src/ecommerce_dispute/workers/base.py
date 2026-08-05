"""Shared mechanics for deterministic domain workers."""

from __future__ import annotations

from hashlib import sha256
from typing import Generic, TypeVar

from ecommerce_dispute.schemas.case import CaseInput
from ecommerce_dispute.schemas.common import FrozenStrictModel
from ecommerce_dispute.schemas.facts import FactHandoff, HandoffMetadata
from ecommerce_dispute.tracing import TraceWriter

PayloadT = TypeVar("PayloadT", bound=FrozenStrictModel)


class WorkerBase(Generic[PayloadT]):
    name: str

    def __init__(self, trace_writer: TraceWriter) -> None:
        self.trace_writer = trace_writer

    def handoff(
        self,
        run_id: str,
        case: CaseInput,
        payload: PayloadT,
        source_refs: list[str],
        attempt: int = 1,
    ) -> FactHandoff[PayloadT]:
        raw_key = f"{run_id}:{case.case_id}:{self.name}:{attempt}"
        metadata = HandoffMetadata(
            run_id=run_id,
            case_id=case.case_id,
            producer=self.name,
            attempt=attempt,
            idempotency_key=sha256(raw_key.encode("utf-8")).hexdigest(),
        )
        result = FactHandoff[PayloadT](
            metadata=metadata,
            payload=payload,
            source_refs=tuple(dict.fromkeys(source_refs)),
        )
        self.trace_writer.write(
            {
                "run_id": run_id,
                "case_id": case.case_id,
                "component": self.name,
                "event": "facts_handoff",
                "attempt": attempt,
                "schema_version": metadata.schema_version,
                "idempotency_key": metadata.idempotency_key,
                "source_ref_count": len(result.source_refs),
                "payload_type": type(payload).__name__,
            }
        )
        return result
