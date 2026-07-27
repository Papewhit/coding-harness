"""Isolated local coding-task runner with auditable native-tool evidence.

The task client receives only a freshly copied public workspace and the task
prompt. Hidden verification remains outside that workspace and runs only after
the client returns. This module contains no provider SDK or Pico Runtime
wiring; callers adapt either a synthetic client or a native client at the
transport boundary.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Mapping, Protocol, Sequence
from uuid import uuid4

from pico.evaluation.contracts import (
    ARTIFACT_CONTRACT_VERSION,
    extend_artifact_contract,
    native_protocol_metadata,
    sanitize_public_artifact,
)
from pico.evaluation.live_utils import (
    compare_manifests,
    sanitize_trace,
    workspace_manifest,
)


FORMAL_RUN_KIND = "formal"
SUPPORTED_RUN_KINDS = frozenset({"synthetic", "probe", FORMAL_RUN_KIND})


class FailureCategory(str, Enum):
    """Stable failure taxonomy used by later aggregation tickets."""

    NONE = "none"
    TASK = "task"
    PROVIDER = "provider"
    PROTOCOL = "protocol"
    INFRASTRUCTURE = "infrastructure"
    MEASUREMENT = "measurement"


class LiveTaskError(RuntimeError):
    category = FailureCategory.INFRASTRUCTURE


class ProviderFailure(LiveTaskError):
    category = FailureCategory.PROVIDER


class ProtocolFailure(LiveTaskError):
    category = FailureCategory.PROTOCOL


class InfrastructureFailure(LiveTaskError):
    category = FailureCategory.INFRASTRUCTURE


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    repo_id: str
    prompt: str
    source_dir: Path
    verifier: Path
    run_kinds: tuple[str, ...] = ("synthetic", "probe", FORMAL_RUN_KIND)
    shard: str = "default"
    reference_paths: tuple[Path, ...] = ()
    expected_files_changed: tuple[str, ...] = ()
    network_access: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, base_dir: Path) -> "TaskSpec":
        def resolved(name: str) -> Path:
            raw = Path(str(value[name]))
            return (base_dir / raw).resolve() if not raw.is_absolute() else raw.resolve()

        references = tuple(
            (base_dir / Path(str(path))).resolve()
            if not Path(str(path)).is_absolute()
            else Path(str(path)).resolve()
            for path in value.get("reference_paths", [])
        )
        run_kinds = tuple(str(kind) for kind in value.get("run_kinds", SUPPORTED_RUN_KINDS))
        return cls(
            task_id=str(value["task_id"]),
            repo_id=str(value["repo_id"]),
            prompt=str(value["prompt"]),
            source_dir=resolved("source_dir"),
            verifier=resolved("verifier"),
            run_kinds=run_kinds,
            shard=str(value.get("shard", "default")),
            reference_paths=references,
            expected_files_changed=tuple(
                str(path) for path in value.get("expected_files_changed", [])
            ),
            network_access=bool(value.get("network_access", False)),
        )


@dataclass(frozen=True)
class HttpAttempt:
    attempt: int
    status_code: int | None = None
    duration_ms: int = 0
    error_type: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "error_type": self.error_type,
        }


@dataclass(frozen=True)
class ClientResult:
    """Provider-neutral observations returned by a live or synthetic client."""

    profile: Mapping[str, Any]
    native_gate_hash: str
    call_ids: tuple[str, ...] = ()
    result_call_ids: tuple[str, ...] = ()
    http_attempts: tuple[HttpAttempt, ...] = ()
    trace: tuple[Mapping[str, Any], ...] = ()
    sdk_retry_count: int = 0
    pico_retry_count: int = 0
    protocol_errors: tuple[str, ...] = ()
    error: str = ""
    failure_category: FailureCategory = FailureCategory.NONE
    session_id: str = ""
    runtime_run_id: str = ""
    final_answer: str = ""
    http_attempts_exact: bool = True
    original_state_paths: tuple[str, ...] = ()
    exit_code: int | None = None


class LiveTaskClient(Protocol):
    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        """Run the task without receiving verifier or reference paths."""


@dataclass(frozen=True)
class RunRequest:
    run_kind: str
    shard: str
    tool_050_s_hash: str = ""
    run_id: str = ""
    cohort_id: str = ""
    row_id: str = ""
    source_commit: str = ""
    source_tree: str = ""
    repetition: int = 1
    stage: str = ""
    run_config_path: Path | None = None
    sensitive_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunEvidence:
    task_id: str
    repo_id: str
    run_kind: str
    shard: str
    run_id: str
    status: str
    failure_category: str
    workspace: Path
    artifact: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.artifact)


@dataclass(frozen=True)
class _VerifierResult:
    passed: bool
    returncode: int
    duration_ms: int
    output: str
    stdout: str = ""
    stderr: str = ""


@dataclass
class LocalLiveTaskRunner:
    output_root: Path
    verifier_timeout_seconds: float = 30.0
    verifier_environment: Mapping[str, str] = field(default_factory=dict)

    def run(self, task: TaskSpec, request: RunRequest, client: LiveTaskClient) -> RunEvidence:
        if request.cohort_id:
            from pico.evaluation.evaluation_v2_artifacts import run_evaluation_v2_row

            return run_evaluation_v2_row(self, task, request, client)
        return self._run_legacy(task, request, client)

    def _run_legacy(
        self, task: TaskSpec, request: RunRequest, client: LiveTaskClient
    ) -> RunEvidence:
        self._validate(task, request)
        run_id = request.run_id or _new_run_id(task.task_id)
        run_dir = self.output_root.resolve() / request.run_kind / request.shard / run_id
        workspace = run_dir / "workspace"
        if run_dir.exists():
            raise InfrastructureFailure(f"run directory already exists: {run_dir}")

        run_dir.mkdir(parents=True)
        try:
            shutil.copytree(task.source_dir, workspace)
            before = workspace_manifest(workspace)
            started = time.monotonic()
            try:
                client_result = client.run(workspace, task.prompt)
            except LiveTaskError as exc:
                client_result = ClientResult(
                    profile={},
                    native_gate_hash="",
                    protocol_errors=(str(exc),) if exc.category is FailureCategory.PROTOCOL else (),
                    error=str(exc),
                    failure_category=exc.category,
                )
            client_duration_ms = int((time.monotonic() - started) * 1000)
            after = workspace_manifest(workspace)
            manifest_diff = compare_manifests(before, after)
            protocol = _native_evidence(client_result)
            protocol_failure = bool(protocol["protocol_errors"])
            failure = client_result.failure_category
            try:
                verifier_result = self._verify(task.verifier, workspace)
            except InfrastructureFailure as exc:
                verifier_result = _VerifierResult(
                    passed=False,
                    returncode=-1,
                    duration_ms=0,
                    output=str(exc),
                    stderr=str(exc),
                )
                if failure is FailureCategory.NONE:
                    failure = FailureCategory.INFRASTRUCTURE
            if failure is FailureCategory.NONE and protocol_failure:
                failure = FailureCategory.PROTOCOL
            if failure is FailureCategory.NONE and not verifier_result.passed:
                failure = FailureCategory.TASK
            status = "passed" if failure is FailureCategory.NONE else "failed"
            legacy = {
                "task_id": task.task_id,
                "repo_id": task.repo_id,
                "run_kind": request.run_kind,
                "shard": request.shard,
                "run_id": run_id,
                "status": status,
                "failure_category": failure.value,
                "workspace_manifest": {
                    "before": before,
                    "after": after,
                    "diff": manifest_diff,
                },
                "verifier": {
                    "passed": verifier_result.passed,
                    "returncode": verifier_result.returncode,
                    "duration_ms": verifier_result.duration_ms,
                    "output": verifier_result.output,
                },
                "client_duration_ms": client_duration_ms,
                "trace": sanitize_trace(client_result.trace),
                "error": client_result.error,
            }
            artifact = extend_artifact_contract(
                legacy,
                source={
                    "task_id": task.task_id,
                    "repo_id": task.repo_id,
                    "run_kind": request.run_kind,
                    "shard": request.shard,
                    "native_gate_hash": client_result.native_gate_hash,
                    "tool_050_s_hash": request.tool_050_s_hash,
                },
                profile=client_result.profile,
                native_protocol=protocol,
            )
            evidence_path = run_dir / "evidence.json"
            evidence_path.write_text(
                json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return RunEvidence(
                task_id=task.task_id,
                repo_id=task.repo_id,
                run_kind=request.run_kind,
                shard=request.shard,
                run_id=run_id,
                status=status,
                failure_category=failure.value,
                workspace=workspace,
                artifact=artifact,
            )
        except LiveTaskError:
            raise
        except Exception as exc:
            raise InfrastructureFailure(str(exc)) from exc

    def _validate(self, task: TaskSpec, request: RunRequest) -> None:
        if request.run_kind not in SUPPORTED_RUN_KINDS:
            raise ValueError(f"unsupported run kind: {request.run_kind}")
        if request.run_kind not in task.run_kinds:
            raise ValueError(f"task {task.task_id} does not support run kind {request.run_kind}")
        if request.shard != task.shard:
            raise ValueError(f"task {task.task_id} belongs to shard {task.shard}")
        if request.run_kind == FORMAL_RUN_KIND and not _is_sha256(request.tool_050_s_hash):
            raise ProtocolFailure("formal runs require the frozen TOOL-050-S selection SHA-256 hash")
        _validate_task_isolation(task)
        if _is_relative_to(self.output_root.resolve(), task.source_dir.resolve()):
            raise InfrastructureFailure("output root must be outside the task source directory")

    def _verify(self, verifier: Path, workspace: Path) -> _VerifierResult:
        env = os.environ.copy()
        env.update(self.verifier_environment)
        env["PICO_TASK_WORKSPACE"] = str(workspace)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                _verifier_command(verifier, workspace),
                cwd=verifier.parent,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.verifier_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise InfrastructureFailure(f"hidden verifier could not run: {type(exc).__name__}") from exc
        stdout = str(sanitize_public_artifact(completed.stdout.strip()))
        stderr = str(sanitize_public_artifact(completed.stderr.strip()))
        output = "\n".join(part for part in (stdout, stderr) if part)
        return _VerifierResult(
            passed=completed.returncode == 0,
            returncode=completed.returncode,
            duration_ms=int((time.monotonic() - started) * 1000),
            output=output,
            stdout=stdout,
            stderr=stderr,
        )


def select_tasks(
    tasks: Sequence[TaskSpec],
    *,
    task_ids: Sequence[str] = (),
    repo_ids: Sequence[str] = (),
    run_kinds: Sequence[str] = (),
    shards: Sequence[str] = (),
) -> list[TaskSpec]:
    from pico.evaluation.taskset import select_tasks as select

    return select(
        tasks,
        task_ids=task_ids,
        repo_ids=repo_ids,
        run_kinds=run_kinds,
        shards=shards,
    )


def load_task_specs(path: Path) -> list[TaskSpec]:
    from pico.evaluation.taskset import load_task_specs as load

    return load(path)


def _native_evidence(result: ClientResult) -> dict[str, Any]:
    calls = Counter(result.call_ids)
    results = Counter(result.result_call_ids)
    matched = sum(min(count, results[call_id]) for call_id, count in calls.items())
    total = sum(calls.values())
    duplicate_after_result = sum(max(0, count - calls[call_id]) for call_id, count in results.items())
    errors = list(result.protocol_errors)
    duplicate_calls = sorted(call_id for call_id, count in calls.items() if count > 1)
    duplicate_results = sorted(call_id for call_id, count in results.items() if count > 1)
    missing = sorted((calls - results).elements())
    unexpected = sorted((results - calls).elements())
    if duplicate_calls:
        errors.append(f"duplicate native call IDs: {', '.join(duplicate_calls)}")
    if duplicate_results:
        errors.append(f"duplicate tool results: {', '.join(duplicate_results)}")
    if missing:
        errors.append(f"missing tool results for call IDs: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected tool results for call IDs: {', '.join(unexpected)}")
    metadata = native_protocol_metadata(
        eligible=bool(result.native_gate_hash),
        native_tool_call_observed=bool(result.call_ids),
        call_id_result_match={"numerator": matched, "denominator": total},
        batch_completeness={"numerator": matched, "denominator": total},
        duplicate_call_after_result=duplicate_after_result,
        protocol_errors=errors,
        http_attempts=len(result.http_attempts),
        sdk_retry_count=result.sdk_retry_count,
        pico_retry_count=result.pico_retry_count,
    )
    metadata["native_gate_hash"] = result.native_gate_hash
    metadata["call_result_pairs"] = [
        {"call_id": call_id, "call_count": calls[call_id], "result_count": results[call_id]}
        for call_id in sorted(calls.keys() | results.keys())
    ]
    metadata["http_attempt_evidence"] = [attempt.as_dict() for attempt in result.http_attempts]
    return metadata


def _validate_task_isolation(task: TaskSpec) -> None:
    source = task.source_dir.resolve()
    if not source.is_dir():
        raise InfrastructureFailure(f"task source directory does not exist: {source}")
    verifier = task.verifier.resolve()
    if not verifier.is_file():
        raise InfrastructureFailure(f"hidden verifier does not exist: {verifier}")
    hidden_paths = (verifier, *(path.resolve() for path in task.reference_paths))
    missing_references = [path for path in task.reference_paths if not path.resolve().is_file()]
    if missing_references:
        raise InfrastructureFailure("hidden reference does not exist")
    if any(_is_relative_to(path, source) for path in hidden_paths):
        raise InfrastructureFailure("hidden verifier/reference must be outside the agent source workspace")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise InfrastructureFailure("task source may not contain symlinks")
    invalid_kinds = set(task.run_kinds) - SUPPORTED_RUN_KINDS
    if invalid_kinds:
        raise ValueError(f"unsupported task run kinds: {', '.join(sorted(invalid_kinds))}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _new_run_id(task_id: str) -> str:
    safe_task = "".join(character if character.isalnum() or character in "-_" else "-" for character in task_id)
    return f"{safe_task}-{time.time_ns()}-{uuid4().hex[:8]}"


def _verifier_command(verifier: Path, workspace: Path) -> list[str]:
    if verifier.suffix.lower() == ".py":
        return [sys.executable, os.fspath(verifier), os.fspath(workspace)]
    return [os.fspath(verifier), os.fspath(workspace)]


__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "ClientResult",
    "FailureCategory",
    "HttpAttempt",
    "InfrastructureFailure",
    "LiveTaskClient",
    "LocalLiveTaskRunner",
    "ProtocolFailure",
    "ProviderFailure",
    "RunEvidence",
    "RunRequest",
    "TaskSpec",
    "compare_manifests",
    "load_task_specs",
    "sanitize_trace",
    "select_tasks",
    "workspace_manifest",
]
