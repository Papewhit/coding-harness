#!/usr/bin/env python3
"""Run the native provider conformance suite through an external runner plugin."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.native_provider import (  # noqa: E402
    load_case_set,
    run_native_provider_conformance,
    write_native_provider_artifact,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run eight native provider conformance cases; no process-restart coverage."
    )
    parser.add_argument("--cases", required=True, help="Frozen eight-case manifest.")
    parser.add_argument("--profile", required=True, help="Public provider profile JSON.")
    parser.add_argument(
        "--runner-plugin",
        required=True,
        help="Callable case runner as module:attribute; receives (case, profile).",
    )
    parser.add_argument("--output", required=True, help="Destination artifact JSON.")
    parser.add_argument("--case", action="append", dest="case_ids", help="Case ID to run.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_case_set(args.cases)
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("provider profile must be an object")
    runner = _load_runner(args.runner_plugin)
    artifact = run_native_provider_conformance(
        case_set=cases,
        profile=profile,
        runner=runner,
        case_ids=args.case_ids,
    )
    write_native_provider_artifact(args.output, artifact)
    print(json.dumps(artifact["summary"], sort_keys=True))
    return 0 if artifact["summary"]["failed"] == 0 and artifact["summary"]["infrastructure_failure"] == 0 else 1


def _load_runner(spec: str) -> Any:
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("runner plugin must use module:attribute syntax")
    runner = getattr(importlib.import_module(module_name), attribute_name)
    if not callable(runner):
        raise TypeError(f"runner plugin {spec} must be callable")
    return runner


if __name__ == "__main__":
    raise SystemExit(main())
