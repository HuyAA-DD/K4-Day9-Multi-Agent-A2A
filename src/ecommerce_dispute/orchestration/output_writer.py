"""Atomic writer restricted to verified CaseOutput objects."""

import os
from pathlib import Path
import tempfile

from ecommerce_dispute.schemas.output import CaseOutput


def write_verified_output(output: CaseOutput, output_dir: Path) -> Path:
    """Write one output atomically after all verification gates have passed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{output.case_id}.json"
    serialized = output.model_dump_json(indent=2) + "\n"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{output.case_id}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(serialized)
            temporary_path = Path(stream.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return destination

