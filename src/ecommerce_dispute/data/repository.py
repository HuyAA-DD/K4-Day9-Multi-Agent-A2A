"""Read-only, indexed access to the Olist CSV sources."""

from collections import defaultdict
from pathlib import Path
from typing import ClassVar

import pandas as pd


class DataIntegrityError(ValueError):
    """Raised when a required source relationship cannot be resolved."""


class OlistRepository:
    """Load required tables once and preserve source-row ordering in every lookup."""

    FILES: ClassVar[dict[str, str]] = {
        "customers": "olist_customers_dataset.csv",
        "orders": "olist_orders_dataset.csv",
        "items": "olist_order_items_dataset.csv",
        "payments": "olist_order_payments_dataset.csv",
        "products": "olist_products_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
    }

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._tables: dict[str, pd.DataFrame] = {}
        self._orders: dict[str, dict[str, str]] = {}
        self._customers: dict[str, dict[str, str]] = {}
        self._products: dict[str, dict[str, str]] = {}
        self._sellers: dict[str, dict[str, str]] = {}
        self._items_by_order: dict[str, list[dict[str, str]]] = {}
        self._payments_by_order: dict[str, list[dict[str, str]]] = {}
        self._orders_by_customer: dict[str, list[dict[str, str]]] = {}
        self._customer_ids_by_unique: dict[str, list[str]] = {}
        self.loaded = False

    def load(self) -> None:
        for table_name, filename in self.FILES.items():
            path = self.data_dir / filename
            if not path.is_file():
                raise FileNotFoundError(f"Missing Olist source: {path}")
            self._tables[table_name] = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )

        self._orders = self._index_unique(self._tables["orders"], "order_id")
        self._customers = self._index_unique(self._tables["customers"], "customer_id")
        self._products = self._index_unique(self._tables["products"], "product_id")
        self._sellers = self._index_unique(self._tables["sellers"], "seller_id")
        self._items_by_order = self._index_many(self._tables["items"], "order_id")
        self._payments_by_order = self._index_many(self._tables["payments"], "order_id")
        self._orders_by_customer = self._index_many(self._tables["orders"], "customer_id")

        customer_ids_by_unique: defaultdict[str, list[str]] = defaultdict(list)
        for row in self._tables["customers"].to_dict(orient="records"):
            customer_ids_by_unique[row["customer_unique_id"]].append(row["customer_id"])
        self._customer_ids_by_unique = dict(customer_ids_by_unique)
        self.loaded = True

    @staticmethod
    def _index_unique(frame: pd.DataFrame, key: str) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for row in frame.to_dict(orient="records"):
            value = row[key]
            if value in result:
                raise DataIntegrityError(f"Duplicate {key}: {value}")
            result[value] = row
        return result

    @staticmethod
    def _index_many(frame: pd.DataFrame, key: str) -> dict[str, list[dict[str, str]]]:
        result: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        for row in frame.to_dict(orient="records"):
            result[row[key]].append(row)
        return dict(result)

    def _require_loaded(self) -> None:
        if not self.loaded:
            raise RuntimeError("OlistRepository.load() must be called before querying")

    def get_order(self, order_id: str) -> dict[str, str] | None:
        self._require_loaded()
        row = self._orders.get(order_id)
        return dict(row) if row is not None else None

    def require_order(self, order_id: str) -> dict[str, str]:
        order = self.get_order(order_id)
        if order is None:
            raise DataIntegrityError(f"Unknown claimed_order_id: {order_id}")
        return order

    def get_order_items(self, order_id: str) -> list[dict[str, str]]:
        self._require_loaded()
        return [dict(row) for row in self._items_by_order.get(order_id, [])]

    def get_order_payments(self, order_id: str) -> list[dict[str, str]]:
        self._require_loaded()
        return [dict(row) for row in self._payments_by_order.get(order_id, [])]

    def get_order_customer(self, order_id: str) -> dict[str, str] | None:
        order = self.require_order(order_id)
        row = self._customers.get(order["customer_id"])
        return dict(row) if row is not None else None

    def get_related_orders(self, customer_unique_id: str, exclude_order_id: str) -> list[str]:
        self._require_loaded()
        related: list[str] = []
        for customer_id in self._customer_ids_by_unique.get(customer_unique_id, []):
            for order in self._orders_by_customer.get(customer_id, []):
                if order["order_id"] != exclude_order_id:
                    related.append(order["order_id"])
        return related

    def get_products(self, product_ids: list[str]) -> list[dict[str, str]]:
        self._require_loaded()
        return [dict(self._products[product_id]) for product_id in product_ids if product_id in self._products]

    def get_sellers(self, seller_ids: list[str]) -> list[dict[str, str]]:
        self._require_loaded()
        return [dict(self._sellers[seller_id]) for seller_id in seller_ids if seller_id in self._sellers]

    def table_counts(self) -> dict[str, int]:
        self._require_loaded()
        return {name: len(frame) for name, frame in self._tables.items()}
