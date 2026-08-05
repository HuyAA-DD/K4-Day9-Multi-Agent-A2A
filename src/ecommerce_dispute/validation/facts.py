"""Validation and canonical hashing for deterministic fact handoffs."""

import json
from decimal import Decimal
from hashlib import sha256

from ecommerce_dispute.schemas import (
    CaseInput,
    CustomerFacts,
    DeliveryFacts,
    FactHandoff,
    MechanicalReport,
    OrderProductFacts,
    PaymentFacts,
    ValidatedPolicyFacts,
    ValidationIssue,
)
from ecommerce_dispute.tools import hours_between, money_sum
from ecommerce_dispute.tools.calculators import round_two


def _issue(field: str, code: str, message: str, owner: str) -> ValidationIssue:
    return ValidationIssue(
        field=field,
        code=code,
        message=message,
        owner_component=owner,
        retryable=False,
    )


def validate_fact_handoffs(
    run_id: str,
    case: CaseInput,
    customer: FactHandoff[CustomerFacts],
    order: FactHandoff[OrderProductFacts],
    payment: FactHandoff[PaymentFacts],
    delivery: FactHandoff[DeliveryFacts],
) -> MechanicalReport:
    issues: list[ValidationIssue] = []
    handoffs = (
        (customer, "customer_facts_worker"),
        (order, "order_product_facts_worker"),
        (payment, "payment_reconciliation_worker"),
        (delivery, "delivery_analysis_worker"),
    )
    for handoff, expected_producer in handoffs:
        metadata = handoff.metadata
        if metadata.run_id != run_id or metadata.case_id != case.case_id:
            issues.append(
                _issue(
                    "handoff.metadata",
                    "HANDOFF_SCOPE_MISMATCH",
                    "Handoff run_id/case_id does not match the active case",
                    metadata.producer,
                )
            )
        if metadata.producer != expected_producer:
            issues.append(
                _issue(
                    "handoff.metadata.producer",
                    "HANDOFF_PRODUCER_MISMATCH",
                    f"Expected {expected_producer}, got {metadata.producer}",
                    metadata.producer,
                )
            )
        expected_key = sha256(
            f"{run_id}:{case.case_id}:{metadata.producer}:{metadata.attempt}".encode()
        ).hexdigest()
        if metadata.idempotency_key != expected_key:
            issues.append(
                _issue(
                    "handoff.metadata.idempotency_key",
                    "IDEMPOTENCY_KEY_MISMATCH",
                    "Handoff idempotency key is invalid",
                    metadata.producer,
                )
            )
        if len(handoff.source_refs) != len(set(handoff.source_refs)):
            issues.append(
                _issue(
                    "handoff.source_refs",
                    "DUPLICATE_SOURCE_REF",
                    "Source references must be unique",
                    metadata.producer,
                )
            )

    order_facts = order.payload
    customer_facts = customer.payload
    payment_facts = payment.payload
    delivery_facts = delivery.payload
    claimed_order_id = case.customer_request.claimed_order_id
    if order_facts.order_id != claimed_order_id:
        issues.append(
            _issue(
                "order.order_id",
                "CLAIMED_ORDER_MISMATCH",
                "Order facts do not match claimed_order_id",
                order.metadata.producer,
            )
        )
    required_refs = (
        {
            f"order:{claimed_order_id}",
            *(
                {f"customer:{customer_facts.customer_unique_id}"}
                if customer_facts.customer_unique_id
                else set()
            ),
            *(f"order:{order_id}" for order_id in customer_facts.related_order_ids),
        },
        {
            f"order:{order_facts.order_id}",
            *(f"item:{item.item_id}" for item in order_facts.items),
            *(f"seller:{seller_id}" for seller_id in order_facts.seller_ids),
            *(f"product:{item.product_id}" for item in order_facts.items),
        },
        {f"payment:{row.payment_id}" for row in payment_facts.payments},
        {
            f"order:{order_facts.order_id}",
            *(f"seller:{seller_id}" for seller_id in order_facts.seller_ids),
        },
    )
    for (handoff, _), expected_refs in zip(handoffs, required_refs, strict=True):
        missing = expected_refs - set(handoff.source_refs)
        if missing:
            issues.append(
                _issue(
                    "handoff.source_refs",
                    "MISSING_SOURCE_REF",
                    f"Missing {len(missing)} required source references",
                    handoff.metadata.producer,
                )
            )
    expected_item_total = (
        float(money_sum(item.price_brl for item in order_facts.items))
        if order_facts.items
        else None
    )
    expected_freight_total = (
        float(money_sum(item.freight_brl for item in order_facts.items))
        if order_facts.items
        else None
    )
    totals = (
        ("item_total_brl", order_facts.item_total_brl, expected_item_total),
        ("freight_total_brl", order_facts.freight_total_brl, expected_freight_total),
        ("payment.item_total_brl", payment_facts.item_total_brl, expected_item_total),
        ("payment.freight_total_brl", payment_facts.freight_total_brl, expected_freight_total),
    )
    for field, actual, expected in totals:
        if actual != expected:
            issues.append(
                _issue(field, "ARITHMETIC_MISMATCH", f"Expected {expected}, got {actual}", "facts")
            )
    derived_flags = (
        ("customer.repeat_customer", customer_facts.repeat_customer, bool(customer_facts.related_order_ids)),
        ("order.multi_item_order", order_facts.multi_item_order, len(order_facts.items) >= 2),
        (
            "order.multi_seller_order",
            order_facts.multi_seller_order,
            len(set(order_facts.seller_ids)) >= 2,
        ),
        (
            "order.multiple_categories",
            order_facts.multiple_categories,
            len(set(order_facts.category_names)) >= 2,
        ),
    )
    for field, actual, expected in derived_flags:
        if actual != expected:
            issues.append(
                _issue(field, "DERIVED_FLAG_MISMATCH", f"Expected {expected}, got {actual}", "facts")
            )

    expected_payment_total = float(
        money_sum(row.payment_value_brl for row in payment_facts.payments)
    )
    if expected_item_total is None or expected_freight_total is None:
        expected_payment_fields = (None, None, None)
    else:
        expected_total_decimal = money_sum([expected_item_total, expected_freight_total])
        difference_decimal = round_two(
            Decimal(str(expected_payment_total)) - expected_total_decimal
        )
        expected_payment_fields = (
            float(expected_total_decimal),
            float(difference_decimal),
            abs(difference_decimal) <= Decimal("0.10"),
        )
    payment_checks = (
        ("payment.payment_total_brl", payment_facts.payment_total_brl, expected_payment_total),
        ("payment.expected_total_brl", payment_facts.expected_total_brl, expected_payment_fields[0]),
        ("payment.difference_brl", payment_facts.difference_brl, expected_payment_fields[1]),
        ("payment.reconciled", payment_facts.reconciled, expected_payment_fields[2]),
    )
    for field, actual, expected in payment_checks:
        if actual != expected:
            issues.append(
                _issue(field, "ARITHMETIC_MISMATCH", f"Expected {expected}, got {actual}", payment.metadata.producer)
            )
    if payment_facts.split_payment != (len(payment_facts.payments) >= 2):
        issues.append(
            _issue(
                "payment.split_payment",
                "DERIVED_FLAG_MISMATCH",
                "split_payment does not match payment row count",
                payment.metadata.producer,
            )
        )
    expected_delivery_variance = (
        float(hours_between(order_facts.delivered_at, order_facts.estimated_delivery_at))
        if order_facts.delivered_at and order_facts.estimated_delivery_at
        else None
    )
    if delivery_facts.delivery_variance_hours != expected_delivery_variance:
        issues.append(
            _issue(
                "delivery.delivery_variance_hours",
                "ARITHMETIC_MISMATCH",
                f"Expected {expected_delivery_variance}, got {delivery_facts.delivery_variance_hours}",
                delivery.metadata.producer,
            )
        )
    if delivery_facts.delivered_late != (
        expected_delivery_variance is not None and expected_delivery_variance > 0
    ):
        issues.append(
            _issue(
                "delivery.delivered_late",
                "DERIVED_FLAG_MISMATCH",
                "delivered_late does not match delivery variance",
                delivery.metadata.producer,
            )
        )
    expected_handoffs: list[tuple[str, str | None, float | None, bool]] = []
    for seller_id in order_facts.seller_ids:
        limits = [
            item.shipping_limit_at
            for item in order_facts.items
            if item.seller_id == seller_id and item.shipping_limit_at
        ]
        shipping_limit = min(limits) if limits else None
        variance = (
            float(hours_between(order_facts.carrier_handoff_at, shipping_limit))
            if order_facts.carrier_handoff_at and shipping_limit
            else None
        )
        expected_handoffs.append(
            (seller_id, shipping_limit, variance, variance is not None and variance > 0)
        )
    actual_handoffs = [
        (
            row.seller_id,
            row.shipping_limit_at,
            row.handoff_variance_hours,
            row.late_handoff,
        )
        for row in delivery_facts.seller_handoff_analysis
    ]
    if actual_handoffs != expected_handoffs:
        issues.append(
            _issue(
                "delivery.seller_handoff_analysis",
                "ARITHMETIC_MISMATCH",
                "Seller handoff analysis does not match source timestamps",
                delivery.metadata.producer,
            )
        )
    expected_late_sellers = tuple(
        row.seller_id for row in delivery_facts.seller_handoff_analysis if row.late_handoff
    )
    if delivery_facts.late_handoff_seller_ids != expected_late_sellers:
        issues.append(
            _issue(
                "delivery.late_handoff_seller_ids",
                "DERIVED_FLAG_MISMATCH",
                "Late seller list does not match handoff analysis",
                delivery.metadata.producer,
            )
        )
    return MechanicalReport(status="fail" if issues else "pass", issues=issues)


def compact_policy_facts(
    case: CaseInput,
    customer: CustomerFacts,
    order: OrderProductFacts,
    payment: PaymentFacts,
    delivery: DeliveryFacts,
) -> ValidatedPolicyFacts:
    return ValidatedPolicyFacts(
        policy_version=case.policy_version,
        order_status=order.order_status,
        order_is_canceled=order.order_status == "canceled",
        order_is_unavailable=order.order_status == "unavailable",
        seller_ids=list(order.seller_ids),
        item_total_brl=order.item_total_brl,
        freight_total_brl=order.freight_total_brl,
        payment_total_brl=payment.payment_total_brl,
        has_positive_payment=payment.payment_total_brl > 0,
        payment_row_count=len(payment.payments),
        reconciled=payment.reconciled,
        split_payment=payment.split_payment,
        delivery_variance_hours=delivery.delivery_variance_hours,
        delivered_late=delivery.delivered_late,
        late_handoff_seller_ids=list(delivery.late_handoff_seller_ids),
        multi_item_order=order.multi_item_order,
        multi_seller_order=order.multi_seller_order,
        repeat_customer=customer.repeat_customer,
        multiple_categories=order.multiple_categories,
    )


def policy_fact_hash(facts: ValidatedPolicyFacts) -> str:
    canonical = json.dumps(
        facts.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
