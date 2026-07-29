"""Command-line interface for rendering one log record."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Sequence

from .formatter import format_record
from .record import LogRecord, parse_timestamp


def build_parser() -> argparse.ArgumentParser:
    """Build the parser separately so integrations can inspect its options."""

    parser = argparse.ArgumentParser(prog="logslice")
    parser.add_argument("--message", required=True, help="text to put in the log record")
    parser.add_argument("--level", default="INFO", help="severity level, such as INFO")
    parser.add_argument(
        "--timestamp",
        help="ISO-8601 timestamp; defaults to the current UTC time",
    )
    return parser


def record_from_args(args: argparse.Namespace) -> LogRecord:
    """Turn parsed CLI arguments into a normalized record."""

    timestamp = parse_timestamp(args.timestamp) if args.timestamp else datetime.now(timezone.utc)
    return LogRecord(timestamp=timestamp, level=args.level, message=args.message)


def main(argv: Sequence[str] | None = None) -> int:
    """Render one record and return a conventional process status."""

    args = build_parser().parse_args(argv)
    record = record_from_args(args)
    print(format_record(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
