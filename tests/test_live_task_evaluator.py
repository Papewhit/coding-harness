from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico.evaluation.contracts import ARTIFACT_CONTRACT_VERSION, REDACTED
from pico.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    HttpAttempt,
    InfrastructureFailure,
    LocalLiveTaskRunner,
    ProtocolFailure,
    ProviderFailure,
    RunRequest,
    TaskSpec,
    load_task_specs,
    select_tasks,
)


FIXTURE = Path(__file__).parent / "fixtures" / "live_task_runner"


class SyntheticClient:
    def __init__(self, *, failure: FailureCategory = FailureCategory.NONE):
        self.failure = failure
        self.workspaces: list[Path] = []

    def run(self, workspace: Path, prompt: str) -> ClientResult:
        self.workspaces.append(workspace)
        assert prompt == "Fix the add function."
        assert not (workspace / "hidden").exists()
        assert not (workspace / "verifier.py").exists()
        assert not (workspace / "reference.txt").exists()
        (workspace / "calculator.py").write_text(
            "def add(left: int, right: int) -> int:\n    return left + right\n",
            encoding="utf-8",
        )
        return _result(failure=self.failure)


class RaisingClient:
    def __init__(self, error: Exception):
        self.error = error

    def run(self, workspace: Path, prompt: str) -> ClientResult:
        raise self.error


def _task() -> TaskSpec:
    return load_task_specs(FIXTURE / "task-manifest.json")[0]


def _result(
    *,
    failure: FailureCategory = FailureCategory.NONE,
    call_ids: tuple[str, ...] = ("call-1",),
    result_call_ids: tuple[str, ...] = ("call-1",),
) -> ClientResult:
    return ClientResult(
        profile={
            "provider": "synthetic",
            "model": "unit-model",
            "wire_dialect": "test-native",
            "adapter_mode": "synthetic",
            "sdk": {"package": "none", "version": "0"},
            "base_url_fingerprint": "offline",
            "capabilities": {"native_tools": True},
            "retry": {"sdk_max_retries": 0, "pico_attempts": 1},
        },
        native_gate_hash="synthetic-gate-hash",
        call_ids=call_ids,
        result_call_ids=result_call_ids,
        http_attempts=(HttpAttempt(attempt=1, status_code=200, duration_ms=4),),
        trace=(
            {
                "event": "native_response",
                "call_id": "call-1",
                "authorization": "Bearer secret",
                "reasoning": "private chain of thought",
            },
        ),
        failure_category=failure,
    )


def test_runner_uses_fresh_workspace_and_external_hidden_verifier(tmp_path: Path) -> None:
    source_text = (_task().source_dir / "calculator.py").read_text(encoding="utf-8")
    client = SyntheticClient()
    runner = LocalLiveTaskRunner(tmp_path / "runs")

    first = runner.run(_task(), RunRequest("synthetic", "unit", run_id="run-1"), client)
    second = runner.run(_task(), RunRequest("synthetic", "unit", run_id="run-2"), client)

    assert first.status == second.status == "passed"
    assert first.workspace != second.workspace
    assert (_task().source_dir / "calculator.py").read_text(encoding="utf-8") == source_text
    assert first.artifact["workspace_manifest"]["diff"] == {
        "created": [],
        "modified": ["calculator.py"],
        "deleted": [],
    }
    for workspace in client.workspaces:
        assert not (workspace / "hidden").exists()


def test_evidence_records_native_profile_pairing_attempts_and_sanitized_trace(tmp_path: Path) -> None:
    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(), RunRequest("synthetic", "unit", run_id="evidence"), SyntheticClient()
    )

    artifact = evidence.as_dict()
    metadata = artifact["evaluation_metadata"]
    native = metadata["native_protocol"]
    assert artifact["artifact_contract_version"] == ARTIFACT_CONTRACT_VERSION
    assert metadata["profile"]["provider"] == "synthetic"
    assert metadata["source"]["native_gate_hash"] == "synthetic-gate-hash"
    assert native["call_result_pairs"] == [{"call_id": "call-1", "call_count": 1, "result_count": 1}]
    assert native["http_attempts"] == 1
    assert native["http_attempt_evidence"][0]["status_code"] == 200
    assert artifact["trace"][0]["authorization"] == REDACTED
    assert artifact["trace"][0]["reasoning"]["type"] == "str"
    assert "private chain" not in json.dumps(artifact)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FailureCategory.PROVIDER, "provider"),
        (FailureCategory.INFRASTRUCTURE, "infrastructure"),
    ],
)
def test_client_failure_taxonomy_is_preserved(
    tmp_path: Path, failure: FailureCategory, expected: str
) -> None:
    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(), RunRequest("synthetic", "unit", run_id=expected), SyntheticClient(failure=failure)
    )
    assert evidence.status == "failed"
    assert evidence.failure_category == expected


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ProviderFailure("provider unavailable"), "provider"),
        (InfrastructureFailure("worker unavailable"), "infrastructure"),
    ],
)
def test_typed_client_exceptions_are_recorded(
    tmp_path: Path, error: Exception, expected: str
) -> None:
    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(), RunRequest("synthetic", "unit", run_id=f"exception-{expected}"), RaisingClient(error)
    )
    assert evidence.failure_category == expected
    assert evidence.artifact["error"] == str(error)


def test_protocol_mismatch_has_distinct_failure_category(tmp_path: Path) -> None:
    class MismatchedClient(SyntheticClient):
        def run(self, workspace: Path, prompt: str) -> ClientResult:
            super().run(workspace, prompt)
            return _result(result_call_ids=("wrong-call",))

    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(), RunRequest("synthetic", "unit", run_id="protocol"), MismatchedClient()
    )
    assert evidence.failure_category == "protocol"
    errors = evidence.artifact["evaluation_metadata"]["native_protocol"]["protocol_errors"]
    assert any("missing tool results" in error for error in errors)
    assert any("unexpected tool results" in error for error in errors)


def test_verifier_failure_is_a_task_failure(tmp_path: Path) -> None:
    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(),
        RunRequest("synthetic", "unit", run_id="task-failure"),
        RaisingClient(ProviderFailure("provider unavailable")),
    )
    assert evidence.failure_category == "provider"
    assert evidence.artifact["verifier"]["passed"] is False


def test_formal_run_requires_tool_050_s_hash_before_creating_workspace(tmp_path: Path) -> None:
    runner = LocalLiveTaskRunner(tmp_path / "runs")
    with pytest.raises(ProtocolFailure, match="TOOL-050-S"):
        runner.run(_task(), RunRequest("formal", "unit", run_id="must-not-exist"), SyntheticClient())
    assert not (tmp_path / "runs").exists()


def test_formal_synthetic_run_records_tool_050_s_hash(tmp_path: Path) -> None:
    selection_hash = "a" * 64
    evidence = LocalLiveTaskRunner(tmp_path / "runs").run(
        _task(),
        RunRequest("formal", "unit", tool_050_s_hash=selection_hash, run_id="formal"),
        SyntheticClient(),
    )
    assert evidence.artifact["evaluation_metadata"]["source"]["tool_050_s_hash"] == selection_hash


def test_filters_work_without_the_final_taskset() -> None:
    task = _task()
    other = TaskSpec(
        task_id="other",
        repo_id="other-repo",
        prompt=task.prompt,
        source_dir=task.source_dir,
        verifier=task.verifier,
        run_kinds=("probe",),
        shard="other-shard",
    )
    tasks = [task, other]

    assert select_tasks(tasks, task_ids=["synthetic-add"]) == [task]
    assert select_tasks(tasks, repo_ids=["other-repo"]) == [other]
    assert select_tasks(tasks, run_kinds=["formal"]) == [task]
    assert select_tasks(tasks, shards=["other-shard"]) == [other]


def test_hidden_material_inside_public_source_is_rejected(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    verifier = public / "verifier.py"
    verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")
    task = TaskSpec("leaky", "repo", "prompt", public, verifier, shard="unit")

    with pytest.raises(InfrastructureFailure, match="outside"):
        LocalLiveTaskRunner(tmp_path / "runs").run(
            task, RunRequest("synthetic", "unit"), SyntheticClient()
        )
