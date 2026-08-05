"""Immutable, source-backed facts produced by deterministic workers."""

from typing import Generic, Literal, TypeVar

from pydantic import Field

from .common import SCHEMA_VERSION, FrozenStrictModel, StrictModel

FactsT = TypeVar("FactsT", bound=FrozenStrictModel)


class HandoffMetadata(FrozenStrictModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    run_id: str = Field(min_length=8)
    case_id: str = Field(pattern=r"^EC_[0-9]{3}$")
    producer: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16)


class FactHandoff(FrozenStrictModel, Generic[FactsT]):
    metadata: HandoffMetadata
    payload: FactsT
    source_refs: tuple[str, ...] = ()


class CustomerFacts(FrozenStrictModel):
    customer_unique_id: str | None
    related_order_ids: tuple[str, ...] = ()
    repeat_customer: bool


class ItemFact(FrozenStrictModel):
    item_id: str
    product_id: str
    seller_id: str
    shipping_limit_at: str | None
    price_brl: float = Field(ge=0.0)
    freight_brl: float = Field(ge=0.0)


class OrderProductFacts(FrozenStrictModel):
    order_id: str
    order_status: str
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    items: tuple[ItemFact, ...] = ()
    seller_ids: tuple[str, ...] = ()
    product_ids: tuple[str, ...] = ()
    category_names: tuple[str, ...] = ()
    item_total_brl: float | None = Field(default=None, ge=0.0)
    freight_total_brl: float | None = Field(default=None, ge=0.0)
    multi_item_order: bool
    multi_seller_order: bool
    multiple_categories: bool


class PaymentFact(FrozenStrictModel):
    payment_id: str
    payment_type: str
    payment_value_brl: float


class PaymentFacts(FrozenStrictModel):
    payments: tuple[PaymentFact, ...] = ()
    item_total_brl: float | None = Field(default=None, ge=0.0)
    freight_total_brl: float | None = Field(default=None, ge=0.0)
    expected_total_brl: float | None = Field(default=None, ge=0.0)
    payment_total_brl: float
    difference_brl: float | None
    reconciled: bool | None
    payment_types: tuple[str, ...] = ()
    split_payment: bool


class SellerHandoffFact(FrozenStrictModel):
    seller_id: str
    shipping_limit_at: str | None
    handoff_variance_hours: float | None
    late_handoff: bool


class DeliveryFacts(FrozenStrictModel):
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    delivered_late: bool
    seller_handoff_analysis: tuple[SellerHandoffFact, ...] = ()
    late_handoff_seller_ids: tuple[str, ...] = ()


class ValidatedPolicyFacts(StrictModel):
    """Minimal fact projection sent to model-backed policy roles."""

    policy_version: Literal["EC_POLICY_V2"]
    order_status: str
    order_is_canceled: bool
    order_is_unavailable: bool
    seller_ids: list[str]
    item_total_brl: float | None
    freight_total_brl: float | None
    payment_total_brl: float
    has_positive_payment: bool
    payment_row_count: int = Field(ge=0)
    reconciled: bool | None
    split_payment: bool
    delivery_variance_hours: float | None
    delivered_late: bool
    late_handoff_seller_ids: list[str]
    multi_item_order: bool
    multi_seller_order: bool
    repeat_customer: bool
    multiple_categories: bool
