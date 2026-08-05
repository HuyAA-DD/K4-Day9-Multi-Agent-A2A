from ecommerce_dispute.policies.ec_policy_v2 import evaluate_ec_policy_v2
from ecommerce_dispute.schemas.handoffs import (
    CustomerFacts,
    DeliveryFacts,
    OrderProductFacts,
    PaymentFact,
    PaymentFacts,
    SellerHandoffFact,
)


def test_ec001_is_unsupported_late_claim() -> None:
    customer = CustomerFacts(
        customer_unique_id="bbf65e7823171a84e70a495dd6c34ceb",
        related_order_ids=["65bbd0719855fe808bb19f62dfa9f42c"],
        repeat_customer=True,
    )
    order = OrderProductFacts(
        order_id="9b75cdaf2d85857ef023980e15d01546",
        order_status="delivered",
        delivered_at="2018-06-19 01:28:42",
        estimated_delivery_at="2018-06-26 00:00:00",
        carrier_handoff_at="2018-06-15 14:15:00",
        items=[],
        seller_ids=["c70c1b0d8ca86052f45a432a38b73958"],
        product_ids=[
            "0a4f9f421af66d2ea061fbb8883419f7",
            "43b54d1fc56ff394092a3dff6be2d39f",
        ],
        category_names=["beleza_saude"],
        item_total_brl=220.64,
        freight_total_brl=16.70,
        multi_item_order=True,
        multi_seller_order=False,
        multiple_categories=False,
    )
    payment = PaymentFacts(
        payments=[
            PaymentFact(
                payment_id="9b75cdaf2d85857ef023980e15d01546:1",
                payment_type="credit_card",
                payment_value_brl=237.34,
            )
        ],
        item_total_brl=220.64,
        freight_total_brl=16.70,
        expected_total_brl=237.34,
        payment_total_brl=237.34,
        difference_brl=0.0,
        reconciled=True,
        payment_types=["credit_card"],
        split_payment=False,
    )
    delivery = DeliveryFacts(
        delivered_at="2018-06-19 01:28:42",
        estimated_delivery_at="2018-06-26 00:00:00",
        carrier_handoff_at="2018-06-15 14:15:00",
        delivery_variance_hours=-166.52,
        delivered_late=False,
        seller_handoff_analysis=[
            SellerHandoffFact(
                seller_id="c70c1b0d8ca86052f45a432a38b73958",
                shipping_limit_at="2018-06-18 07:57:36",
                handoff_variance_hours=-65.71,
                late_handoff=False,
            )
        ],
        late_handoff_seller_ids=[],
    )

    decision = evaluate_ec_policy_v2(customer, order, payment, delivery)

    assert decision.primary_issue == "unsupported_late_claim"
    assert decision.secondary_issues == ["multi_item_order", "repeat_customer"]
    assert decision.case_status == "no_action"
    assert decision.recommended_refund_brl == 0.0
    assert decision.resolution_actions == ["reject_late_refund"]

