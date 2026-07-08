"""Session-level event bus.

The run trace is per-task and diagnostic. The session event bus is the durable,
coarse-grained timeline for the interactive session itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .workspace import now


class SessionEventBus:
    def __init__(self, session_id: str, path: str | Path, redact: Callable[[Any], Any] | None = None):
        self.session_id = str(session_id)
        self.path = Path(path)
        self.redact = redact or (lambda value: value)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        record = dict(payload or {})
        record["event"] = str(event)
        record["session_id"] = self.session_id
        record["created_at"] = now()
        record = self.redact(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record
