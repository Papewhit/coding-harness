"""Provider-neutral adapter for the OpenAI Responses native-tool dialect.

The adapter owns wire compilation and parsing only.  It never executes tools,
uses an SDK runner, or exposes SDK objects outside the transport boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math
import re
from typing import Any, Protocol

from .contracts import (
    JSONValue,
    ModelRequest,
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
    ToolCallResult,
    ToolChoiceMode,
    ToolDefinition,
)
from .provider_transport import ProviderTransportResponse


OPENAI_RESPONSES_DIALECT = "openai-responses"
CONTINUATION_VERSION = "pico-openai-responses-continuation-v1"

PROTOCOL_ERROR_CODES = frozenset(
    {
        "duplicate_call_id",
        "invalid_arguments",
        "invalid_continuation",
        "invalid_message_content",
        "invalid_output",
        "invalid_output_item",
        "invalid_response",
        "missing_call_id",
        "missing_tool_name",
        "profile_mismatch",
    }
)


class OpenAIResponsesProtocolError(ValueError):
    """A fail-closed OpenAI Responses request or response protocol error."""

    def __init__(self, code: str, message: str) -> None:
        if code not in PROTOCOL_ERROR_CODES:
            raise ValueError(f"unknown OpenAI Responses protocol error code: {code}")
        self.code = code
        super().__init__(message)


class OpenAIResponsesTransportLike(Protocol):
    """The narrow transport operation consumed by the adapter."""

    def create(self, request: Mapping[str, Any]) -> ProviderTransportResponse:
        ...


class OpenAIResponsesAdapter:
    """Compile and parse one non-streaming OpenAI Responses exchange."""

    def __init__(
        self,
        *,
        transport: OpenAIResponsesTransportLike,
        model: str,
        profile_id: str,
        instructions: str | None = None,
    ) -> None:
        self._transport = transport
        self.model = _required_config_string("model", model)
        self.profile_id = _required_config_string("profile_id", profile_id)
        if instructions is not None and not isinstance(instructions, str):
            raise TypeError("instructions must be a string or None")
        self.instructions = instructions

    def request(self, model_request: ModelRequest) -> ModelResponse:
        """Send one native operation without executing any returned tool call."""

        if not isinstance(model_request, ModelRequest):
            raise TypeError("OpenAI Responses adapter requires a ModelRequest")
        wire_request = self.compile_request(model_request)
        return self.parse_response(self._transport.create(wire_request))

    def compile_request(self, request: ModelRequest) -> dict[str, Any]:
        """Compile a provider-neutral request to Responses API keyword arguments."""

        if not isinstance(request, ModelRequest):
            raise TypeError("OpenAI Responses adapter requires a ModelRequest")
        payload: dict[str, Any] = {
            "model": self.model,
            "input": self._input(request),
            "max_output_tokens": request.max_output_tokens,
            "stream": False,
            "store": False,
            "parallel_tool_calls": False,
        }
        if self.instructions is not None:
            payload["instructions"] = self.instructions
        if request.tools:
            payload["tools"] = [_function_tool(tool) for tool in request.tools]
            payload["tool_choice"] = _tool_choice(request)
        return payload

    def parse_response(self, response: ProviderTransportResponse) -> ModelResponse:
        """Parse every output item and retain replay state as opaque continuation."""

        if not isinstance(response, ProviderTransportResponse):
            raise TypeError("OpenAI Responses adapter requires a ProviderTransportResponse")
        payload = _response_payload(response)
        output = payload.get("output")
        if not isinstance(output, list):
            raise OpenAIResponsesProtocolError(
                "invalid_output", "OpenAI Responses output must be a list"
            )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        call_ids: set[str] = set()
        replay_required = False
        unknown_types: list[str] = []
        item_counts: dict[str, int] = {}
        output_items: list[dict[str, JSONValue]] = []
        for index, raw_item in enumerate(output):
            item = _json_object(raw_item, code="invalid_output_item", location=f"output[{index}]")
            output_items.append(item)
            raw_type = item.get("type")
            item_type = raw_type if isinstance(raw_type, str) and raw_type else "missing"
            public_type = _public_identifier(item_type)
            item_counts[public_type] = item_counts.get(public_type, 0) + 1
            if item_type == "function_call":
                call = _function_call(item, index=index)
                if call.call_id in call_ids:
                    raise OpenAIResponsesProtocolError(
                        "duplicate_call_id",
                        f"OpenAI Responses output contains duplicate call_id {call.call_id!r}",
                    )
                call_ids.add(call.call_id)
                calls.append(call)
                replay_required = True
            elif item_type == "message":
                text_parts.extend(_message_text(item, index=index))
            elif item_type == "reasoning":
                replay_required = True
            else:
                replay_required = True
                unknown_types.append(public_type)

        continuation = None
        if replay_required:
            continuation = ProviderContinuation(
                profile_id=self.profile_id,
                payload={"version": CONTINUATION_VERSION, "output_items": output_items},
            )
        metadata = _public_metadata(
            payload,
            response=response,
            item_counts=item_counts,
            unknown_types=unknown_types,
        )
        return ModelResponse(
            text="".join(text_parts),
            tool_calls=calls,
            stop_reason=_stop_reason(payload, has_calls=bool(calls)),
            continuation=continuation,
            metadata=metadata,
        )

    def _input(self, request: ModelRequest) -> str | list[dict[str, Any]]:
        replay_items = self._continuation_items(request.continuation)
        if request.tool_results:
            return [*replay_items, *(_function_output(result) for result in request.tool_results)]
        if replay_items:
            if request.prompt:
                return [
                    *replay_items,
                    {"role": "user", "content": request.prompt},
                ]
            return replay_items
        return request.prompt

    def _continuation_items(
        self, continuation: ProviderContinuation | None
    ) -> list[dict[str, Any]]:
        if continuation is None:
            return []
        if continuation.profile_id != self.profile_id:
            raise OpenAIResponsesProtocolError(
                "profile_mismatch",
                "OpenAI Responses continuation profile does not match this adapter",
            )
        payload = continuation.payload
        if not isinstance(payload, Mapping) or payload.get("version") != CONTINUATION_VERSION:
            raise OpenAIResponsesProtocolError(
                "invalid_continuation", "OpenAI Responses continuation has an invalid version"
            )
        items = payload.get("output_items")
        if not isinstance(items, list):
            raise OpenAIResponsesProtocolError(
                "invalid_continuation", "OpenAI Responses continuation output_items must be a list"
            )
        return [
            _json_object(item, code="invalid_continuation", location=f"output_items[{index}]")
            for index, item in enumerate(items)
        ]


def _function_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.input_schema),
        "strict": True,
    }


def _tool_choice(request: ModelRequest) -> str | dict[str, str]:
    choice = request.tool_choice
    if choice.mode is ToolChoiceMode.NAMED:
        assert choice.name is not None
        return {"type": "function", "name": choice.name}
    return choice.mode.value


def _function_output(result: ToolCallResult) -> dict[str, str]:
    output: Any = result.output
    if result.is_error:
        output = {"is_error": True, "output": output}
    if not isinstance(output, str):
        output = json.dumps(
            output,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return {"type": "function_call_output", "call_id": result.call_id, "output": output}


def _function_call(item: Mapping[str, Any], *, index: int) -> ToolCall:
    call_id = item.get("call_id")
    if not isinstance(call_id, str) or not call_id.strip():
        raise OpenAIResponsesProtocolError(
            "missing_call_id", f"OpenAI Responses output[{index}] has no non-empty call_id"
        )
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise OpenAIResponsesProtocolError(
            "missing_tool_name", f"OpenAI Responses output[{index}] has no non-empty tool name"
        )
    raw_arguments = item.get("arguments")
    if not isinstance(raw_arguments, str):
        raise OpenAIResponsesProtocolError(
            "invalid_arguments", f"OpenAI Responses output[{index}] arguments must be JSON text"
        )
    try:
        arguments = json.loads(raw_arguments, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise OpenAIResponsesProtocolError(
            "invalid_arguments", f"OpenAI Responses output[{index}] arguments are invalid JSON"
        ) from exc
    if not isinstance(arguments, Mapping):
        raise OpenAIResponsesProtocolError(
            "invalid_arguments", f"OpenAI Responses output[{index}] arguments must decode to an object"
        )
    try:
        return ToolCall(call_id=call_id, name=name, arguments=arguments)
    except (TypeError, ValueError) as exc:
        raise OpenAIResponsesProtocolError(
            "invalid_arguments", f"OpenAI Responses output[{index}] arguments are not JSON-safe"
        ) from exc


def _message_text(item: Mapping[str, Any], *, index: int) -> list[str]:
    content = item.get("content")
    if not isinstance(content, list):
        raise OpenAIResponsesProtocolError(
            "invalid_message_content", f"OpenAI Responses output[{index}] content must be a list"
        )
    parts: list[str] = []
    for part_index, raw_part in enumerate(content):
        part = _json_object(
            raw_part,
            code="invalid_message_content",
            location=f"output[{index}].content[{part_index}]",
        )
        part_type = part.get("type")
        key = "text" if part_type == "output_text" else "refusal" if part_type == "refusal" else None
        if key is not None:
            value = part.get(key)
            if not isinstance(value, str):
                raise OpenAIResponsesProtocolError(
                    "invalid_message_content",
                    f"OpenAI Responses output[{index}].content[{part_index}].{key} must be text",
                )
            parts.append(value)
    return parts


def _stop_reason(payload: Mapping[str, Any], *, has_calls: bool) -> StopReason:
    if has_calls:
        return StopReason.TOOL_CALLS
    status = payload.get("status")
    if status == "completed":
        return StopReason.END_TURN
    if status == "failed":
        return StopReason.ERROR
    if status == "incomplete":
        details = payload.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, Mapping) else None
        if reason == "max_output_tokens":
            return StopReason.MAX_TOKENS
        if reason == "content_filter":
            return StopReason.CONTENT_FILTER
    return StopReason.UNKNOWN


def _public_metadata(
    payload: Mapping[str, Any],
    *,
    response: ProviderTransportResponse,
    item_counts: Mapping[str, int],
    unknown_types: Sequence[str],
) -> dict[str, JSONValue]:
    metadata: dict[str, JSONValue] = {
        "provider": "openai",
        "dialect": OPENAI_RESPONSES_DIALECT,
        "http_status": response.status_code,
        "http_attempt_count": len(response.http_attempts),
        "sdk_retry_count": response.sdk_retry_count,
        "output_item_counts": dict(item_counts),
        "unknown_item_types": list(unknown_types),
    }
    for source_key, target_key in (
        ("id", "response_id"),
        ("model", "model"),
        ("status", "status"),
    ):
        value = payload.get(source_key)
        if isinstance(value, str) and value:
            metadata[target_key] = _public_identifier(value)
    if response.request_id:
        metadata["request_id"] = _public_identifier(response.request_id)
    usage = _numeric_metadata(payload.get("usage"))
    if usage:
        metadata["usage"] = usage
    return metadata


def _response_payload(response: ProviderTransportResponse) -> Mapping[str, Any]:
    """Use the SDK raw-response bytes so future fields survive typed normalization."""

    try:
        payload = json.loads(response.raw_bytes, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise OpenAIResponsesProtocolError(
            "invalid_response", "OpenAI Responses raw payload must be valid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise OpenAIResponsesProtocolError(
            "invalid_response", "OpenAI Responses payload must be an object"
        )
    return payload


def _numeric_metadata(value: Any) -> JSONValue | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        result = {
            str(key): normalized
            for key, item in value.items()
            if isinstance(key, str) and (normalized := _numeric_metadata(item)) is not None
        }
        return result or None
    if isinstance(value, list):
        result = [normalized for item in value if (normalized := _numeric_metadata(item)) is not None]
        return result or None
    return None


def _json_object(value: Any, *, code: str, location: str) -> dict[str, JSONValue]:
    if not isinstance(value, Mapping):
        raise OpenAIResponsesProtocolError(code, f"OpenAI Responses {location} must be an object")
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise OpenAIResponsesProtocolError(
            code, f"OpenAI Responses {location} is not JSON-safe"
        ) from exc
    if not isinstance(decoded, dict):  # pragma: no cover - guarded by Mapping check
        raise OpenAIResponsesProtocolError(code, f"OpenAI Responses {location} must be an object")
    return decoded


def _required_config_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


_PUBLIC_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")


def _public_identifier(value: str) -> str:
    lowered = value.lower()
    credential_like = lowered.startswith(("sk-", "bearer", "api_key", "apikey"))
    return value if _PUBLIC_IDENTIFIER.fullmatch(value) and not credential_like else "redacted"
