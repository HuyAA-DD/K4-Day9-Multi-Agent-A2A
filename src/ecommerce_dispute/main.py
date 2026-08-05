"""Command-line entry point for the 50-case Supervisor DAG."""

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from ecommerce_dispute.config import (
    DATA_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    TRACE_PATH,
    Settings,
)
from ecommerce_dispute.data import OlistRepository
from ecommerce_dispute.llm import LocalModelClient
from ecommerce_dispute.orchestration.runner import CaseRunResult, DisputeRunner
from ecommerce_dispute.schemas.case import CaseInput
from ecommerce_dispute.tracing import TraceWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Olist dispute cases")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case", help="Run one case ID, for example EC_001")
    selection.add_argument("--all", action="store_true", help="Run all 50 input cases")
    parser.add_argument("--no-write", action="store_true", help="Validate without writing output")
    return parser


def load_case(path: Path) -> CaseInput:
    case = CaseInput.model_validate_json(path.read_text(encoding="utf-8"))
    if case.case_id != path.stem:
        raise ValueError(f"{path.name}: case_id must equal the filename stem")
    return case


def select_cases(case_id: str | None, run_all: bool) -> list[CaseInput]:
    if run_all:
        paths = sorted(INPUT_DIR.glob("EC_*.json"))
        expected = [f"EC_{index:03}.json" for index in range(1, 51)]
        actual = [path.name for path in paths]
        if actual != expected:
            raise ValueError("input/ must contain exactly EC_001.json through EC_050.json")
    else:
        normalized = (case_id or "").upper()
        path = INPUT_DIR / f"{normalized}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Input case not found: {path}")
        paths = [path]
    return [load_case(path) for path in paths]


async def async_main(args: argparse.Namespace) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = Settings.from_environment()
    cases = select_cases(args.case, args.all)

    repository = OlistRepository(DATA_DIR)
    repository.load()
    trace_writer = TraceWriter(TRACE_PATH)
    model_client = LocalModelClient(settings)

    def report_progress(completed: int, total: int, result: CaseRunResult) -> None:
        detail = "success" if result.status == "success" else f"failed: {result.error}"
        print(f"[{completed:02}/{total:02}] {result.case_id}: {detail}", flush=True)

    runner = DisputeRunner(
        repository=repository,
        trace_writer=trace_writer,
        model_client=model_client,
        output_dir=OUTPUT_DIR,
        write_outputs=not args.no_write,
        progress_callback=report_progress,
    )
    results = await runner.run_cases(cases)
    succeeded = sum(result.status == "success" for result in results)
    print(f"Completed {succeeded}/{len(results)} cases")
    return 0 if succeeded == len(results) else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
