"""Provider client boundaries for native requests and legacy migration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .contracts import ModelRequest, ModelResponse


class ModelClient(Protocol):
    """Deprecated prompt-to-text client retained for migration-only callers."""

    def complete(
        self,
        prompt: str,
        max_new_tokens: int,
        prompt_cache_key: str | None = None,
        prompt_cache_retention: str | None = None,
    ) -> str:
        ...


class NativeModelClient(Protocol):
    """Provider-neutral native request/response client used by Runtime."""

    def request(self, request: ModelRequest) -> ModelResponse:
        ...


@dataclass(frozen=True)
class ModelResult:
    text: str
    metadata: dict = field(default_factory=dict)


def complete_model(model_client: ModelClient, prompt: str, max_new_tokens: int, **kwargs: Any) -> ModelResult:
    """Invoke the migration-only prompt-to-text contract."""
    ## 历史兼容分支，函数定义在 pico.testing.ScriptedModelClient
    ## 现版本 runtime 使用统一的 complete() + last_completion_data
    # if hasattr(model_client, "complete_result"):
    #     return model_client.complete_result(prompt, max_new_tokens, **kwargs)
    text = model_client.complete(prompt, max_new_tokens, **kwargs)
    metadata = dict(getattr(model_client, "last_completion_metadata", {}) or {})
    return ModelResult(text=str(text), metadata=metadata)
