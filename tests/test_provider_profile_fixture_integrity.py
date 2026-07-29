"""Guard the W5R2 scripted-native provider-profile fixture migration."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from coda import Coda, SessionStore, WorkspaceContext
from tests.native_fixtures import (
    SCRIPTED_NATIVE_PROFILE_ID,
    final,
    lock_scripted_provider_profile,
    scripted_client,
    scripted_provider_identity,
    scripted_provider_profile,
)


W5R2_BASE_SHAPE_SHA256 = {
    "tests/test_coda.py": "364028d27a0b112c34158089e9464e7c1d248e916ba3f6f804c7b1ecdeaa3381",
    "tests/test_engine_acceptance.py": "4666877295920444172d4eed68104a477ba88c80b07e8db19b47cf02b811046c",
    "tests/test_context_governance_acceptance.py": "e88ee1cda9d9da79ba4992405942a10c1b4d62aa26832b10ae59730b1184cf4b",
    "tests/test_release_smoke.py": "31b07fa25094b72f7bb78b951633b9986ac95e970fd8d8d2f96057af04d2844f",
    "tests/test_v3_runtime.py": "f254a5dcf75f058074533d463818cf2c874b142e0216461a0cfddb15850998e8",
    "tests/test_skills_acceptance.py": "6f14678fd8a7854fc7ec2635161cd5c21484722c14ef0fd631b3013c7fefcff6",
    "tests/test_runtime_evidence_acceptance.py": "66ccb6ec58c51ced65885000f05713c36576988bbf0749b6e86a2892ee6fb86a",
    "tests/test_usage.py": "9894b797d4d906504bfcd0dfb5a16672dcd014b2c21ac5e95a8ed6e25a158b8c",
    "tests/test_todo_ledger_acceptance.py": "a6c35667cf632bc72334a23ebd57af7a0adcfb2b10843abf8f778c1e154d749d",
}
MIGRATED_TESTS = tuple(W5R2_BASE_SHAPE_SHA256)


def _test_shape(source: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(source)
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assertions = [
        ast.dump(node.test, include_attributes=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
    ]
    return functions, assertions


def _shape_sha256(source: str) -> str:
    payload = json.dumps(_test_shape(source), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _agent(tmp_path: Path, *, lock_profile: bool) -> Coda:
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    agent = Coda(
        model_client=scripted_client([final("Done.")]),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".coda" / "sessions"),
        approval_policy="auto",
    )
    if lock_profile:
        return lock_scripted_provider_profile(agent)
    agent.session.pop("provider_profile")
    agent.session_path = agent.session_store.save(agent.session)
    return agent


def test_migrated_test_names_and_assertion_asts_match_w5r2_base():
    for relative_path in MIGRATED_TESTS:
        current = Path(relative_path).read_text(encoding="utf-8")
        assert _shape_sha256(current) == W5R2_BASE_SHAPE_SHA256[relative_path]


def test_scripted_profile_matches_runtime_tool_schema_and_is_json_safe(tmp_path):
    agent = _agent(tmp_path, lock_profile=True)
    profile = agent.session["provider_profile"]

    assert profile == scripted_provider_profile(agent)
    assert agent.model_client._coda_profile_identity == scripted_provider_identity()
    assert profile["profile_id"] == SCRIPTED_NATIVE_PROFILE_ID
    assert profile["tool_schema"] == agent.tool_signature()
    assert json.loads(json.dumps(agent.session))["provider_profile"] == profile


def test_native_runtime_rejects_missing_scripted_provider_profile(tmp_path):
    agent = _agent(tmp_path, lock_profile=False)

    with pytest.raises(
        ValueError, match="native Runtime requires a locked provider_profile"
    ):
        agent.ask("prove the negative control")


def test_migration_does_not_restore_global_or_legacy_adapters():
    assert not Path("tests/conftest.py").exists()
    migrated_text = "\n".join(
        Path(relative_path).read_text(encoding="utf-8")
        for relative_path in MIGRATED_TESTS
    )
    assert "ScriptedModelClient" not in migrated_text
    assert "pytest_" + "collection" not in migrated_text
    assert "NativeSessionRecorder" not in migrated_text
    assert "<tool" not in migrated_text
    assert "<final" not in migrated_text
