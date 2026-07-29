#!/usr/bin/env python3
"""Finalize or verify Evaluation v2 P4 baseline audits and summaries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from coda.config import resolve_provider_config
from coda.evaluation.baseline_summary import (
    STAGE_TASKS,
    finalize_baseline,
    verify_baseline,
)
from coda.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=tuple(STAGE_TASKS))
    parser.add_argument("--audit-input", action="append", default=[], type=Path)
    parser.add_argument("--user-decision-input", action="append", default=[], type=Path)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify_only:
        if args.audit_input or args.user_decision_input:
            raise SystemExit("--verify-only cannot accept audit or decision inputs")
        result = verify_baseline(args.run_config, stage=args.stage)
    else:
        if not args.audit_input and not args.user_decision_input:
            raise SystemExit("finalization requires an audit or user-decision input")
        result = finalize_baseline(
            args.run_config,
            stage=args.stage,
            audit_inputs=args.audit_input,
            decision_inputs=args.user_decision_input,
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
