"""Finalize and verify Evaluation v2 Pilot audits and reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pico.evaluation.coding_report import (
    append_coding_inputs,
    build_coding_rows,
    coding_numeric_metrics,
    coding_provider_metrics,
    coding_ratio,
    cohort_root,
    verify_coding_rows,
)
from pico.evaluation.evaluation_v2_config import canonical_json, verify_run_config
from pico.evaluation.evaluation_v2_schedule import PILOT_COHORTS
from pico.evaluation.evaluation_v2_row_capture import write_json
from pico.evaluation.pilot_audit import (
    AUDIT_SCHEMA,
    DECISION_SCHEMA,
    FINAL_CLASSIFICATIONS,
    load_object as _load_object,
    optional_object as _optional_object,
)


REPORT_SCHEMA = "pico-evaluation-v2-pilot-report-v1"
REPORT_JSON = Path("reports/pilot-report.json")
REPORT_MARKDOWN = Path("reports/pilot-report.md")


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
    append_coding_inputs(
        root,
        config,
        audit_inputs=audit_inputs,
        decision_inputs=decision_inputs,
        sensitive_values=sensitive_values,
    )
    return _write_pilot_report(
        run_config_path,
        generator=generator,
    )


def initialize_pilot(
    run_config_path: Path,
    *,
    generator: Mapping[str, Any],
) -> dict[str, Any]:
    """Write a deterministic report even when no Pilot row was created."""

    verified_config(run_config_path)
    return _write_pilot_report(
        run_config_path,
        generator=generator,
    )


def _write_pilot_report(
    run_config_path: Path,
    *,
    generator: Mapping[str, Any],
) -> dict[str, Any]:
    root = cohort_root(run_config_path)
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
    verify_coding_rows(root, config)
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
    rows = build_coding_rows(root, config)
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
            "valid_run_rate": coding_ratio(valid_count, final_count),
            "verified_run_success": coding_ratio(passed_count, valid_count),
            "failure_category_counts": dict(sorted(failure_counts.items())),
            "provider_requests": coding_provider_metrics(rows),
            "tool_steps": coding_numeric_metrics(valid_rows, "tool_steps"),
            "repeated_reads": coding_numeric_metrics(
                valid_rows, "repeated_reads", include_total=True
            ),
            "elapsed_time_ms": coding_numeric_metrics(
                valid_rows,
                "elapsed_time_ms",
            ),
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
