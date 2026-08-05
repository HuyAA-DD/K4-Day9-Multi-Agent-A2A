"""Typed payloads exchanged between agents in the Supervisor DAG."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerFacts(StrictModel):
    customer_unique_id: str | None
    related_order_ids: list[str] = Field(default_factory=list, max_length=5)
    repeat_customer: bool


class ItemFact(StrictModel):
    item_id: str
    product_id: str
    seller_id: str
    shipping_limit_at: str | None
    price_brl: float
    freight_brl: float


class OrderProductFacts(StrictModel):
    order_id: str
    order_status: str
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    items: list[ItemFact] = Field(default_factory=list)
    seller_ids: list[str] = Field(default_factory=list, max_length=3)
    product_ids: list[str] = Field(default_factory=list, max_length=5)
    category_names: list[str] = Field(default_factory=list, max_length=5)
    item_total_brl: float | None
    freight_total_brl: float | None
    multi_item_order: bool
    multi_seller_order: bool
    multiple_categories: bool


class PaymentFact(StrictModel):
    payment_id: str
    payment_type: str
    payment_value_brl: float


class PaymentFacts(StrictModel):
    payments: list[PaymentFact] = Field(default_factory=list, max_length=5)
    item_total_brl: float | None
    freight_total_brl: float | None
    expected_total_brl: float | None
    payment_total_brl: float
    difference_brl: float | None
    reconciled: bool | None
    payment_types: list[str] = Field(default_factory=list)
    split_payment: bool


class SellerHandoffFact(StrictModel):
    seller_id: str
    shipping_limit_at: str | None
    handoff_variance_hours: float | None
    late_handoff: bool


class DeliveryFacts(StrictModel):
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    delivered_late: bool
    seller_handoff_analysis: list[SellerHandoffFact] = Field(default_factory=list)
    late_handoff_seller_ids: list[str] = Field(default_factory=list, max_length=3)


class ResponsibleParty(StrictModel):
    party_type: Literal["platform", "seller", "logistics_provider"]
    party_id: str


class PolicyDecision(StrictModel):
    primary_issue: str
    secondary_issues: list[str]
    case_status: Literal["action_required", "no_action"]
    root_cause_codes: list[str] = Field(max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(max_length=3)
    recommended_refund_brl: float
    resolution_actions: list[str] = Field(max_length=5)


class VerificationIssue(StrictModel):
    field: str
    code: str
    message: str
    owner_agent: str | None = None
    retryable: bool = False


class VerificationReport(StrictModel):
    status: Literal["pass", "fail"]
    issues: list[VerificationIssue] = Field(default_factory=list)


class AgentHandoff(StrictModel):
    case_id: str
    sender: str
    recipient: str
    message_type: str
    attempt: int = Field(ge=1)
    payload: dict[str, Any]
    source_refs: list[str] = Field(default_factory=list)

