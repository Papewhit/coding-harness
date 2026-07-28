#!/usr/bin/env python3
"""Finalize or verify Evaluation v2 P3 Pilot audits and reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from pico.config import resolve_provider_config
from pico.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV
from pico.evaluation.pilot_report import (
    finalize_pilot,
    initialize_pilot,
    verify_pilot,
)


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--audit-input", action="append", default=[], type=Path)
    parser.add_argument("--user-decision-input", action="append", default=[], type=Path)
    parser.add_argument("--initialize-report", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify_only:
        if args.audit_input or args.user_decision_input or args.initialize_report:
            raise SystemExit(
                "--verify-only cannot accept audit, decision, or initialization inputs"
            )
        result = verify_pilot(args.run_config)
    elif args.initialize_report:
        if args.audit_input or args.user_decision_input:
            raise SystemExit(
                "--initialize-report cannot accept audit or decision inputs"
            )
        result = initialize_pilot(
            args.run_config,
            generator=_generator_identity(),
        )
    else:
        if not args.audit_input and not args.user_decision_input:
            raise SystemExit("finalization requires an audit or user-decision input")
        result = finalize_pilot(
            args.run_config,
            audit_inputs=args.audit_input,
            decision_inputs=args.user_decision_input,
            sensitive_values=_sensitive_values(args.run_config),
            generator=_generator_identity(),
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


def _generator_identity() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    script = Path(__file__).resolve()
    return {
        "commit": commit,
        "script": script.relative_to(ROOT).as_posix(),
        "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
