#!/usr/bin/env python3
"""Run isolated coding tasks or manage Evaluation v2 run configurations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

from pico.evaluation.evaluation_v2_config import (
    SUPPORTED_COHORTS,
    TASKSET_PATH,
    canonical_json,
    validate_live_start,
    verify_run_config,
    write_run_config,
)
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    FailureOrigin,
    FailureStage,
    HttpAttempt,
    InfrastructureFailure,
    LocalLiveTaskRunner,
    RunRequest,
    client_failure_record_errors,
    load_task_specs,
    select_tasks,
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class CommandClient:
    """Narrow subprocess adapter; it never executes or interprets Pico tools."""

    def __init__(self, command: list[str], *, timeout_seconds: float):
        if not command:
            raise ValueError("client command cannot be empty")
        self.command = command
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        if evidence_path is not None:
            return self._run(workspace, prompt, evidence_path)
        with tempfile.TemporaryDirectory(prefix="pico-live-client-") as temp_dir:
            return self._run(
                workspace,
                prompt,
                Path(temp_dir) / "client-evidence.json",
            )

    def _run(self, workspace: Path, prompt: str, evidence_path: Path) -> ClientResult:
        env = os.environ.copy()
        env["PICO_LIVE_EVIDENCE_PATH"] = str(evidence_path)
        env["PICO_LIVE_TASK_PROMPT"] = prompt
        try:
            completed = subprocess.run(
                self.command,
                cwd=workspace,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            if evidence_path.is_file():
                _record_exit_code(evidence_path, -1)
            raise InfrastructureFailure(
                "client command timed out before a trustworthy product result"
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise InfrastructureFailure(
                f"client command could not run: {type(exc).__name__}"
            ) from exc
        _record_exit_code(evidence_path, completed.returncode)
        result = _client_result(_client_payload(evidence_path))
        record_errors = client_failure_record_errors(result)
        if record_errors:
            raise InfrastructureFailure(
                "client command wrote invalid original failure evidence: "
                + "; ".join(record_errors)
            )
        if completed.returncode:
            if result.failure_category is FailureCategory.NONE:
                raise InfrastructureFailure(
                    "client command failed without classified original failure evidence"
                )
            if result.failure_origin is FailureOrigin.CLIENT:
                raise InfrastructureFailure(
                    "client infrastructure failed before a product result"
                )
        elif result.failure_category is not FailureCategory.NONE:
            raise InfrastructureFailure(
                "client command succeeded with contradictory failure evidence"
            )
        return result


def _client_result(payload: Mapping[str, Any]) -> ClientResult:
    try:
        failure = FailureCategory(
            str(payload.get("failure_category", FailureCategory.NONE.value))
        )
    except ValueError as exc:
        raise InfrastructureFailure(
            "client evidence has an unknown failure_category"
        ) from exc
    attempts = tuple(
        HttpAttempt(
            attempt=int(row["attempt"]),
            status_code=row.get("status_code"),
            duration_ms=int(row.get("duration_ms", 0)),
            error_type=str(row.get("error_type", "")),
        )
        for row in payload.get("http_attempts", [])
    )
    return ClientResult(
        profile=payload.get("profile", {}),
        native_gate_hash=str(payload.get("native_gate_hash", "")),
        call_ids=tuple(map(str, payload.get("call_ids", []))),
        result_call_ids=tuple(map(str, payload.get("result_call_ids", []))),
        http_attempts=attempts,
        trace=tuple(payload.get("trace", [])),
        sdk_retry_count=int(payload.get("sdk_retry_count", 0)),
        pico_retry_count=int(payload.get("pico_retry_count", 0)),
        protocol_errors=tuple(map(str, payload.get("protocol_errors", []))),
        error=str(payload.get("error", "")),
        error_type=str(payload.get("error_type", "")),
        failure_category=failure,
        failure_origin=_failure_origin(payload),
        failure_stage=_failure_stage(payload),
        session_id=str(payload.get("session_id", "")),
        runtime_run_id=str(payload.get("runtime_run_id", "")),
        final_answer=str(payload.get("final_answer", "")),
        http_attempts_exact=bool(payload.get("http_attempts_exact", True)),
        original_state_paths=tuple(
            map(str, payload.get("original_state_paths", []))
        ),
        exit_code=(
            int(payload["exit_code"])
            if payload.get("exit_code") is not None
            else None
        ),
    )


def _failure_origin(payload: Mapping[str, Any]) -> FailureOrigin:
    try:
        return FailureOrigin(
            str(payload.get("failure_origin", FailureOrigin.NONE.value))
        )
    except ValueError as exc:
        raise InfrastructureFailure(
            "client evidence has an unknown failure_origin"
        ) from exc


def _failure_stage(payload: Mapping[str, Any]) -> FailureStage:
    try:
        return FailureStage(
            str(payload.get("failure_stage", FailureStage.NONE.value))
        )
    except ValueError as exc:
        raise InfrastructureFailure(
            "client evidence has an unknown failure_stage"
        ) from exc


def _client_payload(evidence_path: Path) -> dict[str, Any]:
    if not evidence_path.is_file():
        raise InfrastructureFailure("client did not write PICO_LIVE_EVIDENCE_PATH")
    envelope = _load_object(evidence_path)
    payload = envelope.get("client_result", envelope)
    if not isinstance(payload, Mapping):
        raise InfrastructureFailure("client evidence does not contain client_result")
    return dict(payload)


def _record_exit_code(evidence_path: Path, exit_code: int) -> None:
    """Append only the outer process exit code to existing client evidence."""

    envelope = _load_object(evidence_path)
    if isinstance(envelope.get("client_result"), Mapping):
        payload = dict(envelope["client_result"])
        payload["exit_code"] = exit_code
        envelope["client_result"] = payload
    elif "row" in envelope and "measurement_status" in envelope:
        return
    else:
        envelope["exit_code"] = exit_code
    temporary = evidence_path.with_name(evidence_path.name + ".exit.tmp")
    temporary.write_bytes(canonical_json(envelope))
    temporary.replace(evidence_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-config", type=Path)
    parser.add_argument(
        "--prepare-run-configs",
        action="store_true",
        help="Create frozen Evaluation v2 configs under --output-root.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify --run-config without executing a task.",
    )
    parser.add_argument("--cohort-id", choices=sorted(SUPPORTED_COHORTS))
    parser.add_argument("--stage", default="")
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--repetitions", type=int)
    parser.add_argument(
        "--resume-missing",
        action="store_true",
        help="For baseline-v1, execute only selected rows without existing artifacts.",
    )
    parser.add_argument(
        "--run-kind",
        action="append",
        choices=("synthetic", "probe", "formal"),
        default=[],
    )
    parser.add_argument("--shard", action="append", default=[])
    parser.add_argument("--tool-050-s-hash", default="")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("client_command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.prepare_run_configs:
        return _prepare_configs(args)
    if args.verify_only:
        if args.run_config is None:
            raise SystemExit("--verify-only requires --run-config")
        if (
            args.cohort_id
            or args.stage
            or args.task
            or args.repo
            or args.repetitions is not None
            or args.resume_missing
        ):
            raise SystemExit(
                "--verify-only does not accept live selection parameters"
            )
        print(
            json.dumps(
                verify_run_config(args.run_config),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.run_config is not None:
        return _run_evaluation_v2(args)
    if args.resume_missing:
        raise SystemExit("--resume-missing requires a baseline-v1 run config")
    return _run_legacy(args)


def _prepare_configs(args: argparse.Namespace) -> int:
    if args.output_root is None:
        raise SystemExit("--prepare-run-configs requires --output-root")
    if args.run_config or args.client_command or args.resume_missing:
        raise SystemExit("config preparation cannot execute a client")
    rows = []
    cohort_ids = (
        [args.cohort_id]
        if args.cohort_id
        else sorted(SUPPORTED_COHORTS)
    )
    for cohort_id in cohort_ids:
        path, digest = write_run_config(
            source_root=SOURCE_ROOT,
            artifact_root=args.output_root,
            cohort_id=cohort_id,
        )
        rows.append({"cohort_id": cohort_id, "path": str(path), "sha256": digest})
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


def _run_evaluation_v2(args: argparse.Namespace) -> int:
    if args.client_command:
        raise SystemExit("Evaluation v2 client command is frozen in run-config.json")
    repetitions = 1 if args.repetitions is None else args.repetitions
    if repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    if args.cohort_id is None:
        raise SystemExit("Evaluation v2 live execution requires --cohort-id")
    cohort_id = args.cohort_id
    tasks = select_tasks(
        load_task_specs(SOURCE_ROOT / TASKSET_PATH),
        task_ids=args.task,
        repo_ids=args.repo,
    )
    if not tasks:
        raise SystemExit("no tasks matched the requested filters")
    tasks = sorted(tasks, key=lambda task: task.task_id)
    selected = [
        (task, repetition)
        for repetition in range(1, repetitions + 1)
        for task in tasks
    ]
    cohort_root = args.run_config.resolve().parents[1]
    if args.resume_missing:
        if cohort_id != "baseline-v1":
            raise SystemExit("--resume-missing is only supported for baseline-v1")
        selected = [
            (task, repetition)
            for task, repetition in selected
            if not _row_started(
                cohort_root,
                f"{cohort_id}-{task.task_id}-r{repetition}",
            )
        ]
        if not selected:
            verify_run_config(args.run_config)
            print("[]")
            return 0
    requested_rows = [
        (
            task.task_id,
            repetition,
            f"{cohort_id}-{task.task_id}-r{repetition}",
        )
        for task, repetition in selected
    ]
    validation = validate_live_start(
        args.run_config,
        source_root=SOURCE_ROOT,
        cohort_id=cohort_id,
        requested_rows=requested_rows,
        artifact_root=cohort_root,
    )
    payload = validation.payload
    command = [str(item) for item in payload["client"]["command"]]
    client = CommandClient(
        command,
        timeout_seconds=float(payload["runtime"]["row_timeout_seconds"]),
    )
    runner = LocalLiveTaskRunner(cohort_root)
    source = payload["source"]
    summaries = []
    for (task, repetition), row_id in zip(
        selected,
        validation.row_ids,
        strict=True,
    ):
        evidence = runner.run(
            task,
            RunRequest(
                run_kind="formal",
                shard=task.shard,
                tool_050_s_hash=str(payload["profile"]["native_gate_hash"]),
                run_id=row_id,
                cohort_id=cohort_id,
                row_id=row_id,
                source_commit=str(source["commit"]),
                source_tree=str(source["tree"]),
                repetition=repetition,
                stage=args.stage,
                run_config_path=args.run_config.resolve(),
                sensitive_values=validation.sensitive_values,
            ),
            client,
        )
        summaries.append(
            {
                "task_id": evidence.task_id,
                "row_id": evidence.run_id,
                "status": evidence.status,
                "failure_category": evidence.failure_category,
            }
        )
        if evidence.failure_category in {
            FailureCategory.MEASUREMENT.value,
            FailureCategory.PROTOCOL.value,
            FailureCategory.INFRASTRUCTURE.value,
        }:
            break
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return int(any(row["status"] != "passed" for row in summaries))


def _row_started(cohort_root: Path, row_id: str) -> bool:
    return any(
        (
            cohort_root / visibility / "rows" / row_id
        ).exists()
        for visibility in ("private", "public")
    )


def _run_legacy(args: argparse.Namespace) -> int:
    if args.task_manifest is None or args.output_root is None:
        raise SystemExit("legacy mode requires --task-manifest and --output-root")
    command = args.client_command
    if command and command[0] == "--":
        command = command[1:]
    client = CommandClient(command, timeout_seconds=args.timeout)
    tasks = select_tasks(
        load_task_specs(args.task_manifest),
        task_ids=args.task,
        repo_ids=args.repo,
        run_kinds=args.run_kind,
        shards=args.shard,
    )
    if not tasks:
        raise SystemExit("no tasks matched the requested filters")
    runner = LocalLiveTaskRunner(args.output_root)
    summaries = []
    for task in tasks:
        for run_kind in args.run_kind or ["synthetic"]:
            if run_kind not in task.run_kinds:
                continue
            evidence = runner.run(
                task,
                RunRequest(
                    run_kind=run_kind,
                    shard=task.shard,
                    tool_050_s_hash=args.tool_050_s_hash,
                ),
                client,
            )
            summaries.append(
                {
                    "task_id": evidence.task_id,
                    "run_id": evidence.run_id,
                    "status": evidence.status,
                    "failure_category": evidence.failure_category,
                }
            )
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return int(any(row["status"] != "passed" for row in summaries))


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
