"""Deterministic evidence views, diffs, scans, and manifests for Evaluation v2."""

from __future__ import annotations

from collections import Counter
import difflib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from pico.evaluation.evaluation_v2_config import sha256_file
from pico.evaluation.live_tasks import ClientResult


EVIDENCE_VIEW_SCHEMA = "pico-evaluation-v2-evidence-view-v1"
CHECKSUM_SCHEMA = "pico-evaluation-v2-checksums-v1"


def build_evidence_view(
    *,
    private_row: Path,
    public_row: Path,
    client_result: ClientResult,
    verifier: Any,
    manifest_diff: Mapping[str, Any],
    unified_diff: str,
) -> dict[str, Any]:
    session_path = _first(private_row / "original" / ".pico" / "sessions", "*.json")
    event_path = _first(public_row / "original" / ".pico" / "sessions", "*.events.jsonl")
    trace_path = _first(public_row / "original" / ".pico" / "runs", "*/trace.jsonl")
    session = _load_object(session_path) if session_path else {}
    event_rows = _load_jsonl(event_path) if event_path else []
    trace_rows = _load_jsonl(trace_path) if trace_path else []
    calls: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    for index, event in enumerate(session.get("model_exchange", {}).get("events", [])):
        if event.get("event") == "assistant_tool_batch":
            for call_index, call in enumerate(event.get("tool_calls", [])):
                calls.append(
                    {
                        "call_id": str(call.get("call_id", "")),
                        "tool_name": str(call.get("name", "")),
                        "source": {
                            "path": _relative(session_path, private_row),
                            "pointer": f"/model_exchange/events/{index}/tool_calls/{call_index}",
                        },
                    }
                )
        elif event.get("event") == "tool_result":
            result_rows.append(
                {
                    "call_id": str(event.get("call_id", "")),
                    "tool_name": str(event.get("name", "")),
                    "status": str(event.get("status", "")),
                    "source": {
                        "path": _relative(session_path, private_row),
                        "pointer": f"/model_exchange/events/{index}",
                    },
                }
            )
    finished_rows = [
        {
            "call_id": str(event.get("call_id", "")),
            "tool_name": str(event.get("tool_name", "")),
            "status": str(event.get("status", "")),
            "source": {"path": _relative(event_path, public_row), "line": index + 1},
        }
        for index, event in enumerate(event_rows)
        if event.get("event") == "tool_finished"
    ]
    traced_rows = [
        {
            "call_id": str(event.get("call_id", "")),
            "tool_name": str(event.get("name", "")),
            "status": str(event.get("tool_status", "")),
            "source": {"path": _relative(trace_path, public_row), "line": index + 1},
        }
        for index, event in enumerate(trace_rows)
        if event.get("event") == "tool_executed"
    ]
    results = _index_by_call_id(result_rows)
    finished = _index_by_call_id(finished_rows)
    traced = _index_by_call_id(traced_rows)
    errors = _call_protocol_errors(
        calls,
        result_rows,
        finished_rows,
        traced_rows,
        client_result,
    )
    ordered = [
        {
            **call,
            "result": results.get(call["call_id"]),
            "runtime_finished": finished.get(call["call_id"]),
            "run_trace": traced.get(call["call_id"]),
        }
        for call in calls
    ]
    return {
        "schema_version": EVIDENCE_VIEW_SCHEMA,
        "tool_calls": ordered,
        "workspace": {"manifest_diff": dict(manifest_diff), "unified_diff": unified_diff},
        "final_answer": client_result.final_answer,
        "verifier": {
            "passed": verifier.passed,
            "returncode": verifier.returncode,
            "source": "verifier/result.json",
        },
        "provider_requests": {
            "count": len(client_result.http_attempts),
            "exact": client_result.http_attempts_exact,
            "sdk_retry_count": client_result.sdk_retry_count,
            "pico_retry_count": client_result.pico_retry_count,
            "source": "run-record.json#/client_result",
        },
        "protocol_errors": errors,
    }


def workspace_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".pico" not in path.relative_to(root).parts
    }


def unified_diff(before: Mapping[str, bytes], after: Mapping[str, bytes]) -> str:
    chunks = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name, b"").decode("utf-8", errors="replace").splitlines(True)
        new = after.get(name, b"").decode("utf-8", errors="replace").splitlines(True)
        if old == new:
            continue
        chunks.extend(
            difflib.unified_diff(old, new, fromfile=f"a/{name}", tofile=f"b/{name}")
        )
    return "".join(chunks)


def scan_known_values(root: Path, sensitive_values: tuple[str, ...]) -> dict[str, Any]:
    needles = [value.encode("utf-8") for value in sensitive_values if value]
    files = [path for path in sorted(root.rglob("*")) if path.is_file()] if root.exists() else []
    hits = []
    for path in files:
        content = path.read_bytes()
        if any(needle in content for needle in needles):
            hits.append(path.relative_to(root.parent).as_posix())
    return {"passed": not hits, "files_scanned": len(files), "hit_paths": hits}


def checksums(root: Path, subtree: str | None = None) -> dict[str, Any]:
    start = root / subtree if subtree else root
    manifest_path = root / "checksums.json"
    files = []
    if start.exists():
        for path in sorted(start.rglob("*")):
            if path.is_file() and path != manifest_path:
                files.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
    return {"schema_version": CHECKSUM_SCHEMA, "files": files}


def verify_checksums(manifest_path: Path, root: Path) -> None:
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    try:
        manifest_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("checksum manifest must be inside its inventory root") from exc
    payload = _load_object(manifest_path)
    if set(payload) != {"schema_version", "files"}:
        raise ValueError("checksum manifest fields drift")
    if payload["schema_version"] != CHECKSUM_SCHEMA:
        raise ValueError("unsupported checksum manifest schema")
    items = payload["files"]
    if not isinstance(items, list):
        raise ValueError("checksum manifest files must be a list")
    declared: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping) or set(item) != {"path", "bytes", "sha256"}:
            raise ValueError("checksum manifest entry fields drift")
        relative = _safe_inventory_path(item.get("path"))
        if relative in declared:
            raise ValueError(f"duplicate checksum inventory path: {relative}")
        size = item.get("bytes")
        digest = item.get("sha256")
        if type(size) is not int or size < 0:
            raise ValueError(f"invalid checksum byte count: {relative}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"invalid checksum digest: {relative}")
        declared[relative] = item
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(declared) != actual:
        missing = sorted(actual - set(declared))
        unexpected = sorted(set(declared) - actual)
        raise ValueError(
            f"checksum inventory is incomplete: unlisted={missing}, missing={unexpected}"
        )
    for relative, item in declared.items():
        path = root / relative
        if path.is_symlink():
            raise ValueError(f"checksum inventory path must not be a symlink: {relative}")
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"checksum verification failed: {item['path']}")


def _safe_inventory_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("checksum inventory path is not a safe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe checksum inventory path: {value}")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"non-canonical checksum inventory path: {value}")
    return normalized


def _call_protocol_errors(
    calls: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    finished_rows: list[dict[str, Any]],
    traced_rows: list[dict[str, Any]],
    client_result: ClientResult,
) -> list[str]:
    call_ids = [call["call_id"] for call in calls]
    results = _index_by_call_id(result_rows)
    finished = _index_by_call_id(finished_rows)
    traced = _index_by_call_id(traced_rows)
    errors = list(client_result.protocol_errors)
    for label, values in (
        ("model calls", call_ids),
        ("tool results", [row["call_id"] for row in result_rows]),
        ("runtime completions", [row["call_id"] for row in finished_rows]),
        ("run trace", [row["call_id"] for row in traced_rows]),
        ("client calls", list(client_result.call_ids)),
        ("client results", list(client_result.result_call_ids)),
    ):
        duplicates = sorted(
            key for key, count in Counter(values).items() if not key or count != 1
        )
        if duplicates:
            errors.append(f"{label} contain empty or duplicate call IDs: {duplicates}")
    expected = set(call_ids)
    for label, observed in (
        ("tool results", set(results)),
        ("runtime completions", set(finished)),
        ("run trace", set(traced)),
        ("client calls", set(client_result.call_ids)),
        ("client results", set(client_result.result_call_ids)),
    ):
        if observed != expected:
            errors.append(f"{label} call ID set does not match model calls")
    by_id = {call["call_id"]: call["tool_name"] for call in calls}
    for call_id, name in by_id.items():
        if any(
            layer.get(call_id, {}).get("tool_name") != name
            for layer in (results, finished, traced)
        ):
            errors.append(f"tool name mismatch for call ID {call_id}")
        result_status = str(results.get(call_id, {}).get("status", ""))
        runtime_status = str(finished.get(call_id, {}).get("status", ""))
        trace_status = str(traced.get(call_id, {}).get("status", ""))
        if result_status not in {"completed", "rejected", "error"}:
            errors.append(f"missing or invalid model-exchange terminal status for {call_id}")
        if not runtime_status or runtime_status != trace_status:
            errors.append(f"runtime terminal status mismatch for call ID {call_id}")
    return sorted(set(errors))


def _index_by_call_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["call_id"]): row for row in rows}


def _first(root: Path, pattern: str) -> Path | None:
    return next(iter(sorted(root.glob(pattern))), None) if root.exists() else None


def _relative(path: Path | None, root: Path) -> str:
    return path.relative_to(root).as_posix() if path else ""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


__all__ = [
    "EVIDENCE_VIEW_SCHEMA",
    "build_evidence_view",
    "checksums",
    "scan_known_values",
    "unified_diff",
    "verify_checksums",
    "workspace_files",
]
