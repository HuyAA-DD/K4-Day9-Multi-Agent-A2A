"""Deterministic first-match implementation of EC_POLICY_V2."""

from ecommerce_dispute.schemas.handoffs import (
    CustomerFacts,
    DeliveryFacts,
    OrderProductFacts,
    PaymentFacts,
    PolicyDecision,
    ResponsibleParty,
)


class PolicyNotMatchedError(ValueError):
    """Raised when source facts do not satisfy any rule declared in the README."""


def evaluate_ec_policy_v2(
    customer: CustomerFacts,
    order: OrderProductFacts,
    payment: PaymentFacts,
    delivery: DeliveryFacts,
) -> PolicyDecision:
    """Evaluate primary and secondary issues in mandatory policy order."""
    payment_total = round(payment.payment_total_brl, 2)
    freight_total = round(order.freight_total_brl or 0.0, 2)

    if order.order_status == "canceled" and payment_total > 0:
        primary = "canceled_order_paid"
        root_cause = "ORDER_CANCELED_AFTER_PAYMENT"
        refund = payment_total
        parties = [ResponsibleParty(party_type="platform", party_id="OLIST_PLATFORM")]
        primary_action = "issue_full_refund"
    elif order.order_status == "unavailable" and payment_total > 0:
        primary = "unavailable_order_paid"
        root_cause = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
        refund = payment_total
        parties = [ResponsibleParty(party_type="platform", party_id="OLIST_PLATFORM")]
        primary_action = "issue_full_refund"
    elif delivery.delivered_late and delivery.late_handoff_seller_ids:
        primary = "late_delivery_seller"
        root_cause = "SELLER_HANDOFF_AFTER_LIMIT"
        refund = freight_total
        parties = [
            ResponsibleParty(party_type="seller", party_id=seller_id)
            for seller_id in delivery.late_handoff_seller_ids
        ]
        primary_action = "refund_freight"
    elif delivery.delivered_late:
        primary = "late_delivery_logistics"
        root_cause = "CARRIER_DELIVERED_AFTER_ESTIMATE"
        refund = freight_total
        parties = [
            ResponsibleParty(
                party_type="logistics_provider",
                party_id="LOGISTICS_PROVIDER",
            )
        ]
        primary_action = "refund_freight"
    elif payment.split_payment and payment.reconciled is True:
        primary = "valid_split_payment"
        root_cause = "MULTIPLE_PAYMENTS_RECONCILED"
        refund = 0.0
        parties = []
        primary_action = "explain_valid_split_payment"
    elif not delivery.delivered_late and payment.reconciled is True:
        primary = "unsupported_late_claim"
        root_cause = "DELIVERY_WITHIN_ESTIMATE"
        refund = 0.0
        parties = []
        primary_action = "reject_late_refund"
    else:
        raise PolicyNotMatchedError(f"No EC_POLICY_V2 rule matched order {order.order_id}")

    secondary: list[str] = []
    if order.multi_item_order:
        secondary.append("multi_item_order")
    if order.multi_seller_order:
        secondary.append("multi_seller_order")
    if payment.split_payment:
        secondary.append("split_payment")
    if customer.repeat_customer:
        secondary.append("repeat_customer")
    if order.multiple_categories:
        secondary.append("multiple_categories")

    actions = [primary_action]
    if primary == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary == "late_delivery_logistics":
        actions.append("review_carrier_delay")
    if refund > 0:
        actions.append("verify_refund_completion")
    if order.multi_seller_order:
        actions.append("coordinate_multi_seller_case")
    if payment.split_payment and primary != "valid_split_payment":
        actions.append("verify_payment_allocation")

    return PolicyDecision(
        primary_issue=primary,
        secondary_issues=secondary,
        case_status="action_required" if refund > 0 else "no_action",
        root_cause_codes=[root_cause],
        responsible_parties=parties,
        recommended_refund_brl=round(refund, 2),
        resolution_actions=actions,
    )

