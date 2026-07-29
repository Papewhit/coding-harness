"""Finalize and summarize Evaluation v2 baseline coding rows."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from coda.evaluation.coding_report import (
    append_coding_inputs,
    build_coding_rows,
    coding_numeric_metrics,
    coding_provider_metrics,
    coding_ratio,
    cohort_root,
    verify_coding_rows,
)
from coda.evaluation.evaluation_v2_config import verify_run_config
from coda.evaluation.pilot_audit import FINAL_CLASSIFICATIONS, load_object


SUMMARY_SCHEMA = "coda-evaluation-v2-baseline-summary-v1"
BASELINE_COHORT = "baseline-v1"
STAGE_TASKS = {
    "P4A": ("T01", "T02", "T03"),
    "P4B": ("T04", "T05", "T06"),
    "P4C": ("T07", "T08", "T09"),
}
STAGE_REPOSITORIES = {
    "P4A": "tinyconfig",
    "P4B": "miniqueue",
    "P4C": "logslice",
}


def verified_baseline_config(run_config_path: Path) -> dict[str, Any]:
    payload = load_object(run_config_path)
    verify_run_config(run_config_path)
    if payload.get("cohort_id") != BASELINE_COHORT:
        raise ValueError("baseline summary requires a baseline-v1 run config")
    return payload


def finalize_baseline(
    run_config_path: Path,
    *,
    stage: str,
    audit_inputs: Sequence[Path] = (),
    decision_inputs: Sequence[Path] = (),
    sensitive_values: Sequence[str] = (),
) -> dict[str, Any]:
    config = verified_baseline_config(run_config_path)
    root = cohort_root(run_config_path)
    append_coding_inputs(
        root,
        config,
        audit_inputs=audit_inputs,
        decision_inputs=decision_inputs,
        sensitive_values=sensitive_values,
    )
    return verify_baseline(run_config_path, stage=stage)


def verify_baseline(run_config_path: Path, *, stage: str) -> dict[str, Any]:
    config = verified_baseline_config(run_config_path)
    root = cohort_root(run_config_path)
    verify_coding_rows(root, config)
    return build_baseline_summary(run_config_path, stage=stage)


def build_baseline_summary(
    run_config_path: Path,
    *,
    stage: str,
) -> dict[str, Any]:
    if stage not in STAGE_TASKS:
        raise ValueError(f"unsupported P4 stage: {stage}")
    config = verified_baseline_config(run_config_path)
    root = cohort_root(run_config_path)
    rows = build_coding_rows(root, config)
    selected_tasks = STAGE_TASKS[stage]
    stage_rows = [row for row in rows if row["task_id"] in selected_tasks]
    cohort = summarize_coding_rows(rows)
    return {
        "schema_version": SUMMARY_SCHEMA,
        "cohort_id": BASELINE_COHORT,
        "source": dict(config["source"]),
        "run_config": {
            "path": run_config_path.resolve().as_posix(),
            "sha256": run_config_path.with_name("run-config.sha256")
            .read_text(encoding="ascii")
            .strip(),
        },
        "stage": {
            "id": stage,
            "repository": STAGE_REPOSITORIES[stage],
            "task_ids": list(selected_tasks),
            **summarize_coding_rows(stage_rows),
        },
        "cohort": cohort,
        "g1": {
            "status": (
                "passed"
                if cohort["counts"]["final_classified"]
                == cohort["counts"]["planned"]
                else "pending"
            ),
            "final_classified": cohort["counts"]["final_classified"],
            "planned": cohort["counts"]["planned"],
        },
    }


def summarize_coding_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate one coding-row scope using the Evaluation v2 metric contract."""

    counts = Counter(str(row["status"]) for row in rows)
    classifications = [
        str(row["final_classification"])
        for row in rows
        if row.get("final_classification") in FINAL_CLASSIFICATIONS
    ]
    final_count = len(classifications)
    valid_rows = [
        row
        for row in rows
        if str(row.get("final_classification", "")).startswith("valid +")
    ]
    valid_count = len(valid_rows)
    passed_count = classifications.count("valid + passed")
    failure_counts = Counter(
        str(row["failure_category"])
        for row in rows
        if row.get("final_classification") == "valid + failed"
    )
    task_ids = sorted({str(row["task_id"]) for row in rows})
    return {
        "counts": {
            "planned": len(rows),
            "started": len(rows) - counts["no result"],
            "final_classified": final_count,
            "valid_passed": passed_count,
            "valid_failed": classifications.count("valid + failed"),
            "invalid": classifications.count("invalid"),
            "pending_audit": counts["pending audit"],
            "pending_decision": counts["pending decision"],
            "no_result": counts["no result"],
        },
        "metrics": {
            "valid_run_rate": coding_ratio(valid_count, final_count),
            "verified_run_success": coding_ratio(passed_count, valid_count),
            "stable_task_status": {
                task_id: _stable_task_status(rows, task_id)
                for task_id in task_ids
            },
            "failure_category_counts": dict(sorted(failure_counts.items())),
            "provider_requests": coding_provider_metrics(rows),
            "tool_steps": coding_numeric_metrics(valid_rows, "tool_steps"),
            "repeated_reads": coding_numeric_metrics(
                valid_rows,
                "repeated_reads",
                include_total=True,
            ),
            "elapsed_time_ms": coding_numeric_metrics(
                valid_rows,
                "elapsed_time_ms",
            ),
        },
        "rows": list(rows),
    }


def _stable_task_status(
    rows: Sequence[Mapping[str, Any]],
    task_id: str,
) -> str:
    task_rows = [row for row in rows if row["task_id"] == task_id]
    classifications = [
        str(row.get("final_classification", ""))
        for row in task_rows
    ]
    if len(classifications) != 3 or any(
        value not in {"valid + passed", "valid + failed"}
        for value in classifications
    ):
        return "insufficient-evidence"
    if all(value == "valid + passed" for value in classifications):
        return "stable-pass"
    if all(value == "valid + failed" for value in classifications):
        return "stable-fail"
    return "mixed-valid"


__all__ = [
    "BASELINE_COHORT",
    "STAGE_REPOSITORIES",
    "STAGE_TASKS",
    "SUMMARY_SCHEMA",
    "build_baseline_summary",
    "finalize_baseline",
    "summarize_coding_rows",
    "verified_baseline_config",
    "verify_baseline",
]
