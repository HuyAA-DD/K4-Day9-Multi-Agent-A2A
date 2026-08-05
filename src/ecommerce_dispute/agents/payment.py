"""Payment reconciliation specialist."""

from decimal import Decimal

from ecommerce_dispute.orchestration.state import CaseState
from ecommerce_dispute.schemas.handoffs import HandoffDecision, PaymentFact, PaymentFacts
from ecommerce_dispute.tools import PaymentTools, money_sum, stable_unique
from ecommerce_dispute.tools.calculators import round_two

from .base import AgentSpec, BaseAgent


class PaymentAgent(BaseAgent):
    spec = AgentSpec(
        name="payment_agent",
        prompt_file=BaseAgent.prompt_path("payment_agent.md"),
        allowed_tools=("get_order_payments", "reconcile_payment"),
    )

    def __init__(self, tools: PaymentTools, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools

    async def run(self, state: CaseState) -> PaymentFacts:
        case_id = state.case_input.case_id
        order_id = state.case_input.customer_request.claimed_order_id
        if state.order_product_facts is None:
            raise RuntimeError("Payment Agent requires OrderProductFacts")
        self.trace("started", case_id, order_id=order_id)
        rows = self.tools.get_order_payments(order_id)
        payments = [
            PaymentFact(
                payment_id=f"{order_id}:{row['payment_sequential']}",
                payment_type=row["payment_type"],
                payment_value_brl=float(row["payment_value"]),
            )
            for row in rows
        ]
        payment_total = money_sum(payment.payment_value_brl for payment in payments)
        item_total = state.order_product_facts.item_total_brl
        freight_total = state.order_product_facts.freight_total_brl
        if item_total is None or freight_total is None:
            expected_total = None
            difference = None
            reconciled = None
        else:
            expected_decimal = money_sum([item_total, freight_total])
            difference_decimal = round_two(payment_total - expected_decimal)
            expected_total = float(expected_decimal)
            difference = float(difference_decimal)
            reconciled = abs(difference_decimal) <= Decimal("0.10")
        await self.decide(
            case_id,
            {
                "task": "Interpret the calculator result and authorize the payment handoff.",
                "policy": "reconciled is null without item totals; otherwise abs(difference)<=0.10",
                "observation": {
                    "payment_row_count": len(payments),
                    "item_total_brl": item_total,
                    "freight_total_brl": freight_total,
                    "expected_total_brl": expected_total,
                    "payment_total_brl": float(payment_total),
                    "difference_brl": difference,
                },
            },
            HandoffDecision,
            accept=lambda value: value.action == "handoff",
            rejection_message="A complete calculator result must be handed off",
            max_new_tokens=112,
        )

        facts = PaymentFacts(
            payments=payments,
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            expected_total_brl=expected_total,
            payment_total_brl=float(payment_total),
            difference_brl=difference,
            reconciled=reconciled,
            payment_types=stable_unique(payment.payment_type for payment in payments),
            split_payment=len(payments) >= 2,
        )
        self.trace("handoff", case_id, recipient="supervisor_agent", payload_type="PaymentFacts")
        return facts
