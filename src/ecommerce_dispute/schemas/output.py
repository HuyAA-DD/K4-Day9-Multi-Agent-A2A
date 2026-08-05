"""Strict final output contract required by the assignment."""

from typing import Literal

from pydantic import Field

from .common import StrictModel
from .decisions import (
    PrimaryIssue,
    ResolutionAction,
    ResponsibleParty,
    RootCauseCode,
    SecondaryIssue,
)
from .facts import SellerHandoffFact


class CaseAssessment(StrictModel):
    primary_issue: PrimaryIssue
    secondary_issues: list[SecondaryIssue] = Field(max_length=5)
    case_status: Literal["action_required", "no_action"]
    confidence: float = Field(ge=0.0, le=1.0)


class AffectedEntities(StrictModel):
    order_ids: list[str] = Field(max_length=5)
    item_ids: list[str] = Field(max_length=5)
    seller_ids: list[str] = Field(max_length=3)
    payment_ids: list[str] = Field(max_length=5)


class CustomerContext(StrictModel):
    customer_unique_id: str | None
    related_order_ids: list[str] = Field(max_length=5)


class ProductContext(StrictModel):
    product_ids: list[str] = Field(max_length=5)
    category_names: list[str] = Field(max_length=5)


class DeliveryAnalysis(StrictModel):
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    seller_handoff_analysis: list[SellerHandoffFact] = Field(max_length=3)
    late_handoff_seller_ids: list[str] = Field(max_length=3)


class PaymentReconciliation(StrictModel):
    currency: Literal["BRL"] = "BRL"
    item_total_brl: float | None
    freight_total_brl: float | None
    expected_total_brl: float | None
    payment_total_brl: float
    difference_brl: float | None
    reconciled: bool | None
    payment_types: list[str]


class RankedCause(StrictModel):
    cause_code: RootCauseCode
    rank: int = Field(ge=1, le=3)


class RootCauseAnalysis(StrictModel):
    ranked_causes: list[RankedCause] = Field(max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(max_length=3)


class FinancialResolution(StrictModel):
    currency: Literal["BRL"] = "BRL"
    recommended_refund_brl: float = Field(ge=0.0)


class CaseOutput(StrictModel):
    case_id: str
    case_assessment: CaseAssessment
    affected_entities: AffectedEntities
    customer_context: CustomerContext
    product_context: ProductContext
    delivery_analysis: DeliveryAnalysis
    payment_reconciliation: PaymentReconciliation
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: list[str] = Field(max_length=20)
    financial_resolution: FinancialResolution
    resolution_actions: list[ResolutionAction] = Field(max_length=5)
