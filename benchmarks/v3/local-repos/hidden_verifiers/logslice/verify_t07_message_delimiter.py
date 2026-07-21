"""Hidden verifier for T07; invoke with the candidate repository as argv[1]."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(workspace))
    from logslice.formatter import format_record
    from logslice.record import LogRecord

    record = LogRecord(
        timestamp=datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        level="info",
        message="worker started",
    )
    actual = format_record(record)
    expected = "2025-01-02T03:04:05Z [INFO] | worker started"
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
