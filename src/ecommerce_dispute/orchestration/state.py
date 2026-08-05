"""Mutable state owned exclusively by the Supervisor Agent."""

from dataclasses import dataclass, field
from enum import StrEnum

from ecommerce_dispute.schemas.case import CaseInput
from ecommerce_dispute.schemas.handoffs import (
    CustomerFacts,
    DeliveryFacts,
    OrderProductFacts,
    PaymentFacts,
    PolicyDecision,
    VerificationReport,
)
from ecommerce_dispute.schemas.output import CaseOutput


class CasePhase(StrEnum):
    RECEIVED = "received"
    INVESTIGATING = "investigating"
    POLICY_READY = "policy_ready"
    DECIDED = "decided"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    WRITTEN = "written"
    FAILED = "failed"


@dataclass(slots=True)
class CaseState:
    case_input: CaseInput
    phase: CasePhase = CasePhase.RECEIVED
    customer_facts: CustomerFacts | None = None
    order_product_facts: OrderProductFacts | None = None
    payment_facts: PaymentFacts | None = None
    delivery_facts: DeliveryFacts | None = None
    policy_decision: PolicyDecision | None = None
    draft_output: CaseOutput | None = None
    verification: VerificationReport | None = None
    attempts: dict[str, int] = field(default_factory=dict)

    def all_investigation_facts_ready(self) -> bool:
        return all(
            value is not None
            for value in (
                self.customer_facts,
                self.order_product_facts,
                self.payment_facts,
                self.delivery_facts,
            )
        )
