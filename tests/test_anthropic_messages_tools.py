from __future__ import annotations

import json

import pytest

from pico.providers.anthropic_messages import (
    AnthropicMessagesAdapter,
    AnthropicMessagesProtocolError,
)
from pico.providers.contracts import (
    ModelRequest,
    ProviderContinuation,
    StopReason,
    ToolCallResult,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
)
from pico.providers.provider_transport import (
    HttpAttempt,
    ProviderTransportResponse,
)


class StubTransport:
    def __init__(self, response: ProviderTransportResponse) -> None:
        self.response = response
        self.requests: list[dict] = []

    def create(self, request: dict) -> ProviderTransportResponse:
        self.requests.append(request)
        return self.response


def _tool(name: str = "echo") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="Echo a value",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )


def _message(content: list[dict], *, stop_reason: str | None = "tool_use") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


def _transport_response(payload: dict) -> ProviderTransportResponse:
    return ProviderTransportResponse(
        payload=payload,
        raw_bytes=json.dumps(payload).encode(),
        status_code=200,
        request_id="req_test",
        http_attempts=(
            HttpAttempt(
                number=1,
                method="POST",
                url="https://provider.invalid/v1/messages",
                status_code=200,
                request_id="req_test",
            ),
        ),
        sdk_retry_count=0,
    )


def _adapter(response: dict | None = None, **kwargs) -> AnthropicMessagesAdapter:
    payload = response or _message([{"type": "text", "text": "done"}], stop_reason="end_turn")
    return AnthropicMessagesAdapter(
        StubTransport(_transport_response(payload)),
        model="claude-test",
        profile_id="anthropic-messages:test-profile",
        **kwargs,
    )


def test_request_golden_compiles_system_tools_and_all_tool_choices() -> None:
    adapter = _adapter(
        system="You are Pico.",
        thinking={"type": "enabled", "budget_tokens": 1024},
    )
    request = ModelRequest(
        prompt="Use echo.",
        max_output_tokens=256,
        tools=(_tool(),),
        tool_choice=ToolChoice(mode=ToolChoiceMode.REQUIRED),
    )

    payload = adapter.compile_request(request)

    assert payload == {
        "model": "claude-test",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Use echo."}],
        "stream": False,
        "system": "You are Pico.",
        "tools": [
            {
                "name": "echo",
                "description": "Echo a value",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
            }
        ],
        "tool_choice": {"type": "any", "disable_parallel_tool_use": True},
        "thinking": {"type": "enabled", "budget_tokens": 1024},
    }

    named = ModelRequest(
        prompt="Use echo.",
        max_output_tokens=10,
        tools=(_tool(),),
        tool_choice=ToolChoice.named("echo"),
    )
    assert adapter.compile_request(named)["tool_choice"] == {
        "type": "tool",
        "name": "echo",
        "disable_parallel_tool_use": True,
    }
    none = ModelRequest(
        prompt="Do not call.",
        max_output_tokens=10,
        tools=(_tool(),),
        tool_choice=ToolChoice(mode=ToolChoiceMode.NONE),
    )
    assert adapter.compile_request(none)["tool_choice"] == {"type": "none"}


def test_response_golden_parses_text_batch_and_keeps_all_blocks_private() -> None:
    private = "private chain of thought"
    redacted = "opaque-redacted-data"
    future = "future-private-data"
    content = [
        {"type": "thinking", "thinking": private, "signature": "sig-secret"},
        {"type": "redacted_thinking", "data": redacted},
        {"type": "text", "text": "Working. "},
        {"type": "future_private", "opaque": future},
        {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {"value": "一"}},
        {"type": "tool_use", "id": "toolu_2", "name": "echo", "input": {"value": "二"}},
    ]
    response = _adapter().parse_response(_message(content))

    assert response.text == "Working. "
    assert response.stop_reason is StopReason.TOOL_CALLS
    assert [call.call_id for call in response.tool_calls] == ["toolu_1", "toolu_2"]
    assert response.tool_calls[0].arguments == {"value": "一"}
    assert response.continuation is not None
    assert response.continuation.payload["assistant_content"] == content
    public = json.dumps(response.metadata, ensure_ascii=False)
    for secret in (private, redacted, future, "sig-secret"):
        assert secret not in public
    summary = response.metadata["content_blocks"]
    assert summary["private_count"] == 2
    assert summary["unknown_types"] == ["future_private"]
    assert summary["private_hash"].startswith("sha256:")


def test_batch_results_match_call_ids_and_precede_any_user_text() -> None:
    adapter = _adapter()
    first = adapter.parse_response(
        _message(
            [
                {"type": "thinking", "thinking": "keep", "signature": "sig"},
                {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {}},
                {"type": "tool_use", "id": "toolu_2", "name": "echo", "input": {}},
            ]
        )
    )
    request = ModelRequest(
        prompt="Use both tools.",
        max_output_tokens=64,
        tools=(_tool(),),
        tool_results=(
            ToolCallResult("toolu_2", {"value": "二"}),
            ToolCallResult("toolu_1", "一", is_error=True),
        ),
        continuation=first.continuation,
    )

    payload = adapter.compile_request(request)

    assert [message["role"] for message in payload["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert payload["messages"][1]["content"] == first.continuation.payload["assistant_content"]
    user_content = payload["messages"][-1]["content"]
    assert [block["type"] for block in user_content] == ["tool_result", "tool_result"]
    assert [block["tool_use_id"] for block in user_content] == ["toolu_1", "toolu_2"]
    assert user_content[0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "一",
        "is_error": True,
    }
    assert user_content[1]["content"] == '{"value":"二"}'


@pytest.mark.parametrize(
    ("results", "pattern"),
    [
        ((ToolCallResult("toolu_1", "only one"),), "exactly one"),
        (
            (
                ToolCallResult("toolu_1", "one"),
                ToolCallResult("not-from-provider", "two"),
            ),
            "exactly one",
        ),
    ],
)
def test_batch_rejects_missing_or_unmatched_results(results, pattern: str) -> None:
    adapter = _adapter()
    response = adapter.parse_response(
        _message(
            [
                {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {}},
                {"type": "tool_use", "id": "toolu_2", "name": "echo", "input": {}},
            ]
        )
    )
    request = ModelRequest(
        prompt="Use tools.",
        max_output_tokens=64,
        tools=(_tool(),),
        tool_results=results,
        continuation=response.continuation,
    )

    with pytest.raises(AnthropicMessagesProtocolError, match=pattern):
        adapter.compile_request(request)


def test_profile_mismatch_and_result_without_continuation_fail_closed() -> None:
    adapter = _adapter()
    wrong = ProviderContinuation(
        "anthropic-messages:other-profile",
        {"version": "pico-anthropic-messages-continuation-v1", "assistant_content": []},
    )
    with pytest.raises(AnthropicMessagesProtocolError, match="profile_id"):
        adapter.compile_request(
            ModelRequest(prompt="x", max_output_tokens=1, continuation=wrong)
        )
    with pytest.raises(AnthropicMessagesProtocolError, match="preceding assistant"):
        adapter.compile_request(
            ModelRequest(
                prompt="x",
                max_output_tokens=1,
                tool_results=(ToolCallResult("toolu_1", "x"),),
            )
        )


@pytest.mark.parametrize(
    ("provider_reason", "expected"),
    [
        ("end_turn", StopReason.END_TURN),
        ("tool_use", StopReason.TOOL_CALLS),
        ("stop_sequence", StopReason.STOP_SEQUENCE),
        ("max_tokens", StopReason.MAX_TOKENS),
        ("model_context_window_exceeded", StopReason.MAX_TOKENS),
        ("refusal", StopReason.CONTENT_FILTER),
        ("pause_turn", StopReason.UNKNOWN),
        ("future_reason", StopReason.UNKNOWN),
        (None, StopReason.UNKNOWN),
    ],
)
def test_stop_reasons_do_not_turn_truncation_or_unknown_into_success(
    provider_reason: str | None,
    expected: StopReason,
) -> None:
    content = (
        [{"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {}}]
        if provider_reason == "tool_use"
        else [{"type": "text", "text": "partial"}]
    )
    response = _adapter().parse_response(_message(content, stop_reason=provider_reason))
    assert response.stop_reason is expected
    if provider_reason in {"max_tokens", "future_reason", None}:
        assert response.stop_reason is not StopReason.END_TURN


def test_request_uses_json_transport_and_exposes_only_sanitized_evidence() -> None:
    private = "do-not-publish"
    payload = _message(
        [
            {"type": "thinking", "thinking": private, "signature": "private-signature"},
            {"type": "text", "text": "done"},
        ],
        stop_reason="end_turn",
    )
    transport = StubTransport(_transport_response(payload))
    adapter = AnthropicMessagesAdapter(
        transport,
        model="claude-test",
        profile_id="anthropic-messages:test-profile",
    )

    response = adapter.request(ModelRequest(prompt="Finish.", max_output_tokens=32))

    assert transport.requests[0]["stream"] is False
    assert response.text == "done"
    assert response.metadata["request_id"] == "req_test"
    assert response.metadata["sdk_retry_count"] == 0
    assert response.metadata["http_attempts"][0]["status_code"] == 200
    assert private not in json.dumps(response.metadata)


def test_malformed_blocks_and_sdk_objects_fail_at_adapter_boundary() -> None:
    adapter = _adapter()
    with pytest.raises(AnthropicMessagesProtocolError, match="object input"):
        adapter.parse_response(
            _message(
                [{"type": "tool_use", "id": "toolu_1", "name": "echo", "input": "{}"}]
            )
        )
    with pytest.raises(AnthropicMessagesProtocolError, match="non-JSON-safe object"):
        adapter.parse_response(
            _message([{"type": "future_private", "opaque": object()}], stop_reason="end_turn")
        )
    with pytest.raises(AnthropicMessagesProtocolError, match="at least one"):
        adapter.parse_response(_message([{"type": "text", "text": "no call"}]))
