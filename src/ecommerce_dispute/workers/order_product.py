"""Deterministic order, item, seller and product facts worker."""

import asyncio

from ecommerce_dispute.schemas import CaseInput, FactHandoff, ItemFact, OrderProductFacts
from ecommerce_dispute.tools import OrderProductTools, money_sum, stable_unique

from .base import WorkerBase


def _optional(value: str | None) -> str | None:
    return value or None


class OrderProductFactsWorker(WorkerBase[OrderProductFacts]):
    name = "order_product_facts_worker"

    def __init__(self, tools: OrderProductTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(self, run_id: str, case: CaseInput) -> FactHandoff[OrderProductFacts]:
        order_id = case.customer_request.claimed_order_id
        order, rows = await asyncio.gather(
            asyncio.to_thread(self.tools.require_order, order_id),
            asyncio.to_thread(self.tools.get_order_items, order_id),
        )
        items = tuple(
            ItemFact(
                item_id=f"{order_id}:{row['order_item_id']}",
                product_id=row["product_id"],
                seller_id=row["seller_id"],
                shipping_limit_at=_optional(row.get("shipping_limit_date")),
                price_brl=float(row["price"]),
                freight_brl=float(row["freight_value"]),
            )
            for row in rows
        )
        seller_ids = stable_unique(item.seller_id for item in items)
        source_product_ids = stable_unique(item.product_id for item in items)
        products = (
            await asyncio.to_thread(self.tools.get_products, source_product_ids)
            if case.investigation_scope.include_product_context
            else []
        )
        categories = stable_unique(
            row["product_category_name"]
            for row in products
            if row.get("product_category_name")
        )
        payload = OrderProductFacts(
            order_id=order_id,
            order_status=order["order_status"],
            delivered_at=_optional(order.get("order_delivered_customer_date")),
            estimated_delivery_at=_optional(order.get("order_estimated_delivery_date")),
            carrier_handoff_at=_optional(order.get("order_delivered_carrier_date")),
            items=items,
            seller_ids=tuple(seller_ids),
            product_ids=(
                tuple(source_product_ids)
                if case.investigation_scope.include_product_context
                else ()
            ),
            category_names=tuple(categories),
            item_total_brl=float(money_sum(item.price_brl for item in items)) if items else None,
            freight_total_brl=(
                float(money_sum(item.freight_brl for item in items)) if items else None
            ),
            multi_item_order=len(items) >= 2,
            multi_seller_order=len(seller_ids) >= 2,
            multiple_categories=len(categories) >= 2,
        )
        refs = [f"order:{order_id}"]
        refs.extend(f"item:{item.item_id}" for item in items)
        refs.extend(f"seller:{seller_id}" for seller_id in seller_ids)
        refs.extend(f"product:{product_id}" for product_id in source_product_ids)
        return self.handoff(run_id, case, payload, refs)
