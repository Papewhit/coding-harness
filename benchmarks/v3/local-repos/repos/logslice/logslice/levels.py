"""Severity-level helpers shared by the formatter and CLI."""

from __future__ import annotations

import logging


LEVEL_NAMES = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def normalize_level(value: str) -> str:
    """Return a canonical level name or raise a useful ValueError."""

    normalized = value.strip().upper()
    if normalized not in LEVEL_NAMES:
        choices = ", ".join(LEVEL_NAMES)
        raise ValueError(f"unknown log level {value!r}; expected one of {choices}")
    return normalized


def level_number(value: str) -> int:
    """Translate a user-facing level name into the logging numeric value."""

    return LEVEL_NAMES[normalize_level(value)]


def is_enabled(record_level: str, minimum_level: str) -> bool:
    """Whether a record at ``record_level`` is visible at the configured floor."""

    return level_number(record_level) >= level_number(minimum_level)
