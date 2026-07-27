from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shlex
import shutil
import sys

import pytest

import pico.config as pico_config
from pico.evaluation import evaluation_v2_config as configlib
from pico.evaluation import evaluation_v2_row_capture as capturelib
from pico.evaluation.evaluation_v2_config import (
    canonical_json,
    sha256_bytes,
    verify_run_config,
    verify_taskset_lock,
)
from pico.evaluation.live_client import required_network_sandbox
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    HttpAttempt,
    LocalLiveTaskRunner,
    RunRequest,
    load_task_specs,
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
        session = {
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
        result = super().run(
            workspace,
            prompt,
            evidence_path=evidence_path,
        )
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
            error="ServiceUnavailable",
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
        result = super().run(
            workspace,
            prompt,
            evidence_path=evidence_path,
        )
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


def test_taskset_lock_recomputes_all_frozen_inputs() -> None:
    result = verify_taskset_lock(ROOT)

    assert result["task_count"] == 9
    assert (
        result["taskset_sha256"]
        == "b6c1d16720583767b86cf8c8f535b0ff744a84216e0843a79660fea87389909a"
    )


def test_taskset_lock_rejects_content_drift(tmp_path: Path) -> None:
    target = tmp_path / "benchmarks" / "v3" / "local-repos"
    shutil.copytree(TASKSET.parent, target, ignore=shutil.ignore_patterns(".ruff_cache", "__pycache__"))
    taskset = target / "taskset.json"
    taskset.write_text(taskset.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="taskset content"):
        verify_taskset_lock(tmp_path)


def test_fake_t01_end_to_end_writes_protocol_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pico_config,
        "resolve_provider_config",
        lambda *_args, **_kwargs: pytest.fail(
            "fake flow must not resolve provider configuration"
        ),
    )
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    task = load_task_specs(TASKSET)[0]
    runner = LocalLiveTaskRunner(cohort_root)
    evidence = runner.run(task, _request(config_path), FakeT01Client())

    assert evidence.status == "passed"
    assert evidence.failure_category == "none"
    assert not evidence.workspace.exists()
    public = cohort_root / "public" / "rows" / "pilot-v1-T01-r1"
    private = cohort_root / "private" / "rows" / "pilot-v1-T01-r1"
    assert (public / "run-record.json").is_file()
    assert (public / "evidence-view.json").is_file()
    assert (public / "checksums.json").is_file()
    assert (private / "checksums.json").is_file()
    assert not list(public.rglob("raw-provider-response.json"))
    assert not list(private.rglob("raw-provider-response.json"))
    record = json.loads((public / "run-record.json").read_text(encoding="utf-8"))
    view = json.loads((public / "evidence-view.json").read_text(encoding="utf-8"))
    assert record["measurement_status"] == "complete"
    assert record["client_result"]["http_attempts"] == []
    assert view["provider_requests"] == {
        "count": 0,
        "exact": True,
        "pico_retry_count": 0,
        "sdk_retry_count": 0,
        "source": "run-record.json#/client_result",
    }
    assert view["protocol_errors"] == []
    assert [row["call_id"] for row in view["tool_calls"]] == ["call-1"]


def test_call_id_mismatch_is_a_measurement_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        FakeT01Client(mismatched=True),
    )

    assert evidence.failure_category == "measurement"
    record = evidence.artifact
    assert record["measurement_status"] == "invalid"
    assert any("client results" in error for error in record["measurement_errors"])


def test_duplicate_tool_result_is_a_measurement_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        DuplicateResultClient(),
    )

    assert evidence.failure_category == "measurement"
    assert any(
        "tool results contain empty or duplicate" in error
        for error in evidence.artifact["measurement_errors"]
    )


def test_known_secret_is_not_copied_or_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "test-secret-never-persist"
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    request = replace(_request(config_path), sensitive_values=(secret,))
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        request,
        FakeT01Client(secret=secret),
    )

    assert evidence.failure_category == "measurement"
    persisted = b"".join(
        path.read_bytes()
        for path in cohort_root.rglob("*")
        if path.is_file()
    )
    assert secret.encode() not in persisted


def test_run_config_hash_detects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _ = _write_config(tmp_path, monkeypatch)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["runtime"]["max_tool_steps"] = 49
    config_path.write_bytes(canonical_json(payload))

    with pytest.raises(ValueError, match="SHA-256"):
        verify_run_config(config_path)


def test_run_config_validation_detects_rehashed_policy_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _ = _write_config(tmp_path, monkeypatch)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["runtime"]["max_tool_steps"] = 49
    encoded = canonical_json(payload)
    config_path.write_bytes(encoded)
    config_path.with_name("run-config.sha256").write_text(
        sha256_bytes(encoded) + "\n",
        encoding="ascii",
    )

    with pytest.raises(ValueError, match="runtime drift"):
        verify_run_config(config_path)


def test_run_config_never_persists_locator_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locator = "C:/private/provider-config.toml"
    monkeypatch.setenv(configlib.CONFIG_LOCATOR_ENV, locator)
    config_path, _ = _write_config(tmp_path, monkeypatch)

    assert locator not in config_path.read_text(encoding="utf-8")


def test_network_isolated_shell_includes_unshare_net(tmp_path: Path) -> None:
    sandbox = required_network_sandbox()
    argv = sandbox._bubblewrap_argv(
        "/usr/bin/bwrap",
        "python -m pytest -q",
        tmp_path,
        sandbox.config,
    )

    assert argv[1] == "--unshare-net"
    assert "--bind" in argv


def test_network_isolated_shell_blocks_outbound_socket(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is unavailable")
    command = (
        f"{shlex.quote(sys.executable)} -c "
        + shlex.quote(
            "import socket; socket.create_connection(('1.1.1.1', 53), timeout=1)"
        )
    )
    result = required_network_sandbox(
        extra_readonly_paths=(
            sys.prefix,
            str(Path(sys.base_prefix).parent),
        )
    ).run(
        command,
        cwd=tmp_path,
        env={},
        timeout=10,
    )

    assert result.returncode != 0
    assert "Network is unreachable" in result.stderr


def test_provider_failure_preserves_exact_attempt_and_failure_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        FailedT01Client(),
    )

    assert evidence.failure_category == "provider"
    assert evidence.artifact["measurement_status"] == "complete"
    assert evidence.artifact["failure"] == {
        "category": "provider",
        "exit_code": 1,
        "provider_request_count": 1,
        "provider_request_count_exact": True,
        "stage": "client",
    }


def test_client_exception_preserves_minimum_invalid_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        ExplodingClient(),
    )

    public = cohort_root / "public" / "rows" / "pilot-v1-T01-r1"
    assert evidence.failure_category == "measurement"
    assert evidence.artifact["phase"] == "failed"
    assert evidence.artifact["failure"]["stage"] == "client"
    assert evidence.artifact["failure"]["provider_request_count"] == 0
    assert (public / "run-record.json").is_file()
    assert (public / "checksums.json").is_file()


def test_evidence_copy_failure_preserves_minimum_invalid_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        capturelib,
        "_copy_originals",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("copy failed")),
    )
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        FakeT01Client(),
    )

    assert evidence.failure_category == "measurement"
    assert evidence.artifact["phase"] == "failed"
    assert evidence.artifact["failure"]["stage"] == "evidence_copy"


def test_lock_drift_fails_before_row_directories_are_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        configlib,
        "verify_taskset_lock",
        lambda _root: (_ for _ in ()).throw(ValueError("taskset drift")),
    )

    with pytest.raises(ValueError, match="taskset drift"):
        LocalLiveTaskRunner(cohort_root).run(
            load_task_specs(TASKSET)[0],
            _request(config_path),
            FakeT01Client(),
        )

    assert not (cohort_root / "public" / "rows").exists()
    assert not (cohort_root / "private" / "rows").exists()


def test_row_directory_collision_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    runner = LocalLiveTaskRunner(cohort_root)
    task = load_task_specs(TASKSET)[0]
    runner.run(task, _request(config_path), FakeT01Client())

    with pytest.raises(Exception, match="row directory already exists"):
        runner.run(task, _request(config_path), FakeT01Client())


def _request(config_path: Path) -> RunRequest:
    return RunRequest(
        run_kind="formal",
        shard="tinyconfig",
        tool_050_s_hash=NATIVE_GATE,
        run_id="pilot-v1-T01-r1",
        cohort_id="pilot-v1",
        row_id="pilot-v1-T01-r1",
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
        repetition=1,
        stage="p2-fake",
        run_config_path=config_path,
    )


def _write_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
        cohort_id="pilot-v1",
        environment=environment,
    )
    cohort_root = tmp_path / "pilot-v1" / SOURCE_COMMIT
    public = cohort_root / "public"
    public.mkdir(parents=True)
    config_path = public / "run-config.json"
    encoded = canonical_json(payload)
    config_path.write_bytes(encoded)
    (public / "run-config.sha256").write_text(
        sha256_bytes(encoded) + "\n", encoding="ascii"
    )
    return config_path, cohort_root
