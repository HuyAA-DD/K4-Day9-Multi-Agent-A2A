from decimal import Decimal

from ecommerce_dispute.tools.calculators import hours_between, money_sum


def test_money_sum_uses_decimal_rounding() -> None:
    assert money_sum(["0.10", "0.20"]) == Decimal("0.30")


def test_hours_between_rounds_to_two_places() -> None:
    assert hours_between("2018-03-31 15:23:33", "2018-03-28 00:00:00") == Decimal(
        "87.39"
    )
