"""Deterministic payment reconciliation worker."""

import asyncio
from decimal import Decimal

from ecommerce_dispute.schemas import (
    CaseInput,
    FactHandoff,
    OrderProductFacts,
    PaymentFact,
    PaymentFacts,
)
from ecommerce_dispute.tools import PaymentTools, money_sum, stable_unique
from ecommerce_dispute.tools.calculators import round_two

from .base import WorkerBase


class PaymentReconciliationWorker(WorkerBase[PaymentFacts]):
    name = "payment_reconciliation_worker"

    def __init__(self, tools: PaymentTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(
        self,
        run_id: str,
        case: CaseInput,
        order: OrderProductFacts,
    ) -> FactHandoff[PaymentFacts]:
        order_id = order.order_id
        rows = await asyncio.to_thread(self.tools.get_order_payments, order_id)
        payments = tuple(
            PaymentFact(
                payment_id=f"{order_id}:{row['payment_sequential']}",
                payment_type=row["payment_type"],
                payment_value_brl=float(row["payment_value"]),
            )
            for row in rows
        )
        payment_total = money_sum(payment.payment_value_brl for payment in payments)
        if order.item_total_brl is None or order.freight_total_brl is None:
            expected_total = None
            difference = None
            reconciled = None
        else:
            expected_decimal = money_sum([order.item_total_brl, order.freight_total_brl])
            difference_decimal = round_two(payment_total - expected_decimal)
            expected_total = float(expected_decimal)
            difference = float(difference_decimal)
            reconciled = abs(difference_decimal) <= Decimal("0.10")
        payload = PaymentFacts(
            payments=payments,
            item_total_brl=order.item_total_brl,
            freight_total_brl=order.freight_total_brl,
            expected_total_brl=expected_total,
            payment_total_brl=float(payment_total),
            difference_brl=difference,
            reconciled=reconciled,
            payment_types=tuple(stable_unique(payment.payment_type for payment in payments)),
            split_payment=len(payments) >= 2,
        )
        refs = [f"payment:{payment.payment_id}" for payment in payments]
        return self.handoff(run_id, case, payload, refs)
