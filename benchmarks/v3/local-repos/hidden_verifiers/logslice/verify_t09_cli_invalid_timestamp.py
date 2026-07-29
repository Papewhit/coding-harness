"""Hidden verifier for T09; invoke with the candidate repository as argv[1]."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_cli(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(workspace)
    return subprocess.run(
        [sys.executable, "-m", "logslice.cli", *arguments],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=3,
    )


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    invalid = run_cli(workspace, "--message", "hello", "--timestamp", "not-a-timestamp")
    if invalid.returncode != 2:
        raise AssertionError(f"invalid timestamp returned {invalid.returncode}, expected 2")
    if "invalid timestamp" not in invalid.stderr.lower():
        raise AssertionError("invalid timestamp error must be shown on stderr")
    if "traceback" in invalid.stderr.lower():
        raise AssertionError("invalid timestamp must not expose a traceback")
    valid = run_cli(workspace, "--message", "hello", "--timestamp", "2025-01-02T03:04:05Z")
    if valid.returncode != 0:
        raise AssertionError(f"valid timestamp failed: {valid.stderr}")
    if valid.stdout.strip() != "2025-01-02T03:04:05Z [INFO] hello":
        raise AssertionError("valid timestamp output changed unexpectedly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
