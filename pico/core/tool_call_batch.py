"""Provider-neutral native tool batch execution.

Persistence is deliberately injected.  This module exposes durable state to
the Runtime without owning checkpoint storage, which remains a later wiring
concern.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..providers.contracts import (
    JSONValue,
    ModelRequest,
    ModelResponse,
    StopReason,
    ToolCall,
    ToolCallResult,
    ToolChoice,
    ToolChoiceMode,
)


class ToolCallStatus(str, Enum):
    """Crash-relevant lifecycle of one provider tool call."""

    RECEIVED = "received"
    PERSISTED = "persisted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


TERMINAL_TOOL_CALL_STATUSES = frozenset(
    {ToolCallStatus.COMPLETED, ToolCallStatus.REJECTED, ToolCallStatus.UNCERTAIN}
)
_TRANSITIONS = {
    ToolCallStatus.RECEIVED: {ToolCallStatus.PERSISTED},
    ToolCallStatus.PERSISTED: {ToolCallStatus.EXECUTING, ToolCallStatus.REJECTED},
    ToolCallStatus.EXECUTING: TERMINAL_TOOL_CALL_STATUSES,
}


@dataclass
class ToolCallState:
    """Mutable in-memory state whose snapshots are safe to persist."""

    call: ToolCall
    status: ToolCallStatus = ToolCallStatus.RECEIVED
    result: ToolCallResult | None = None
    result_metadata: dict[str, JSONValue] = field(default_factory=dict)

    def transition(
        self,
        status: ToolCallStatus,
        *,
        result: ToolCallResult | None = None,
        result_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if status not in _TRANSITIONS.get(self.status, set()):
            raise ValueError(
                f"invalid tool call transition: {self.status.value} -> {status.value}"
            )
        if status in TERMINAL_TOOL_CALL_STATUSES and result is None:
            raise ValueError("terminal tool call state requires a result")
        if status not in TERMINAL_TOOL_CALL_STATUSES and result is not None:
            raise ValueError("non-terminal tool call state cannot have a result")
        self.status = status
        self.result = result
        self.result_metadata = _json_mapping(result_metadata or {})

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {
            "call": self.call.to_dict(),
            "status": self.status.value,
            "result_metadata": dict(self.result_metadata),
        }
        if self.result is not None:
            payload["result"] = self.result.to_dict()
        return payload


@dataclass
class ToolCallBatch:
    """One atomic provider batch and the one-to-one results it produces."""

    response: ModelResponse
    calls: list[ToolCallState]

    @classmethod
    def receive(cls, response: ModelResponse) -> ToolCallBatch:
        if not response.tool_calls:
            raise ValueError("native tool batch requires at least one call")
        return cls(
            response=response,
            calls=[ToolCallState(call=call) for call in response.tool_calls],
        )

    @property
    def complete(self) -> bool:
        return all(call.status in TERMINAL_TOOL_CALL_STATUSES for call in self.calls)

    def results(self) -> tuple[ToolCallResult, ...]:
        if not self.complete:
            raise RuntimeError("native tool batch results requested before completion")
        results = tuple(call.result for call in self.calls)
        if any(result is None for result in results):
            raise RuntimeError("terminal native tool call is missing its result")
        return tuple(result for result in results if result is not None)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "response": self.response.to_dict(),
            "calls": [call.to_dict() for call in self.calls],
            "complete": self.complete,
        }


@dataclass(frozen=True)
class NativeLoopResult:
    """Terminal value from a provider-native Engine exchange."""

    final_text: str
    interim_text: tuple[str, ...]
    responses: tuple[ModelResponse, ...]
    batches: tuple[ToolCallBatch, ...]
    stop_reason: StopReason
    step_limit_reached: bool = False


class NativeModelProtocolError(RuntimeError):
    """A structured response cannot be consumed without violating the contract."""


PersistHook = Callable[[dict[str, JSONValue]], None]
EventHook = Callable[[dict[str, JSONValue]], None]

_STEP_LIMIT_SUMMARY_NOTICE = (
    "The per-turn tool budget is exhausted. Do not call tools. Return a concise final "
    "summary of completed work, remaining work, and how the user can continue."
)


def run_native_tool_loop(
    runtime: Any,
    initial_request: ModelRequest,
    *,
    persist_hook: PersistHook,
    event_hook: EventHook | None = None,
    max_steps: int | None = None,
) -> NativeLoopResult:
    """Run structured model responses without invoking the legacy text parser."""

    if not isinstance(initial_request, ModelRequest):
        raise TypeError("native engine loop requires a ModelRequest")
    if not callable(persist_hook):
        raise TypeError("native engine loop requires a persist hook")
    step_limit = runtime.max_steps if max_steps is None else max_steps
    if type(step_limit) is not int or step_limit < 0:
        raise ValueError("max_steps must be a non-negative integer")

    request = initial_request
    responses: list[ModelResponse] = []
    batches: list[ToolCallBatch] = []
    interim_text: list[str] = []
    tool_steps = 0

    while True:
        response = runtime.model_client.request(request)
        if not isinstance(response, ModelResponse):
            raise TypeError("native model client must return a ModelResponse")
        responses.append(response)
        if response.stop_reason is StopReason.ERROR:
            if response.tool_calls:
                batches.append(
                    _reject_response_calls(
                        response,
                        persist_hook,
                        "model_protocol_error",
                        _protocol_error_message(response),
                    )
                )
            raise NativeModelProtocolError(_protocol_error_message(response))
        if not response.tool_calls:
            _emit(
                event_hook,
                "native_final",
                {"text": response.text, "stop_reason": response.stop_reason.value},
            )
            return NativeLoopResult(
                final_text=response.text.strip(),
                interim_text=tuple(interim_text),
                responses=tuple(responses),
                batches=tuple(batches),
                stop_reason=response.stop_reason,
            )

        if response.text:
            interim_text.append(response.text)
            _emit(event_hook, "native_interim_text", {"text": response.text})
        batch = ToolCallBatch.receive(response)
        batches.append(batch)
        _persist(persist_hook, batch)
        for state in batch.calls:
            state.transition(ToolCallStatus.PERSISTED)
        _persist(persist_hook, batch)

        for state in batch.calls:
            if tool_steps >= step_limit:
                state.transition(
                    ToolCallStatus.REJECTED,
                    result=_error_result(
                        state.call.call_id,
                        "step_limit_exceeded",
                        "tool call was not executed because the per-turn budget is exhausted",
                    ),
                    result_metadata={
                        "tool_status": "rejected",
                        "tool_error_code": "step_limit_exceeded",
                    },
                )
                _persist(persist_hook, batch)
                _emit_call_state(event_hook, state)
                continue
            tool_steps += 1
            state.transition(ToolCallStatus.EXECUTING)
            _persist(persist_hook, batch)
            _emit_call_state(event_hook, state)
            _execute_runtime_tool(runtime, state)
            _persist(persist_hook, batch)
            _emit_call_state(event_hook, state)

        results = batch.results()
        request = _followup_request(initial_request, response, results)
        if tool_steps >= step_limit:
            summary_response = runtime.model_client.request(
                _summary_request(initial_request, response, results)
            )
            if not isinstance(summary_response, ModelResponse):
                raise TypeError("native model client must return a ModelResponse")
            responses.append(summary_response)
            if summary_response.tool_calls:
                batches.append(
                    _reject_response_calls(
                        summary_response,
                        persist_hook,
                        "tool_choice_none_violation",
                        "tool call was not executed because tool_choice was none",
                    )
                )
                raise NativeModelProtocolError(
                    "model emitted tool calls when tool_choice was none"
                )
            if summary_response.stop_reason is StopReason.ERROR:
                raise NativeModelProtocolError(
                    _protocol_error_message(summary_response)
                )
            final = (
                summary_response.text.strip()
                or "Stopped after reaching the step limit."
            )
            _emit(
                event_hook,
                "native_final",
                {"text": final, "stop_reason": summary_response.stop_reason.value},
            )
            return NativeLoopResult(
                final_text=final,
                interim_text=tuple(interim_text),
                responses=tuple(responses),
                batches=tuple(batches),
                stop_reason=summary_response.stop_reason,
                step_limit_reached=True,
            )


def _execute_runtime_tool(runtime: Any, state: ToolCallState) -> None:
    call = state.call
    try:
        output = runtime.run_tool(call.name, dict(call.arguments))
    except Exception as exc:
        state.transition(
            ToolCallStatus.UNCERTAIN,
            result=_error_result(call.call_id, "tool_execution_uncertain", str(exc)),
            result_metadata={
                "tool_status": "uncertain",
                "tool_error_code": "tool_execution_uncertain",
            },
        )
        return
    metadata = _json_mapping(getattr(runtime, "_last_tool_result_metadata", {}) or {})
    tool_status = str(metadata.get("tool_status", ""))
    error_code = str(metadata.get("tool_error_code", ""))
    is_error = tool_status not in {"", "ok"} or bool(error_code)
    if not is_error:
        terminal_status = ToolCallStatus.COMPLETED
        result = ToolCallResult(call_id=call.call_id, output=str(output))
    elif tool_status == "rejected":
        terminal_status = ToolCallStatus.REJECTED
        result = _error_result(call.call_id, error_code or "tool_rejected", str(output))
    else:
        terminal_status = ToolCallStatus.UNCERTAIN
        result = _error_result(call.call_id, error_code or "tool_failed", str(output))
    state.transition(terminal_status, result=result, result_metadata=metadata)


def _reject_response_calls(
    response: ModelResponse,
    persist_hook: PersistHook,
    code: str,
    message: str,
) -> ToolCallBatch:
    batch = ToolCallBatch.receive(response)
    _persist(persist_hook, batch)
    for state in batch.calls:
        state.transition(ToolCallStatus.PERSISTED)
    _persist(persist_hook, batch)
    for state in batch.calls:
        state.transition(
            ToolCallStatus.REJECTED,
            result=_error_result(state.call.call_id, code, message),
            result_metadata={"tool_status": "rejected", "tool_error_code": code},
        )
        _persist(persist_hook, batch)
    return batch


def _followup_request(
    initial: ModelRequest, response: ModelResponse, results: tuple[ToolCallResult, ...]
) -> ModelRequest:
    return ModelRequest(
        prompt=initial.prompt,
        max_output_tokens=initial.max_output_tokens,
        tools=initial.tools,
        tool_choice=ToolChoice(),
        tool_results=results,
        continuation=response.continuation,
    )


def _summary_request(
    initial: ModelRequest, response: ModelResponse, results: tuple[ToolCallResult, ...]
) -> ModelRequest:
    return ModelRequest(
        prompt=_STEP_LIMIT_SUMMARY_NOTICE,
        max_output_tokens=initial.max_output_tokens,
        tools=initial.tools,
        tool_choice=ToolChoice(mode=ToolChoiceMode.NONE),
        tool_results=results,
        continuation=response.continuation,
    )


def _error_result(call_id: str, code: str, message: str) -> ToolCallResult:
    return ToolCallResult(
        call_id=call_id,
        output={"error": {"code": code, "message": message}},
        is_error=True,
    )


def _persist(hook: PersistHook, batch: ToolCallBatch) -> None:
    hook(batch.to_dict())


def _emit_call_state(hook: EventHook | None, state: ToolCallState) -> None:
    _emit(
        hook,
        "native_tool_call_state",
        {
            "call_id": state.call.call_id,
            "name": state.call.name,
            "status": state.status.value,
        },
    )


def _emit(hook: EventHook | None, event: str, payload: dict[str, JSONValue]) -> None:
    if hook is not None:
        hook({"event": event, **payload})


def _protocol_error_message(response: ModelResponse) -> str:
    error = response.metadata.get("protocol_error")
    if isinstance(error, dict):
        return str(
            error.get("message") or error.get("code") or "native model protocol error"
        )
    return response.text or "native model protocol error"


def _json_mapping(value: Mapping[str, Any]) -> dict[str, JSONValue]:
    # Provider contracts perform the canonical JSON-safety check for us.
    checked = ToolCallResult(call_id="metadata", output=dict(value)).output
    if not isinstance(checked, dict):  # pragma: no cover - construction guarantees this
        raise TypeError("tool result metadata must be a mapping")
    return checked
