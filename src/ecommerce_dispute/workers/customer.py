"""Deterministic customer identity and history worker."""

import asyncio

from ecommerce_dispute.data import DataIntegrityError
from ecommerce_dispute.schemas import CaseInput, CustomerFacts, FactHandoff
from ecommerce_dispute.tools import CustomerTools

from .base import WorkerBase


class CustomerFactsWorker(WorkerBase[CustomerFacts]):
    name = "customer_facts_worker"

    def __init__(self, tools: CustomerTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(self, run_id: str, case: CaseInput) -> FactHandoff[CustomerFacts]:
        order_id = case.customer_request.claimed_order_id
        customer = await asyncio.to_thread(self.tools.get_order_customer, order_id)
        if customer is None:
            raise DataIntegrityError(f"No customer row for claimed order {order_id}")
        unique_id = customer.get("customer_unique_id") or None
        related = (
            await asyncio.to_thread(self.tools.get_related_orders, unique_id, order_id)
            if unique_id and case.investigation_scope.include_customer_history
            else []
        )
        payload = CustomerFacts(
            customer_unique_id=unique_id,
            related_order_ids=tuple(dict.fromkeys(related)),
            repeat_customer=bool(related),
        )
        refs = [f"order:{order_id}"]
        if unique_id:
            refs.append(f"customer:{unique_id}")
        refs.extend(f"order:{value}" for value in related)
        return self.handoff(run_id, case, payload, refs)
