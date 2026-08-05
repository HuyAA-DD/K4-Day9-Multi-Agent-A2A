"""Money and timestamp calculations used by Payment and Delivery agents."""

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

CSV_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
TWO_PLACES = Decimal("0.01")


def round_two(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money_sum(values: Iterable[str | float | Decimal]) -> Decimal:
    return round_two(sum((Decimal(str(value)) for value in values), start=Decimal(0)))


def hours_between(later: str, earlier: str) -> Decimal:
    # README requires comparing raw CSV values without timezone conversion. UTC
    # is attached equally to both values only to keep datetime objects aware.
    later_at = datetime.strptime(later, CSV_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    earlier_at = datetime.strptime(earlier, CSV_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    hours = Decimal(str((later_at - earlier_at).total_seconds())) / Decimal(3600)
    return round_two(hours)
