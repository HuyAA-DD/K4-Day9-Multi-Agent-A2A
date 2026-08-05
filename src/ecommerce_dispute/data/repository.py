"""Read-only repository for Olist CSV data.

CSV files will be loaded once and indexed by their join keys. Agent tools must
query this repository instead of exposing full DataFrames to the model.
"""

from pathlib import Path
from typing import Any


class OlistRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._tables: dict[str, Any] = {}

    def load(self) -> None:
        """Load and index the nine CSV sources exactly once."""
        raise NotImplementedError

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_order_items(self, order_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_order_payments(self, order_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_order_customer(self, order_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_related_orders(self, customer_unique_id: str, exclude_order_id: str) -> list[str]:
        raise NotImplementedError

    def get_products(self, product_ids: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_sellers(self, seller_ids: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError
