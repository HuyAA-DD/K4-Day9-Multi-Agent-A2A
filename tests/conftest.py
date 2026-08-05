import json
from collections import defaultdict
from typing import Any

import pytest

from ecommerce_dispute.config import DATA_DIR, INPUT_DIR, Settings
from ecommerce_dispute.data import OlistRepository
from ecommerce_dispute.llm import ModelCompletion
from ecommerce_dispute.schemas import CaseInput


def select_primary_issue(facts: dict[str, Any]) -> str:
    """Golden test oracle; production agents never import or call this function."""

    if facts["order_is_canceled"] and facts["has_positive_payment"]:
        return "canceled_order_paid"
    if facts["order_is_unavailable"] and facts["has_positive_payment"]:
        return "unavailable_order_paid"
    if facts["delivered_late"] and facts["late_handoff_seller_ids"]:
        return "late_delivery_seller"
    if facts["delivered_late"]:
        return "late_delivery_logistics"
    if facts["split_payment"] and facts["reconciled"]:
        return "valid_split_payment"
    if not facts["delivered_late"] and facts["reconciled"]:
        return "unsupported_late_claim"
    raise AssertionError(f"No EC_POLICY_V2 outcome matches facts: {facts}")


def complete_outcome(primary: str, facts: dict[str, Any]) -> dict[str, Any]:
    secondary = [
        name
        for name in (
            "multi_item_order",
            "multi_seller_order",
            "split_payment",
            "repeat_customer",
            "multiple_categories",
        )
        if facts[name]
    ]
    mappings: dict[str, tuple[str, str, list[dict[str, str]], float, str]] = {
        "canceled_order_paid": (
            "action_required",
            "ORDER_CANCELED_AFTER_PAYMENT",
            [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            facts["payment_total_brl"],
            "issue_full_refund",
        ),
        "unavailable_order_paid": (
            "action_required",
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            facts["payment_total_brl"],
            "issue_full_refund",
        ),
        "late_delivery_seller": (
            "action_required",
            "SELLER_HANDOFF_AFTER_LIMIT",
            [
                {"party_type": "seller", "party_id": seller_id}
                for seller_id in facts["late_handoff_seller_ids"][:3]
            ],
            facts["freight_total_brl"] or 0.0,
            "refund_freight",
        ),
        "late_delivery_logistics": (
            "action_required",
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
            facts["freight_total_brl"] or 0.0,
            "refund_freight",
        ),
        "valid_split_payment": (
            "no_action",
            "MULTIPLE_PAYMENTS_RECONCILED",
            [],
            0.0,
            "explain_valid_split_payment",
        ),
        "unsupported_late_claim": (
            "no_action",
            "DELIVERY_WITHIN_ESTIMATE",
            [],
            0.0,
            "reject_late_refund",
        ),
    }
    status, root, parties, refund, first_action = mappings[primary]
    actions = [first_action]
    if primary == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary == "late_delivery_logistics":
        actions.append("review_carrier_delay")
    if refund > 0:
        actions.append("verify_refund_completion")
    if facts["multi_seller_order"]:
        actions.append("coordinate_multi_seller_case")
    if facts["split_payment"] and primary != "valid_split_payment":
        actions.append("verify_payment_allocation")
    return {
        "primary_issue": primary,
        "secondary_issues": secondary,
        "case_status": status,
        "root_cause_codes": [root],
        "responsible_parties": parties,
        "recommended_refund_brl": refund,
        "resolution_actions": actions,
        "confidence": 0.95,
    }


class OracleModelClient:
    device_name = "scripted-offline"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls: defaultdict[str, int] = defaultdict(int)

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        *,
        model: str,
        response_schema: dict[str, Any],
        max_output_tokens: int | None = None,
    ) -> ModelCompletion:
        del system_prompt, max_output_tokens
        self.calls[model] += 1
        request = json.loads(user_payload)
        facts = request["facts"]
        primary = select_primary_issue(facts)
        if response_schema.get("title") == "PrimarySelection":
            content = {"primary_issue": primary, "confidence": 0.95}
        else:
            content = complete_outcome(primary, facts)
        return ModelCompletion(
            content=content,
            model_id=model,
            request_id=f"{model}-{self.calls[model]}",
            usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )


@pytest.fixture(scope="session")
def repository() -> OlistRepository:
    result = OlistRepository(DATA_DIR)
    result.load()
    return result


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        api_key="test-only",
        policy_model="policy-test-model",
        evaluator_model="evaluator-test-model",
        max_agent_attempts=2,
        semantic_retry_rounds=1,
        max_case_concurrency=8,
        retry_backoff_seconds=0,
    )


def load_case(case_id: str) -> CaseInput:
    return CaseInput.model_validate_json(
        (INPUT_DIR / f"{case_id}.json").read_text(encoding="utf-8")
    )
