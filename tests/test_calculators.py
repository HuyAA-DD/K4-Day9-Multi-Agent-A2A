from decimal import Decimal

from ecommerce_dispute.tools.calculators import hours_between, money_sum


def test_money_sum_rounds_to_two_places() -> None:
    assert money_sum(["110.32", "110.32", "8.35", "8.35"]) == Decimal("237.34")


def test_ec001_delivery_variance() -> None:
    assert hours_between(
        "2018-06-19 01:28:42",
        "2018-06-26 00:00:00",
    ) == Decimal("-166.52")

