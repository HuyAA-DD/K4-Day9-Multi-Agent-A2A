"""Thread-safe, per-run JSONL tracing and atomic JSON artifact writes."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            temporary = Path(stream.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class TraceWriter:
    def __init__(self, logging_root: Path, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = logging_root / run_id
        self.trace_path = self.run_dir / "trace.jsonl"
        self.metadata_path = self.run_dir / "metadata.json"
        self.manifest_path = self.run_dir / "manifest.json"
        self._lock = Lock()

    def start_run(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text("", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        safe_event = {key: value for key, value in event.items() if key != "api_key"}
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            **safe_event,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock, self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(line)

    def write_metadata(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.metadata_path, payload)

    def write_manifest(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.manifest_path, payload)

    def count_events(self) -> int:
        if not self.trace_path.exists():
            return 0
        return sum(1 for line in self.trace_path.read_text(encoding="utf-8").splitlines() if line)
