"""Anthropic Messages adapter for Pico's provider-neutral native contracts.

The adapter consumes only JSON returned by the raw-response transport.  It
never exposes SDK values or delegates tool execution to the Anthropic SDK.
All assistant content blocks are retained in a private continuation so that
thinking, redacted thinking, and future block types can be replayed without
loss on the tool-result request.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from typing import Any

from .contracts import (
    JSONValue,
    ModelRequest,
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
    ToolChoiceMode,
    ToolDefinition,
)
from .provider_transport import AnthropicMessagesTransport, ProviderTransportResponse


_CONTINUATION_VERSION = "pico-anthropic-messages-continuation-v1"
_PRIVATE_BLOCK_TYPES = frozenset({"thinking", "redacted_thinking"})
_PUBLIC_BLOCK_TYPES = frozenset({"text", "tool_use"})


class AnthropicMessagesProtocolError(ValueError):
    """Raised when an Anthropic payload cannot be represented safely."""


class AnthropicMessagesAdapter:
    """Compile and parse one non-streaming ``anthropic-messages`` dialect."""

    dialect = "anthropic-messages"

    def __init__(
        self,
        transport: AnthropicMessagesTransport,
        *,
        model: str,
        profile_id: str,
        system: str = "",
        thinking: Mapping[str, Any] | None = None,
        disable_parallel_tool_use: bool = True,
    ) -> None:
        self._transport = transport
        self.model = _non_empty("model", model)
        self.profile_id = _non_empty("profile_id", profile_id)
        if not isinstance(system, str):
            raise TypeError("Anthropic system prompt must be a string")
        if type(disable_parallel_tool_use) is not bool:
            raise TypeError("disable_parallel_tool_use must be a boolean")
        self.system = system
        self.thinking = (
            _json_object("thinking configuration", thinking) if thinking is not None else None
        )
        self.disable_parallel_tool_use = disable_parallel_tool_use

    def request(self, request: ModelRequest) -> ModelResponse:
        """Perform exactly one raw Messages operation and parse its JSON."""

        wire_request = self.compile_request(request)
        transport_response = self._transport.create(wire_request)
        return self.parse_response(transport_response)

    def compile_request(self, request: ModelRequest) -> dict[str, JSONValue]:
        """Compile a provider-neutral request into an Anthropic JSON payload."""

        if not isinstance(request, ModelRequest):
            raise TypeError("request must be a ModelRequest")

        payload: dict[str, JSONValue] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "messages": self._messages(request),
            "stream": False,
        }
        if self.system:
            payload["system"] = self.system
        if request.tools:
            payload["tools"] = [_tool_definition(tool) for tool in request.tools]
            payload["tool_choice"] = self._tool_choice(request)
        elif request.tool_choice.mode not in {ToolChoiceMode.AUTO, ToolChoiceMode.NONE}:
            raise AnthropicMessagesProtocolError("Anthropic tool choice requires declared tools")
        if self.thinking is not None:
            payload["thinking"] = _copy_json(self.thinking)
        return payload

    # ``build_request`` is a codec-friendly spelling used by deterministic
    # request-golden tests and callers that do not own a transport yet.
    build_request = compile_request

    def parse_response(
        self,
        response: ProviderTransportResponse | Mapping[str, Any],
    ) -> ModelResponse:
        """Parse every content block while keeping opaque blocks private."""

        transport_metadata: dict[str, JSONValue] = {}
        if isinstance(response, ProviderTransportResponse):
            payload = _json_object("Anthropic response", response.payload)
            transport_metadata = _transport_metadata(response)
        elif isinstance(response, Mapping):
            payload = _json_object("Anthropic response", response)
        else:
            raise TypeError("Anthropic response must be JSON or ProviderTransportResponse")

        content = payload.get("content")
        if not isinstance(content, list):
            raise AnthropicMessagesProtocolError("Anthropic response content must be a list")

        blocks: list[dict[str, JSONValue]] = []
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        private_blocks: list[dict[str, JSONValue]] = []
        unknown_types: list[str] = []
        block_types: list[str] = []

        for index, value in enumerate(content):
            block = _json_object(f"Anthropic content[{index}]", value)
            block_type = block.get("type")
            if not isinstance(block_type, str) or not block_type:
                raise AnthropicMessagesProtocolError(
                    f"Anthropic content[{index}] requires a non-empty string type"
                )
            blocks.append(block)
            block_types.append(block_type)
            if block_type == "text":
                block_text = block.get("text")
                if not isinstance(block_text, str):
                    raise AnthropicMessagesProtocolError(
                        f"Anthropic text block {index} requires string text"
                    )
                text_parts.append(block_text)
            elif block_type == "tool_use":
                calls.append(_tool_call(block, index=index))
            elif block_type in _PRIVATE_BLOCK_TYPES:
                private_blocks.append(block)
            else:
                unknown_types.append(block_type)

        stop_reason = _stop_reason(payload.get("stop_reason"))
        if stop_reason is StopReason.TOOL_CALLS and not calls:
            raise AnthropicMessagesProtocolError(
                "Anthropic stop_reason=tool_use requires at least one tool_use block"
            )

        continuation = ProviderContinuation(
            self.profile_id,
            {
                "version": _CONTINUATION_VERSION,
                "assistant_content": blocks,
            },
        )
        metadata: dict[str, JSONValue] = {
            "provider": "anthropic",
            "wire_dialect": self.dialect,
            "provider_stop_reason": _optional_string(
                "Anthropic stop_reason", payload.get("stop_reason")
            ),
            "content_blocks": {
                "count": len(blocks),
                "types": block_types,
                "unknown_types": unknown_types,
                "private_count": len(private_blocks),
                "private_hash": _blocks_hash(private_blocks) if private_blocks else None,
                "continuation_hash": continuation.stable_hash(),
            },
        }
        for field in ("id", "model", "type", "role"):
            value = payload.get(field)
            if value is not None:
                metadata[field] = _required_string(f"Anthropic response {field}", value)
        stop_sequence = payload.get("stop_sequence")
        if stop_sequence is not None:
            metadata["stop_sequence"] = _required_string(
                "Anthropic response stop_sequence", stop_sequence
            )
        usage = payload.get("usage")
        if usage is not None:
            metadata["usage"] = _json_object("Anthropic response usage", usage)
        metadata.update(transport_metadata)

        return ModelResponse(
            text="".join(text_parts),
            tool_calls=calls,
            stop_reason=stop_reason,
            continuation=continuation,
            metadata=metadata,
        )

    def _messages(self, request: ModelRequest) -> list[JSONValue]:
        prompt_message: dict[str, JSONValue] = {
            "role": "user",
            "content": request.prompt,
        }
        continuation = request.continuation
        if continuation is None:
            if request.tool_results:
                raise AnthropicMessagesProtocolError(
                    "Anthropic tool results require a preceding assistant continuation"
                )
            return [prompt_message]
        if continuation.profile_id != self.profile_id:
            raise AnthropicMessagesProtocolError(
                "Anthropic continuation profile_id does not match this adapter"
            )

        assistant_blocks = _continuation_blocks(continuation)
        call_ids = [
            _required_string("Anthropic tool_use id", block.get("id"))
            for block in assistant_blocks
            if block.get("type") == "tool_use"
        ]
        if len(call_ids) != len(set(call_ids)):
            raise AnthropicMessagesProtocolError(
                "Anthropic continuation contains duplicate tool_use IDs"
            )
        result_by_id = {result.call_id: result for result in request.tool_results}
        if set(call_ids) != set(result_by_id) or len(call_ids) != len(result_by_id):
            raise AnthropicMessagesProtocolError(
                "each Anthropic tool_use_id must have exactly one tool result"
            )

        result_blocks: list[JSONValue] = []
        for call_id in call_ids:
            result = result_by_id[call_id]
            result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": _result_content(result.output),
                    "is_error": result.is_error,
                }
            )
        return [
            prompt_message,
            {"role": "assistant", "content": assistant_blocks},
            {"role": "user", "content": result_blocks},
        ]

    def _tool_choice(self, request: ModelRequest) -> dict[str, JSONValue]:
        mode = request.tool_choice.mode
        if mode is ToolChoiceMode.AUTO:
            payload: dict[str, JSONValue] = {"type": "auto"}
        elif mode is ToolChoiceMode.NONE:
            return {"type": "none"}
        elif mode is ToolChoiceMode.REQUIRED:
            payload = {"type": "any"}
        else:
            payload = {"type": "tool", "name": request.tool_choice.name}
        payload["disable_parallel_tool_use"] = self.disable_parallel_tool_use
        return payload


def _tool_definition(tool: ToolDefinition) -> dict[str, JSONValue]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": _copy_json(tool.input_schema),
    }


def _tool_call(block: Mapping[str, Any], *, index: int) -> ToolCall:
    arguments = block.get("input")
    if not isinstance(arguments, Mapping):
        raise AnthropicMessagesProtocolError(
            f"Anthropic tool_use block {index} requires an object input"
        )
    try:
        return ToolCall(
            call_id=_required_string("Anthropic tool_use id", block.get("id")),
            name=_required_string("Anthropic tool_use name", block.get("name")),
            arguments=arguments,
        )
    except (TypeError, ValueError) as exc:
        raise AnthropicMessagesProtocolError(
            f"invalid Anthropic tool_use block {index}: {exc}"
        ) from exc


def _continuation_blocks(continuation: ProviderContinuation) -> list[dict[str, JSONValue]]:
    payload = continuation.payload
    if not isinstance(payload, Mapping) or payload.get("version") != _CONTINUATION_VERSION:
        raise AnthropicMessagesProtocolError("unsupported Anthropic continuation payload")
    values = payload.get("assistant_content")
    if not isinstance(values, list):
        raise AnthropicMessagesProtocolError(
            "Anthropic continuation assistant_content must be a list"
        )
    return [
        _json_object(f"Anthropic continuation assistant_content[{index}]", value)
        for index, value in enumerate(values)
    ]


def _result_content(output: JSONValue) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(
        output,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _stop_reason(value: Any) -> StopReason:
    if value == "end_turn":
        return StopReason.END_TURN
    if value == "tool_use":
        return StopReason.TOOL_CALLS
    if value in {"max_tokens", "model_context_window_exceeded"}:
        return StopReason.MAX_TOKENS
    if value == "stop_sequence":
        return StopReason.STOP_SEQUENCE
    if value == "refusal":
        return StopReason.CONTENT_FILTER
    return StopReason.UNKNOWN


def _transport_metadata(response: ProviderTransportResponse) -> dict[str, JSONValue]:
    attempts: list[JSONValue] = []
    for attempt in response.http_attempts:
        attempts.append(
            {
                "number": attempt.number,
                "method": attempt.method,
                "status_code": attempt.status_code,
                "request_id": attempt.request_id,
                "error_type": attempt.error_type,
            }
        )
    return {
        "http_status": response.status_code,
        "request_id": response.request_id,
        "http_attempts": attempts,
        "sdk_retry_count": response.sdk_retry_count,
    }


def _blocks_hash(blocks: Sequence[Mapping[str, Any]]) -> str:
    material = json.dumps(
        blocks,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


def _non_empty(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise AnthropicMessagesProtocolError(f"{name} must be a non-empty string")
    return value


def _optional_string(name: str, value: Any) -> str | None:
    if value is None:
        return None
    return _required_string(name, value)


def _json_object(name: str, value: Any) -> dict[str, JSONValue]:
    normalized = _json_value(name, value)
    if not isinstance(normalized, dict):
        raise AnthropicMessagesProtocolError(f"{name} must be a JSON object")
    return normalized


def _json_value(path: str, value: Any) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AnthropicMessagesProtocolError(f"{path} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise AnthropicMessagesProtocolError(
                    f"{path} contains a non-string mapping key"
                )
            result[key] = _json_value(f"{path}.{key}", item)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_value(f"{path}[]", item) for item in value]
    raise AnthropicMessagesProtocolError(
        f"{path} contains a non-JSON-safe {type(value).__name__}"
    )


def _copy_json(value: Any) -> JSONValue:
    return _json_value("JSON value", value)
