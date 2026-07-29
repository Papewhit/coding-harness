from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

import pytest

import coda.config as coda_config
from coda.evaluation import evaluation_v2_config as configlib
from coda.evaluation import evaluation_v2_row_capture as capturelib
from coda.evaluation.evaluation_v2_config import (
    canonical_json,
    sha256_bytes,
    verify_run_config,
    verify_taskset_lock,
)
from coda.evaluation.evaluation_v2_evidence import checksums, verify_checksums
from coda.evaluation.live_client import required_network_sandbox
from coda.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    FailureOrigin,
    FailureStage,
    LocalLiveTaskRunner,
    load_task_specs,
    resolve_failure_category,
)
from tests.evaluation_v2_helpers import (
    DuplicateResultClient,
    ExplodingClient,
    FailedT01Client,
    FakeT01Client,
    ROOT,
    TASKSET,
    request as _request,
    write_config as _write_config,
)


def test_taskset_lock_recomputes_all_frozen_inputs() -> None:
    result = verify_taskset_lock(ROOT)

    assert result["task_count"] == 9
    assert (
        result["taskset_sha256"]
        == "e02e1012de151984911690d259170fd6add8aeb9dc7e0840982130fa0c79ff54"
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
        coda_config,
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
        "coda_retry_count": 0,
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


@pytest.mark.parametrize("cohort_id", ["pilot-v2", "pilot-v3", "pilot-v4"])
def test_corrective_pilot_config_has_new_rows_and_p3_only_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cohort_id: str,
) -> None:
    config_path, cohort_root = _write_config(
        tmp_path,
        monkeypatch,
        cohort_id=cohort_id,
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert cohort_root.parent.name == cohort_id
    assert payload["cohort_id"] == cohort_id
    assert [row["row_id"] for row in payload["allowed_rows"]] == [
        f"{cohort_id}-T01-r1",
        f"{cohort_id}-T04-r1",
        f"{cohort_id}-T07-r1",
    ]
    assert set(payload["launch_commands"]) == {"p3_g0", "p3_remainder"}
    assert payload["launch_commands"]["p3_g0"]["argv"][-6:] == [
        "--task",
        "T01",
        "--repo",
        "tinyconfig",
        "--repetitions",
        "1",
    ]
    assert (
        f"--cohort-id {cohort_id}"
        in payload["launch_commands"]["p3_g0"]["display"]
    )
    assert verify_run_config(config_path)["cohort_id"] == cohort_id


def test_baseline_config_freezes_missing_row_resume_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, _ = _write_config(
        tmp_path,
        monkeypatch,
        cohort_id="baseline-v1",
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert len(payload["allowed_rows"]) == 27
    assert set(payload["launch_commands"]) == {"p4a", "p4b", "p4c"}
    for command in payload["launch_commands"].values():
        assert command["argv"][-1] == "--resume-missing"
        assert command["display"].endswith("--resume-missing")
    assert verify_run_config(config_path)["cohort_id"] == "baseline-v1"


def test_run_config_normalizes_venv_python_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        configlib.sys,
        "executable",
        str(Path(configlib.sys.prefix) / "bin" / "python3"),
    )
    config_path, _ = _write_config(
        tmp_path,
        monkeypatch,
        cohort_id="pilot-v3",
    )
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    relative = (
        Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    )
    assert payload["client"]["command"][0] == str(
        Path(configlib.sys.prefix) / relative
    )


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
        "error_type": "ServiceUnavailable",
        "exit_code": 1,
        "origin": "provider",
        "provider_request_count": 1,
        "provider_request_count_exact": True,
        "stage": "request",
    }


def test_pre_request_runtime_failure_is_a_valid_product_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PreRequestRuntimeFailure:
        def run(
            self,
            workspace: Path,
            prompt: str,
            *,
            evidence_path: Path | None = None,
        ) -> ClientResult:
            del workspace, prompt, evidence_path
            return ClientResult(
                profile={"provider": "fake"},
                native_gate_hash="c" * 64,
                error="ValueError",
                error_type="ValueError",
                failure_category=FailureCategory.TASK,
                failure_origin=FailureOrigin.RUNTIME,
                failure_stage=FailureStage.PRE_REQUEST,
                http_attempts_exact=True,
                exit_code=1,
            )

    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        PreRequestRuntimeFailure(),
    )

    assert evidence.failure_category == "task"
    assert evidence.artifact["measurement_status"] == "complete"
    assert evidence.artifact["product_result"] == "pending_audit"
    assert evidence.artifact["provider_requests"] == {"count": 0, "exact": True}
    assert evidence.artifact["failure"] == {
        "category": "task",
        "error_type": "ValueError",
        "exit_code": 1,
        "origin": "runtime",
        "provider_request_count": 0,
        "provider_request_count_exact": True,
        "stage": "pre_request",
    }


def test_missing_original_failure_record_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class IncompleteFailure:
        def run(
            self,
            workspace: Path,
            prompt: str,
            *,
            evidence_path: Path | None = None,
        ) -> ClientResult:
            del workspace, prompt, evidence_path
            return ClientResult(
                profile={"provider": "fake"},
                native_gate_hash="c" * 64,
                error="lost",
                failure_category=FailureCategory.TASK,
                http_attempts_exact=True,
                exit_code=1,
            )

    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        IncompleteFailure(),
    )

    assert evidence.failure_category == "measurement"
    assert evidence.artifact["measurement_status"] == "invalid"
    assert any(
        "original" in error for error in evidence.artifact["measurement_errors"]
    )


def test_failure_precedence_keeps_original_client_failure() -> None:
    client_result = ClientResult(
        profile={},
        native_gate_hash="",
        error="ServiceUnavailable",
        error_type="ServiceUnavailable",
        failure_category=FailureCategory.PROVIDER,
        failure_origin=FailureOrigin.PROVIDER,
        failure_stage=FailureStage.REQUEST,
    )

    assert (
        resolve_failure_category(
            client_result=client_result,
            protocol_errors=("later protocol observation",),
            verifier_passed=False,
        )
        is FailureCategory.PROVIDER
    )
    assert (
        resolve_failure_category(
            measurement_errors=("damaged record",),
            client_result=client_result,
            protocol_errors=("later protocol observation",),
            verifier_passed=False,
        )
        is FailureCategory.MEASUREMENT
    )


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
        FailedT01Client(),
    )

    assert evidence.failure_category == "measurement"
    assert evidence.artifact["phase"] == "failed"
    assert evidence.artifact["failure"]["stage"] == "evidence_copy"
    assert evidence.artifact["failure"]["provider_request_count"] == 1
    assert evidence.artifact["failure"]["provider_request_count_exact"] is True
    assert evidence.artifact["failure"]["client_result_recovery"] == "validated"
    assert len(evidence.artifact["client_result"]["http_attempts"]) == 1


def test_request_count_recovery_rejects_inconsistent_persisted_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)

    def corrupt_summary_then_fail(**kwargs: object) -> object:
        public_row = Path(str(kwargs["public_row"]))
        record_path = public_row / "run-record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["provider_requests"]["count"] = 2
        record_path.write_bytes(canonical_json(record))
        raise RuntimeError("copy failed")

    monkeypatch.setattr(capturelib, "_copy_originals", corrupt_summary_then_fail)
    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        _request(config_path),
        FailedT01Client(),
    )

    assert evidence.artifact["failure"]["client_result_recovery"] == "unavailable"
    assert evidence.artifact["failure"]["provider_request_count_exact"] is False
    assert any(
        "request count does not match" in error
        for error in evidence.artifact["measurement_errors"]
    )


def test_checksum_verifier_rejects_unlisted_extra_file(tmp_path: Path) -> None:
    root = tmp_path / "row"
    root.mkdir()
    (root / "record.json").write_text("{}\n", encoding="utf-8")
    _write_checksum_manifest(root)
    (root / "unlisted.txt").write_text("extra\n", encoding="utf-8")

    with pytest.raises(ValueError, match="inventory is incomplete"):
        verify_checksums(root / "checksums.json", root)


def test_checksum_verifier_rejects_schema_and_unsafe_paths(tmp_path: Path) -> None:
    root = tmp_path / "row"
    root.mkdir()
    (root / "record.json").write_text("{}\n", encoding="utf-8")
    manifest = _write_checksum_manifest(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["schema_version"] = "drift"
    manifest.write_bytes(canonical_json(payload))
    with pytest.raises(ValueError, match="schema"):
        verify_checksums(manifest, root)

    payload["schema_version"] = "coda-evaluation-v2-checksums-v1"
    payload["files"][0]["path"] = "../record.json"
    manifest.write_bytes(canonical_json(payload))
    with pytest.raises(ValueError, match="unsafe"):
        verify_checksums(manifest, root)


def test_checksum_verifier_rejects_duplicate_and_invalid_metadata(
    tmp_path: Path,
) -> None:
    root = tmp_path / "row"
    root.mkdir()
    (root / "record.json").write_text("{}\n", encoding="utf-8")
    manifest = _write_checksum_manifest(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"].append(dict(payload["files"][0]))
    manifest.write_bytes(canonical_json(payload))
    with pytest.raises(ValueError, match="duplicate"):
        verify_checksums(manifest, root)

    payload["files"] = payload["files"][:1]
    payload["files"][0]["bytes"] = True
    manifest.write_bytes(canonical_json(payload))
    with pytest.raises(ValueError, match="byte count"):
        verify_checksums(manifest, root)


def test_row_directory_collision_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, cohort_root = _write_config(tmp_path, monkeypatch)
    runner = LocalLiveTaskRunner(cohort_root)
    task = load_task_specs(TASKSET)[0]
    runner.run(task, _request(config_path), FakeT01Client())

    with pytest.raises(Exception, match="row directory already exists"):
        runner.run(task, _request(config_path), FakeT01Client())


def _write_checksum_manifest(root: Path) -> Path:
    path = root / "checksums.json"
    path.write_bytes(canonical_json(checksums(root)))
    return path
