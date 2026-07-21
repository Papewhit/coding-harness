from __future__ import annotations

import copy
import json

import pytest

from pico.evaluation.contracts import (
    ARTIFACT_CONTRACT_VERSION,
    NATIVE_PROTOCOL_METADATA_SCHEMA,
    extend_artifact_contract,
    native_protocol_metadata,
    ratio,
    sanitize_public_artifact,
)


def test_extend_artifact_contract_preserves_legacy_fields_without_mutation() -> None:
    legacy = {"schema_version": 1, "summary": {"pass_rate": 0.5}, "rows": [{"id": "case-1"}]}
    original = copy.deepcopy(legacy)
    protocol = native_protocol_metadata(
        eligible=True,
        native_tool_call_observed=True,
        call_id_result_match=ratio(2, 2),
        batch_completeness=ratio(1, 1),
        http_attempts=1,
    )

    artifact = extend_artifact_contract(
        legacy,
        source={"taskset": "native-conformance"},
        profile={"provider": "openai", "model": "test-model", "wire_dialect": "responses", "adapter_mode": "http"},
        native_protocol=protocol,
    )

    assert legacy == original
    assert {key: artifact[key] for key in legacy} == legacy
    assert artifact["artifact_contract_version"] == ARTIFACT_CONTRACT_VERSION
    assert artifact["evaluation_metadata"]["source"] == {"taskset": "native-conformance"}


def test_native_protocol_metadata_has_auditable_ratios_and_attempts() -> None:
    metadata = native_protocol_metadata(
        eligible=True,
        native_tool_call_observed=True,
        call_id_result_match={"numerator": 3, "denominator": 4, "excluded": 1},
        batch_completeness={"numerator": 2, "denominator": 2},
        duplicate_call_after_result=1,
        protocol_errors=[{"code": "unknown_block"}],
        http_attempts=2,
        sdk_retry_count=0,
        pico_retry_count=1,
        opaque_continuation={"hash": "sha256:abc", "type": "reasoning", "count": 2},
    )

    assert set(NATIVE_PROTOCOL_METADATA_SCHEMA["required"]) <= set(metadata)
    assert metadata["call_id_result_match"] == {"numerator": 3, "denominator": 4, "excluded": 1, "value": 0.75}
    assert metadata["batch_completeness"]["excluded"] == 0
    assert metadata["opaque_continuation"] == {"hash": "sha256:abc", "type": "reasoning", "count": 2}


def test_ratios_reject_unauditable_values() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        ratio(2, 1)
    with pytest.raises(ValueError, match="non-negative"):
        ratio(0, 1, -1)
    for value in (True, 1.9, "1"):
        with pytest.raises(ValueError, match="integer"):
            ratio(value, 2)  # type: ignore[arg-type]


def test_native_protocol_metadata_rejects_non_boolean_flags_and_non_integer_attempts() -> None:
    with pytest.raises(ValueError, match="eligible must be a boolean"):
        native_protocol_metadata(eligible="false", native_tool_call_observed=False)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="native_tool_call_observed must be a boolean"):
        native_protocol_metadata(eligible=False, native_tool_call_observed=0)  # type: ignore[arg-type]
    for field in ("http_attempts", "sdk_retry_count", "pico_retry_count", "duplicate_call_after_result"):
        with pytest.raises(ValueError, match="integer"):
            native_protocol_metadata(eligible=False, native_tool_call_observed=False, **{field: "1"})  # type: ignore[arg-type]


def test_profile_identity_and_public_artifacts_redact_secrets_and_opaque_content() -> None:
    protocol = native_protocol_metadata(
        eligible=False,
        native_tool_call_observed=False,
        opaque_continuation={"hash": "sha256:opaque", "type": "thinking", "count": 1, "content": "do not persist"},
    )
    artifact = extend_artifact_contract(
        {"schema_version": 1},
        source={"endpoint": "https://user:pass@example.test/v1?api_key=secret"},
        profile={
            "provider": "openai",
            "model": "gpt-test",
            "wire_dialect": "responses",
            "adapter_mode": "sdk",
            "sdk": {"package": "openai", "version": "1.2.3"},
            "base_url": "https://user:pass@example.test/v1?api_key=secret",
            "api_key": "sk-super-secret-value",
            "capabilities": {"native_tools": True},
        },
        native_protocol=protocol,
    )

    rendered = repr(artifact)
    assert "super-secret" not in rendered
    assert "user:pass" not in rendered
    assert "do not persist" not in rendered
    assert "base_url" not in artifact["evaluation_metadata"]["profile"]
    assert artifact["evaluation_metadata"]["native_protocol"]["opaque_continuation"] == {
        "hash": "sha256:opaque",
        "type": "thinking",
        "count": 1,
    }
    assert sanitize_public_artifact({"authorization": "Bearer top-secret"}) == {"authorization": "[redacted]"}


def test_sanitization_preserves_public_token_usage_and_fails_closed_for_non_json_values() -> None:
    sanitized = sanitize_public_artifact(
        {
            "token_usage": {"input_tokens": 5, "output_tokens": 3, "reasoning_tokens": 2, "cached_tokens": 1, "max_tokens": 10},
            "access_token": "secret",
        }
    )

    assert sanitized["token_usage"] == {
        "input_tokens": 5,
        "output_tokens": 3,
        "reasoning_tokens": 2,
        "cached_tokens": 1,
        "max_tokens": 10,
    }
    assert sanitized["access_token"] == "[redacted]"
    assert json.dumps(sanitized, allow_nan=False)
    with pytest.raises(TypeError, match="not JSON-safe"):
        sanitize_public_artifact({"opaque_sdk_object": object()})
    with pytest.raises(ValueError, match="finite"):
        sanitize_public_artifact({"latency": float("nan")})
