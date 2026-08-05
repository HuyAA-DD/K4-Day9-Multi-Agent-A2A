"""Validated contracts shared by agents and mechanical components."""

from .case import CaseInput
from .handoffs import (
    CustomerFacts,
    DeliveryFacts,
    OrderProductFacts,
    PaymentFacts,
    PolicyDecision,
    SupervisorDecision,
    VerificationReport,
)

__all__ = [
    "CaseInput",
    "CustomerFacts",
    "DeliveryFacts",
    "OrderProductFacts",
    "PaymentFacts",
    "PolicyDecision",
    "SupervisorDecision",
    "VerificationReport",
]
