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
BINDING = ROOT / "benchmarks" / "v3" / "context-assets" / "cases-v3.binding.json"
EXPECTED_OID = "c3ca89d08163111f7612557a85e7ac477388378a"
EXPECTED_SHA256 = "6feadd16451408ff77596e8cabf357b2fc20eda8ea0c0934f5db35373346638d"
HISTORICAL_BINDING_OID = "3426371758b7bb9569680e271d3d782a486d2bd1"


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
    assert report["source_schema_version"] == "coda-context-asset-cases-v1"
    assert report["source_case_count"] == 15
    assert report["canonical_hash_basis"] == "git_blob_bytes"


def test_binding_records_the_historical_source_without_copying_its_schema() -> None:
    """The successor records only the immutable source ref, path, and blob."""

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    provenance = binding["provenance"]

    assert binding["schema_version"] == BINDING_SCHEMA_VERSION
    assert binding["binding_version"] == 3
    assert provenance == {
        "source_ref": "eval-v2/p5-integrated",
        "source_path_at_ref": "benchmarks/v3/context-assets/cases-v2.binding.json",
        "source_git_blob_oid": HISTORICAL_BINDING_OID,
    }
    assert (
        _git(
            ROOT,
            "rev-parse",
            f"{provenance['source_ref']}:{provenance['source_path_at_ref']}",
        )
        == HISTORICAL_BINDING_OID
    )


def test_crlf_checkout_does_not_change_canonical_binding(tmp_path: Path) -> None:
    """Covers verification from Git objects when checkout bytes use CRLF."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "context-freeze@example.invalid")
    _git(repo, "config", "user.name", "Context Freeze Test")
    source = repo / "cases.json"
    source.write_bytes(
        b'{\n  "schema_version": "coda-context-asset-cases-v1",\n  "cases": [{}]\n}\n'
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
    binding["provenance"] = {
        "source_ref": "HEAD",
        "source_path_at_ref": "cases.json",
        "source_git_blob_oid": oid,
    }
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
