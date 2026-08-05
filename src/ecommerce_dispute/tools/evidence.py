"""Source-backed evidence ID constructors."""


def order_evidence_id(order_id: str) -> str:
    return f"order:{order_id}"


def item_evidence_id(order_id: str, order_item_id: str | int) -> str:
    return f"item:{order_id}:{order_item_id}"


def payment_evidence_id(order_id: str, payment_sequential: str | int) -> str:
    return f"payment:{order_id}:{payment_sequential}"


def seller_evidence_id(seller_id: str) -> str:
    return f"seller:{seller_id}"


def policy_evidence_id(root_cause_code: str) -> str:
    return f"policy:{root_cause_code}"

