import ast
from pathlib import Path

from ecommerce_dispute.config import PROJECT_ROOT


def test_agent_modules_contain_no_business_rule_branching() -> None:
    agent_dir = PROJECT_ROOT / "src" / "ecommerce_dispute" / "agents"
    business_literals = {
        "canceled_order_paid",
        "unavailable_order_paid",
        "late_delivery_seller",
        "late_delivery_logistics",
        "valid_split_payment",
        "unsupported_late_claim",
    }
    for path in agent_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not (literals & business_literals), path.name


def test_obsolete_agent_modules_are_removed() -> None:
    agent_dir = Path(PROJECT_ROOT) / "src" / "ecommerce_dispute" / "agents"
    assert {path.name for path in agent_dir.glob("*.py")} == {
        "__init__.py",
        "adjudicator.py",
        "base.py",
        "evaluator.py",
        "policy.py",
    }


def test_production_validator_contains_no_policy_outcome_table() -> None:
    validator = (
        PROJECT_ROOT / "src" / "ecommerce_dispute" / "validation" / "policy.py"
    )
    source = validator.read_text(encoding="utf-8")
    business_literals = {
        "canceled_order_paid",
        "unavailable_order_paid",
        "late_delivery_seller",
        "late_delivery_logistics",
        "valid_split_payment",
        "unsupported_late_claim",
        "ORDER_CANCELED_AFTER_PAYMENT",
        "SELLER_HANDOFF_AFTER_LIMIT",
    }
    assert not any(literal in source for literal in business_literals)
