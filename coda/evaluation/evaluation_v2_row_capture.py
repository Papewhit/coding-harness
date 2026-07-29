"""One-row workspace capture and deterministic evidence finalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from coda.evaluation.evaluation_v2_config import canonical_json
from coda.evaluation.evaluation_v2_evidence import (
    build_evidence_view,
    checksums,
    scan_known_values,
    unified_diff,
    verify_checksums,
    workspace_files,
)
from coda.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    FailureOrigin,
    FailureStage,
    HttpAttempt,
    InfrastructureFailure,
    RunRequest,
    TaskSpec,
    client_failure_record_errors,
)
from coda.evaluation.live_utils import compare_manifests, workspace_manifest


COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".coda", ".pytest_cache", ".ruff_cache", "__pycache__", "*.pyc"
)


@dataclass(frozen=True)
class RowCapture:
    client_result: ClientResult
    verifier: Any
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    manifest_diff: Mapping[str, Any]
    before_files: Mapping[str, bytes]
    after_files: Mapping[str, bytes]
    copied: Mapping[str, Any]
    source_scan: Mapping[str, Any]


def capture_row(
    *,
    runner: Any,
    task: TaskSpec,
    request: RunRequest,
    client: Any,
    private_row: Path,
    public_row: Path,
    run_record_path: Path,
) -> tuple[RowCapture, Path]:
    """Run the client/verifier and copy evidence before workspace cleanup."""

    with tempfile.TemporaryDirectory(prefix=f"coda-eval-{request.row_id}-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(task.source_dir, workspace, ignore=COPY_IGNORE)
        before = workspace_manifest(workspace)
        before_files = workspace_files(workspace)
        update_record(run_record_path, {"phase": "client", "workspace_created": True})
        client_result = _run_client(client, workspace, task.prompt, run_record_path)
        update_record(
            run_record_path,
            {
                "client_result": client_result_dict(client_result),
                "provider_requests": {
                    "count": len(client_result.http_attempts),
                    "exact": client_result.http_attempts_exact,
                },
                "phase": "verifier",
            },
            request.sensitive_values,
        )
        after = workspace_manifest(workspace)
        after_files = workspace_files(workspace)
        manifest_diff = compare_manifests(before, after)
        verifier = _run_verifier(
            runner,
            task,
            workspace,
            public_row,
            request.sensitive_values,
        )
        update_record(run_record_path, {"phase": "evidence_copy"})
        source_scan = scan_known_values(workspace / ".coda", request.sensitive_values)
        copied = _copy_originals(
            workspace=workspace,
            private_row=private_row,
            public_row=public_row,
            client_result=client_result,
            blocked_paths=set(source_scan["hit_paths"]),
        )
        capture = RowCapture(
            client_result=client_result,
            verifier=verifier,
            before=before,
            after=after,
            manifest_diff=manifest_diff,
            before_files=before_files,
            after_files=after_files,
            copied=copied,
            source_scan=source_scan,
        )
    return capture, workspace


def finalize_row(
    *,
    capture: RowCapture,
    request: RunRequest,
    private_row: Path,
    public_row: Path,
    run_record_path: Path,
    measurement_errors: list[str],
) -> None:
    """Build and verify final artifacts after the temporary workspace is gone."""

    if not capture.source_scan["passed"]:
        measurement_errors.append("known sensitive value found in Coda original state")
    if not capture.client_result.http_attempts_exact:
        measurement_errors.append("provider request count is not exact")
    measurement_errors.extend(client_failure_record_errors(capture.client_result))
    if capture.client_result.failure_origin is FailureOrigin.CLIENT:
        measurement_errors.append(
            "client infrastructure failure prevents a product conclusion"
        )
    view = build_evidence_view(
        private_row=private_row,
        public_row=public_row,
        client_result=capture.client_result,
        verifier=capture.verifier,
        manifest_diff=capture.manifest_diff,
        unified_diff=unified_diff(capture.before_files, capture.after_files),
    )
    measurement_errors.extend(view["protocol_errors"])
    write_json(public_row / "evidence-view.json", view)
    persisted_scan = _scan_persisted(private_row, public_row, request.sensitive_values)
    if not persisted_scan["passed"]:
        measurement_errors.append("known sensitive value found in persisted row artifacts")
    update_record(
        run_record_path,
        {
            "phase": "complete",
            "finished_at": now(),
            "workspace_cleaned": True,
            "workspace_manifest": {
                "before": capture.before,
                "after": capture.after,
                "diff": capture.manifest_diff,
            },
            "credential_scan": {
                "source_originals": capture.source_scan,
                "persisted_artifacts": persisted_scan,
            },
            "evidence": capture.copied,
            "measurement_status": "invalid" if measurement_errors else "complete",
            "measurement_errors": sorted(set(measurement_errors)),
            "product_result": (
                "pending_audit"
                if measurement_errors
                or capture.client_result.failure_category is not FailureCategory.NONE
                else "passed"
                if capture.verifier.passed
                else "failed"
            ),
            "failure": _row_failure(capture, measurement_errors),
        },
        request.sensitive_values,
    )
    write_json(private_row / "checksums.json", checksums(private_row, "original"))
    write_json(public_row / "checksums.json", checksums(public_row))
    verify_checksums(private_row / "checksums.json", private_row)
    verify_checksums(public_row / "checksums.json", public_row)


def _row_failure(
    capture: RowCapture, measurement_errors: list[str]
) -> dict[str, Any] | None:
    result = capture.client_result
    common = {
        "provider_request_count": len(result.http_attempts),
        "provider_request_count_exact": result.http_attempts_exact,
    }
    if measurement_errors:
        return {
            "origin": "measurement",
            "stage": "evidence",
            "category": FailureCategory.MEASUREMENT.value,
            "error_type": "MeasurementError",
            "exit_code": result.exit_code,
            **common,
        }
    if result.failure_category is not FailureCategory.NONE:
        return {
            "origin": result.failure_origin.value,
            "stage": result.failure_stage.value,
            "category": result.failure_category.value,
            "error_type": result.error_type,
            "exit_code": result.exit_code,
            **common,
        }
    if not capture.verifier.passed:
        return {
            "origin": "verifier",
            "stage": "verifier",
            "category": FailureCategory.TASK.value,
            "error_type": "VerifierFailure",
            "exit_code": capture.verifier.returncode,
            **common,
        }
    return None


def _run_client(
    client: Any, workspace: Path, prompt: str, evidence_path: Path
) -> ClientResult:
    try:
        result = client.run(workspace, prompt, evidence_path=evidence_path)
    except TypeError as exc:
        if "evidence_path" not in str(exc):
            raise
        result = client.run(workspace, prompt)
    if not isinstance(result, ClientResult):
        raise InfrastructureFailure("client returned a non-ClientResult value")
    return result


def _run_verifier(
    runner: Any,
    task: TaskSpec,
    workspace: Path,
    public_row: Path,
    sensitive_values: tuple[str, ...],
) -> Any:
    verifier_dir = public_row / "verifier"
    verifier_dir.mkdir()
    write_json(
        verifier_dir / "invocation.json",
        {
            "verifier": task.verifier.as_posix(),
            "workspace_argument": "<temporary-workspace>",
            "expected_files_changed": list(task.expected_files_changed),
        },
    )
    try:
        result = runner._verify(task.verifier, workspace)
    except InfrastructureFailure as exc:
        from coda.evaluation.live_tasks import _VerifierResult

        result = _VerifierResult(
            passed=False,
            returncode=-1,
            duration_ms=0,
            output=str(exc),
            stderr=str(exc),
        )
    stdout = _redact_known(result.stdout, sensitive_values)
    stderr = _redact_known(result.stderr, sensitive_values)
    (verifier_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (verifier_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    write_json(
        verifier_dir / "result.json",
        {
            "passed": result.passed,
            "returncode": result.returncode,
            "duration_ms": result.duration_ms,
        },
    )
    return result


def _scan_persisted(
    private_row: Path,
    public_row: Path,
    sensitive_values: tuple[str, ...],
) -> dict[str, Any]:
    private = scan_known_values(private_row, sensitive_values)
    public = scan_known_values(public_row, sensitive_values)
    return {
        "passed": private["passed"] and public["passed"],
        "files_scanned": private["files_scanned"] + public["files_scanned"],
        "hit_paths": [
            *(f"private/{path}" for path in private["hit_paths"]),
            *(f"public/{path}" for path in public["hit_paths"]),
        ],
    }


def _copy_originals(
    *,
    workspace: Path,
    private_row: Path,
    public_row: Path,
    client_result: ClientResult,
    blocked_paths: set[str],
) -> dict[str, Any]:
    coda = workspace / ".coda"
    private_original = private_row / "original"
    public_original = public_row / "original"
    copied_private: list[str] = []
    copied_public: list[str] = []
    session_id = client_result.session_id
    run_id = client_result.runtime_run_id
    candidates = []
    if session_id:
        candidates.extend(
            [
                coda / "sessions" / f"{session_id}.json",
                coda / "sessions" / f"{session_id}.events.jsonl",
            ]
        )
    if run_id:
        run_root = coda / "runs" / run_id
        candidates.extend(
            run_root / name
            for name in ("task_state.json", "trace.jsonl", "report.json", "artifacts")
        )
    for source in candidates:
        if not source.exists():
            continue
        relative = source.relative_to(workspace).as_posix()
        if _is_blocked(relative, blocked_paths):
            continue
        destination = private_original / source.relative_to(workspace)
        _copy_path(source, destination)
        copied_private.append(relative)
    events = coda / "sessions" / f"{session_id}.events.jsonl"
    if session_id and events.is_file():
        relative = events.relative_to(workspace).as_posix()
        if not _is_blocked(relative, blocked_paths):
            _copy_path(events, public_original / events.relative_to(workspace))
            copied_public.append(relative)
    if run_id:
        for name in ("task_state.json", "trace.jsonl", "report.json"):
            source = coda / "runs" / run_id / name
            relative = source.relative_to(workspace).as_posix()
            if source.is_file() and not _is_blocked(relative, blocked_paths):
                _copy_path(source, public_original / source.relative_to(workspace))
                copied_public.append(relative)
    return {
        "private_originals": copied_private,
        "public_originals": copied_public,
    }


def _is_blocked(relative: str, blocked_paths: set[str]) -> bool:
    return any(
        hit == relative
        or hit.startswith(relative + "/")
        or relative.startswith(hit + "/")
        for hit in blocked_paths
    )


def client_result_dict(result: ClientResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["failure_category"] = result.failure_category.value
    payload["failure_origin"] = result.failure_origin.value
    payload["failure_stage"] = result.failure_stage.value
    payload["http_attempts"] = [attempt.as_dict() for attempt in result.http_attempts]
    return payload


def recover_client_result(record: Mapping[str, Any]) -> ClientResult:
    """Rebuild and validate the request-count facts already persisted by the client."""

    payload = record.get("client_result")
    if not isinstance(payload, Mapping):
        raise ValueError("run-record has no persisted client_result")
    raw_attempts = payload.get("http_attempts")
    if not isinstance(raw_attempts, list):
        raise ValueError("persisted client_result http_attempts must be a list")
    attempts = tuple(
        _recover_http_attempt(item, expected=index)
        for index, item in enumerate(raw_attempts, start=1)
    )
    exact = payload.get("http_attempts_exact")
    if type(exact) is not bool:
        raise ValueError("persisted request-count exactness flag is not boolean")
    category = FailureCategory(str(payload.get("failure_category", "none")))
    origin = FailureOrigin(str(payload.get("failure_origin", "none")))
    stage = FailureStage(str(payload.get("failure_stage", "none")))
    result = ClientResult(
        profile=dict(payload.get("profile", {})),
        native_gate_hash=str(payload.get("native_gate_hash", "")),
        call_ids=tuple(map(str, payload.get("call_ids", []))),
        result_call_ids=tuple(map(str, payload.get("result_call_ids", []))),
        http_attempts=attempts,
        trace=tuple(payload.get("trace", [])),
        sdk_retry_count=int(payload.get("sdk_retry_count", 0)),
        coda_retry_count=int(payload.get("coda_retry_count", 0)),
        protocol_errors=tuple(map(str, payload.get("protocol_errors", []))),
        error=str(payload.get("error", "")),
        error_type=str(payload.get("error_type", "")),
        failure_category=category,
        failure_origin=origin,
        failure_stage=stage,
        session_id=str(payload.get("session_id", "")),
        runtime_run_id=str(payload.get("runtime_run_id", "")),
        final_answer=str(payload.get("final_answer", "")),
        http_attempts_exact=exact,
        original_state_paths=tuple(map(str, payload.get("original_state_paths", []))),
        exit_code=(
            int(payload["exit_code"])
            if payload.get("exit_code") is not None
            else None
        ),
    )
    failure_errors = client_failure_record_errors(result)
    if failure_errors:
        raise ValueError(
            "persisted client failure record is invalid: "
            + "; ".join(failure_errors)
        )
    _validate_persisted_request_summary(record, result)
    return result


def _recover_http_attempt(value: Any, *, expected: int) -> HttpAttempt:
    if not isinstance(value, Mapping):
        raise ValueError("persisted HTTP attempt must be an object")
    attempt = value.get("attempt")
    duration = value.get("duration_ms", 0)
    status = value.get("status_code")
    if type(attempt) is not int or attempt != expected:
        raise ValueError("persisted HTTP attempts are not uniquely sequential")
    if type(duration) is not int or duration < 0:
        raise ValueError("persisted HTTP attempt duration is invalid")
    if status is not None and type(status) is not int:
        raise ValueError("persisted HTTP attempt status is invalid")
    return HttpAttempt(
        attempt=attempt,
        status_code=status,
        duration_ms=duration,
        error_type=str(value.get("error_type", "")),
    )


def _validate_persisted_request_summary(
    record: Mapping[str, Any],
    result: ClientResult,
) -> None:
    summary = record.get("provider_requests")
    if summary is None:
        return
    if not isinstance(summary, Mapping):
        raise ValueError("persisted provider request summary must be an object")
    if type(summary.get("count")) is not int or summary["count"] != len(
        result.http_attempts
    ):
        raise ValueError("persisted provider request count does not match attempts")
    if (
        type(summary.get("exact")) is not bool
        or summary["exact"] is not result.http_attempts_exact
    ):
        raise ValueError("persisted provider request exactness does not match")


def update_record(
    path: Path,
    updates: Mapping[str, Any],
    sensitive_values: tuple[str, ...] = (),
) -> None:
    payload = load_object(path)
    payload.update(updates)
    write_json(path, _redact_known(payload, sensitive_values))


def _redact_known(value: Any, sensitive_values: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        for sensitive in sensitive_values:
            if sensitive:
                value = value.replace(sensitive, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {str(key): _redact_known(item, sensitive_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_known(item, sensitive_values) for item in value]
    return value


def _copy_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json(dict(payload)))
    temporary.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "capture_row",
    "client_result_dict",
    "finalize_row",
    "load_object",
    "now",
    "recover_client_result",
    "update_record",
    "write_json",
]
