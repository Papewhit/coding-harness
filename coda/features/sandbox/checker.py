"""Sandbox backend availability checks."""

from __future__ import annotations

from collections.abc import Callable


class SandboxChecker:
    def __init__(self, which: Callable[[str], str | None]):
        self.which = which

    def backend_path(self, backend: str) -> str:
        backend = "bubblewrap" if backend == "auto" else backend
        if backend in {"none", "off"}:
            return ""
        if backend == "bubblewrap":
            return self.which("bwrap") or ""
        return ""
