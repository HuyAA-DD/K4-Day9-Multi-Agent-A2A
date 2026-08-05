"""Capability-scoped read-only data tools for individual agents."""

from ecommerce_dispute.data import OlistRepository


class CustomerTools:
    """Only customer identity and history lookups."""

    def __init__(self, repository: OlistRepository) -> None:
        self.__repository = repository

    def get_order_customer(self, order_id: str) -> dict[str, str] | None:
        return self.__repository.get_order_customer(order_id)

    def get_related_orders(self, customer_unique_id: str, order_id: str) -> list[str]:
        return self.__repository.get_related_orders(customer_unique_id, order_id)


class OrderProductTools:
    """Only order, item, product and seller lookups."""

    def __init__(self, repository: OlistRepository) -> None:
        self.__repository = repository

    def require_order(self, order_id: str) -> dict[str, str]:
        return self.__repository.require_order(order_id)

    def get_order_items(self, order_id: str) -> list[dict[str, str]]:
        return self.__repository.get_order_items(order_id)

    def get_products(self, product_ids: list[str]) -> list[dict[str, str]]:
        return self.__repository.get_products(product_ids)

    def get_sellers(self, seller_ids: list[str]) -> list[dict[str, str]]:
        return self.__repository.get_sellers(seller_ids)


class PaymentTools:
    """Only payment-row lookups."""

    def __init__(self, repository: OlistRepository) -> None:
        self.__repository = repository

    def get_order_payments(self, order_id: str) -> list[dict[str, str]]:
        return self.__repository.get_order_payments(order_id)
