"""Atomic writer restricted to fully verified outputs in the current run namespace."""

import os
import tempfile
from pathlib import Path

from ecommerce_dispute.schemas import CaseOutput, MechanicalReport, VerificationReport


def write_verified_output(
    output: CaseOutput,
    output_root: Path,
    run_id: str,
    mechanical: MechanicalReport,
    verification: VerificationReport,
) -> Path:
    if mechanical.status != "pass" or verification.status != "pass":
        raise ValueError("Output writer accepts only mechanically and semantically verified output")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    destination = run_dir / f"{output.case_id}.json"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=run_dir,
            prefix=f".{output.case_id}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(output.model_dump_json(indent=2))
            stream.write("\n")
            temporary = Path(stream.name)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return destination
