#!/usr/bin/env python3
"""Run standalone local coding-task manifests in isolated workspaces.

The client command must write provider-neutral JSON to the path in
``PICO_LIVE_EVIDENCE_PATH``. It runs with the fresh task workspace as cwd and
receives the prompt through ``PICO_LIVE_TASK_PROMPT``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

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


class CommandClient:
    """Narrow subprocess adapter; it does not execute or interpret Pico tools."""

    def __init__(self, command: list[str], *, timeout_seconds: float):
        if not command:
            raise ValueError("client command cannot be empty")
        self.command = command
        self.timeout_seconds = timeout_seconds

    def run(self, workspace: Path, prompt: str) -> ClientResult:
        with tempfile.TemporaryDirectory(prefix="pico-live-client-") as temp_dir:
            evidence_path = Path(temp_dir) / "client-evidence.json"
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
            except (OSError, subprocess.SubprocessError) as exc:
                raise InfrastructureFailure(f"client command could not run: {type(exc).__name__}") from exc
            if not evidence_path.is_file():
                raise InfrastructureFailure("client did not write PICO_LIVE_EVIDENCE_PATH")
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            if completed.returncode and not payload.get("failure_category"):
                payload["failure_category"] = FailureCategory.PROVIDER.value
                payload["error"] = payload.get("error") or completed.stderr.strip()
            return _client_result(payload)


def _client_result(payload: Mapping[str, Any]) -> ClientResult:
    try:
        failure = FailureCategory(str(payload.get("failure_category", FailureCategory.NONE.value)))
    except ValueError as exc:
        raise InfrastructureFailure("client evidence has an unknown failure_category") from exc
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
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--run-kind", action="append", choices=("synthetic", "probe", "formal"), default=[])
    parser.add_argument("--shard", action="append", default=[])
    parser.add_argument("--tool-050-s-hash", default="")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("client_command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
        run_kinds = args.run_kind or ["synthetic"]
        for run_kind in run_kinds:
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


if __name__ == "__main__":
    raise SystemExit(main())
