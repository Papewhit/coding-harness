"""Build a canonical sanitized native-provider profile manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coda.evaluation.native_provider_profiles import (  # noqa: E402
    resolve_public_provider_profile,
    write_public_provider_profile,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a named local Coda provider and write its canonical, "
            "credential-free public evaluation profile."
        )
    )
    parser.add_argument(
        "--provider",
        required=True,
        help="Named provider profile resolved by Coda's existing config resolver.",
    )
    parser.add_argument(
        "--manifest-out",
        required=True,
        help="Destination for canonical sanitized JSON.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional Coda config TOML path; credentials are never written.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    profile = resolve_public_provider_profile(
        args.provider,
        start=Path.cwd(),
        config_path=args.config,
    )
    write_public_provider_profile(args.manifest_out, profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
