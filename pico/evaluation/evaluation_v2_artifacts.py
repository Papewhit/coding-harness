"""Protocol-shaped row capture for Evaluation v2 coding tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pico.evaluation.evaluation_v2_evidence import (
    EVIDENCE_VIEW_SCHEMA,
    checksums,
)
from pico.evaluation.evaluation_v2_row_capture import (
    capture_row,
    finalize_row,
    load_object,
    now,
    recover_client_result,
    update_record,
    write_json,
)
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    InfrastructureFailure,
    RunEvidence,
    RunRequest,
    TaskSpec,
    _native_evidence,
    resolve_failure_category,
)


RUN_RECORD_SCHEMA = "pico-evaluation-v2-run-record-v1"


def run_evaluation_v2_row(
    runner: Any,
    task: TaskSpec,
    request: RunRequest,
    client: Any,
) -> RunEvidence:
    """Run one immutable-identity row while preserving partial evidence."""

    root = runner.output_root.resolve()
    private_row = root / "private" / "rows" / request.row_id
    public_row = root / "public" / "rows" / request.row_id
    if private_row.exists() or public_row.exists():
        raise InfrastructureFailure(f"row directory already exists: {request.row_id}")
    private_row.mkdir(parents=True)
    public_row.mkdir(parents=True)
    run_record_path = public_row / "run-record.json"
    record = _initial_record(task, request)
    write_json(run_record_path, record)

    client_result = ClientResult(
        profile={},
        native_gate_hash="",
        http_attempts_exact=False,
    )
    verifier = None
    workspace_path = Path()
    measurement_errors: list[str] = []
    try:
        capture, workspace_path = capture_row(
            runner=runner,
            task=task,
            request=request,
            client=client,
            private_row=private_row,
            public_row=public_row,
            run_record_path=run_record_path,
        )
        client_result = capture.client_result
        verifier = capture.verifier
        finalize_row(
            capture=capture,
            request=request,
            private_row=private_row,
            public_row=public_row,
            run_record_path=run_record_path,
            measurement_errors=measurement_errors,
        )
    except Exception as exc:
        client_result = _preserve_failed_row(
            exc=exc,
            client_result=client_result,
            measurement_errors=measurement_errors,
            request=request,
            private_row=private_row,
            public_row=public_row,
            run_record_path=run_record_path,
        )

    protocol = _native_evidence(client_result)
    failure = resolve_failure_category(
        measurement_errors=measurement_errors,
        client_result=client_result,
        protocol_errors=protocol["protocol_errors"],
        verifier_passed=verifier.passed if verifier is not None else None,
    )
    status = "passed" if failure is FailureCategory.NONE else "failed"
    artifact = load_object(run_record_path)
    return RunEvidence(
        task_id=task.task_id,
        repo_id=task.repo_id,
        run_kind=request.run_kind,
        shard=request.shard,
        run_id=request.row_id,
        status=status,
        failure_category=failure.value,
        workspace=workspace_path,
        artifact=artifact,
    )


def _preserve_failed_row(
    *,
    exc: Exception,
    client_result: ClientResult,
    measurement_errors: list[str],
    request: RunRequest,
    private_row: Path,
    public_row: Path,
    run_record_path: Path,
) -> ClientResult:
    measurement_errors.append(f"{type(exc).__name__}: {exc}")
    current = load_object(run_record_path)
    recovery_status = "unavailable"
    try:
        client_result = recover_client_result(current)
        recovery_status = "validated"
    except (TypeError, ValueError) as recovery_error:
        measurement_errors.append(
            f"persisted client result recovery failed: {recovery_error}"
        )
    update_record(
        run_record_path,
        {
            "phase": "failed",
            "finished_at": now(),
            "measurement_status": "invalid",
            "measurement_errors": sorted(set(measurement_errors)),
            "failure_type": type(exc).__name__,
            "failure": {
                "stage": current.get("phase", "unknown"),
                "exit_code": client_result.exit_code,
                "provider_request_count": len(client_result.http_attempts),
                "provider_request_count_exact": client_result.http_attempts_exact,
                "client_result_recovery": recovery_status,
            },
        },
        request.sensitive_values,
    )
    if private_row.exists() and not (private_row / "checksums.json").exists():
        write_json(private_row / "checksums.json", checksums(private_row, "original"))
    write_json(public_row / "checksums.json", checksums(public_row))
    return client_result


def _initial_record(task: TaskSpec, request: RunRequest) -> dict[str, Any]:
    return {
        "schema_version": RUN_RECORD_SCHEMA,
        "row": {
            "row_id": request.row_id,
            "cohort_id": request.cohort_id,
            "task_id": task.task_id,
            "repo_id": task.repo_id,
            "repetition": request.repetition,
            "stage": request.stage,
        },
        "source": {"commit": request.source_commit, "tree": request.source_tree},
        "run_config": {
            "path": request.run_config_path.as_posix() if request.run_config_path else "",
            "sha256": (
                request.run_config_path.with_name("run-config.sha256")
                .read_text(encoding="ascii")
                .strip()
                if request.run_config_path
                else ""
            ),
        },
        "started_at": now(),
        "finished_at": None,
        "phase": "initialized",
        "workspace_created": False,
        "measurement_status": "running",
        "measurement_errors": [],
        "product_result": "pending_audit",
    }


__all__ = ["EVIDENCE_VIEW_SCHEMA", "RUN_RECORD_SCHEMA", "run_evaluation_v2_row"]
