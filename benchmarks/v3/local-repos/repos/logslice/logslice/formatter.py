"""Rendering and standard-library logger configuration."""

from __future__ import annotations

import logging

from .levels import level_number
from .record import LogRecord, display_timestamp


def format_record(record: LogRecord) -> str:
    """Return the compact one-line representation of ``record``.

    The header is deliberately kept stable because people use it in shell
    output and small text-processing scripts.
    """

    timestamp = display_timestamp(record.timestamp)
    return f"{timestamp} [{record.level}] {record.message}"


def configure_logger(name: str, minimum_level: str = "INFO") -> logging.Logger:
    """Create an isolated logger with a stream handler when it has none."""

    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
        logger.addHandler(handler)
    return logger


def emit_if_enabled(logger: logging.Logger, record: LogRecord, minimum_level: str) -> bool:
    """Emit a rendered record only when the configured logger allows it."""

    numeric_level = level_number(record.level)
    if numeric_level < level_number(minimum_level):
        return False
    logger.log(numeric_level, format_record(record))
    return True
