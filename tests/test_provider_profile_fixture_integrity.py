"""Guard the W5R2 scripted-native provider-profile fixture migration."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from pico import Pico, SessionStore, WorkspaceContext
from tests.native_fixtures import (
    SCRIPTED_NATIVE_PROFILE_ID,
    final,
    lock_scripted_provider_profile,
    scripted_client,
    scripted_provider_identity,
    scripted_provider_profile,
)


W5R2_BASE_SHAPE_SHA256 = {
    "tests/test_pico.py": "8461659c7937216ef9816cfcf5ebf8b39e841b8c1f4d4d0ed08a5a518a3dd124",
    "tests/test_engine_acceptance.py": "4666877295920444172d4eed68104a477ba88c80b07e8db19b47cf02b811046c",
    "tests/test_context_governance_acceptance.py": "e88ee1cda9d9da79ba4992405942a10c1b4d62aa26832b10ae59730b1184cf4b",
    "tests/test_release_smoke.py": "a6e46da4f1a0fa635f75cee56f2ccb5f29bf60371d4aaf1e83172e14fed6767a",
    "tests/test_v3_runtime.py": "d7384c818b42428996f4945717a956b00d7758eb62ca8370abd4eafdf4b7d333",
    "tests/test_skills_acceptance.py": "f48ba3d180170c91a7a8b7b5a4dadfa8847e469ca2362b5be3751c90d2364075",
    "tests/test_runtime_evidence_acceptance.py": "66ccb6ec58c51ced65885000f05713c36576988bbf0749b6e86a2892ee6fb86a",
    "tests/test_usage.py": "097c3f36738614a60b0d4c2c75eb6ae75a0085c6a60ba4ea9eed6c9aaa0078d5",
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


def _agent(tmp_path: Path, *, lock_profile: bool) -> Pico:
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    agent = Pico(
        model_client=scripted_client([final("Done.")]),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".pico" / "sessions"),
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
    assert agent.model_client._pico_profile_identity == scripted_provider_identity()
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
