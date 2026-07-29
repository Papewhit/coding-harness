"""Tool abstraction shared by the runtime and prompt builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .definitions import ToolDefinition
from .schemas import first_error_message


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class RegisteredTool(ToolDefinition):
    """Executable tool whose contract is carried by its Pydantic args model."""

    runner: Callable[[dict], str]

    @property
    def read_only(self) -> bool:
        return not self.risky

    def execute(self, args: dict) -> ToolResult:
        result = self.runner(args)
        if isinstance(result, ToolResult):
            return result
        return ToolResult(content=str(result))

    def validate(self, args: dict[str, Any]) -> None:
        """Validate raw arguments locally even when a provider used the schema."""

        try:
            self.args_model.model_validate(args)
        except ValidationError as exc:
            raise ValueError(first_error_message(exc)) from exc

    @property
    def parameter_model(self) -> type[BaseModel]:
        """Compatibility alias for integrations using singular terminology."""

        return self.args_model

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Compatibility alias for provider adapters expecting parameters."""

        return self.input_schema

    def __getitem__(self, key: str) -> Any:
        if key == "run":
            return self.runner
        return getattr(self, key)
