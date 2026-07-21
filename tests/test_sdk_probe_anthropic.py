from __future__ import annotations

import json

import httpx
import pytest

from pico.evaluation.sdk_probe import ProbeCase, ProbeProfile, RawResponse, ToolResult, run_sdk_viability_probe
from pico.evaluation.sdk_probe_anthropic import (
    AnthropicMessagesDialect,
    AnthropicMessagesTransport,
    create_anthropic_messages_transport,
)


def _profile() -> ProbeProfile:
    return ProbeProfile.from_mapping(
        {
            "provider": "anthropic",
            "model": "claude-probe",
            "wire_dialect": "anthropic-messages",
            "adapter_mode": "sdk",
            "sdk": {"package": "anthropic", "version": "probe"},
            "base_url_fingerprint": "sha256:fake-endpoint",
            "capabilities": {"native_tools": True, "opaque_continuation_support": True},
            "retry": {"sdk_max_retries": 0, "pico_attempts": 1},
        }
    )


def _case() -> ProbeCase:
    return ProbeCase.from_mapping(
        {
            "id": "roundtrip",
            "kind": "result_roundtrip",
            "prompt": "Use echo",
            "tool": {
                "name": "echo",
                "description": "Echo a value",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            },
            "tool_result": {"value": "一"},
        }
    )


def _message(content: list[dict[str, object]], *, stop_reason: str) -> dict[str, object]:
    return {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": "claude-probe",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def test_dialect_roundtrips_tool_ids_and_keeps_thinking_private() -> None:
    dialect = AnthropicMessagesDialect()
    first = dialect.build_request(_case(), _profile(), ())
    assert first["stream"] is False
    assert first["tools"][0]["input_schema"]["required"] == ["value"]

    private = "private chain of thought"
    parsed = dialect.parse_response(
        RawResponse.from_json(
            _message(
                [
                    {"type": "thinking", "thinking": private, "signature": "sig-secret"},
                    {"type": "redacted_thinking", "data": "redacted-secret"},
                    {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {"value": "一"}},
                ],
                stop_reason="tool_use",
            )
        )
    )
    assert parsed.tool_calls[0].call_id == "toolu_1"
    assert parsed.opaque_continuation["type"] == "anthropic-thinking"
    assert parsed.opaque_continuation["count"] == 2
    assert parsed.opaque_continuation["hash"].startswith("sha256:")
    assert private not in json.dumps(parsed.opaque_continuation)

    follow_up = dialect.build_request(
        _case(), _profile(), (ToolResult("toolu_1", "echo", {"value": "一"}),)
    )
    assert [message["role"] for message in follow_up["messages"]] == ["user", "assistant", "user"]
    assistant = follow_up["messages"][1]["content"]
    assert [block["type"] for block in assistant] == ["thinking", "redacted_thinking", "tool_use"]
    results = follow_up["messages"][2]["content"]
    assert [block["tool_use_id"] for block in results] == ["toolu_1"]
    assert results[0]["is_error"] is False

    with pytest.raises(ValueError, match="exactly one"):
        dialect.build_request(
            _case(),
            _profile(),
            (
                ToolResult("toolu_1", "echo", "first"),
                ToolResult("toolu_1", "echo", "duplicate"),
            ),
        )


def test_transport_uses_custom_base_url_raw_response_and_zero_retries() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_message([{"type": "text", "text": "ready"}], stop_reason="end_turn"))

    transport = create_anthropic_messages_transport(
        base_url="https://probe.invalid/custom", http_transport=httpx.MockTransport(handler)
    )
    exchange = transport.send(
        {"model": "claude-probe", "max_tokens": 32, "messages": [{"role": "user", "content": "hi"}]}
    )

    assert requests[0].url == httpx.URL("https://probe.invalid/custom/v1/messages")
    assert len(exchange.http_attempts) == 1
    assert exchange.http_attempts[0].status_code == 200
    assert exchange.sdk_retry_count == 0
    assert exchange.response.raw_bytes.startswith(b"{")
    assert exchange.response.payload["content"][0]["text"] == "ready"


def test_sdk_fake_roundtrip_has_adjacent_result_turn_and_sanitized_artifact() -> None:
    requests: list[dict[str, object]] = []
    private = "never publish this thinking"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            content = [
                {"type": "thinking", "thinking": private, "signature": "sig-secret"},
                {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {"value": "一"}},
            ]
            return httpx.Response(200, json=_message(content, stop_reason="tool_use"))
        return httpx.Response(200, json=_message([{"type": "text", "text": "handled"}], stop_reason="end_turn"))

    artifact = run_sdk_viability_probe(
        cases=[_case()],
        profile=_profile(),
        dialect=AnthropicMessagesDialect(),
        transport=create_anthropic_messages_transport(
            base_url="https://probe.invalid", http_transport=httpx.MockTransport(handler)
        ),
    )

    assert artifact["summary"] == {"case_count": 1, "passed": 1, "failed": 0}
    assert [message["role"] for message in requests[1]["messages"]] == ["user", "assistant", "user"]
    result_blocks = requests[1]["messages"][2]["content"]
    assert [block["tool_use_id"] for block in result_blocks] == ["toolu_1"]
    rendered = json.dumps(artifact, ensure_ascii=False)
    assert private not in rendered
    assert "sig-secret" not in rendered
    assert "toolu_1" in rendered
    protocol = artifact["evaluation_metadata"]["native_protocol"]
    assert protocol["http_attempts"] == 2
    assert protocol["sdk_retry_count"] == 0


def test_transport_rejects_sdk_clients_with_retries_enabled() -> None:
    class Client:
        max_retries = 2

    with pytest.raises(ValueError, match="max_retries=0"):
        AnthropicMessagesTransport(Client(), [])
