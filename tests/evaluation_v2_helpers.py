"""Shared fake Runtime state and run-config fixtures for Evaluation v2 tests."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from pico.evaluation import evaluation_v2_config as configlib
from pico.evaluation.evaluation_v2_config import canonical_json, sha256_bytes
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    FailureOrigin,
    FailureStage,
    HttpAttempt,
    RunRequest,
)


ROOT = Path(__file__).resolve().parents[1]
TASKSET = ROOT / "benchmarks" / "v3" / "local-repos" / "taskset.json"
SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40
NATIVE_GATE = "c" * 64


class FakeT01Client:
    def __init__(self, *, mismatched: bool = False, secret: str = "") -> None:
        self.mismatched = mismatched
        self.secret = secret

    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        assert prompt.startswith("# T01")
        assert evidence_path is not None
        config = workspace / "tinyconfig" / "config.py"
        text = config.read_text(encoding="utf-8")
        text = text.replace(
            '    debug = bool(_read_value(values, "APP_DEBUG", "false"))',
            """    debug_text = _read_value(values, "APP_DEBUG", "false").strip().lower()
    if debug_text in {"true", "1", "yes", "on"}:
        debug = True
    elif debug_text in {"false", "0", "no", "off"}:
        debug = False
    else:
        raise ConfigError("APP_DEBUG has an unsupported boolean value")""",
        )
        config.write_text(text, encoding="utf-8")
        self._write_pico_state(workspace)
        result_id = "wrong-call" if self.mismatched else "call-1"
        return ClientResult(
            profile={"provider": "fake"},
            native_gate_hash=NATIVE_GATE,
            call_ids=("call-1",),
            result_call_ids=(result_id,),
            http_attempts=(),
            session_id="session-1",
            runtime_run_id="runtime-1",
            final_answer="Implemented conventional APP_DEBUG parsing.",
            http_attempts_exact=True,
        )

    def _write_pico_state(self, workspace: Path) -> None:
        sessions = workspace / ".pico" / "sessions"
        run = workspace / ".pico" / "runs" / "runtime-1"
        sessions.mkdir(parents=True)
        run.mkdir(parents=True)
        session: dict[str, Any] = {
            "id": "session-1",
            "model_exchange": {
                "events": [
                    {
                        "event": "assistant_tool_batch",
                        "tool_calls": [
                            {
                                "call_id": "call-1",
                                "name": "patch_file",
                                "arguments": {"path": "tinyconfig/config.py"},
                            }
                        ],
                    },
                    {
                        "event": "tool_result",
                        "call_id": "call-1",
                        "name": "patch_file",
                        "status": "completed",
                    },
                ]
            },
        }
        if self.secret:
            session["leak"] = self.secret
        (sessions / "session-1.json").write_text(
            json.dumps(session), encoding="utf-8"
        )
        (sessions / "session-1.events.jsonl").write_text(
            json.dumps(
                {
                    "event": "tool_finished",
                    "call_id": "call-1",
                    "tool_name": "patch_file",
                    "status": "ok",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (run / "task_state.json").write_text("{}\n", encoding="utf-8")
        (run / "trace.jsonl").write_text(
            json.dumps(
                {
                    "event": "tool_executed",
                    "call_id": "call-1",
                    "name": "patch_file",
                    "tool_status": "ok",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (run / "report.json").write_text(
            json.dumps({"final_answer": "done"}) + "\n", encoding="utf-8"
        )
        (run / "raw-provider-response.json").write_text(
            '{"must_not_publish": true}\n', encoding="utf-8"
        )


class FailedT01Client(FakeT01Client):
    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        result = super().run(workspace, prompt, evidence_path=evidence_path)
        return replace(
            result,
            http_attempts=(
                HttpAttempt(
                    attempt=1,
                    status_code=503,
                    duration_ms=12,
                    error_type="ServiceUnavailable",
                ),
            ),
            failure_category=FailureCategory.PROVIDER,
            failure_origin=FailureOrigin.PROVIDER,
            failure_stage=FailureStage.REQUEST,
            error="ServiceUnavailable",
            error_type="ServiceUnavailable",
            exit_code=1,
        )


class ExplodingClient:
    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        del workspace, prompt, evidence_path
        raise RuntimeError("synthetic client failure")


class DuplicateResultClient(FakeT01Client):
    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        evidence_path: Path | None = None,
    ) -> ClientResult:
        result = super().run(workspace, prompt, evidence_path=evidence_path)
        session_path = workspace / ".pico" / "sessions" / "session-1.json"
        session = json.loads(session_path.read_text(encoding="utf-8"))
        session["model_exchange"]["events"].append(
            {
                "event": "tool_result",
                "call_id": "call-1",
                "name": "patch_file",
                "status": "completed",
            }
        )
        session_path.write_text(json.dumps(session), encoding="utf-8")
        return result


def request(
    config_path: Path, *, cohort_id: str = "pilot-v1"
) -> RunRequest:
    row_id = f"{cohort_id}-T01-r1"
    return RunRequest(
        run_kind="formal",
        shard="tinyconfig",
        tool_050_s_hash=NATIVE_GATE,
        run_id=row_id,
        cohort_id=cohort_id,
        row_id=row_id,
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
        repetition=1,
        stage="p2-fake",
        run_config_path=config_path,
    )


def write_config(
    tmp_path: Path,
    monkeypatch: Any,
    *,
    cohort_id: str = "pilot-v1",
) -> tuple[Path, Path]:
    monkeypatch.setattr(
        configlib,
        "_git_identity",
        lambda _root, require_clean=True: (SOURCE_COMMIT, SOURCE_TREE),
    )
    environment = {
        "execution_environment": "test",
        "os": "test",
        "python": "3.12.13",
        "implementation": "CPython",
    }
    monkeypatch.setattr(configlib, "_runtime_environment", lambda: environment)
    payload = configlib.build_run_config(
        source_root=ROOT,
        artifact_root=tmp_path,
        cohort_id=cohort_id,
        environment=environment,
    )
    cohort_root = tmp_path / cohort_id / SOURCE_COMMIT
    public = cohort_root / "public"
    public.mkdir(parents=True)
    config_path = public / "run-config.json"
    encoded = canonical_json(payload)
    config_path.write_bytes(encoded)
    (public / "run-config.sha256").write_text(
        sha256_bytes(encoded) + "\n", encoding="ascii"
    )
    return config_path, cohort_root


__all__ = [
    "DuplicateResultClient",
    "ExplodingClient",
    "FailedT01Client",
    "FakeT01Client",
    "ROOT",
    "TASKSET",
    "request",
    "write_config",
]
