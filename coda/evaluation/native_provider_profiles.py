"""Sanitized, reproducible identities for native-provider evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from coda.config import ProviderConfig, resolve_provider_config
from coda.providers import native_provider_profile


PROFILE_SCHEMA_VERSION = "coda-native-provider-profile-v1"
PUBLIC_CAPABILITY_FIELDS = {
    "native_tools": "native_tools",
    "strict_tool_schema": "strict_tool_schema",
    "parallel_tool_calls": "parallel_tool_calls",
    "reasoning": "reasoning_support",
    "thinking": "thinking_support",
    "opaque_continuation": "opaque_continuation_support",
}
_SHA256_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")
PROFILE_KEYS = frozenset(
    {
        "schema_version",
        "provider",
        "profile_id",
        "model",
        "base_url_fingerprint",
        "wire_dialect",
        "adapter_mode",
        "sdk",
        "capabilities",
        "retry",
        "stream",
        "parallel_tool_calls",
    }
)


class ProviderProfileMismatchError(ValueError):
    """Raised before HTTP when local config does not match the frozen profile."""


def build_public_provider_profile(config: ProviderConfig) -> dict[str, Any]:
    """Build the canonical public identity without credentials or raw URLs."""

    if not isinstance(config, ProviderConfig):
        raise TypeError("config must be a ProviderConfig")
    identity = config.public_identity()
    transport = native_provider_profile(config.wire_dialect)
    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "provider": config.name,
        "profile_id": identity["profile_id"],
        "model": config.model,
        "base_url_fingerprint": identity["base_url_fingerprint"],
        "wire_dialect": config.wire_dialect,
        "adapter_mode": transport["adapter_mode"],
        "sdk": {
            "package": transport["sdk_package"],
            "version": transport["sdk_version"],
        },
        "capabilities": {
            public_key: config.capabilities.to_dict()[config_key]
            for config_key, public_key in PUBLIC_CAPABILITY_FIELDS.items()
        },
        "retry": {
            "sdk_max_retries": transport["sdk_max_retries"],
            "coda_provider_attempts": transport["provider_attempts"],
        },
        "stream": False,
        "parallel_tool_calls": False,
    }
    validate_public_provider_profile(profile)
    return profile


def resolve_public_provider_profile(
    provider: str,
    *,
    start: str | Path = ".",
    config_path: str | None = None,
) -> dict[str, Any]:
    """Resolve one named local profile and return only its public identity."""

    config = resolve_provider_config(
        provider,
        start=start,
        config_path=config_path,
    )
    return build_public_provider_profile(config)


def load_public_provider_profile(path: str | Path) -> dict[str, Any]:
    """Load and validate a frozen public profile manifest."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("native provider profile must be a JSON object")
    profile = deepcopy(dict(payload))
    validate_public_provider_profile(profile)
    return profile


def validate_public_provider_profile(profile: Mapping[str, Any]) -> None:
    """Fail closed on schema drift or unsafe public-profile fields."""

    if not isinstance(profile, Mapping):
        raise TypeError("native provider profile must be a mapping")
    if set(profile) != PROFILE_KEYS:
        missing = sorted(PROFILE_KEYS - set(profile))
        extra = sorted(set(profile) - PROFILE_KEYS)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError("invalid native provider profile fields: " + "; ".join(details))
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError("unsupported native provider profile schema")
    for key in (
        "provider",
        "profile_id",
        "model",
        "base_url_fingerprint",
        "wire_dialect",
        "adapter_mode",
    ):
        _required_string(profile, key)
    if _SHA256_IDENTITY.fullmatch(str(profile["profile_id"])) is None:
        raise ValueError("profile_id must be a sha256 identity")
    if (
        _SHA256_IDENTITY.fullmatch(str(profile["base_url_fingerprint"]))
        is None
    ):
        raise ValueError("base_url_fingerprint must be a sha256 identity")
    sdk = _required_mapping(profile, "sdk")
    if set(sdk) != {"package", "version"}:
        raise ValueError("profile sdk must contain only package and version")
    _required_string(sdk, "package")
    _required_string(sdk, "version")
    capabilities = _required_mapping(profile, "capabilities")
    expected_capabilities = set(PUBLIC_CAPABILITY_FIELDS.values())
    if set(capabilities) != expected_capabilities:
        raise ValueError("profile capabilities do not match the public capability set")
    if not all(type(value) is bool for value in capabilities.values()):
        raise ValueError("profile capabilities must be a boolean mapping")
    if capabilities.get("native_tools") is not True:
        raise ValueError("profile must declare native_tools=true")
    retry = _required_mapping(profile, "retry")
    if retry != {"sdk_max_retries": 0, "coda_provider_attempts": 1}:
        raise ValueError("profile retry policy must be SDK=0 and Coda attempts=1")
    if profile.get("stream") is not False:
        raise ValueError("native provider evaluation requires stream=false")
    if profile.get("parallel_tool_calls") is not False:
        raise ValueError("native provider evaluation requires parallel_tool_calls=false")
    _assert_json_safe(profile)


def assert_provider_profile_matches(
    config: ProviderConfig, expected: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild the identity from local config and compare it exactly."""

    validate_public_provider_profile(expected)
    actual = build_public_provider_profile(config)
    expected_copy = deepcopy(dict(expected))
    if actual != expected_copy:
        differing = sorted(
            key for key in PROFILE_KEYS if actual.get(key) != expected_copy.get(key)
        )
        raise ProviderProfileMismatchError(
            "resolved provider profile does not match frozen manifest: "
            + ", ".join(differing)
        )
    return actual


def provider_session_identity(
    config: ProviderConfig, *, tool_schema: str | None = None
) -> dict[str, Any]:
    """Return the flattened credential-free identity consumed by Coda Runtime."""

    identity = config.public_identity(tool_schema=tool_schema)
    return {
        **identity,
        **native_provider_profile(config.wire_dialect),
    }


def canonical_profile_json(profile: Mapping[str, Any]) -> str:
    """Serialize a validated profile with deterministic UTF-8 JSON."""

    validate_public_provider_profile(profile)
    return json.dumps(
        dict(profile),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def write_public_provider_profile(
    path: str | Path, profile: Mapping[str, Any]
) -> None:
    """Write only the canonical sanitized manifest."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical_profile_json(profile), encoding="utf-8")


def _required_mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"profile {key} must be an object")
    return item


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"profile {key} must be a non-empty string")
    return item


def _assert_json_safe(value: Any) -> None:
    try:
        encoded = json.dumps(value, allow_nan=False)
        json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("native provider profile must be JSON-safe") from exc


__all__ = [
    "PROFILE_SCHEMA_VERSION",
    "ProviderProfileMismatchError",
    "assert_provider_profile_matches",
    "build_public_provider_profile",
    "canonical_profile_json",
    "load_public_provider_profile",
    "provider_session_identity",
    "resolve_public_provider_profile",
    "validate_public_provider_profile",
    "write_public_provider_profile",
]
