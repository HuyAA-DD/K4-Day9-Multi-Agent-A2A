"""Money and timestamp calculations used by Payment and Delivery agents."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from collections.abc import Iterable


CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
TWO_PLACES = Decimal("0.01")


def round_two(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money_sum(values: Iterable[str | float | Decimal]) -> Decimal:
    return round_two(sum((Decimal(str(value)) for value in values), start=Decimal("0")))


def hours_between(later: str, earlier: str) -> Decimal:
    later_at = datetime.strptime(later, CSV_TIMESTAMP_FORMAT)
    earlier_at = datetime.strptime(earlier, CSV_TIMESTAMP_FORMAT)
    hours = Decimal(str((later_at - earlier_at).total_seconds())) / Decimal("3600")
    return round_two(hours)

