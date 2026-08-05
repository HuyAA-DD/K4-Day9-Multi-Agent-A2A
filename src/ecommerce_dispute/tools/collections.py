"""Stable collection helpers used by source-data agents."""

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def stable_unique(values: Iterable[T]) -> list[T]:
    seen: set[T] = set()
    result: list[T] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
