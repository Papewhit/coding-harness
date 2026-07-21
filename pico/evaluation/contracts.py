"""Provider-neutral contracts for persisted evaluation artifacts.

The contract deliberately stores observations rather than provider response
objects.  This keeps evaluation evidence JSON-safe and makes the denominator
of every native-protocol ratio auditable.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


ARTIFACT_CONTRACT_VERSION = "pico-evaluation-artifact-v1"
REDACTED = "[redacted]"

# These are intentionally plain dictionaries rather than SDK schema objects.
ARTIFACT_CONTRACT_SCHEMA: dict[str, Any] = {
    "version": ARTIFACT_CONTRACT_VERSION,
    "required": ("artifact_contract_version", "evaluation_metadata"),
    "evaluation_metadata": ("source", "profile", "native_protocol"),
}
NATIVE_PROTOCOL_METADATA_SCHEMA: dict[str, Any] = {
    "required": (
        "eligible",
        "native_tool_call_observed",
        "call_id_result_match",
        "batch_completeness",
        "duplicate_call_after_result",
        "protocol_errors",
        "http_attempts",
        "sdk_retry_count",
        "pico_retry_count",
    ),
    "ratio_fields": ("call_id_result_match", "batch_completeness"),
    "opaque_continuation_fields": ("hash", "type", "count"),
}

_SECRET_KEY = re.compile(r"(?:api[._-]?key|authorization|credential|password|secret|token)", re.IGNORECASE)
_SECRET_VALUE = re.compile(r"(?:^|\s)(?:sk|pk|rk|xox[baprs])-?[A-Za-z0-9_-]{12,}")
_OPAQUE_CONTINUATION_KEYS = frozenset({"opaque_continuation", "continuation", "thinking", "reasoning"})


def ratio(numerator: int, denominator: int, excluded: int = 0) -> dict[str, int | float | None]:
    """Return an auditable ratio without hiding zero-denominator cases."""

    numerator = _non_negative_int("numerator", numerator)
    denominator = _non_negative_int("denominator", denominator)
    excluded = _non_negative_int("excluded", excluded)
    if numerator > denominator:
        raise ValueError("numerator cannot exceed denominator")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "excluded": excluded,
        "value": numerator / denominator if denominator else None,
    }


def native_protocol_metadata(
    *,
    eligible: bool,
    native_tool_call_observed: bool,
    call_id_result_match: Mapping[str, Any] | None = None,
    batch_completeness: Mapping[str, Any] | None = None,
    duplicate_call_after_result: int = 0,
    protocol_errors: list[Mapping[str, Any] | str] | None = None,
    http_attempts: int = 0,
    sdk_retry_count: int = 0,
    pico_retry_count: int = 0,
    opaque_continuation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create JSON-safe native protocol evidence for one evaluation row."""

    payload: dict[str, Any] = {
        "eligible": bool(eligible),
        "native_tool_call_observed": bool(native_tool_call_observed),
        "call_id_result_match": _normalize_ratio(call_id_result_match),
        "batch_completeness": _normalize_ratio(batch_completeness),
        "duplicate_call_after_result": _non_negative_int(
            "duplicate_call_after_result", duplicate_call_after_result
        ),
        "protocol_errors": sanitize_public_artifact(protocol_errors or []),
        "http_attempts": _non_negative_int("http_attempts", http_attempts),
        "sdk_retry_count": _non_negative_int("sdk_retry_count", sdk_retry_count),
        "pico_retry_count": _non_negative_int("pico_retry_count", pico_retry_count),
    }
    if opaque_continuation is not None:
        payload["opaque_continuation"] = sanitize_opaque_continuation(opaque_continuation)
    validate_native_protocol_metadata(payload)
    return payload


def profile_identity(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Keep reproducibility identity while excluding credentials and raw URLs."""

    sdk = profile.get("sdk", {})
    retry = profile.get("retry", {})
    if not isinstance(sdk, Mapping):
        sdk = {}
    if not isinstance(retry, Mapping):
        retry = {}
    capabilities = profile.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    return {
        "provider": _safe_scalar(profile.get("provider")),
        "model": _safe_scalar(profile.get("model")),
        "wire_dialect": _safe_scalar(profile.get("wire_dialect")),
        "adapter_mode": _safe_scalar(profile.get("adapter_mode")),
        "sdk": {
            "package": _safe_scalar(sdk.get("package", profile.get("sdk_package"))),
            "version": _safe_scalar(sdk.get("version", profile.get("sdk_version"))),
        },
        "base_url_fingerprint": _safe_scalar(profile.get("base_url_fingerprint")),
        "capabilities": sanitize_public_artifact(dict(capabilities)),
        "retry": sanitize_public_artifact(dict(retry)),
    }


def extend_artifact_contract(
    legacy_artifact: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    profile: Mapping[str, Any],
    native_protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Add v1 metadata without changing any existing artifact fields."""

    if "artifact_contract_version" in legacy_artifact or "evaluation_metadata" in legacy_artifact:
        raise ValueError("artifact already contains evaluation contract metadata")
    normalized_protocol = sanitize_public_artifact(dict(native_protocol))
    validate_native_protocol_metadata(normalized_protocol)
    artifact = deepcopy(dict(legacy_artifact))
    artifact["artifact_contract_version"] = ARTIFACT_CONTRACT_VERSION
    artifact["evaluation_metadata"] = {
        "source": sanitize_public_artifact(dict(source)),
        "profile": profile_identity(profile),
        "native_protocol": normalized_protocol,
    }
    return artifact


def validate_native_protocol_metadata(metadata: Mapping[str, Any]) -> None:
    """Fail early when evidence cannot support a later audit."""

    missing = [field for field in NATIVE_PROTOCOL_METADATA_SCHEMA["required"] if field not in metadata]
    if missing:
        raise ValueError(f"native protocol metadata missing required fields: {', '.join(missing)}")
    for field in NATIVE_PROTOCOL_METADATA_SCHEMA["ratio_fields"]:
        _normalize_ratio(metadata[field])
    for field in ("duplicate_call_after_result", "http_attempts", "sdk_retry_count", "pico_retry_count"):
        _non_negative_int(field, metadata[field])
    if not isinstance(metadata["protocol_errors"], list):
        raise ValueError("protocol_errors must be a list")
    continuation = metadata.get("opaque_continuation")
    if continuation is not None:
        sanitized = sanitize_opaque_continuation(continuation)
        if dict(continuation) != sanitized:
            raise ValueError("opaque_continuation may contain only hash, type, and count")


def sanitize_opaque_continuation(value: Mapping[str, Any]) -> dict[str, Any]:
    """Represent opaque provider state by its shape only, never its contents."""

    return {
        "hash": _safe_scalar(value.get("hash")),
        "type": _safe_scalar(value.get("type")),
        "count": _non_negative_int("opaque continuation count", value.get("count", 0)),
    }


def sanitize_public_artifact(value: Any, *, key: str | None = None) -> Any:
    """Redact secret-bearing fields before public evaluation evidence is written."""

    if key and _SECRET_KEY.search(key):
        return REDACTED
    if key and key.lower() in _OPAQUE_CONTINUATION_KEYS and isinstance(value, Mapping):
        return sanitize_opaque_continuation(value)
    if isinstance(value, Mapping):
        return {str(item_key): sanitize_public_artifact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_public_artifact(item, key=key) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _normalize_ratio(value: Mapping[str, Any] | None) -> dict[str, int | float | None]:
    value = value or {}
    if not isinstance(value, Mapping):
        raise ValueError("ratio must be a mapping")
    return ratio(value.get("numerator", 0), value.get("denominator", 0), value.get("excluded", 0))


def _non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _safe_scalar(value: Any) -> str:
    return _sanitize_text(str(value or ""))


def _sanitize_text(value: str) -> str:
    if _SECRET_VALUE.search(value):
        return REDACTED
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value.split("?", 1)[0].split("#", 1)[0]
    if not parsed.scheme or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    if not hostname:
        return value.split("?", 1)[0].split("#", 1)[0]
    netloc = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    try:
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
    except ValueError:
        pass
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
