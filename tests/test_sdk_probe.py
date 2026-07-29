from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pytest

from pico.evaluation.sdk_probe import (
    HttpAttempt,
    ParsedResponse,
    ProbeCase,
    ProbeProfile,
    RawResponse,
    ToolCall,
    ToolResult,
    TransportExchange,
    run_sdk_viability_probe,
    write_probe_artifact,
)


class FakeDialect:
    def __init__(self, name: str = "fake-native") -> None:
        self.name = name

    def build_request(
        self,
        case: ProbeCase,
        profile: ProbeProfile,
        tool_results: Sequence[ToolResult],
    ) -> Mapping[str, Any]:
        return {
            "case_id": case.id,
            "kind": case.kind,
            "model": profile.model,
            "tool_results": [
                {"call_id": result.call_id, "output": result.output, "is_error": result.is_error}
                for result in tool_results
            ],
        }

    def parse_response(self, response: RawResponse) -> ParsedResponse:
        payload = response.payload
        calls = tuple(
            ToolCall(item["id"], item["name"], item["arguments"])
            for item in payload.get("tool_calls", [])
        )
        return ParsedResponse(
            final_text=payload.get("final"),
            tool_calls=calls,
            opaque_continuation=payload.get("opaque_continuation"),
            unknown_block_types=tuple(payload.get("unknown_block_types", [])),
        )


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[Mapping[str, Any]] = []

    def send(self, request: Mapping[str, Any]) -> TransportExchange:
        self.requests.append(request)
        kind = request["kind"]
        results = request["tool_results"]
        if results:
            payload = {"final": "handled", "authorization": "Bearer do-not-persist"}
            if kind == "result_roundtrip":
                assert results[0]["call_id"] == "call-1"
                assert results[0]["is_error"] is False
            if kind == "invalid_args":
                assert results[0]["is_error"] is True
                assert results[0]["output"]["error"] == "invalid_arguments"
        elif kind == "final":
            payload = {"final": "ready", "api_key": "sk-secret-secret-secret"}
        elif kind == "unicode":
            payload = {"final": "工具调用 café 🚀"}
        elif kind == "opaque_block":
            payload = {
                "final": "ready",
                "private_reasoning": "must never enter the artifact",
                "opaque_continuation": {"hash": "sha256:opaque", "type": "reasoning", "count": 1},
            }
        elif kind == "invalid_args":
            payload = {"tool_calls": [{"id": "call-bad", "name": "echo", "arguments": "{bad json"}]}
        else:
            payload = {"tool_calls": [{"id": "call-1", "name": "echo", "arguments": {"value": "一"}}]}
        retries = 1 if kind == "result_roundtrip" and not results else 0
        attempts = (
            (HttpAttempt(1, status_code=429), HttpAttempt(2, status_code=200))
            if retries
            else (HttpAttempt(1, status_code=200),)
        )
        return TransportExchange(
            response=RawResponse.from_json(payload),
            http_attempts=attempts,
            sdk_retry_count=retries,
        )


def fake_dialect_factory(profile: ProbeProfile) -> FakeDialect:
    return FakeDialect(profile.wire_dialect)


def fake_transport_factory(profile: ProbeProfile) -> FakeTransport:
    del profile
    return FakeTransport()


def _profile() -> ProbeProfile:
    return ProbeProfile.from_mapping(
        {
            "provider": "fake",
            "model": "fake-model",
            "wire_dialect": "fake-native",
            "adapter_mode": "sdk",
            "sdk": {"package": "fake-sdk", "version": "1.2.3"},
            "base_url_fingerprint": "sha256:endpoint",
            "capabilities": {"native_tools": True, "opaque_continuation_support": True},
            "retry": {"sdk_max_retries": 0, "pico_attempts": 1},
        }
    )


def _cases() -> list[ProbeCase]:
    return [
        ProbeCase.from_mapping({"id": "final", "kind": "final", "prompt": "final", "expected": {"final_text": "ready"}}),
        ProbeCase.from_mapping(
            {"id": "native", "kind": "native_call", "prompt": "call", "tool": {"name": "echo"}}
        ),
        ProbeCase.from_mapping(
            {
                "id": "roundtrip",
                "kind": "result_roundtrip",
                "prompt": "roundtrip",
                "tool": {"name": "echo"},
                "tool_result": {"value": "一"},
            }
        ),
        ProbeCase.from_mapping(
            {"id": "invalid", "kind": "invalid_args", "prompt": "invalid", "tool": {"name": "echo"}}
        ),
        ProbeCase.from_mapping(
            {"id": "unicode", "kind": "unicode", "prompt": "unicode", "expected": {"final_text": "工具调用 café 🚀"}}
        ),
        ProbeCase.from_mapping(
            {"id": "opaque", "kind": "opaque_block", "prompt": "opaque", "expected": {"final_text": "ready"}}
        ),
    ]


def test_probe_supports_all_case_kinds_and_one_to_one_result_roundtrip(tmp_path) -> None:
    transport = FakeTransport()
    artifact = run_sdk_viability_probe(
        cases=_cases(), profile=_profile(), dialect=FakeDialect(), transport=transport
    )

    assert artifact["summary"] == {"case_count": 6, "passed": 6, "failed": 0}
    rows = {row["id"]: row for row in artifact["rows"]}
    assert rows["native"]["excluded_tool_call_count"] == 1
    assert rows["roundtrip"]["roundtrip_complete"] is True
    assert rows["invalid"]["invalid_argument_count"] == 1
    assert rows["unicode"]["passed"] is True
    assert rows["opaque"]["opaque_continuations"] == [
        {"hash": "sha256:opaque", "type": "reasoning", "count": 1}
    ]
    protocol = artifact["evaluation_metadata"]["native_protocol"]
    assert protocol["call_id_result_match"] == {
        "numerator": 2,
        "denominator": 2,
        "excluded": 1,
        "value": 1.0,
    }
    assert protocol["batch_completeness"]["value"] == 1.0
    assert protocol["http_attempts"] == 9
    assert protocol["sdk_retry_count"] == 1
    assert protocol["pico_retry_count"] == 0

    output = tmp_path / "artifact.json"
    write_probe_artifact(output, artifact)
    rendered = output.read_text(encoding="utf-8")
    assert "do-not-persist" not in rendered
    assert "secret-secret" not in rendered
    assert "must never enter" not in rendered
    persisted = json.loads(rendered)
    raw_capture = persisted["rows"][0]["turns"][0]["raw_response"]
    assert set(raw_capture) == {"byte_count", "sha256"}
    assert raw_capture["byte_count"] > 0
    assert len(raw_capture["sha256"]) == 64


def test_profile_and_dialect_are_plugins_and_ineligible_profiles_do_not_send() -> None:
    profile_value = _profile().artifact_identity()
    profile_value["capabilities"] = {"native_tools": False}
    profile = ProbeProfile.from_mapping(profile_value)
    transport = FakeTransport()

    artifact = run_sdk_viability_probe(
        cases=[_cases()[0]], profile=profile, dialect=FakeDialect(), transport=transport
    )

    assert transport.requests == []
    assert artifact["summary"]["failed"] == 1
    assert artifact["evaluation_metadata"]["native_protocol"]["eligible"] is False
    with pytest.raises(ValueError, match="does not match"):
        run_sdk_viability_probe(
            cases=[_cases()[0]],
            profile=ProbeProfile.from_mapping({**profile_value, "wire_dialect": "other"}),
            dialect=FakeDialect(),
            transport=transport,
        )


def test_transport_must_report_auditable_http_attempts_and_sdk_retries() -> None:
    response = RawResponse.from_json({"final": "ready"})
    with pytest.raises(ValueError, match="at least one"):
        TransportExchange(response=response, http_attempts=())
    with pytest.raises(ValueError, match="non-negative"):
        TransportExchange(response=response, http_attempts=(HttpAttempt(1, 200),), sdk_retry_count=-1)
    with pytest.raises(ValueError, match="contiguous"):
        TransportExchange(response=response, http_attempts=(HttpAttempt(2, 200),))


def test_case_schema_rejects_missing_tools_and_unknown_kinds() -> None:
    with pytest.raises(ValueError, match="requires a tool"):
        ProbeCase.from_mapping({"id": "bad", "kind": "native_call", "prompt": "call"})
    with pytest.raises(ValueError, match="unsupported"):
        ProbeCase.from_mapping({"id": "bad", "kind": "text-envelope", "prompt": "call"})
