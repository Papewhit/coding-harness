"""Hidden verifier for T08; invoke with the candidate repository as argv[1]."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from uuid import uuid4


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(workspace))
    from logslice.formatter import configure_logger

    logger = configure_logger(f"logslice-hidden-{uuid4()}", "warning")
    if logger.getEffectiveLevel() != logging.WARNING:
        raise AssertionError("minimum_level='warning' must configure WARNING")
    if logger.propagate:
        raise AssertionError("configured logger must not propagate")
    if len(logger.handlers) != 1:
        raise AssertionError("configured logger must retain one handler")
    try:
        configure_logger(f"logslice-hidden-{uuid4()}", "not-a-level")
    except ValueError as error:
        if "unknown log level" not in str(error):
            raise AssertionError("invalid level error should explain the problem") from error
    else:
        raise AssertionError("invalid minimum level must raise ValueError")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
