"""Order, item, seller, product and category specialist."""

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import (
    HandoffDecision,
    ItemFact,
    OrderProductFacts,
)
from ecommerce_dispute.tools import OrderProductTools, money_sum, stable_unique

from .base import AgentSpec, BaseAgent


def _optional(value: str | None) -> str | None:
    return value or None


class OrderProductAgent(BaseAgent):
    spec = AgentSpec(
        name="order_product_agent",
        prompt_file=BaseAgent.prompt_path("order_product_agent.md"),
        allowed_tools=("get_order", "get_order_items", "get_products", "get_sellers"),
    )

    def __init__(self, tools: OrderProductTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(self, state: CaseState) -> OrderProductFacts:
        case_id = state.case_input.case_id
        order_id = state.case_input.customer_request.claimed_order_id
        self.trace("started", case_id, order_id=order_id)
        order = self.tools.require_order(order_id)
        rows = self.tools.get_order_items(order_id)

        items = [
            ItemFact(
                item_id=f"{order_id}:{row['order_item_id']}",
                product_id=row["product_id"],
                seller_id=row["seller_id"],
                shipping_limit_at=_optional(row.get("shipping_limit_date")),
                price_brl=float(row["price"]),
                freight_brl=float(row["freight_value"]),
            )
            for row in rows
        ]
        seller_ids = stable_unique(item.seller_id for item in items)
        product_ids = stable_unique(item.product_id for item in items)
        products = (
            self.tools.get_products(product_ids)
            if state.case_input.investigation_scope.include_product_context
            else []
        )
        category_names = stable_unique(
            row["product_category_name"]
            for row in products
            if row.get("product_category_name")
        )
        item_total = float(money_sum(item.price_brl for item in items)) if items else None
        freight_total = float(money_sum(item.freight_brl for item in items)) if items else None

        await self.decide(
            case_id,
            {
                "task": "Classify the validated order observation and authorize its handoff.",
                "observation": {
                    "item_count": len(items),
                    "seller_count": len(seller_ids),
                    "category_count": len(category_names),
                    "has_source_order": True,
                    "item_total_brl": item_total,
                    "freight_total_brl": freight_total,
                },
            },
            HandoffDecision,
            accept=lambda value: value.action == "handoff",
            rejection_message="Validated source order must be authorized for handoff",
            max_new_tokens=112,
        )
        facts = OrderProductFacts(
            order_id=order_id,
            order_status=order["order_status"],
            delivered_at=_optional(order.get("order_delivered_customer_date")),
            estimated_delivery_at=_optional(order.get("order_estimated_delivery_date")),
            carrier_handoff_at=_optional(order.get("order_delivered_carrier_date")),
            items=items,
            seller_ids=seller_ids,
            product_ids=product_ids if state.case_input.investigation_scope.include_product_context else [],
            category_names=category_names,
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            multi_item_order=len(items) >= 2,
            multi_seller_order=len(seller_ids) >= 2,
            multiple_categories=len(category_names) >= 2,
        )
        self.trace(
            "handoff",
            case_id,
            recipient="supervisor_agent",
            payload_type="OrderProductFacts",
        )
        return facts
