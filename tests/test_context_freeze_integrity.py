from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts.verify_context_freeze import (
    BINDING_SCHEMA_VERSION,
    BindingVerificationError,
    verify_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "benchmarks" / "v3" / "context-assets" / "cases-v2.binding.json"
EXPECTED_OID = "5e9bdf06e75f6661660947e880f07edfe7480880"
EXPECTED_SHA256 = "e08066749520a52af5bb14a9435e359f4a85d3f3ae6e8dd0e962001f99c2df17"
INVALIDATED_SHA256 = "d69dfc1808cb12b179f8a1fb30ffa74136339d7783d9f11a5fbe8fd4259400ba"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def test_repository_binding_reconstructs_canonical_git_blob() -> None:
    """Covers OID, Git-blob SHA-256, schema, case count, and hash-basis binding."""

    report = verify_binding(BINDING, repo_root=ROOT)

    assert report["verified"] is True
    assert report["source_git_blob_oid"] == EXPECTED_OID
    assert report["source_git_blob_sha256"] == EXPECTED_SHA256
    assert report["source_schema_version"] == "pico-context-asset-cases-v1"
    assert report["source_case_count"] == 15
    assert report["canonical_hash_basis"] == "git_blob_bytes"


def test_binding_preserves_and_invalidates_the_historical_declaration() -> None:
    """Covers retention and explicit supersession of the unreproducible v1 digest."""

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    retained = binding["supersession"]["supersedes"]

    assert binding["schema_version"] == BINDING_SCHEMA_VERSION
    assert len(retained) == 1
    assert retained[0]["declared_sha256"] == INVALIDATED_SHA256
    assert retained[0]["status"] == "invalidated"
    assert retained[0]["superseded_by"] == BINDING_SCHEMA_VERSION
    assert retained[0]["invalidated_reason"]


def test_crlf_checkout_does_not_change_canonical_binding(tmp_path: Path) -> None:
    """Covers verification from Git objects when checkout bytes use CRLF."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "context-freeze@example.invalid")
    _git(repo, "config", "user.name", "Context Freeze Test")
    source = repo / "cases.json"
    source.write_bytes(
        b'{\n  "schema_version": "pico-context-asset-cases-v1",\n  "cases": [{}]\n}\n'
    )
    _git(repo, "add", "cases.json")
    _git(repo, "commit", "-m", "add cases")
    oid = _git(repo, "rev-parse", "HEAD:cases.json")
    blob = subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", oid])
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    binding["source"].update(
        {
            "path": "cases.json",
            "git_blob_oid": oid,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size_bytes": len(blob),
            "case_count": 1,
        }
    )
    binding_path = repo / "binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8", newline="\n")
    source.write_bytes(blob.replace(b"\n", b"\r\n"))

    report = verify_binding(binding_path, repo_root=repo)

    assert report["source_git_blob_sha256"] == hashlib.sha256(blob).hexdigest()
    assert report["checkout_file_sha256"] != report["source_git_blob_sha256"]
    assert report["checkout_matches_git_blob"] is False


def test_materialized_evaluator_input_is_exact_bound_blob(tmp_path: Path) -> None:
    """Covers evaluator input materialization from the verified object, not checkout bytes."""

    destination = tmp_path / "inputs" / "cases.json"
    report = verify_binding(BINDING, repo_root=ROOT, materialize=destination)

    assert report["materialized_path"] == str(destination.resolve())
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert _git(ROOT, "hash-object", str(destination)) == EXPECTED_OID


def test_verifier_rejects_a_digest_that_does_not_match_the_git_blob(tmp_path: Path) -> None:
    """Covers fail-closed behavior for a tampered canonical digest."""

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    binding["source"]["sha256"] = "0" * 64
    tampered = tmp_path / "binding.json"
    tampered.write_text(json.dumps(binding), encoding="utf-8")

    with pytest.raises(BindingVerificationError, match="Git blob SHA-256 mismatch"):
        verify_binding(tampered, repo_root=ROOT)
