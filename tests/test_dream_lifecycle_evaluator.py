from __future__ import annotations

import copy
import json

import pytest

from coda.evaluation.contracts import ARTIFACT_CONTRACT_VERSION
from coda.evaluation.dream_lifecycle_eval import (
    DEFAULT_CASES_PATH,
    DreamLifecycleViolation,
    evaluate_dream_lifecycle,
    load_lifecycle_cases,
)


def test_offline_lifecycle_artifact_unifies_gate_lock_failure_and_scope_evidence() -> None:
    artifact = evaluate_dream_lifecycle()

    assert artifact["status"] == "passed"
    assert artifact["summary"] == {"cases": 8, "passed": 8, "failed": 0, "hard_failures": 0}
    assert {row["category"] for row in artifact["rows"]} == {
        "gate",
        "lock",
        "failure_isolation",
        "write_scope",
    }
    assert all(row["passed"] and not row["hard_failure"] for row in artifact["rows"])
    assert artifact["artifact_contract_version"] == ARTIFACT_CONTRACT_VERSION
    metadata = artifact["evaluation_metadata"]
    assert metadata["source"]["execution"] == "offline"
    assert metadata["profile"]["capabilities"] == {"native_tools": False, "online_model": False}
    assert metadata["native_protocol"]["http_attempts"] == 0
    assert metadata["native_protocol"]["native_tool_call_observed"] is False


def test_gate_rows_reuse_interval_and_session_count_behavior() -> None:
    rows = {row["id"]: row for row in evaluate_dream_lifecycle()["rows"]}

    assert rows["interval-gate"]["observation"] == {
        "should_run": False,
        "skip_reason": "interval_gate",
        "session_count": 3,
        "session_ids": ["session-1", "session-2", "session-3"],
        "current_session_excluded": True,
    }
    assert rows["session-count-gate"]["observation"]["skip_reason"] == "session_gate"
    assert rows["eligible-gate"]["observation"]["should_run"] is True


def test_lock_rows_distinguish_active_and_stale_holders() -> None:
    rows = {row["id"]: row for row in evaluate_dream_lifecycle()["rows"]}

    assert rows["active-lock"]["observation"] == {
        "acquired": False,
        "holder_replaced": False,
        "classified_stale": False,
    }
    assert rows["stale-lock"]["observation"] == {
        "acquired": True,
        "holder_replaced": True,
        "classified_stale": True,
    }


def test_failure_row_proves_dream_failure_does_not_replace_primary_result() -> None:
    row = next(row for row in evaluate_dream_lifecycle()["rows"] if row["id"] == "dream-failure-isolated")

    assert row["observation"] == {
        "primary_result_preserved": True,
        "dream_status": "failed",
        "error_recorded": True,
    }
    assert "tests/test_coda.py::test_background_auto_dream_failure_restores_lock_and_reports_error" in row[
        "evidence_sources"
    ]


def test_denied_out_of_scope_attempt_is_recorded_without_a_write() -> None:
    row = next(row for row in evaluate_dream_lifecycle()["rows"] if row["id"] == "outside-write-denied")

    assert row["observation"]["outside_attempts_denied"] is True
    assert row["observation"]["changed_paths"] == []
    assert row["observation"]["outside_changes"] == []


def test_out_of_scope_change_is_a_hard_failure_with_artifact(tmp_path) -> None:
    suite = copy.deepcopy(load_lifecycle_cases())
    case = next(case for case in suite["cases"] if case["id"] == "memory-write-contained")
    case["evidence"]["changed_paths"].append("README.md")
    path = tmp_path / "lifecycle.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(DreamLifecycleViolation, match="memory-write-contained") as captured:
        evaluate_dream_lifecycle(path)

    artifact = captured.value.artifact
    row = next(row for row in artifact["rows"] if row["id"] == "memory-write-contained")
    assert artifact["status"] == "failed"
    assert artifact["summary"]["hard_failures"] == 1
    assert row["hard_failure"] is True
    assert row["observation"]["outside_changes"] == ["README.md"]


def test_scope_normalization_catches_parent_traversal(tmp_path) -> None:
    suite = copy.deepcopy(load_lifecycle_cases())
    case = next(case for case in suite["cases"] if case["id"] == "memory-write-contained")
    case["evidence"]["changed_paths"] = [".coda/memory/../../README.md"]
    path = tmp_path / "lifecycle.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(DreamLifecycleViolation):
        evaluate_dream_lifecycle(path)


def test_committed_case_file_is_valid_and_has_unique_ids() -> None:
    suite = load_lifecycle_cases(DEFAULT_CASES_PATH)

    assert suite["write_scope"] == ".coda/memory"
    assert len({case["id"] for case in suite["cases"]}) == len(suite["cases"])
