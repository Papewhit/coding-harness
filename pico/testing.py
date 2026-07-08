"""Testing helpers for deterministic Pico runtime checks."""

from __future__ import annotations

from typing import Any

from .providers.base import ModelResult


class ScriptedModelClient:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []
        self.supports_prompt_cache = False
        self.last_completion_metadata: dict[str, Any] = {}

    def complete(self, prompt: str, max_new_tokens: int, **kwargs: Any) -> str:
        self.prompts.append(prompt)
        if not getattr(self, "last_completion_metadata", None):
            self.last_completion_metadata = {}
        if not self.outputs:
            raise RuntimeError("scripted model ran out of outputs")
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return output

    def complete_result(self, prompt: str, max_new_tokens: int, **kwargs: Any) -> ModelResult:
        return ModelResult(
            text=self.complete(prompt, max_new_tokens, **kwargs),
            metadata=dict(self.last_completion_metadata),
        )
