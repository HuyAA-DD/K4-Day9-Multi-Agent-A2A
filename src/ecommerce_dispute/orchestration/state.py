"""Single-writer case state for the deterministic workflow."""

from dataclasses import dataclass, field
from enum import StrEnum

from ecommerce_dispute.schemas import (
    CaseInput,
    CaseOutput,
    CustomerFacts,
    DeliveryFacts,
    ExpectedPolicyDecision,
    FactHandoff,
    MechanicalReport,
    OrderProductFacts,
    PaymentFacts,
    PolicyDecision,
    ValidatedPolicyFacts,
    VerificationReport,
)


class CasePhase(StrEnum):
    RECEIVED = "received"
    INVESTIGATING = "investigating"
    FACTS_READY = "facts_ready"
    DECIDING = "deciding"
    MECHANICALLY_VALIDATED = "mechanically_validated"
    COMPARING = "comparing"
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    WRITTEN = "written"


TERMINAL_PHASES = {CasePhase.NEEDS_REVIEW, CasePhase.FAILED, CasePhase.WRITTEN}


@dataclass(slots=True)
class CaseState:
    run_id: str
    case_input: CaseInput
    phase: CasePhase = CasePhase.RECEIVED
    customer_handoff: FactHandoff[CustomerFacts] | None = None
    order_handoff: FactHandoff[OrderProductFacts] | None = None
    payment_handoff: FactHandoff[PaymentFacts] | None = None
    delivery_handoff: FactHandoff[DeliveryFacts] | None = None
    policy_facts: ValidatedPolicyFacts | None = None
    source_fact_hash: str | None = None
    policy_decision: PolicyDecision | None = None
    expected_decision: ExpectedPolicyDecision | None = None
    draft_output: CaseOutput | None = None
    mechanical_report: MechanicalReport | None = None
    verification_report: VerificationReport | None = None
    attempts: dict[str, int] = field(default_factory=dict)
    transition_history: list[str] = field(default_factory=lambda: [CasePhase.RECEIVED.value])
    error: str | None = None

    def facts_ready(self) -> bool:
        return all(
            handoff is not None
            for handoff in (
                self.customer_handoff,
                self.order_handoff,
                self.payment_handoff,
                self.delivery_handoff,
            )
        )
