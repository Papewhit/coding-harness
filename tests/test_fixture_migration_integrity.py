"""Guard the W5R protected-fixture migration against semantic test edits."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


CANONICAL_W5_BLOCKED_SHA = "a885581bb39b46f7f856b40cffdbbfbc3da0918a"
PROTECTED_TESTS = (
    "tests/test_tool_policy_acceptance.py",
    "tests/test_safety_invariants.py",
    "tests/test_permissions_acceptance.py",
)


def _protected_shape(source: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(source)
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assertions = [
        ast.dump(node.test, include_attributes=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
    ]
    return functions, assertions


def _canonical_source(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{CANONICAL_W5_BLOCKED_SHA}:{path}"],
        text=True,
        encoding="utf-8",
    )


def test_protected_test_names_and_assertion_asts_match_w5_blocked_snapshot():
    for relative_path in PROTECTED_TESTS:
        current = Path(relative_path).read_text(encoding="utf-8")
        assert _protected_shape(current) == _protected_shape(_canonical_source(relative_path))


def test_fixture_migration_has_no_global_or_legacy_test_adapter():
    assert not Path("tests/conftest.py").exists()
    protected_text = "\n".join(
        Path(relative_path).read_text(encoding="utf-8")
        for relative_path in PROTECTED_TESTS
    )
    assert "ScriptedModelClient" not in protected_text
    assert "<tool" not in protected_text
    assert "<final" not in protected_text
