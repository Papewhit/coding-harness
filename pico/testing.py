"""Testing helpers for deterministic Pico runtime checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .providers.base import ModelResult
from .providers.contracts import (
    ModelRequest,
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
)


class ScriptedModelClient:
    """Deprecated text-protocol helper retained for migration tests."""

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


class ScriptedNativeModelClient:
    """Return native responses in order and retain every structured request.

    The client performs no I/O. ``requests`` is the deterministic call log and
    stores the frozen :class:`ModelRequest` objects exactly as received, making
    tool results and opaque continuation state directly assertable in tests.
    """

    def __init__(self, responses: Iterable[ModelResponse | BaseException]) -> None:
        self._responses = list(responses)
        self.requests: list[ModelRequest] = []

    @property
    def remaining_responses(self) -> int:
        return len(self._responses)

    @property
    def call_log(self) -> tuple[ModelRequest, ...]:
        """Return an immutable snapshot of requests in call order."""

        return tuple(self.requests)

    def request(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("scripted native model requires a ModelRequest")
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("scripted native model ran out of responses")
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if not isinstance(response, ModelResponse):
            raise TypeError("scripted native response must be a ModelResponse or exception")
        return response


def native_continuation(
    payload: Any,
    *,
    profile_id: str = "scripted-native:test-profile",
) -> ProviderContinuation:
    """Construct JSON-safe opaque continuation state for a scripted exchange."""

    return ProviderContinuation(profile_id=profile_id, payload=payload)


def native_final_response(
    text: str,
    *,
    continuation: ProviderContinuation | None = None,
    metadata: Mapping[str, Any] | None = None,
    stop_reason: StopReason = StopReason.END_TURN,
) -> ModelResponse:
    """Construct a structured response with no tool calls."""

    return ModelResponse(
        text=text,
        tool_calls=(),
        stop_reason=stop_reason,
        continuation=continuation,
        metadata={} if metadata is None else metadata,
    )


def native_tool_call(
    call_id: str,
    name: str,
    arguments: Mapping[str, Any] | None = None,
) -> ToolCall:
    """Construct one provider-neutral native tool call."""

    return ToolCall(call_id=call_id, name=name, arguments={} if arguments is None else arguments)


def native_tool_call_response(
    call_id: str,
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    text: str = "",
    continuation: ProviderContinuation | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ModelResponse:
    """Construct a response containing exactly one native tool call."""

    return native_multi_tool_call_response(
        native_tool_call(call_id, name, arguments),
        text=text,
        continuation=continuation,
        metadata=metadata,
    )


def native_multi_tool_call_response(
    *tool_calls: ToolCall,
    text: str = "",
    continuation: ProviderContinuation | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ModelResponse:
    """Construct a response containing one or more native tool calls."""

    if not tool_calls:
        raise ValueError("a tool-call response requires at least one tool call")
    return ModelResponse(
        text=text,
        tool_calls=tool_calls,
        stop_reason=StopReason.TOOL_CALLS,
        continuation=continuation,
        metadata={} if metadata is None else metadata,
    )


def native_protocol_error_response(
    message: str,
    *,
    code: str = "scripted_protocol_error",
    text: str = "",
    continuation: ProviderContinuation | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ModelResponse:
    """Construct a normalized provider protocol-error response."""

    error_metadata = dict(metadata or {})
    error_metadata["protocol_error"] = {"code": code, "message": message}
    return ModelResponse(
        text=text,
        tool_calls=(),
        stop_reason=StopReason.ERROR,
        continuation=continuation,
        metadata=error_metadata,
    )
