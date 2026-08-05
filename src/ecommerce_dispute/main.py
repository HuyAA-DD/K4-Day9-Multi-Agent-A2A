"""Command-line entry point for the 50-case Supervisor DAG."""

import argparse
from collections.abc import Sequence

from ecommerce_dispute.config import MODEL_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Olist dispute cases")
    parser.add_argument("--case", help="Run one case ID, for example EC_001")
    parser.add_argument("--all", action="store_true", help="Run all input cases")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.case and not args.all:
        raise SystemExit("Choose --case EC_XXX or --all")
    raise SystemExit(f"Runtime wiring for {MODEL_NAME} is not implemented yet")


if __name__ == "__main__":
    main()

