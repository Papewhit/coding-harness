"""Evidence extraction for worker child runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import Pico


def collect_worker_artifacts(root: Path, child: Pico, task_state: dict[str, Any] | None) -> dict[str, Any]:
    run_dir = getattr(child, "current_run_dir", None)
    payload = {
        "run_id": str(getattr(task_state, "run_id", "") or ""),
        "run_dir": relative_path(root, run_dir),
        "report_path": relative_path(root, run_dir / "report.json" if run_dir else None),
        "trace_path": relative_path(root, run_dir / "trace.jsonl" if run_dir else None),
        "session_event_path": relative_path(root, getattr(getattr(child, "session_event_bus", None), "path", None)),
        "tool_error_codes": [],
    }
    trace_path = run_dir / "trace.jsonl" if run_dir else None
    if trace_path and trace_path.exists():
        payload["tool_error_codes"] = trace_error_codes(trace_path)
    return payload


def trace_error_codes(trace_path: Path) -> list[str]:
    error_codes = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") != "tool_executed":
            continue
        code = str(event.get("tool_error_code", "")).strip()
        if code and code not in error_codes:
            error_codes.append(code)
    return error_codes


def relative_path(root: Path, path: Path | None) -> str:
    if not path:
        return ""
    try:
        return str(path.relative_to(root).as_posix())
    except ValueError:
        return str(path)
