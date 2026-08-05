"""JSONL trace writer for real agent executions."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def start_run(self) -> None:
        """Clear the previous run as required by the assignment."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(UTC).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")

    def count_events(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as stream:
            return sum(1 for line in stream if line.strip())
