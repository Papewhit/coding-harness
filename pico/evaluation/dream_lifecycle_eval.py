"""Deterministic, offline evidence for the automatic Dream lifecycle.

The evaluator exercises the existing gate and lock helpers in temporary
directories.  Failure isolation and write-scope cases consume persisted-style
observations so they can be audited without invoking a model or changing the
runtime's asynchronous and permission behavior.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import time
from typing import Any, Mapping

from pico.evaluation.contracts import extend_artifact_contract, native_protocol_metadata
from pico.features.memory_durable import (
    HOLDER_STALE_S,
    LOCK_FILE_NAME,
    ensure_memory_dir,
    evaluate_auto_dream_gate,
    try_acquire_lock,
)


SCHEMA_VERSION = "pico-dream-lifecycle-evaluation-v1"
DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "v3" / "auto-dream" / "lifecycle.json"


class DreamLifecycleViolation(RuntimeError):
    """Raised when lifecycle evidence contains a hard safety failure."""

    def __init__(self, artifact: dict[str, Any]):
        self.artifact = artifact
        failures = [row["id"] for row in artifact["rows"] if row["hard_failure"]]
        super().__init__(f"Dream lifecycle hard failure: {', '.join(failures)}")


def load_lifecycle_cases(path: str | Path = DEFAULT_CASES_PATH) -> dict[str, Any]:
    """Load and minimally validate the frozen offline lifecycle cases."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported Dream lifecycle schema: {payload.get('schema_version')!r}")
    if not isinstance(payload.get("cases"), list) or not payload["cases"]:
        raise ValueError("Dream lifecycle cases must be a non-empty list")
    identifiers = [case.get("id") for case in payload["cases"] if isinstance(case, Mapping)]
    if len(identifiers) != len(payload["cases"]) or any(not isinstance(item, str) or not item for item in identifiers):
        raise ValueError("every Dream lifecycle case must have a non-empty string id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Dream lifecycle case ids must be unique")
    return payload


def evaluate_dream_lifecycle(
    path: str | Path = DEFAULT_CASES_PATH,
    *,
    fail_on_violation: bool = True,
) -> dict[str, Any]:
    """Evaluate all cases and return one artifact containing auditable rows.

    No provider or Pico runtime is instantiated.  A hard failure is retained in
    the returned artifact attached to :class:`DreamLifecycleViolation`.
    """

    cases_path = Path(path)
    suite = load_lifecycle_cases(cases_path)
    rows: list[dict[str, Any]] = []
    for case in suite["cases"]:
        category = case.get("category")
        if category == "gate":
            row = _evaluate_gate(case)
        elif category == "lock":
            row = _evaluate_lock(case)
        elif category == "failure_isolation":
            row = _evaluate_failure_isolation(case)
        elif category == "write_scope":
            row = _evaluate_write_scope(case, str(suite.get("write_scope", ".pico/memory")))
        else:
            raise ValueError(f"unsupported Dream lifecycle category: {category!r}")
        rows.append(row)

    hard_failures = sum(1 for row in rows if row["hard_failure"])
    passed = sum(1 for row in rows if row["passed"])
    legacy_artifact = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if hard_failures == 0 and passed == len(rows) else "failed",
        "summary": {
            "cases": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "hard_failures": hard_failures,
        },
        "rows": rows,
    }
    artifact = extend_artifact_contract(
        legacy_artifact,
        source={
            "taskset": _taskset_identity(cases_path),
            "taskset_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
            "execution": "offline",
        },
        profile={
            "provider": "none",
            "model": "none",
            "wire_dialect": "none",
            "adapter_mode": "offline-deterministic",
            "sdk": {"package": "", "version": ""},
            "base_url_fingerprint": "",
            "capabilities": {"native_tools": False, "online_model": False},
            "retry": {"sdk_max_retries": 0, "pico_attempts": 0},
        },
        native_protocol=native_protocol_metadata(
            eligible=False,
            native_tool_call_observed=False,
        ),
    )
    if hard_failures and fail_on_violation:
        raise DreamLifecycleViolation(artifact)
    return artifact


def _evaluate_gate(case: Mapping[str, Any]) -> dict[str, Any]:
    setup = _mapping(case, "setup")
    expected = _mapping(case, "expected")
    with tempfile.TemporaryDirectory(prefix="pico-dream-gate-") as raw_root:
        root = Path(raw_root)
        memory_dir = root / ".pico" / "memory"
        sessions_dir = root / ".pico" / "sessions"
        ensure_memory_dir(memory_dir)
        sessions_dir.mkdir(parents=True)
        now = time.time()
        age_hours = float(setup["last_consolidated_age_hours"])
        lock_path = memory_dir / LOCK_FILE_NAME
        lock_path.write_text("released", encoding="utf-8")
        consolidated_at = now - age_hours * 3600
        os.utime(lock_path, (consolidated_at, consolidated_at))
        session_ids = [f"session-{index + 1}" for index in range(int(setup["session_count"]))]
        for session_id in [*session_ids, "current-session"]:
            session_path = sessions_dir / f"{session_id}.json"
            session_path.write_text("{}", encoding="utf-8")
            os.utime(session_path, (now - 1, now - 1))
        observation = evaluate_auto_dream_gate(
            memory_dir,
            min_hours=float(setup["min_hours"]),
            min_sessions=int(setup["min_sessions"]),
            current_session_id="current-session",
            sessions_dir=sessions_dir,
        )
    stable_observation = {
        "should_run": observation["should_run"],
        "skip_reason": observation["skip_reason"],
        "session_count": observation["session_count"],
        "session_ids": observation["session_ids"],
        "current_session_excluded": "current-session" not in observation["session_ids"],
    }
    passed = all(stable_observation.get(key) == value for key, value in expected.items())
    return _row(case, stable_observation, expected, passed, hard_failure=not passed)


def _evaluate_lock(case: Mapping[str, Any]) -> dict[str, Any]:
    setup = _mapping(case, "setup")
    expected = _mapping(case, "expected")
    with tempfile.TemporaryDirectory(prefix="pico-dream-lock-") as raw_root:
        memory_dir = Path(raw_root) / ".pico" / "memory"
        ensure_memory_dir(memory_dir)
        lock_path = memory_dir / LOCK_FILE_NAME
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        age_seconds = float(setup["age_seconds"])
        lock_time = time.time() - age_seconds
        os.utime(lock_path, (lock_time, lock_time))
        acquired = try_acquire_lock(memory_dir)
        holder_replaced = lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()) and acquired
    observation = {
        "acquired": acquired,
        "holder_replaced": holder_replaced,
        "classified_stale": age_seconds >= HOLDER_STALE_S,
    }
    passed = all(observation.get(key) == value for key, value in expected.items())
    return _row(case, observation, expected, passed, hard_failure=not passed)


def _evaluate_failure_isolation(case: Mapping[str, Any]) -> dict[str, Any]:
    evidence = _mapping(case, "evidence")
    expected = _mapping(case, "expected")
    errors = evidence.get("errors")
    observation = {
        "primary_result_preserved": evidence.get("primary_result_before") == evidence.get("primary_result_after"),
        "dream_status": evidence.get("dream_status"),
        "error_recorded": isinstance(errors, list) and bool(errors),
    }
    passed = all(observation.get(key) == value for key, value in expected.items())
    return _row(case, observation, expected, passed, hard_failure=not passed)


def _evaluate_write_scope(case: Mapping[str, Any], raw_scope: str) -> dict[str, Any]:
    evidence = _mapping(case, "evidence")
    expected = _mapping(case, "expected")
    scope = _normalize_workspace_path(raw_scope)
    attempted = _string_list(evidence, "attempted_paths")
    denied = _string_list(evidence, "denied_paths")
    changed = _string_list(evidence, "changed_paths")
    outside_attempts = [path for path in attempted if not _within_scope(path, scope)]
    outside_changes = [path for path in changed if not _within_scope(path, scope)]
    undenied_outside_attempts = [path for path in outside_attempts if not _path_in(path, denied)]
    observation = {
        "scope": scope,
        "changed_paths": changed,
        "outside_changes": outside_changes,
        "outside_attempts_denied": not undenied_outside_attempts,
    }
    passed = not outside_changes and not undenied_outside_attempts
    passed = passed and all(observation.get(key) == value for key, value in expected.items())
    return _row(case, observation, expected, passed, hard_failure=not passed)


def _within_scope(raw_path: str, scope: str) -> bool:
    try:
        path = _normalize_workspace_path(raw_path)
    except ValueError:
        return False
    return path == scope or path.startswith(f"{scope}/")


def _path_in(raw_path: str, candidates: list[str]) -> bool:
    try:
        normalized = _normalize_workspace_path(raw_path)
    except ValueError:
        normalized = raw_path.replace("\\", "/")
    for candidate in candidates:
        try:
            candidate_normalized = _normalize_workspace_path(candidate)
        except ValueError:
            candidate_normalized = candidate.replace("\\", "/")
        if normalized == candidate_normalized:
            return True
    return False


def _normalize_workspace_path(raw_path: str) -> str:
    value = str(raw_path).replace("\\", "/")
    candidate = PurePosixPath(value)
    has_drive_prefix = bool(candidate.parts) and ":" in candidate.parts[0]
    if candidate.is_absolute() or has_drive_prefix:
        raise ValueError(f"path must be workspace-relative: {raw_path!r}")
    parts: list[str] = []
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"path escapes workspace: {raw_path!r}")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("path must not resolve to workspace root")
    return "/".join(parts)


def _taskset_identity(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix()
    except ValueError:
        return path.name


def _mapping(case: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = case.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"case {case.get('id')!r} field {field!r} must be a mapping")
    return value


def _string_list(evidence: Mapping[str, Any], field: str) -> list[str]:
    value = evidence.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"write-scope evidence {field!r} must be a list of strings")
    return [item.replace("\\", "/") for item in value]


def _row(
    case: Mapping[str, Any],
    observation: Mapping[str, Any],
    expected: Mapping[str, Any],
    passed: bool,
    *,
    hard_failure: bool,
) -> dict[str, Any]:
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "hard_failure": hard_failure,
        "observation": dict(observation),
        "expected": dict(expected),
        "evidence_sources": list(case.get("evidence_sources", [])),
    }
