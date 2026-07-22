from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

import pytest

from pico.providers.contracts import (
    ModelRequest,
    ProviderContinuation,
    StopReason,
    ToolCallResult,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
)
from pico.providers.openai_responses import (
    CONTINUATION_VERSION,
    OpenAIResponsesAdapter,
    OpenAIResponsesProtocolError,
)
from pico.providers.provider_transport import HttpAttempt, ProviderTransportResponse


def _tool() -> ToolDefinition:
    return ToolDefinition(
        name="weather",
        description="Get the weather.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
    )


def _wire_response(
    output: list[Any],
    *,
    status: str = "completed",
    metadata: dict[str, Any] | None = None,
) -> ProviderTransportResponse:
    payload = {
        "id": "resp_1",
        "status": status,
        "model": "gpt-test",
        "output": output,
        "usage": {"input_tokens": 10, "private_label": "must-not-leak"},
        "metadata": metadata or {},
    }
    return ProviderTransportResponse(
        payload=payload,
        raw_bytes=json.dumps(payload).encode(),
        status_code=200,
        request_id="req_1",
        http_attempts=(
            HttpAttempt(1, "POST", "https://redacted.invalid/v1/responses", 200),
        ),
        sdk_retry_count=0,
    )


class RecordingTransport:
    def __init__(self, response: ProviderTransportResponse) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    def create(self, request: Any) -> ProviderTransportResponse:
        self.requests.append(dict(request))
        return self.response


def _adapter(
    response: ProviderTransportResponse | None = None,
) -> tuple[OpenAIResponsesAdapter, RecordingTransport]:
    transport = RecordingTransport(response or _wire_response([]))
    return (
        OpenAIResponsesAdapter(
            transport=transport,
            model="gpt-test",
            profile_id="openai-responses:test-profile",
            instructions="Follow Pico policy.",
        ),
        transport,
    )


def test_request_golden_compiles_instructions_input_tools_and_named_choice() -> None:
    adapter, _ = _adapter()
    request = ModelRequest(
        prompt="Check Hong Kong.",
        max_output_tokens=256,
        tools=[_tool()],
        tool_choice=ToolChoice.named("weather"),
    )

    assert adapter.compile_request(request) == {
        "model": "gpt-test",
        "instructions": "Follow Pico policy.",
        "input": "Check Hong Kong.",
        "max_output_tokens": 256,
        "stream": False,
        "store": False,
        "parallel_tool_calls": False,
        "tools": [
            {
                "type": "function",
                "name": "weather",
                "description": "Get the weather.",
                "parameters": _tool().input_schema,
                "strict": True,
            }
        ],
        "tool_choice": {"type": "function", "name": "weather"},
    }


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        (ToolChoice(), "auto"),
        (ToolChoice(mode=ToolChoiceMode.NONE), "none"),
        (ToolChoice(mode=ToolChoiceMode.REQUIRED), "required"),
    ],
)
def test_request_compiles_each_non_named_tool_choice(
    choice: ToolChoice, expected: str
) -> None:
    adapter, _ = _adapter()
    request = ModelRequest(
        prompt="next", max_output_tokens=32, tools=[_tool()], tool_choice=choice
    )

    assert adapter.compile_request(request)["tool_choice"] == expected


def test_response_golden_keeps_interim_text_calls_reasoning_and_unknown_items() -> None:
    reasoning = {
        "type": "reasoning",
        "id": "rs_1",
        "encrypted_content": "private-reasoning",
        "summary": [],
    }
    interim = {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "I will check. "}],
    }
    call = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": "call_1",
        "name": "weather",
        "arguments": '{"city":"Hong Kong"}',
    }
    unknown = {"type": "future_private", "opaque": {"token": "private-unknown"}}
    adapter, _ = _adapter(_wire_response([reasoning, interim, call, unknown]))

    parsed = adapter.parse_response(_wire_response([reasoning, interim, call, unknown]))

    assert parsed.text == "I will check. "
    assert parsed.stop_reason is StopReason.TOOL_CALLS
    assert parsed.tool_calls[0].to_dict() == {
        "call_id": "call_1",
        "name": "weather",
        "arguments": {"city": "Hong Kong"},
    }
    assert parsed.continuation is not None
    assert parsed.continuation.payload == {
        "version": CONTINUATION_VERSION,
        "output_items": [reasoning, interim, call, unknown],
    }
    public = json.dumps(parsed.metadata)
    assert "private-reasoning" not in public
    assert "private-unknown" not in public
    assert parsed.metadata["unknown_item_types"] == ["future_private"]


def test_continuation_and_each_tool_result_roundtrip_by_provider_call_id() -> None:
    adapter, _ = _adapter()
    output_items = [
        {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque"},
        {
            "type": "future_private",
            "opaque": [1, {"nested": "kept"}],
        },
    ]
    continuation = ProviderContinuation(
        "openai-responses:test-profile",
        {"version": CONTINUATION_VERSION, "output_items": output_items},
    )
    request = ModelRequest(
        prompt="original prompt is not repeated during the tool loop",
        max_output_tokens=64,
        tools=[_tool()],
        tool_choice=ToolChoice(mode=ToolChoiceMode.NONE),
        tool_results=[
            ToolCallResult("call_1", {"temperature": 22}),
            ToolCallResult("call_2", {"reason": "denied"}, is_error=True),
        ],
        continuation=continuation,
    )

    wire = adapter.compile_request(request)

    assert wire["input"] == [
        *output_items,
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": '{"temperature":22}',
        },
        {
            "type": "function_call_output",
            "call_id": "call_2",
            "output": '{"is_error":true,"output":{"reason":"denied"}}',
        },
    ]
    assert wire["tool_choice"] == "none"


def test_raw_sdk_response_bytes_win_over_lossy_typed_unknown_item() -> None:
    unknown = {"type": "future_private", "opaque": {"nested": [1, "two"]}}
    raw = _wire_response([unknown])
    lossy_payload = dict(raw.payload)
    lossy_payload["output"] = [{**unknown, "content": None, "status": None}]
    response = replace(raw, payload=lossy_payload)
    adapter, _ = _adapter()

    parsed = adapter.parse_response(response)

    assert parsed.continuation is not None
    assert parsed.continuation.payload["output_items"] == [unknown]


def test_adapter_sends_exactly_one_operation_and_returns_native_contract() -> None:
    response = _wire_response(
        [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "done"}],
            }
        ]
    )
    adapter, transport = _adapter(response)

    parsed = adapter.request(ModelRequest(prompt="finish", max_output_tokens=16))

    assert len(transport.requests) == 1
    assert parsed.text == "done"
    assert parsed.stop_reason is StopReason.END_TURN
    assert parsed.continuation is None
    assert parsed.metadata == {
        "provider": "openai",
        "dialect": "openai-responses",
        "http_status": 200,
        "http_attempt_count": 1,
        "sdk_retry_count": 0,
        "output_item_counts": {"message": 1},
        "unknown_item_types": [],
        "response_id": "resp_1",
        "model": "gpt-test",
        "status": "completed",
        "request_id": "req_1",
        "usage": {"input_tokens": 10},
    }


@pytest.mark.parametrize(
    ("item", "code"),
    [
        (
            {"type": "function_call", "name": "weather", "arguments": "{}"},
            "missing_call_id",
        ),
        (
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "weather",
                "arguments": "{",
            },
            "invalid_arguments",
        ),
        (
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "weather",
                "arguments": "[]",
            },
            "invalid_arguments",
        ),
        (
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "weather",
                "arguments": '{"value":NaN}',
            },
            "invalid_arguments",
        ),
    ],
)
def test_malformed_native_call_fails_closed_with_stable_taxonomy(
    item: dict[str, Any], code: str
) -> None:
    adapter, _ = _adapter()

    with pytest.raises(OpenAIResponsesProtocolError) as captured:
        adapter.parse_response(_wire_response([item]))

    assert captured.value.code == code


def test_duplicate_call_id_fails_closed() -> None:
    call = {
        "type": "function_call",
        "call_id": "same",
        "name": "weather",
        "arguments": "{}",
    }
    adapter, _ = _adapter()

    with pytest.raises(OpenAIResponsesProtocolError) as captured:
        adapter.parse_response(_wire_response([call, call]))

    assert captured.value.code == "duplicate_call_id"


def test_continuation_is_profile_bound_and_structurally_validated() -> None:
    adapter, _ = _adapter()
    wrong_profile = ProviderContinuation(
        "openai-responses:other-profile",
        {"version": CONTINUATION_VERSION, "output_items": []},
    )
    malformed = ProviderContinuation(
        "openai-responses:test-profile",
        {"version": "future-version", "output_items": []},
    )

    for continuation, code in (
        (wrong_profile, "profile_mismatch"),
        (malformed, "invalid_continuation"),
    ):
        with pytest.raises(OpenAIResponsesProtocolError) as captured:
            adapter.compile_request(
                ModelRequest(
                    prompt="next", max_output_tokens=16, continuation=continuation
                )
            )
        assert captured.value.code == code


def test_metadata_redacts_untrusted_identifiers_and_drops_provider_metadata() -> None:
    response = _wire_response([], metadata={"authorization": "Bearer secret"})
    payload = dict(response.payload)
    payload["id"] = "secret id with spaces"
    payload["model"] = "model\nsecret"
    payload["status"] = "completed"
    response = replace(
        response,
        payload=payload,
        raw_bytes=json.dumps(payload).encode(),
        request_id="req secret",
    )
    adapter, _ = _adapter()

    parsed = adapter.parse_response(response)

    rendered = json.dumps(parsed.metadata)
    assert "Bearer secret" not in rendered
    assert "secret id" not in rendered
    assert parsed.metadata["response_id"] == "redacted"
    assert parsed.metadata["model"] == "redacted"
    assert parsed.metadata["request_id"] == "redacted"


def test_no_text_protocol_or_chat_completions_fallback_is_present() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "pico"
        / "providers"
        / "openai_responses.py"
    ).read_text(encoding="utf-8")
    assert "<" + "tool>" not in source
    assert "<" + "final>" not in source
    assert "chat/completions" not in source
    assert "ToolRunner" not in source
    assert "AgentRunner" not in source
