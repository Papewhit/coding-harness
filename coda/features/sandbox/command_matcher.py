"""Command pattern matching for sandbox exclusions."""

from __future__ import annotations

from fnmatch import fnmatch


def command_is_excluded(command: str | None, patterns: tuple[str, ...] | None) -> bool:
    command = str(command or "").strip()
    return any(fnmatch(command, str(pattern)) for pattern in patterns or ())
