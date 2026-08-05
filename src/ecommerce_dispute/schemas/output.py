"""Strict final output contract matching the assignment README."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ecommerce_dispute.schemas.handoffs import ResponsibleParty, SellerHandoffFact


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseAssessment(StrictOutputModel):
    primary_issue: str
    secondary_issues: list[str] = Field(max_length=5)
    case_status: Literal["action_required", "no_action"]
    confidence: float = Field(ge=0.0, le=1.0)


class AffectedEntities(StrictOutputModel):
    order_ids: list[str] = Field(max_length=5)
    item_ids: list[str] = Field(max_length=5)
    seller_ids: list[str] = Field(max_length=3)
    payment_ids: list[str] = Field(max_length=5)


class CustomerContext(StrictOutputModel):
    customer_unique_id: str | None
    related_order_ids: list[str] = Field(max_length=5)


class ProductContext(StrictOutputModel):
    product_ids: list[str] = Field(max_length=5)
    category_names: list[str] = Field(max_length=5)


class DeliveryAnalysis(StrictOutputModel):
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    seller_handoff_analysis: list[SellerHandoffFact] = Field(max_length=3)
    late_handoff_seller_ids: list[str] = Field(max_length=3)


class PaymentReconciliation(StrictOutputModel):
    currency: Literal["BRL"] = "BRL"
    item_total_brl: float | None
    freight_total_brl: float | None
    expected_total_brl: float | None
    payment_total_brl: float
    difference_brl: float | None
    reconciled: bool | None
    payment_types: list[str]


class RankedCause(StrictOutputModel):
    cause_code: str
    rank: int = Field(ge=1, le=3)


class RootCauseAnalysis(StrictOutputModel):
    ranked_causes: list[RankedCause] = Field(max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(max_length=3)


class FinancialResolution(StrictOutputModel):
    currency: Literal["BRL"] = "BRL"
    recommended_refund_brl: float = Field(ge=0.0)


class CaseOutput(StrictOutputModel):
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
    resolution_actions: list[str] = Field(max_length=5)
