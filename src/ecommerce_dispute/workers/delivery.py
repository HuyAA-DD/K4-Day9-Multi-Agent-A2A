"""Deterministic delivery and seller-handoff analysis worker."""

from decimal import Decimal

from ecommerce_dispute.schemas import (
    CaseInput,
    DeliveryFacts,
    FactHandoff,
    OrderProductFacts,
    SellerHandoffFact,
)
from ecommerce_dispute.tools import hours_between

from .base import WorkerBase


class DeliveryAnalysisWorker(WorkerBase[DeliveryFacts]):
    name = "delivery_analysis_worker"

    async def run(
        self,
        run_id: str,
        case: CaseInput,
        order: OrderProductFacts,
    ) -> FactHandoff[DeliveryFacts]:
        delivery_variance = (
            float(hours_between(order.delivered_at, order.estimated_delivery_at))
            if order.delivered_at and order.estimated_delivery_at
            else None
        )
        handoffs: list[SellerHandoffFact] = []
        for seller_id in order.seller_ids:
            limits = [
                item.shipping_limit_at
                for item in order.items
                if item.seller_id == seller_id and item.shipping_limit_at
            ]
            shipping_limit = min(limits) if limits else None
            variance = (
                float(hours_between(order.carrier_handoff_at, shipping_limit))
                if order.carrier_handoff_at and shipping_limit
                else None
            )
            handoffs.append(
                SellerHandoffFact(
                    seller_id=seller_id,
                    shipping_limit_at=shipping_limit,
                    handoff_variance_hours=variance,
                    late_handoff=(
                        variance is not None and Decimal(str(variance)) > Decimal(0)
                    ),
                )
            )
        late_sellers = tuple(row.seller_id for row in handoffs if row.late_handoff)
        payload = DeliveryFacts(
            delivered_at=order.delivered_at,
            estimated_delivery_at=order.estimated_delivery_at,
            carrier_handoff_at=order.carrier_handoff_at,
            delivery_variance_hours=delivery_variance,
            delivered_late=(
                delivery_variance is not None
                and Decimal(str(delivery_variance)) > Decimal(0)
            ),
            seller_handoff_analysis=tuple(handoffs),
            late_handoff_seller_ids=late_sellers,
        )
        refs = [f"order:{order.order_id}"]
        refs.extend(f"seller:{seller_id}" for seller_id in order.seller_ids)
        return self.handoff(run_id, case, payload, refs)
