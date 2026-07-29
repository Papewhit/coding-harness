from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Mapping


BINDING_SCHEMA_VERSION = "coda-context-asset-cases-binding-v3"


class BindingVerificationError(ValueError):
    """Raised when a Context freeze binding cannot be reconstructed."""


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise BindingVerificationError(f"{key} must be an object")
    return value


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BindingVerificationError(f"{key} must be a non-empty string")
    return value


def _git(repo_root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args], stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.output.decode("utf-8", errors="replace").strip()
        raise BindingVerificationError(f"git {' '.join(args)} failed: {detail}") from exc


def _repository_root(binding_path: Path, repo_root: str | Path | None) -> Path:
    if repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        root = Path(
            _git(binding_path.parent, "rev-parse", "--show-toplevel")
            .decode("utf-8")
            .strip()
        ).resolve()
    if not (root / ".git").exists() and not (root / ".git").is_file():
        raise BindingVerificationError(f"not a Git worktree: {root}")
    return root


def _safe_repo_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BindingVerificationError("source.path must be a repository-relative POSIX path")
    return path.as_posix()


def verify_binding(
    binding_path: str | Path,
    *,
    repo_root: str | Path | None = None,
    revision: str | None = None,
    materialize: str | Path | None = None,
) -> dict[str, Any]:
    """Verify a binding from Git object bytes and optionally materialize those bytes."""

    binding_file = Path(binding_path).resolve()
    try:
        binding_bytes = binding_file.read_bytes()
        binding = json.loads(binding_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise BindingVerificationError(f"cannot read binding: {exc}") from exc
    if not isinstance(binding, Mapping):
        raise BindingVerificationError("binding must be an object")
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        raise BindingVerificationError(
            f"schema_version must be {BINDING_SCHEMA_VERSION!r}"
        )
    if binding.get("binding_version") != 3:
        raise BindingVerificationError("binding_version must be 3")

    source = _required_mapping(binding, "source")
    source_path = _safe_repo_path(_required_string(source, "path"))
    expected_oid = _required_string(source, "git_blob_oid")
    expected_sha256 = _required_string(source, "sha256")
    if source.get("hash_basis") != "git_blob_bytes":
        raise BindingVerificationError("source.hash_basis must be 'git_blob_bytes'")
    selected_revision = revision or _required_string(source, "revision")
    root = _repository_root(binding_file, repo_root)

    actual_oid = (
        _git(root, "rev-parse", f"{selected_revision}:{source_path}")
        .decode("ascii")
        .strip()
    )
    if actual_oid != expected_oid:
        raise BindingVerificationError(
            f"Git blob OID mismatch: expected {expected_oid}, got {actual_oid}"
        )
    blob_bytes = _git(root, "cat-file", "blob", actual_oid)
    blob_sha256 = hashlib.sha256(blob_bytes).hexdigest()
    if blob_sha256 != expected_sha256:
        raise BindingVerificationError(
            f"Git blob SHA-256 mismatch: expected {expected_sha256}, got {blob_sha256}"
        )
    if len(blob_bytes) != source.get("size_bytes"):
        raise BindingVerificationError(
            f"Git blob size mismatch: expected {source.get('size_bytes')}, got {len(blob_bytes)}"
        )

    try:
        cases_payload = json.loads(blob_bytes)
    except json.JSONDecodeError as exc:
        raise BindingVerificationError(f"bound Git blob is not valid JSON: {exc}") from exc
    if not isinstance(cases_payload, Mapping):
        raise BindingVerificationError("bound cases payload must be an object")
    if cases_payload.get("schema_version") != source.get("content_schema_version"):
        raise BindingVerificationError("bound cases schema does not match the binding")
    cases = cases_payload.get("cases")
    if not isinstance(cases, list) or len(cases) != source.get("case_count"):
        raise BindingVerificationError("bound case count does not match the binding")

    checkout_path = root / Path(source_path)
    checkout_bytes = checkout_path.read_bytes() if checkout_path.is_file() else None
    checkout_sha256 = (
        hashlib.sha256(checkout_bytes).hexdigest() if checkout_bytes is not None else None
    )
    materialized_path = None
    if materialize is not None:
        destination = Path(materialize).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob_bytes)
        materialized_path = str(destination)

    provenance = _required_mapping(binding, "provenance")
    source_ref = _required_string(provenance, "source_ref")
    source_path_at_ref = _safe_repo_path(
        _required_string(provenance, "source_path_at_ref")
    )
    expected_source_oid = _required_string(provenance, "source_git_blob_oid")
    actual_source_oid = (
        _git(root, "rev-parse", f"{source_ref}:{source_path_at_ref}")
        .decode("ascii")
        .strip()
    )
    if actual_source_oid != expected_source_oid:
        raise BindingVerificationError(
            "historical source Git blob OID mismatch: "
            f"expected {expected_source_oid}, got {actual_source_oid}"
        )

    return {
        "schema_version": "coda-context-asset-binding-verification-v1",
        "verified": True,
        "binding_path": str(binding_file),
        "binding_file_sha256": hashlib.sha256(binding_bytes).hexdigest(),
        "repo_root": str(root),
        "revision": selected_revision,
        "source_path": source_path,
        "source_git_blob_oid": actual_oid,
        "source_git_blob_sha256": blob_sha256,
        "source_git_blob_size": len(blob_bytes),
        "source_schema_version": cases_payload["schema_version"],
        "source_case_count": len(cases),
        "checkout_file_sha256": checkout_sha256,
        "checkout_matches_git_blob": checkout_bytes == blob_bytes,
        "canonical_hash_basis": "git_blob_bytes",
        "provenance_source_ref": source_ref,
        "provenance_source_path": source_path_at_ref,
        "provenance_source_git_blob_oid": actual_source_oid,
        "provenance_verified": True,
        "materialized_path": materialized_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a versioned Context cases binding from canonical Git blob bytes."
    )
    parser.add_argument("--binding", required=True, help="Path to the v3 binding JSON.")
    parser.add_argument("--repo-root", help="Git worktree root; auto-detected by default.")
    parser.add_argument("--revision", help="Revision to verify instead of binding source.revision.")
    parser.add_argument(
        "--materialize", help="Write the exact verified Git blob bytes to this path."
    )
    parser.add_argument("--report", help="Write the verification report as JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = verify_binding(
            args.binding,
            repo_root=args.repo_root,
            revision=args.revision,
            materialize=args.materialize,
        )
    except BindingVerificationError as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
