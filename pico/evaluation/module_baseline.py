"""Build and verify Evaluation v2 deterministic module Artifact metadata."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .metrics import render_benchmark_core_report

COHORT_ID = "module-baseline-v1"
MODULE_PATHS = {
    "harness": Path("public/modules/harness-regression-v2.json"),
    "context": Path("public/modules/context-ablation-v2.json"),
    "memory": Path("public/modules/memory-ablation-v2.json"),
    "recovery": Path("public/modules/recovery-ablation-v2.json"),
}
REPORT_JSON_PATH = Path("reports/pico-module-baseline-v2.json")
REPORT_MARKDOWN_PATH = Path("reports/pico-module-baseline-v2.md")
CHECKSUMS_PATH = Path("public/modules/checksums.json")
CHECKSUMMED_PATHS = (*MODULE_PATHS.values(), REPORT_JSON_PATH)


def _require_source_sha(value: str, name: str) -> str:
    if (
        len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a full lowercase Git commit SHA")
    return value


def module_source_sha(output_root: str | Path) -> str:
    output_root = Path(output_root).resolve()
    if not output_root.is_dir():
        raise ValueError(f"module baseline root is not a directory: {output_root}")
    return _require_source_sha(output_root.name, "module baseline directory")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_module_checksums(output_root: str | Path) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    files = {}
    for relative_path in CHECKSUMMED_PATHS:
        path = output_root / relative_path
        if not path.is_file():
            raise ValueError(f"missing P1 artifact: {relative_path.as_posix()}")
        files[relative_path.as_posix()] = {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    return {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": files,
    }


def _load_json_object(path: Path, name: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {name}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{name} must contain a JSON object")
    return payload


def _verify_report_contract(report: Mapping[str, Any], source_sha: str) -> None:
    if report.get("schema_version") != 1:
        raise ValueError("unsupported module report schema")
    if report.get("artifact_type") != "pico-module-baseline-v2":
        raise ValueError("module report artifact_type is invalid")
    if report.get("cohort_id") != COHORT_ID:
        raise ValueError("report cohort_id does not identify module-baseline-v1")
    if report.get("source_sha") != source_sha:
        raise ValueError("report source_sha does not match the output directory")
    scope = report.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("module report scope must be an object")
    if scope.get("evidence_level") != "deterministic-module":
        raise ValueError("module report evidence_level is invalid")
    if scope.get("provider_http_requests") != 0:
        raise ValueError("module report must record zero provider HTTP requests")
    if scope.get("is_end_to_end_coding_result") is not False:
        raise ValueError("module report must not claim an end-to-end coding result")


def verify_module_baseline(
    output_root: str | Path,
    expected_source_sha: str | None = None,
) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    source_sha = module_source_sha(output_root)
    if expected_source_sha is not None:
        expected_source_sha = _require_source_sha(
            expected_source_sha, "expected_source_sha"
        )
        if source_sha != expected_source_sha:
            raise ValueError("module directory does not match expected_source_sha")

    checksums = _load_json_object(output_root / CHECKSUMS_PATH, "checksum manifest")
    if checksums.get("schema_version") != 1:
        raise ValueError("unsupported checksum manifest schema")
    if checksums.get("algorithm") != "sha256":
        raise ValueError("checksum manifest must use sha256")
    files = checksums.get("files")
    if not isinstance(files, Mapping):
        raise ValueError("checksum manifest files must be an object")

    expected_paths = {path.as_posix() for path in CHECKSUMMED_PATHS}
    if set(files) != expected_paths:
        raise ValueError(
            "checksum manifest paths differ from the fixed P1 artifact set"
        )
    for relative_path in CHECKSUMMED_PATHS:
        path = output_root / relative_path
        if not path.is_file():
            raise ValueError(f"missing P1 artifact: {relative_path.as_posix()}")
        record = files[relative_path.as_posix()]
        if not isinstance(record, Mapping):
            raise ValueError(
                f"checksum record must be an object: {relative_path.as_posix()}"
            )
        if record.get("sha256") != _sha256(path):
            raise ValueError(f"checksum mismatch: {relative_path.as_posix()}")
        if record.get("size_bytes") != path.stat().st_size:
            raise ValueError(f"size mismatch: {relative_path.as_posix()}")

    report = _load_json_object(output_root / REPORT_JSON_PATH, "module report")
    _verify_report_contract(report, source_sha)
    expected_markdown = render_benchmark_core_report(report)
    markdown_path = output_root / REPORT_MARKDOWN_PATH
    if not markdown_path.is_file():
        raise ValueError(f"missing P1 report: {REPORT_MARKDOWN_PATH.as_posix()}")
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise ValueError("Markdown report cannot be rebuilt from report JSON")

    return {
        "cohort_id": COHORT_ID,
        "source_sha": source_sha,
        "verified_json_files": len(CHECKSUMMED_PATHS),
        "markdown_rebuilt": True,
    }


__all__ = [
    "CHECKSUMMED_PATHS",
    "CHECKSUMS_PATH",
    "COHORT_ID",
    "MODULE_PATHS",
    "REPORT_JSON_PATH",
    "REPORT_MARKDOWN_PATH",
    "build_module_checksums",
    "module_source_sha",
    "verify_module_baseline",
]
