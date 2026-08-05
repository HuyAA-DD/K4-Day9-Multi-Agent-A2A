"""Input contract for one dispute case."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    message: str
    claimed_order_id: str


class InvestigationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_customer_history: bool
    include_product_context: bool


class CaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: Literal["EC_POLICY_V2"]

