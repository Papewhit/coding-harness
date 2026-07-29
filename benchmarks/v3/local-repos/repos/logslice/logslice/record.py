"""Data model and timestamp conversion for a single log record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .levels import normalize_level


@dataclass(frozen=True)
class LogRecord:
    """A normalized record ready for rendering."""

    timestamp: datetime
    level: str
    message: str

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("log message must not be empty")
        object.__setattr__(self, "level", normalize_level(self.level))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))


def normalize_timestamp(value: datetime) -> datetime:
    """Convert a timestamp to UTC without losing the instant it represents."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    """Parse the ISO-8601 form accepted by the command-line interface."""

    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return normalize_timestamp(datetime.fromisoformat(value))


def display_timestamp(value: datetime) -> str:
    """Render timestamps in the stable wire format used by logslice."""

    normalized = normalize_timestamp(value)
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")
