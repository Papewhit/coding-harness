"""Provider-neutral contracts for native model and tool exchanges."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class ToolChoiceMode(str, Enum):
    """Provider-neutral tool selection modes."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"
    NAMED = "named"


class StopReason(str, Enum):
    """Normalized reasons for a provider ending one model turn."""

    END_TURN = "end_turn"
    TOOL_CALLS = "tool_calls"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolChoice:
    """Select whether, or which, tool the model may call."""

    mode: ToolChoiceMode = ToolChoiceMode.AUTO
    name: str | None = None

    def __post_init__(self) -> None:
        try:
            mode = ToolChoiceMode(self.mode)
        except ValueError as exc:
            raise ValueError(f"unsupported tool choice mode: {self.mode!r}") from exc
        object.__setattr__(self, "mode", mode)
        if mode is ToolChoiceMode.NAMED:
            object.__setattr__(self, "name", _non_empty("tool choice name", self.name))
        elif self.name is not None:
            raise ValueError("tool choice name is valid only for named mode")

    @classmethod
    def named(cls, name: str) -> ToolChoice:
        return cls(mode=ToolChoiceMode.NAMED, name=name)

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {"mode": self.mode.value}
        if self.name is not None:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class ToolDefinition:
    """A provider-independent tool declaration using JSON Schema."""

    name: str
    description: str
    input_schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _non_empty("tool name", self.name))
        if not isinstance(self.description, str):
            raise TypeError("tool description must be a string")
        object.__setattr__(self, "input_schema", _json_object("tool input schema", self.input_schema))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": _copy_json(self.input_schema),
        }


@dataclass(frozen=True)
class ToolCall:
    """One native tool call emitted by a provider."""

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "call_id", _non_empty("call_id", self.call_id))
        object.__setattr__(self, "name", _non_empty("tool call name", self.name))
        object.__setattr__(self, "arguments", _json_object("tool call arguments", self.arguments))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": _copy_json(self.arguments),
        }


@dataclass(frozen=True)
class ToolCallResult:
    """The JSON-safe result paired with exactly one provider call ID."""

    call_id: str
    output: Any
    is_error: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "call_id", _non_empty("call_id", self.call_id))
        if type(self.is_error) is not bool:
            raise TypeError("tool result is_error must be a boolean")
        object.__setattr__(self, "output", _normalize_json(self.output, path="tool result output"))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "call_id": self.call_id,
            "output": _copy_json(self.output),
            "is_error": self.is_error,
        }


@dataclass(frozen=True, init=False)
class ProviderContinuation:
    """Opaque, JSON-safe provider state bound to one public profile identity."""

    profile_id: str
    _payload_json: str = field(repr=False)

    def __init__(self, profile_id: str, payload: Any) -> None:
        object.__setattr__(self, "profile_id", _non_empty("provider profile_id", profile_id))
        normalized = _normalize_json(payload, path="provider continuation")
        object.__setattr__(self, "_payload_json", _canonical_json(normalized))

    @property
    def payload(self) -> JSONValue:
        """Return a detached copy so callers cannot mutate persisted state."""

        return json.loads(self._payload_json)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "profile_id": self.profile_id,
            "payload": self.payload,
        }

    def stable_hash(self) -> str:
        """Return a deterministic hash without interpreting the opaque payload."""

        encoded = _canonical_json(self.to_dict()).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class ModelRequest:
    """One provider-neutral model request in a native tool exchange."""

    prompt: str
    max_output_tokens: int
    tools: Sequence[ToolDefinition] = ()
    tool_choice: ToolChoice = field(default_factory=ToolChoice)
    tool_results: Sequence[ToolCallResult] = ()
    continuation: ProviderContinuation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str):
            raise TypeError("model request prompt must be a string")
        if type(self.max_output_tokens) is not int or self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        tools = _typed_tuple("tools", self.tools, ToolDefinition)
        tool_results = _typed_tuple("tool_results", self.tool_results, ToolCallResult)
        if not isinstance(self.tool_choice, ToolChoice):
            raise TypeError("tool_choice must be a ToolChoice")
        if self.continuation is not None and not isinstance(self.continuation, ProviderContinuation):
            raise TypeError("continuation must be a ProviderContinuation")
        _require_unique("tool definition name", (tool.name for tool in tools))
        _require_unique("tool result call_id", (result.call_id for result in tool_results))
        if self.tool_choice.mode is ToolChoiceMode.REQUIRED and not tools:
            raise ValueError("required tool choice needs at least one tool definition")
        if self.tool_choice.mode is ToolChoiceMode.NAMED and self.tool_choice.name not in {
            tool.name for tool in tools
        }:
            raise ValueError("named tool choice must reference a declared tool")
        object.__setattr__(self, "tools", tools)
        object.__setattr__(self, "tool_results", tool_results)

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {
            "prompt": self.prompt,
            "max_output_tokens": self.max_output_tokens,
            "tools": [tool.to_dict() for tool in self.tools],
            "tool_choice": self.tool_choice.to_dict(),
            "tool_results": [result.to_dict() for result in self.tool_results],
        }
        if self.continuation is not None:
            payload["continuation"] = self.continuation.to_dict()
        return payload


@dataclass(frozen=True)
class ModelResponse:
    """Text, native calls, and stop state returned by one model request."""

    text: str
    tool_calls: Sequence[ToolCall]
    stop_reason: StopReason
    continuation: ProviderContinuation | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("model response text must be a string")
        tool_calls = _typed_tuple("tool_calls", self.tool_calls, ToolCall)
        _require_unique("tool call call_id", (call.call_id for call in tool_calls))
        try:
            stop_reason = StopReason(self.stop_reason)
        except ValueError as exc:
            raise ValueError(f"unsupported stop reason: {self.stop_reason!r}") from exc
        if self.continuation is not None and not isinstance(self.continuation, ProviderContinuation):
            raise TypeError("continuation must be a ProviderContinuation")
        object.__setattr__(self, "tool_calls", tool_calls)
        object.__setattr__(self, "stop_reason", stop_reason)
        object.__setattr__(self, "metadata", _json_object("model response metadata", self.metadata))

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {
            "text": self.text,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "stop_reason": self.stop_reason.value,
            "metadata": _copy_json(self.metadata),
        }
        if self.continuation is not None:
            payload["continuation"] = self.continuation.to_dict()
        return payload


def _non_empty(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _typed_tuple(name: str, values: Sequence[Any], expected_type: type[Any]) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence")
    normalized = tuple(values)
    if not all(isinstance(value, expected_type) for value in normalized):
        raise TypeError(f"{name} must contain only {expected_type.__name__} values")
    return normalized


def _require_unique(name: str, values: Any) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {name}: {value}")
        seen.add(value)


def _json_object(name: str, value: Any) -> dict[str, JSONValue]:
    normalized = _normalize_json(value, path=name)
    if not isinstance(normalized, dict):
        raise TypeError(f"{name} must be a mapping")
    return normalized


def _normalize_json(value: Any, *, path: str) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string mapping key")
            normalized[key] = _normalize_json(item, path=f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item, path=f"{path}[]") for item in value]
    raise TypeError(f"{path} contains a non-JSON-safe {type(value).__name__}")


def _copy_json(value: Any) -> JSONValue:
    return json.loads(_canonical_json(value))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
