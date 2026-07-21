"""Schema metadata for the configuration values understood by tinyconfig.

The loader intentionally keeps parsing close to the application-facing API.
This module supplies metadata for callers that want to render a configuration
reference, generate a sample environment file, or inspect supported fields
without importing implementation details from :mod:`tinyconfig.config`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FieldSpec:
    """A single documented configuration field.

    ``environment_key`` is the flat spelling used by environment mappings.
    ``section`` and ``name`` describe the optional nested mapping spelling.
    """

    environment_key: str
    section: str
    name: str
    default: str
    description: str
    required: bool = False

    @property
    def nested_path(self) -> tuple[str, str]:
        """Return the path used by structured configuration mappings."""

        return (self.section, self.name)

    def example_line(self) -> str:
        """Return a commented environment-file entry for documentation."""

        return f"{self.environment_key}={self.default}"


APP_DEBUG = FieldSpec(
    environment_key="APP_DEBUG",
    section="app",
    name="debug",
    default="false",
    description="Enable application debug mode.",
)

DATABASE_HOST = FieldSpec(
    environment_key="DATABASE_HOST",
    section="database",
    name="host",
    default="localhost",
    description="Hostname of the application database.",
)

DATABASE_PORT = FieldSpec(
    environment_key="DATABASE_PORT",
    section="database",
    name="port",
    default="5432",
    description="TCP port of the application database.",
)


DEFAULT_SCHEMA: tuple[FieldSpec, ...] = (
    APP_DEBUG,
    DATABASE_HOST,
    DATABASE_PORT,
)


def iter_fields() -> Iterable[FieldSpec]:
    """Yield fields in the stable order used by generated documentation."""

    return iter(DEFAULT_SCHEMA)


def field_for_environment_key(key: str) -> FieldSpec | None:
    """Return the specification for a flat environment key, if supported."""

    for field in DEFAULT_SCHEMA:
        if field.environment_key == key:
            return field
    return None


def field_for_nested_path(section: str, name: str) -> FieldSpec | None:
    """Return the specification for a nested key, if supported."""

    for field in DEFAULT_SCHEMA:
        if field.nested_path == (section, name):
            return field
    return None


def environment_keys() -> tuple[str, ...]:
    """Return flat keys in a stable presentation order."""

    return tuple(field.environment_key for field in DEFAULT_SCHEMA)


def sections() -> tuple[str, ...]:
    """Return nested section names without duplicates."""

    names: list[str] = []
    for field in DEFAULT_SCHEMA:
        if field.section not in names:
            names.append(field.section)
    return tuple(names)


def render_environment_example() -> str:
    """Render a small, deterministic example ``.env`` file."""

    lines = [
        "# Generated from tinyconfig's public schema.",
        "# Values shown here are safe local-development defaults.",
    ]
    lines.extend(field.example_line() for field in DEFAULT_SCHEMA)
    return "\n".join(lines) + "\n"


def render_nested_example() -> dict[str, dict[str, str]]:
    """Render the equivalent nested configuration representation."""

    result: dict[str, dict[str, str]] = {}
    for field in DEFAULT_SCHEMA:
        result.setdefault(field.section, {})[field.name] = field.default
    return result


def describe_fields() -> tuple[dict[str, object], ...]:
    """Return JSON-friendly metadata suitable for a help command."""

    return tuple(
        {
            "environment_key": field.environment_key,
            "nested_path": ".".join(field.nested_path),
            "default": field.default,
            "description": field.description,
            "required": field.required,
        }
        for field in DEFAULT_SCHEMA
    )


def render_markdown_reference() -> str:
    """Render a compact Markdown reference for the supported settings."""

    lines = [
        "# tinyconfig settings",
        "",
        "| Environment key | Nested key | Default | Description |",
        "| --- | --- | --- | --- |",
    ]
    for field in DEFAULT_SCHEMA:
        nested_key = ".".join(field.nested_path)
        lines.append(
            "| {key} | {nested} | `{default}` | {description} |".format(
                key=field.environment_key,
                nested=nested_key,
                default=field.default,
                description=field.description,
            )
        )
    return "\n".join(lines) + "\n"


def defaults_by_section() -> dict[str, dict[str, str]]:
    """Return a defensive copy of all documented nested defaults."""

    return {section: dict(values) for section, values in render_nested_example().items()}


def is_supported_environment_key(key: str) -> bool:
    """Report whether a flat key is part of the public schema."""

    return field_for_environment_key(key) is not None


def is_supported_nested_path(section: str, name: str) -> bool:
    """Report whether a nested key is part of the public schema."""

    return field_for_nested_path(section, name) is not None


def required_fields() -> tuple[FieldSpec, ...]:
    """Return fields that callers must supply in non-development profiles."""

    return tuple(field for field in DEFAULT_SCHEMA if field.required)


def optional_fields() -> tuple[FieldSpec, ...]:
    """Return fields with a documented default value."""

    return tuple(field for field in DEFAULT_SCHEMA if not field.required)


def summary() -> dict[str, object]:
    """Return a concise, JSON-friendly schema summary for diagnostics."""

    return {
        "field_count": len(DEFAULT_SCHEMA),
        "sections": sections(),
        "environment_keys": environment_keys(),
        "required_keys": tuple(field.environment_key for field in required_fields()),
    }


def defaults_by_environment_key() -> dict[str, str]:
    """Return documented defaults indexed by their flat environment keys.

    The returned mapping may be safely mutated by a caller.
    """

    return {
        field.environment_key: field.default
        for field in DEFAULT_SCHEMA
    }
