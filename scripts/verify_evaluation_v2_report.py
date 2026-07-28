#!/usr/bin/env python3
"""Read and deterministically verify the final Evaluation v2 report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pico.evaluation.evaluation_report import verify_evaluation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--module-root", required=True, type=Path)
    parser.add_argument("--publish-doc", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = verify_evaluation_report(
        args.run_config,
        args.module_root,
        args.publish_doc,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
