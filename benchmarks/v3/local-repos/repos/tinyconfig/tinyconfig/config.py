"""Load a small application configuration from environment-style mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ConfigError(ValueError):
    """Raised when configuration cannot be converted to the expected type."""


@dataclass(frozen=True)
class Settings:
    debug: bool
    database_host: str
    database_port: int


def _read_value(values: Mapping[str, str], key: str, default: str) -> str:
    return values.get(key, default)


def load_settings(values: Mapping[str, str]) -> Settings:
    """Build settings from a mapping such as ``os.environ``.

    Values are supplied as strings so callers can use this function without
    mutating the process environment.
    """

    debug = bool(_read_value(values, "APP_DEBUG", "false"))
    database_host = _read_value(values, "DATABASE_HOST", "localhost")
    database_port_text = _read_value(values, "DATABASE_PORT", "5432")

    try:
        database_port = int(database_port_text)
    except ValueError as error:
        raise ConfigError(f"DATABASE_PORT must be an integer; got {database_port_text!r}") from error

    if not 1 <= database_port <= 65535:
        raise ConfigError(f"DATABASE_PORT must be between 1 and 65535; got {database_port}")

    return Settings(
        debug=debug,
        database_host=database_host,
        database_port=database_port,
    )
