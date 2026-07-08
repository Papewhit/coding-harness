"""Provider-facing result types."""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelResult:
    text: str
    metadata: dict = field(default_factory=dict)


def complete_model(model_client: Any, prompt: str, max_new_tokens: int, **kwargs: Any) -> ModelResult:
    if hasattr(model_client, "complete_result"):
        return model_client.complete_result(prompt, max_new_tokens, **kwargs)
    text = model_client.complete(prompt, max_new_tokens, **kwargs)
    metadata = dict(getattr(model_client, "last_completion_metadata", {}) or {})
    return ModelResult(text=str(text), metadata=metadata)
