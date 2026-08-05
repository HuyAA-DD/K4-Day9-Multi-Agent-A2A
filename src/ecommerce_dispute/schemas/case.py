"""Input contract for one dispute case."""

from typing import Literal

from pydantic import Field

from .common import StrictModel


class CustomerRequest(StrictModel):
    language: str = Field(min_length=2, max_length=10)
    message: str = Field(min_length=1, max_length=4000)
    claimed_order_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class InvestigationScope(StrictModel):
    include_customer_history: bool
    include_product_context: bool


class CaseInput(StrictModel):
    case_id: str = Field(pattern=r"^EC_[0-9]{3}$")
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: Literal["EC_POLICY_V2"]
