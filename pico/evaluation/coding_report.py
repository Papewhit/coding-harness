"""Shared audit, row, and metric helpers for Evaluation v2 coding cohorts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path, PurePosixPath
import statistics
from typing import Any

from pico.evaluation.evaluation_v2_evidence import checksums, verify_checksums
from pico.evaluation.evaluation_v2_row_capture import write_json
from pico.evaluation.pilot_audit import (
    load_object,
    optional_object,
    reject_sensitive,
    validate_audit,
    validate_decision,
)


def cohort_root(run_config_path: Path) -> Path:
    return run_config_path.resolve().parents[1]


def append_coding_inputs(
    root: Path,
    config: Mapping[str, Any],
    *,
    audit_inputs: Sequence[Path] = (),
    decision_inputs: Sequence[Path] = (),
    sensitive_values: Sequence[str] = (),
) -> None:
    """Append validated coding-row audits and decisions without overwriting."""

    allowed = _allowed_rows(config)
    for path in audit_inputs:
        audit = load_object(path)
        reject_sensitive(audit, sensitive_values)
        _append_audit(root, allowed, audit)
    for path in decision_inputs:
        decision = load_object(path)
        reject_sensitive(decision, sensitive_values)
        _append_decision(root, allowed, decision)


def verify_coding_rows(root: Path, config: Mapping[str, Any]) -> None:
    """Verify every existing row and its optional audit/decision records."""

    for row in config["allowed_rows"]:
        public_row = root / "public" / "rows" / str(row["row_id"])
        if not public_row.exists():
            continue
        verify_checksums(public_row / "checksums.json", public_row)
        audit_path = public_row / "codex-audit.json"
        if audit_path.is_file():
            validate_audit(public_row, load_object(audit_path))
        decision_path = public_row / "user-decision.json"
        if decision_path.is_file():
            validate_decision(public_row, load_object(decision_path))


def build_coding_rows(
    root: Path,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build deterministic row summaries from frozen identities and evidence."""

    return [_row_report(root, row) for row in config["allowed_rows"]]


def coding_provider_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [
        row.get("facts", {}).get("provider_requests", {})
        for row in rows
        if row.get("status") != "no result"
    ]
    exact = [
        item
        for item in values
        if item.get("exact") is True and type(item.get("count")) is int
    ]
    return {
        "available_samples": len(exact),
        "started_samples": len(values),
        "total": sum(int(item["count"]) for item in exact),
        "complete": len(exact) == len(values),
    }


def coding_numeric_metrics(
    rows: Sequence[Mapping[str, Any]],
    key: str,
    *,
    include_total: bool = False,
) -> dict[str, Any]:
    values = [
        row.get("facts", {}).get(key)
        for row in rows
        if isinstance(row.get("facts", {}).get(key), (int, float))
    ]
    payload: dict[str, Any] = {
        "available_samples": len(values),
        "valid_samples": len(rows),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
    }
    if include_total:
        payload["total"] = sum(values)
    return payload


def coding_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _append_audit(
    root: Path,
    allowed: Mapping[str, Mapping[str, Any]],
    audit: Mapping[str, Any],
) -> None:
    row_id = str(audit.get("row_id", ""))
    if row_id not in allowed:
        raise ValueError(f"audit row is outside the frozen cohort: {row_id}")
    public_row = root / "public" / "rows" / row_id
    _require_started_row(public_row)
    verify_checksums(public_row / "checksums.json", public_row)
    target = public_row / "codex-audit.json"
    if target.exists():
        raise ValueError(f"Codex audit already exists: {row_id}")
    validate_audit(public_row, audit)
    write_json(target, dict(audit))
    _reseal(public_row)


def _append_decision(
    root: Path,
    allowed: Mapping[str, Mapping[str, Any]],
    decision: Mapping[str, Any],
) -> None:
    row_id = str(decision.get("row_id", ""))
    if row_id not in allowed:
        raise ValueError(f"user decision row is outside the frozen cohort: {row_id}")
    public_row = root / "public" / "rows" / row_id
    _require_started_row(public_row)
    verify_checksums(public_row / "checksums.json", public_row)
    target = public_row / "user-decision.json"
    if target.exists():
        raise ValueError(f"user decision already exists: {row_id}")
    audit = load_object(public_row / "codex-audit.json")
    if audit.get("user_decision") != "required":
        raise ValueError("user decision is only allowed when the Codex audit requires it")
    validate_decision(public_row, decision)
    write_json(target, dict(decision))
    _reseal(public_row)


def _row_report(root: Path, allowed: Mapping[str, Any]) -> dict[str, Any]:
    row_id = str(allowed["row_id"])
    public_row = root / "public" / "rows" / row_id
    base = {
        "row_id": row_id,
        "task_id": str(allowed["task_id"]),
        "repetition": int(allowed["repetition"]),
    }
    if not public_row.exists():
        return {**base, "status": "no result"}
    record = load_object(public_row / "run-record.json")
    view = optional_object(public_row / "evidence-view.json")
    facts = _row_facts(public_row, record, view)
    audit = optional_object(public_row / "codex-audit.json")
    if not audit:
        return {**base, "status": "pending audit", "facts": facts}
    validate_audit(public_row, audit)
    if audit["user_decision"] == "required":
        decision = optional_object(public_row / "user-decision.json")
        if not decision:
            return {
                **base,
                "status": "pending decision",
                "reason": audit["reason"],
                "facts": facts,
            }
        validate_decision(public_row, decision)
        classification = decision["final_classification"]
        category = decision["failure_category"]
        reason = decision["reason"]
    else:
        classification = audit["final_classification"]
        category = audit["failure_category"]
        reason = audit["reason"]
    return {
        **base,
        "status": "final",
        "final_classification": classification,
        "failure_category": category,
        "reason": reason,
        "facts": facts,
        "evidence": {
            "run_record": f"public/rows/{row_id}/run-record.json",
            "evidence_view": f"public/rows/{row_id}/evidence-view.json",
            "codex_audit": f"public/rows/{row_id}/codex-audit.json",
        },
    }


def _row_facts(
    public_row: Path,
    record: Mapping[str, Any],
    view: Mapping[str, Any],
) -> dict[str, Any]:
    provider = view.get("provider_requests", record.get("provider_requests", {}))
    report = _first_object(public_row / "original" / ".pico" / "runs", "*/report.json")
    trace = _first_jsonl(public_row / "original" / ".pico" / "runs", "*/trace.jsonl")
    reads = [
        str(row.get("args", {}).get("path", ""))
        for row in trace
        if row.get("event") == "tool_executed"
        and row.get("name") == "read_file"
        and row.get("tool_status") in {"ok", "completed", "success"}
        and isinstance(row.get("args"), Mapping)
        and row.get("args", {}).get("path")
    ]
    read_counts = Counter(PurePosixPath(path).as_posix() for path in reads)
    finished = next(
        (row for row in reversed(trace) if row.get("event") == "run_finished"),
        {},
    )
    return {
        "measurement_status": record.get("measurement_status"),
        "provider_requests": {
            "count": provider.get("count"),
            "exact": provider.get("exact"),
        },
        "tool_steps": report.get("tool_steps"),
        "repeated_reads": sum(max(count - 1, 0) for count in read_counts.values()),
        "elapsed_time_ms": finished.get("run_duration_ms"),
    }


def _allowed_rows(
    config: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {str(row["row_id"]): row for row in config["allowed_rows"]}


def _require_started_row(public_row: Path) -> None:
    if not public_row.is_dir() or not (public_row / "run-record.json").is_file():
        raise ValueError(f"coding row has not started: {public_row.name}")


def _reseal(public_row: Path) -> None:
    write_json(public_row / "checksums.json", checksums(public_row))
    verify_checksums(public_row / "checksums.json", public_row)


def _first_object(root: Path, pattern: str) -> dict[str, Any]:
    path = next(iter(sorted(root.glob(pattern))), None) if root.exists() else None
    return load_object(path) if path else {}


def _first_jsonl(root: Path, pattern: str) -> list[dict[str, Any]]:
    path = next(iter(sorted(root.glob(pattern))), None) if root.exists() else None
    if not path:
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


__all__ = [
    "append_coding_inputs",
    "build_coding_rows",
    "cohort_root",
    "coding_numeric_metrics",
    "coding_provider_metrics",
    "coding_ratio",
    "verify_coding_rows",
]
