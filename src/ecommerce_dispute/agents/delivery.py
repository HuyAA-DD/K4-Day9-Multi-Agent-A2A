"""Delivery and seller-handoff specialist."""

from decimal import Decimal

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import (
    DeliveryFacts,
    HandoffDecision,
    SellerHandoffFact,
)
from ecommerce_dispute.tools import hours_between

from .base import AgentSpec, BaseAgent


class DeliveryAgent(BaseAgent):
    spec = AgentSpec(
        name="delivery_agent",
        prompt_file=BaseAgent.prompt_path("delivery_agent.md"),
        allowed_tools=("calculate_delivery_variance", "calculate_handoff_variance"),
    )

    async def run(self, state: CaseState) -> DeliveryFacts:
        case_id = state.case_input.case_id
        if state.order_product_facts is None:
            raise RuntimeError("Delivery Agent requires OrderProductFacts")
        order = state.order_product_facts
        self.trace("started", case_id, order_id=order.order_id)

        if order.delivered_at and order.estimated_delivery_at:
            delivery_variance = float(
                hours_between(
                order.delivered_at,
                order.estimated_delivery_at,
                )
            )
        else:
            delivery_variance = None

        handoff_observations: list[dict[str, object]] = []
        for seller_id in order.seller_ids:
            limits = [
                item.shipping_limit_at
                for item in order.items
                if item.seller_id == seller_id and item.shipping_limit_at
            ]
            shipping_limit = min(limits) if limits else None
            if order.carrier_handoff_at and shipping_limit:
                variance = float(hours_between(order.carrier_handoff_at, shipping_limit))
            else:
                variance = None
            handoff_observations.append(
                {
                    "seller_id": seller_id,
                    "shipping_limit_at": shipping_limit,
                    "handoff_variance_hours": variance,
                }
            )

        await self.decide(
            case_id,
            {
                "task": "Interpret timestamp calculator results and authorize delivery handoff.",
                "policy": (
                    "delivered_late is true iff delivery_variance_hours>0. "
                    "late_handoff_indices are zero-based rows with handoff_variance_hours>0."
                ),
                "observation": {
                    "delivery_variance_hours": delivery_variance,
                    "seller_handoffs": handoff_observations,
                },
            },
            HandoffDecision,
            accept=lambda value: value.action == "handoff",
            rejection_message="A complete timestamp calculator result must be handed off",
            max_new_tokens=128,
        )
        handoff_analysis = [
            SellerHandoffFact(
                seller_id=str(row["seller_id"]),
                shipping_limit_at=(
                    str(row["shipping_limit_at"]) if row["shipping_limit_at"] is not None else None
                ),
                handoff_variance_hours=(
                    float(row["handoff_variance_hours"])
                    if row["handoff_variance_hours"] is not None
                    else None
                ),
                late_handoff=(
                    row["handoff_variance_hours"] is not None
                    and Decimal(str(row["handoff_variance_hours"])) > Decimal(0)
                ),
            )
            for row in handoff_observations
        ]
        late_sellers = [row.seller_id for row in handoff_analysis if row.late_handoff]

        facts = DeliveryFacts(
            delivered_at=order.delivered_at,
            estimated_delivery_at=order.estimated_delivery_at,
            carrier_handoff_at=order.carrier_handoff_at,
            delivery_variance_hours=delivery_variance,
            delivered_late=(
                delivery_variance is not None
                and Decimal(str(delivery_variance)) > Decimal(0)
            ),
            seller_handoff_analysis=handoff_analysis,
            late_handoff_seller_ids=late_sellers,
        )
        self.trace("handoff", case_id, recipient="supervisor_agent", payload_type="DeliveryFacts")
        return facts
