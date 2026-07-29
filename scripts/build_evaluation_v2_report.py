#!/usr/bin/env python3
"""Build the final Evaluation v2 report without running provider tasks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pico.config import resolve_provider_config
from pico.evaluation.evaluation_report import write_evaluation_report
from pico.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--module-root", required=True, type=Path)
    parser.add_argument("--publish-doc", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = write_evaluation_report(
        args.run_config,
        args.module_root,
        args.publish_doc,
        sensitive_values=_sensitive_values(args.run_config),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _sensitive_values(run_config_path: Path) -> tuple[str, ...]:
    locator = os.environ.get(CONFIG_LOCATOR_ENV, "")
    if not locator or not Path(locator).is_file():
        raise SystemExit(f"{CONFIG_LOCATOR_ENV} must identify an existing file")
    config_payload = json.loads(run_config_path.read_text(encoding="utf-8"))
    profile = config_payload["profile"]["public_profile"]
    provider = resolve_provider_config(
        str(profile["provider"]),
        start=ROOT,
        config_path=locator,
    )
    return tuple(value for value in (locator, provider.api_key) if value)


if __name__ == "__main__":
    raise SystemExit(main())
