"""Structured semantic decisions produced by model-backed agents."""

from typing import Literal

from pydantic import Field, field_validator

from .common import SCHEMA_VERSION, StrictModel

PrimaryIssue = Literal[
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]
SecondaryIssue = Literal[
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
]
RootCauseCode = Literal[
    "SELLER_HANDOFF_AFTER_LIMIT",
    "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT",
    "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED",
    "DELIVERY_WITHIN_ESTIMATE",
]
ResolutionAction = Literal[
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
    "review_seller_handoff",
    "review_carrier_delay",
    "verify_refund_completion",
    "coordinate_multi_seller_case",
    "verify_payment_allocation",
]


class ResponsibleParty(StrictModel):
    party_type: Literal["platform", "seller", "logistics_provider"]
    party_id: str


class PrimarySelection(StrictModel):
    primary_issue: PrimaryIssue
    confidence: float = Field(ge=0.0, le=1.0)


class PolicyOutcome(StrictModel):
    """Only semantic fields are decoded from the model."""

    primary_issue: PrimaryIssue
    secondary_issues: list[SecondaryIssue] = Field(max_length=5)
    case_status: Literal["action_required", "no_action"]
    root_cause_codes: list[RootCauseCode] = Field(min_length=1, max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(max_length=3)
    recommended_refund_brl: float = Field(ge=0.0)
    resolution_actions: list[ResolutionAction] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence_percent(cls, value: object) -> object:
        if isinstance(value, (int, float)) and 1 < value <= 100:
            return value / 100
        return value

    @field_validator(
        "secondary_issues", "root_cause_codes", "responsible_parties", "resolution_actions"
    )
    @classmethod
    def reject_duplicates(cls, values: list[object]) -> list[object]:
        normalized = [repr(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("collection must not contain duplicates")
        return values


class DecisionMetadata(StrictModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    policy_version: Literal["EC_POLICY_V2"]
    prompt_version: str
    prompt_hash: str
    source_fact_hash: str
    model_id: str
    provider_request_id: str | None = None
    agent_role: Literal["policy", "evaluator", "adjudicator"]


class PolicyDecision(StrictModel):
    metadata: DecisionMetadata
    outcome: PolicyOutcome


class ExpectedPolicyDecision(StrictModel):
    metadata: DecisionMetadata
    outcome: PolicyOutcome


SEMANTIC_FIELDS: tuple[str, ...] = (
    "primary_issue",
    "secondary_issues",
    "case_status",
    "root_cause_codes",
    "responsible_parties",
    "recommended_refund_brl",
    "resolution_actions",
)
