#!/usr/bin/env python3
"""Run and verify the offline Evaluation v2 deterministic module baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from coda.evaluation.evaluator import run_harness_regression_v2
from coda.evaluation.module_baseline import (
    CHECKSUMS_PATH,
    COHORT_ID,
    MODULE_PATHS,
    REPORT_JSON_PATH,
    REPORT_MARKDOWN_PATH,
    build_module_checksums,
    verify_module_baseline,
)
from coda.evaluation.metrics import (
    run_context_ablation_v2,
    run_memory_ablation_v2,
    run_recovery_ablation_v2,
    write_benchmark_core_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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
    if (
        len(source_sha) != 40
        or any(character not in "0123456789abcdef" for character in source_sha)
    ):
        raise RuntimeError("git HEAD is not a full lowercase commit SHA")
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


def run_module_baseline(output_root: Path, source_sha: str) -> dict[str, Any]:
    output_root = output_root.resolve()
    _prepare_output_root(output_root, source_sha)
    module_root = output_root / "public" / "modules"
    reports_root = output_root / "reports"

    with tempfile.TemporaryDirectory(prefix="coda-evaluation-v2-modules-") as temp_dir:
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
    _write_json(output_root / CHECKSUMS_PATH, build_module_checksums(output_root))
    return verify_module_baseline(output_root, expected_source_sha=source_sha)


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
    if args.verify_only:
        result = verify_module_baseline(args.output_root)
    else:
        require_clean_checkout()
        source_sha = repository_source_sha()
        result = run_module_baseline(args.output_root, source_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
