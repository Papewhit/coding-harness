"""Finalize and verify Evaluation v2 Pilot audits and reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path, PurePosixPath
import statistics
from typing import Any

from pico.evaluation.evaluation_v2_config import canonical_json, verify_run_config
from pico.evaluation.evaluation_v2_schedule import PILOT_COHORTS
from pico.evaluation.evaluation_v2_evidence import (
    checksums,
    verify_checksums,
)
from pico.evaluation.evaluation_v2_row_capture import write_json
from pico.evaluation.pilot_audit import (
    AUDIT_SCHEMA,
    DECISION_SCHEMA,
    FINAL_CLASSIFICATIONS,
    load_object as _load_object,
    optional_object as _optional_object,
    reject_sensitive as _reject_sensitive,
    validate_audit as _validate_audit,
    validate_decision as _validate_decision,
)


REPORT_SCHEMA = "pico-evaluation-v2-pilot-report-v1"
REPORT_JSON = Path("reports/pilot-report.json")
REPORT_MARKDOWN = Path("reports/pilot-report.md")


def cohort_root(run_config_path: Path) -> Path:
    return run_config_path.resolve().parents[1]


def verified_config(run_config_path: Path) -> dict[str, Any]:
    payload = _load_object(run_config_path)
    verify_run_config(run_config_path)
    if payload.get("cohort_id") not in PILOT_COHORTS:
        raise ValueError("Pilot report requires a supported Pilot run config")
    return payload


def finalize_pilot(
    run_config_path: Path,
    *,
    audit_inputs: Sequence[Path] = (),
    decision_inputs: Sequence[Path] = (),
    sensitive_values: Sequence[str] = (),
    generator: Mapping[str, Any],
) -> dict[str, Any]:
    config = verified_config(run_config_path)
    root = cohort_root(run_config_path)
    allowed = _allowed_rows(config)
    for path in audit_inputs:
        audit = _load_object(path)
        _reject_sensitive(audit, sensitive_values)
        _append_audit(root, allowed, audit)
    for path in decision_inputs:
        decision = _load_object(path)
        _reject_sensitive(decision, sensitive_values)
        _append_decision(root, allowed, decision)
    prior = _optional_object(root / REPORT_JSON)
    stable_generator = dict(prior.get("generator", generator)) if prior else dict(generator)
    report = build_pilot_report(run_config_path, generator=stable_generator)
    write_json(root / REPORT_JSON, report)
    markdown = render_pilot_markdown(report)
    _write_text_atomic(root / REPORT_MARKDOWN, markdown)
    return verify_pilot(run_config_path)


def verify_pilot(run_config_path: Path) -> dict[str, Any]:
    config = verified_config(run_config_path)
    root = cohort_root(run_config_path)
    for row in config["allowed_rows"]:
        public_row = root / "public" / "rows" / str(row["row_id"])
        if not public_row.exists():
            continue
        verify_checksums(public_row / "checksums.json", public_row)
        audit_path = public_row / "codex-audit.json"
        if audit_path.is_file():
            _validate_audit(public_row, _load_object(audit_path))
        decision_path = public_row / "user-decision.json"
        if decision_path.is_file():
            _validate_decision(public_row, _load_object(decision_path))
    report_path = root / REPORT_JSON
    report = _load_object(report_path)
    expected = build_pilot_report(run_config_path, generator=report.get("generator", {}))
    if canonical_json(report) != canonical_json(expected):
        raise ValueError("Pilot report JSON cannot be rebuilt from row evidence")
    markdown = (root / REPORT_MARKDOWN).read_text(encoding="utf-8")
    if markdown != render_pilot_markdown(report):
        raise ValueError("Pilot Markdown cannot be rebuilt from report JSON")
    return {
        "cohort_id": str(config["cohort_id"]),
        "g0_status": report["g0"]["status"],
        "rows": report["counts"],
        "markdown_rebuilt": True,
    }


def build_pilot_report(
    run_config_path: Path, *, generator: Mapping[str, Any]
) -> dict[str, Any]:
    config = verified_config(run_config_path)
    cohort_id = str(config["cohort_id"])
    root = cohort_root(run_config_path)
    rows = [_row_report(root, row) for row in config["allowed_rows"]]
    counts = Counter(str(row["status"]) for row in rows)
    classifications = [
        str(row["final_classification"])
        for row in rows
        if row.get("final_classification") in FINAL_CLASSIFICATIONS
    ]
    valid_count = sum(item.startswith("valid +") for item in classifications)
    passed_count = classifications.count("valid + passed")
    final_count = len(classifications)
    failure_counts = Counter(
        str(row["failure_category"])
        for row in rows
        if row.get("final_classification") == "valid + failed"
    )
    valid_rows = [
        row for row in rows if str(row.get("final_classification", "")).startswith("valid +")
    ]
    t01 = next(row for row in rows if row["task_id"] == "T01")
    if t01.get("final_classification") == "invalid":
        g0_status = "failed"
    elif str(t01.get("final_classification", "")).startswith("valid +"):
        g0_status = "passed"
    else:
        g0_status = "pending"
    return {
        "schema_version": REPORT_SCHEMA,
        "cohort_id": cohort_id,
        "source": dict(config["source"]),
        "run_config": {
            "path": run_config_path.resolve().as_posix(),
            "sha256": run_config_path.with_name("run-config.sha256")
            .read_text(encoding="ascii")
            .strip(),
        },
        "profile": dict(config["profile"]["public_profile"]),
        "generator": dict(generator),
        "g0": {
            "status": g0_status,
            "rule": "T01 measurement valid under evidence protocol rules 1-5",
            "row_id": f"{cohort_id}-T01-r1",
        },
        "counts": {
            "planned": len(rows),
            "final_classified": final_count,
            "valid_passed": classifications.count("valid + passed"),
            "valid_failed": classifications.count("valid + failed"),
            "invalid": classifications.count("invalid"),
            "pending_audit": counts["pending audit"],
            "pending_decision": counts["pending decision"],
            "no_result": counts["no result"],
        },
        "metrics": {
            "valid_run_rate": _ratio(valid_count, final_count),
            "verified_run_success": _ratio(passed_count, valid_count),
            "failure_category_counts": dict(sorted(failure_counts.items())),
            "provider_requests": _provider_metrics(rows),
            "tool_steps": _numeric_metrics(valid_rows, "tool_steps"),
            "repeated_reads": _numeric_metrics(
                valid_rows, "repeated_reads", include_total=True
            ),
            "elapsed_time_ms": _numeric_metrics(valid_rows, "elapsed_time_ms"),
        },
        "rows": rows,
    }


def render_pilot_markdown(report: Mapping[str, Any]) -> str:
    counts = report["counts"]
    metrics = report["metrics"]
    lines = [
        "# Pico Evaluation v2 — P3 Pilot",
        "",
        f"- Cohort: `{report['cohort_id']}`",
        f"- Source: `{report['source']['commit']}`",
        f"- Run config SHA-256: `{report['run_config']['sha256']}`",
        f"- G0: **{report['g0']['status']}**",
        "",
        "## 结果",
        "",
        "| Row | Task | 状态 | 分类 | 原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        classification = row.get("final_classification") or "—"
        reason = str(row.get("reason") or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{row['row_id']}` | {row['task_id']} | {row['status']} "
            f"| {classification} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## 汇总",
            "",
            f"- Final classified: {counts['final_classified']}/{counts['planned']}",
            f"- Valid passed / failed / invalid: {counts['valid_passed']} / "
            f"{counts['valid_failed']} / {counts['invalid']}",
            f"- Pending audit / decision / no result: {counts['pending_audit']} / "
            f"{counts['pending_decision']} / {counts['no_result']}",
            f"- Valid-run rate: {_format_ratio(metrics['valid_run_rate'])}",
            f"- Verified-run success: {_format_ratio(metrics['verified_run_success'])}",
            f"- Provider requests: {metrics['provider_requests']['total']}",
            f"- Tool steps: {_format_numeric(metrics['tool_steps'])}",
            f"- Repeated reads: {_format_numeric(metrics['repeated_reads'])}",
            f"- Runtime elapsed: {_format_numeric(metrics['elapsed_time_ms'], ' ms')}",
            "",
            "## 证据",
            "",
            "每条结果的原始入口为 `public/rows/<row-id>/run-record.json`，"
            "`evidence-view.json` 和 `codex-audit.json`。聚合值只使用最终 valid 行；"
            "invalid 行的局部事实不进入产品聚合。",
            "",
        ]
    )
    return "\n".join(lines)


def _append_audit(
    root: Path, allowed: Mapping[str, Mapping[str, Any]], audit: Mapping[str, Any]
) -> None:
    row_id = str(audit.get("row_id", ""))
    if row_id not in allowed:
        raise ValueError(f"audit row is outside the frozen Pilot: {row_id}")
    public_row = root / "public" / "rows" / row_id
    _require_started_row(public_row)
    verify_checksums(public_row / "checksums.json", public_row)
    target = public_row / "codex-audit.json"
    if target.exists():
        raise ValueError(f"Codex audit already exists: {row_id}")
    _validate_audit(public_row, audit)
    write_json(target, dict(audit))
    _reseal(public_row)


def _append_decision(
    root: Path, allowed: Mapping[str, Mapping[str, Any]], decision: Mapping[str, Any]
) -> None:
    row_id = str(decision.get("row_id", ""))
    if row_id not in allowed:
        raise ValueError(f"user decision row is outside the frozen Pilot: {row_id}")
    public_row = root / "public" / "rows" / row_id
    _require_started_row(public_row)
    verify_checksums(public_row / "checksums.json", public_row)
    target = public_row / "user-decision.json"
    if target.exists():
        raise ValueError(f"user decision already exists: {row_id}")
    audit = _load_object(public_row / "codex-audit.json")
    if audit.get("user_decision") != "required":
        raise ValueError("user decision is only allowed when the Codex audit requires it")
    _validate_decision(public_row, decision)
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
    record = _load_object(public_row / "run-record.json")
    view = _optional_object(public_row / "evidence-view.json")
    facts = _row_facts(public_row, record, view)
    audit = _optional_object(public_row / "codex-audit.json")
    if not audit:
        return {**base, "status": "pending audit", "facts": facts}
    _validate_audit(public_row, audit)
    if audit["user_decision"] == "required":
        decision = _optional_object(public_row / "user-decision.json")
        if not decision:
            return {
                **base,
                "status": "pending decision",
                "reason": audit["reason"],
                "facts": facts,
            }
        _validate_decision(public_row, decision)
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
    public_row: Path, record: Mapping[str, Any], view: Mapping[str, Any]
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
        (row for row in reversed(trace) if row.get("event") == "run_finished"), {}
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


def _provider_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [
        row.get("facts", {}).get("provider_requests", {})
        for row in rows
        if row.get("status") != "no result"
    ]
    exact = [item for item in values if item.get("exact") is True and type(item.get("count")) is int]
    return {
        "available_samples": len(exact),
        "started_samples": len(values),
        "total": sum(int(item["count"]) for item in exact),
        "complete": len(exact) == len(values),
    }


def _numeric_metrics(
    rows: Sequence[Mapping[str, Any]], key: str, *, include_total: bool = False
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


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _format_ratio(value: Mapping[str, Any]) -> str:
    ratio = value.get("value")
    if ratio is None:
        return f"不可计算 ({value['numerator']}/{value['denominator']})"
    return f"{value['numerator']}/{value['denominator']} ({ratio:.2%})"


def _format_numeric(value: Mapping[str, Any], suffix: str = "") -> str:
    if value.get("mean") is None:
        return f"不可计算 (0/{value['valid_samples']} samples)"
    total = f", total={value['total']}{suffix}" if "total" in value else ""
    return (
        f"mean={value['mean']:.2f}{suffix}, median={value['median']:.2f}{suffix}"
        f"{total} ({value['available_samples']}/{value['valid_samples']} samples)"
    )


def _allowed_rows(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["row_id"]): row for row in config["allowed_rows"]}


def _require_started_row(public_row: Path) -> None:
    if not public_row.is_dir() or not (public_row / "run-record.json").is_file():
        raise ValueError(f"Pilot row has not started: {public_row.name}")


def _reseal(public_row: Path) -> None:
    write_json(public_row / "checksums.json", checksums(public_row))
    verify_checksums(public_row / "checksums.json", public_row)


def _first_object(root: Path, pattern: str) -> dict[str, Any]:
    path = next(iter(sorted(root.glob(pattern))), None) if root.exists() else None
    return _load_object(path) if path else {}


def _first_jsonl(root: Path, pattern: str) -> list[dict[str, Any]]:
    path = next(iter(sorted(root.glob(pattern))), None) if root.exists() else None
    if not path:
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


__all__ = [
    "AUDIT_SCHEMA",
    "DECISION_SCHEMA",
    "REPORT_JSON",
    "REPORT_MARKDOWN",
    "build_pilot_report",
    "finalize_pilot",
    "render_pilot_markdown",
    "verify_pilot",
]
