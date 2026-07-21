#!/usr/bin/env python3
"""Run an SDK viability probe using externally supplied transport plugins."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.sdk_probe import (  # noqa: E402
    ProbeProfile,
    load_probe_cases,
    load_probe_profile,
    run_sdk_viability_probe,
    write_probe_artifact,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run provider-neutral native-tool viability cases. Install a temporary SDK with "
            "`uv run --with package==version` and provide local dialect/transport factories."
        )
    )
    parser.add_argument("--cases", required=True, help="Probe case-set JSON path.")
    parser.add_argument("--profile", required=True, help="Provider profile JSON path.")
    parser.add_argument("--dialect-plugin", required=True, help="Dialect factory as module:attribute.")
    parser.add_argument("--transport-plugin", required=True, help="Transport factory as module:attribute.")
    parser.add_argument("--output", required=True, help="Sanitized output artifact JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    profile = load_probe_profile(args.profile)
    cases = load_probe_cases(args.cases)
    dialect = _instantiate(args.dialect_plugin, profile)
    transport = _instantiate(args.transport_plugin, profile)
    artifact = run_sdk_viability_probe(
        cases=cases,
        profile=profile,
        dialect=dialect,
        transport=transport,
    )
    write_probe_artifact(args.output, artifact)
    return 0 if artifact["summary"]["failed"] == 0 else 1


def _instantiate(spec: str, profile: ProbeProfile) -> Any:
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("plugin must use module:attribute syntax")
    component = getattr(importlib.import_module(module_name), attribute_name)
    if not callable(component):
        raise TypeError(f"plugin {spec} must be callable")
    return component(profile)


if __name__ == "__main__":
    raise SystemExit(main())
