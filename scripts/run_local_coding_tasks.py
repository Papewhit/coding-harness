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

from pico.config import resolve_provider_config
from pico.evaluation.evaluation_v2_config import (
    CONFIG_LOCATOR_ENV,
    SUPPORTED_COHORTS,
    TASKSET_PATH,
    verify_run_config,
    write_run_config,
)
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    HttpAttempt,
    InfrastructureFailure,
    LocalLiveTaskRunner,
    RunRequest,
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
                payload = _client_payload(evidence_path)
                payload["failure_category"] = FailureCategory.INFRASTRUCTURE.value
                payload["error"] = type(exc).__name__
                payload["exit_code"] = -1
                return _client_result(payload)
            raise InfrastructureFailure(
                "client command timed out before writing request evidence"
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise InfrastructureFailure(
                f"client command could not run: {type(exc).__name__}"
            ) from exc
        payload = _client_payload(evidence_path)
        payload["exit_code"] = completed.returncode
        if completed.returncode and payload.get("failure_category") in {
            None,
            "",
            FailureCategory.NONE.value,
        }:
            payload["failure_category"] = FailureCategory.PROVIDER.value
            payload["error"] = "client command returned a nonzero exit status"
        return _client_result(payload)


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
        failure_category=failure,
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


def _client_payload(evidence_path: Path) -> dict[str, Any]:
    if not evidence_path.is_file():
        raise InfrastructureFailure("client did not write PICO_LIVE_EVIDENCE_PATH")
    envelope = _load_object(evidence_path)
    payload = envelope.get("client_result", envelope)
    if not isinstance(payload, Mapping):
        raise InfrastructureFailure("client evidence does not contain client_result")
    return dict(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-manifest", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-config", type=Path)
    parser.add_argument(
        "--prepare-run-configs",
        action="store_true",
        help="Create pilot-v1 and baseline-v1 configs under --output-root.",
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
    parser.add_argument("--repetitions", type=int, default=1)
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
        print(
            json.dumps(
                verify_run_config(args.run_config, source_root=SOURCE_ROOT),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.run_config is not None:
        return _run_evaluation_v2(args)
    return _run_legacy(args)


def _prepare_configs(args: argparse.Namespace) -> int:
    if args.output_root is None:
        raise SystemExit("--prepare-run-configs requires --output-root")
    if args.run_config or args.client_command:
        raise SystemExit("config preparation cannot execute a client")
    rows = []
    for cohort_id in sorted(SUPPORTED_COHORTS):
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
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    verify_run_config(args.run_config, source_root=SOURCE_ROOT)
    payload = _load_object(args.run_config)
    cohort_id = args.cohort_id or str(payload["cohort_id"])
    if cohort_id != payload["cohort_id"]:
        raise SystemExit("--cohort-id does not match --run-config")
    tasks = select_tasks(
        load_task_specs(SOURCE_ROOT / TASKSET_PATH),
        task_ids=args.task,
        repo_ids=args.repo,
    )
    if not tasks:
        raise SystemExit("no tasks matched the requested filters")
    tasks = sorted(tasks, key=lambda task: task.task_id)
    allowed = {
        (str(row["task_id"]), int(row["repetition"])): str(row["row_id"])
        for row in payload["allowed_rows"]
    }
    selected = [
        (task, repetition)
        for repetition in range(1, args.repetitions + 1)
        for task in tasks
    ]
    if any((task.task_id, repetition) not in allowed for task, repetition in selected):
        raise SystemExit("requested rows are outside the frozen run config")
    _validate_stage_selection(
        cohort_id=cohort_id,
        stage=args.stage,
        selected=selected,
    )

    command = [str(item) for item in payload["client"]["command"]]
    client = CommandClient(
        command,
        timeout_seconds=float(payload["runtime"]["row_timeout_seconds"]),
    )
    cohort_root = args.run_config.resolve().parents[1]
    runner = LocalLiveTaskRunner(cohort_root)
    source = payload["source"]
    sensitive_values = _sensitive_values(payload)
    summaries = []
    for task, repetition in selected:
        row_id = allowed[(task.task_id, repetition)]
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
                sensitive_values=sensitive_values,
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


def _validate_stage_selection(
    *,
    cohort_id: str,
    stage: str,
    selected: list[tuple[Any, int]],
) -> None:
    stage_tasks = {
        ("pilot-v1", "P3-G0"): ("T01",),
        ("pilot-v1", "P3-remainder"): ("T04", "T07"),
        ("baseline-v1", "P4A"): ("T01", "T02", "T03"),
        ("baseline-v1", "P4B"): ("T04", "T05", "T06"),
        ("baseline-v1", "P4C"): ("T07", "T08", "T09"),
    }
    expected_tasks = stage_tasks.get((cohort_id, stage))
    if expected_tasks is None:
        raise SystemExit("Evaluation v2 requires a frozen stage identifier")
    repetitions = 1 if cohort_id == "pilot-v1" else 3
    expected = {
        (task_id, repetition)
        for repetition in range(1, repetitions + 1)
        for task_id in expected_tasks
    }
    observed = {(task.task_id, repetition) for task, repetition in selected}
    if observed != expected:
        raise SystemExit("requested rows do not exactly match the frozen stage")


def _sensitive_values(payload: Mapping[str, Any]) -> tuple[str, ...]:
    locator = os.environ.get(CONFIG_LOCATOR_ENV, "")
    if not locator:
        raise SystemExit(f"{CONFIG_LOCATOR_ENV} is required for live Evaluation v2")
    path = Path(locator)
    if not path.is_file():
        raise SystemExit(f"{CONFIG_LOCATOR_ENV} must identify an existing file")
    profile = payload["profile"]["public_profile"]
    config = resolve_provider_config(
        str(profile["provider"]),
        start=SOURCE_ROOT,
        config_path=locator,
    )
    return tuple(value for value in (locator, config.api_key) if value)


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
