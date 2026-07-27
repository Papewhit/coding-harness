#!/usr/bin/env python3
"""Run and verify the offline Evaluation v2 deterministic module baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pico.evaluation.evaluator import run_harness_regression_v2
from pico.evaluation.metrics import (
    render_benchmark_core_report,
    run_context_ablation_v2,
    run_memory_ablation_v2,
    run_recovery_ablation_v2,
    write_benchmark_core_report,
)

COHORT_ID = "module-baseline-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
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


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def repository_source_sha() -> str:
    source_sha = _run_git("rev-parse", "HEAD")
    if len(source_sha) != 40:
        raise RuntimeError("git HEAD is not a full commit SHA")
    return source_sha


def require_clean_checkout() -> None:
    if _run_git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Evaluation v2 module baseline requires a clean checkout")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_source_directory(output_root: Path, source_sha: str) -> None:
    if output_root.name != source_sha:
        raise ValueError(
            "output-root must end with the current full source SHA "
            f"({source_sha}), got {output_root.name}"
        )


def _prepare_output_root(output_root: Path, source_sha: str) -> None:
    _validate_source_directory(output_root, source_sha)
    if output_root.exists():
        if not output_root.is_dir():
            raise ValueError(f"output-root is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise ValueError(f"output-root must be absent or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "public" / "modules").mkdir(parents=True, exist_ok=True)
    (output_root / "reports").mkdir(parents=True, exist_ok=True)


def _build_checksums(output_root: Path) -> dict[str, Any]:
    files = {}
    for relative_path in CHECKSUMMED_PATHS:
        path = output_root / relative_path
        files[relative_path.as_posix()] = {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    return {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": files,
    }


def verify_module_baseline(output_root: Path, source_sha: str) -> dict[str, Any]:
    output_root = output_root.resolve()
    _validate_source_directory(output_root, source_sha)
    checksums_path = output_root / CHECKSUMS_PATH
    if not checksums_path.is_file():
        raise ValueError(f"missing checksum manifest: {checksums_path}")
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    if checksums.get("schema_version") != 1:
        raise ValueError("unsupported checksum manifest schema")
    if checksums.get("algorithm") != "sha256":
        raise ValueError("checksum manifest must use sha256")

    expected_paths = {path.as_posix() for path in CHECKSUMMED_PATHS}
    recorded_paths = set(checksums.get("files", {}))
    if recorded_paths != expected_paths:
        raise ValueError(
            "checksum manifest paths differ from the fixed P1 artifact set"
        )
    for relative_path in CHECKSUMMED_PATHS:
        path = output_root / relative_path
        if not path.is_file():
            raise ValueError(f"missing P1 artifact: {relative_path.as_posix()}")
        record = checksums["files"][relative_path.as_posix()]
        if record.get("sha256") != _sha256(path):
            raise ValueError(f"checksum mismatch: {relative_path.as_posix()}")
        if record.get("size_bytes") != path.stat().st_size:
            raise ValueError(f"size mismatch: {relative_path.as_posix()}")

    report_json_path = output_root / REPORT_JSON_PATH
    report = json.loads(report_json_path.read_text(encoding="utf-8"))
    if report.get("cohort_id") != COHORT_ID:
        raise ValueError("report cohort_id does not identify module-baseline-v1")
    if report.get("source_sha") != source_sha:
        raise ValueError("report source_sha does not match the output directory")
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


def run_module_baseline(output_root: Path, source_sha: str) -> dict[str, Any]:
    output_root = output_root.resolve()
    _prepare_output_root(output_root, source_sha)
    module_root = output_root / "public" / "modules"
    reports_root = output_root / "reports"

    with tempfile.TemporaryDirectory(prefix="pico-evaluation-v2-modules-") as temp_dir:
        run_harness_regression_v2(
            benchmark_path=REPO_ROOT / "benchmarks" / "coding_tasks.json",
            artifact_path=module_root / MODULE_PATHS["harness"].name,
            workspace_root=Path(temp_dir) / "harness",
        )
    run_context_ablation_v2(
        artifact_path=module_root / MODULE_PATHS["context"].name,
        repetitions=5,
    )
    run_memory_ablation_v2(
        artifact_path=module_root / MODULE_PATHS["memory"].name,
        repetitions=5,
    )
    run_recovery_ablation_v2(
        artifact_path=module_root / MODULE_PATHS["recovery"].name,
        repetitions=3,
    )
    write_benchmark_core_report(
        report_path=reports_root / REPORT_MARKDOWN_PATH.name,
        report_json_path=reports_root / REPORT_JSON_PATH.name,
        harness_artifact_path=output_root / MODULE_PATHS["harness"],
        context_artifact_path=output_root / MODULE_PATHS["context"],
        memory_artifact_path=output_root / MODULE_PATHS["memory"],
        recovery_artifact_path=output_root / MODULE_PATHS["recovery"],
        cohort_id=COHORT_ID,
        source_sha=source_sha,
        artifact_root=output_root,
    )
    _write_json(output_root / CHECKSUMS_PATH, _build_checksums(output_root))
    return verify_module_baseline(output_root, source_sha)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an existing P1 module baseline without running evaluators",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    require_clean_checkout()
    source_sha = repository_source_sha()
    if args.verify_only:
        result = verify_module_baseline(args.output_root, source_sha)
    else:
        result = run_module_baseline(args.output_root, source_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
