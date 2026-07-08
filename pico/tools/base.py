"""Tool abstraction shared by the runtime and prompt builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    schema: dict
    description: str
    risky: bool
    runner: Callable[[dict], str]

    @property
    def read_only(self) -> bool:
        return not self.risky

    def execute(self, args: dict) -> ToolResult:
        result = self.runner(args)
        if isinstance(result, ToolResult):
            return result
        return ToolResult(content=str(result))

    def __getitem__(self, key: str) -> Any:
        if key == "run":
            return self.runner
        return getattr(self, key)
