"""Provider-neutral, JSON-safe session records for native model exchanges."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from ..providers.contracts import ModelResponse, ProviderContinuation, ToolCall, ToolCallResult


EXCHANGE_SCHEMA_VERSION = "coda-model-exchange-v1"
EXCHANGE_EVENTS = frozenset({"assistant_tool_batch", "tool_result", "model_final"})
TERMINAL_TOOL_STATUSES = frozenset({"completed", "rejected", "error", "not_executed"})
_PRIVATE_KEYS = frozenset(
    {"continuation", "private_continuation", "opaque_continuation", "reasoning", "thinking"}
)


class ProfileMismatchError(ValueError):
    """Raised before private provider state can cross a profile boundary."""


@dataclass(frozen=True)
class ModelExchangeEvent:
    """One normalized native exchange event with private and public views."""

    _payload_json: str

    @classmethod
    def assistant_tool_batch(
        cls,
        *,
        exchange_id: str,
        profile: Mapping[str, Any],
        response: ModelResponse,
        created_at: str = "",
    ) -> ModelExchangeEvent:
        if not response.tool_calls:
            raise ValueError("assistant_tool_batch requires at least one tool call")
        payload = _base_event("assistant_tool_batch", exchange_id, profile, created_at)
        payload.update(
            {
                "text": response.text,
                "stop_reason": response.stop_reason.value,
                "tool_calls": [
                    {**call.to_dict(), "status": "pending"} for call in response.tool_calls
                ],
                "metadata": _public_metadata(response.metadata),
            }
        )
        _attach_continuation(payload, response.continuation)
        return cls._from_payload(payload)

    @classmethod
    def tool_result(
        cls,
        *,
        exchange_id: str,
        profile: Mapping[str, Any],
        call: ToolCall,
        result: ToolCallResult,
        status: str = "completed",
        created_at: str = "",
    ) -> ModelExchangeEvent:
        if call.call_id != result.call_id:
            raise ValueError("tool result call_id must match the provider tool call")
        status = str(status)
        if status not in TERMINAL_TOOL_STATUSES:
            raise ValueError(f"unsupported terminal tool status: {status!r}")
        payload = _base_event("tool_result", exchange_id, profile, created_at)
        payload.update(
            {
                "call_id": call.call_id,
                "name": call.name,
                "arguments": call.to_dict()["arguments"],
                "status": status,
                "result": result.to_dict(),
            }
        )
        return cls._from_payload(payload)

    @classmethod
    def model_final(
        cls,
        *,
        exchange_id: str,
        profile: Mapping[str, Any],
        response: ModelResponse,
        created_at: str = "",
    ) -> ModelExchangeEvent:
        if response.tool_calls:
            raise ValueError("model_final cannot contain tool calls")
        payload = _base_event("model_final", exchange_id, profile, created_at)
        payload.update(
            {
                "text": response.text,
                "stop_reason": response.stop_reason.value,
                "metadata": _public_metadata(response.metadata),
            }
        )
        _attach_continuation(payload, response.continuation)
        return cls._from_payload(payload)

    @classmethod
    def _from_payload(cls, payload: Mapping[str, Any]) -> ModelExchangeEvent:
        normalized = _json_copy(payload)
        return cls(_canonical_json(normalized))

    def private_dict(self) -> dict[str, Any]:
        """Return the complete session-private record as a detached JSON value."""

        return json.loads(self._payload_json)

    def public_dict(self) -> dict[str, Any]:
        """Return evidence safe for trace/report persistence."""

        return public_exchange_record(self.private_dict())


def normalize_profile_identity(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the credential-free fields that bind provider continuation."""

    if not isinstance(profile, Mapping):
        raise TypeError("provider profile identity must be a mapping")
    provider = profile.get("provider", profile.get("profile"))
    normalized = {
        "profile_id": _required_string(profile, "profile_id"),
        "provider": _required_value("provider", provider),
        "model": _required_string(profile, "model"),
        "wire_dialect": _required_string(profile, "wire_dialect"),
    }
    for key in (
        "adapter_mode",
        "sdk_package",
        "sdk_version",
        "base_url_fingerprint",
        "capabilities",
        "sdk_max_retries",
        "provider_attempts",
        "tool_schema",
    ):
        if key in profile:
            normalized[key] = _json_copy(profile[key])
    return normalized


def assert_profile_matches(locked: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    """Fail closed and name every provider/model/dialect lock mismatch."""

    expected = normalize_profile_identity(locked)
    actual = normalize_profile_identity(current)
    fields = sorted(key for key in expected if actual.get(key) != expected[key])
    extra = sorted(key for key in actual if key not in expected)
    fields.extend(extra)
    if fields:
        raise ProfileMismatchError(
            "provider profile mismatch: " + ", ".join(dict.fromkeys(fields))
        )


def continuation_evidence(continuation: ProviderContinuation) -> dict[str, Any]:
    """Describe opaque state without reading or exposing its payload."""

    return {
        "hash": continuation.stable_hash(),
        "type": "ProviderContinuation",
        "count": 1,
    }


def public_exchange_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Strip private continuation from one serialized exchange event."""

    if not _is_exchange_record(record):
        return _json_copy(record)
    public = {key: value for key, value in record.items() if key not in _PRIVATE_KEYS}
    continuation = record.get("continuation") or record.get("private_continuation")
    if continuation is not None:
        public["continuation_evidence"] = _serialized_continuation_evidence(continuation)
    return _json_copy(public)


def public_artifact(value: Any) -> Any:
    """Recursively sanitize exchange records embedded in public trace/report data."""

    if isinstance(value, ModelExchangeEvent):
        return value.public_dict()
    if isinstance(value, Mapping):
        if _is_exchange_record(value):
            return public_exchange_record(value)
        return {str(key): public_artifact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [public_artifact(item) for item in value]
    return value


def restore_continuation(value: Mapping[str, Any]) -> ProviderContinuation:
    """Reconstruct only the provider-neutral contract from private JSON state."""

    if not isinstance(value, Mapping):
        raise TypeError("persisted continuation must be a mapping")
    return ProviderContinuation(
        profile_id=_required_string(value, "profile_id"),
        payload=value.get("payload"),
    )


def _base_event(
    event: str, exchange_id: str, profile: Mapping[str, Any], created_at: str
) -> dict[str, Any]:
    if event not in EXCHANGE_EVENTS:
        raise ValueError(f"unsupported model exchange event: {event!r}")
    if not isinstance(created_at, str):
        raise TypeError("model exchange state must contain only JSON-safe values")
    return {
        "schema_version": EXCHANGE_SCHEMA_VERSION,
        "event": event,
        "exchange_id": _non_empty("exchange_id", exchange_id),
        "profile": normalize_profile_identity(profile),
        "created_at": created_at,
    }


def _attach_continuation(
    payload: dict[str, Any], continuation: ProviderContinuation | None
) -> None:
    if continuation is None:
        return
    profile_id = payload["profile"]["profile_id"]
    if continuation.profile_id != profile_id:
        raise ProfileMismatchError("continuation profile_id does not match exchange profile")
    payload["continuation"] = continuation.to_dict()


def _public_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = sorted(key for key in metadata if str(key).lower() in _PRIVATE_KEYS)
    if forbidden:
        raise ValueError(
            "model response metadata cannot contain private continuation fields: "
            + ", ".join(forbidden)
        )
    return _json_copy(metadata)


def _serialized_continuation_evidence(value: Any) -> dict[str, Any]:
    continuation = restore_continuation(value)
    return continuation_evidence(continuation)


def _is_exchange_record(value: Mapping[str, Any]) -> bool:
    return (
        value.get("schema_version") == EXCHANGE_SCHEMA_VERSION
        and value.get("event") in EXCHANGE_EVENTS
    )


def _required_string(value: Mapping[str, Any], key: str) -> str:
    return _non_empty(key, value.get(key))


def _required_value(name: str, value: Any) -> str:
    return _non_empty(name, value)


def _non_empty(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(_canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise TypeError("model exchange state must contain only JSON-safe values") from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def exchange_hash(record: Mapping[str, Any]) -> str:
    """Return a deterministic private-record hash for audit correlation."""

    encoded = _canonical_json(record).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
