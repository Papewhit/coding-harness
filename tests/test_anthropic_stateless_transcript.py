from __future__ import annotations

import json
from typing import Any

import pytest

from coda.core.tool_call_batch import run_native_tool_loop
from coda.providers.anthropic_messages import (
    AnthropicMessagesAdapter,
    AnthropicMessagesProtocolError,
)
from coda.providers.contracts import (
    ModelRequest,
    ProviderContinuation,
    ToolCallResult,
    ToolDefinition,
)
from coda.providers.provider_transport import ProviderTransportResponse


RUNTIME_PROMPT = (
    "Runtime task: update README.md so it contains the marker CODA-STATELESS, "
    "then verify the saved file."
)


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Deterministic {name} test tool.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )


def _assistant_round(call_id: str, name: str, round_number: int) -> list[dict[str, Any]]:
    return [
        {
            "type": "thinking",
            "thinking": f"private-round-{round_number}",
            "signature": f"signature-{round_number}",
        },
        {"type": "text", "text": f"round {round_number}"},
        {
            "type": "tool_use",
            "id": call_id,
            "name": name,
            "input": {"path": "README.md"},
        },
    ]


def _response(
    content: list[dict[str, Any]],
    *,
    response_id: str,
    stop_reason: str,
) -> ProviderTransportResponse:
    payload = {
        "id": response_id,
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    return ProviderTransportResponse(
        payload=payload,
        raw_bytes=json.dumps(payload).encode("utf-8"),
        status_code=200,
        request_id=f"request-{response_id}",
        http_attempts=(),
        sdk_retry_count=0,
    )


class _QueueTransport:
    def __init__(self, responses: list[ProviderTransportResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, request: dict[str, Any]) -> ProviderTransportResponse:
        self.requests.append(request)
        return self.responses.pop(0)


class _Runtime:
    max_steps = 8

    def __init__(self, model_client: AnthropicMessagesAdapter) -> None:
        self.model_client = model_client
        self._last_tool_result_metadata: dict[str, Any] = {}

    def run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"{name} completed for {arguments['path']}"


def _result_block(call_id: str, name: str) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": call_id,
        "content": f"{name} completed for README.md",
        "is_error": False,
    }


def test_three_tool_rounds_replay_complete_anthropic_stateless_transcript() -> None:
    assistant_rounds = [
        _assistant_round("toolu-read-1", "read_file", 1),
        _assistant_round("toolu-patch-1", "patch_file", 2),
        _assistant_round("toolu-read-2", "read_file", 3),
    ]
    transport = _QueueTransport(
        [
            _response(
                assistant_rounds[0],
                response_id="message-1",
                stop_reason="tool_use",
            ),
            _response(
                assistant_rounds[1],
                response_id="message-2",
                stop_reason="tool_use",
            ),
            _response(
                assistant_rounds[2],
                response_id="message-3",
                stop_reason="tool_use",
            ),
            _response(
                [{"type": "text", "text": "verified"}],
                response_id="message-4",
                stop_reason="end_turn",
            ),
        ]
    )
    adapter = AnthropicMessagesAdapter(
        transport,
        model="claude-test",
        profile_id="anthropic-messages:stateless-test",
    )
    request = ModelRequest(
        prompt=RUNTIME_PROMPT,
        max_output_tokens=128,
        tools=(_tool("read_file"), _tool("patch_file")),
    )

    result = run_native_tool_loop(
        _Runtime(adapter),
        request,
        persist_hook=lambda _batch: None,
    )

    assert result.final_text == "verified"
    assert [state.call.name for batch in result.batches for state in batch.calls] == [
        "read_file",
        "patch_file",
        "read_file",
    ]
    expected_messages: list[dict[str, Any]] = [
        {"role": "user", "content": RUNTIME_PROMPT},
    ]
    for round_number, (call_id, name) in enumerate(
        (
            ("toolu-read-1", "read_file"),
            ("toolu-patch-1", "patch_file"),
            ("toolu-read-2", "read_file"),
        )
    ):
        expected_messages.extend(
            [
                {"role": "assistant", "content": assistant_rounds[round_number]},
                {"role": "user", "content": [_result_block(call_id, name)]},
            ]
        )
        assert transport.requests[round_number + 1]["messages"] == expected_messages

    final_messages = transport.requests[3]["messages"]
    assert sum(
        message == {"role": "user", "content": RUNTIME_PROMPT}
        for message in final_messages
    ) == 1
    assert [
        block["tool_use_id"]
        for message in final_messages
        if message["role"] == "user" and isinstance(message["content"], list)
        for block in message["content"]
    ] == ["toolu-read-1", "toolu-patch-1", "toolu-read-2"]
    assert all(
        "store" not in wire_request and "previous_response_id" not in wire_request
        for wire_request in transport.requests
    )


def test_continuation_is_json_safe_and_legacy_v1_fails_before_transport() -> None:
    assistant_content = _assistant_round("toolu-read-1", "read_file", 1)
    transport = _QueueTransport(
        [
            _response(
                assistant_content,
                response_id="message-1",
                stop_reason="tool_use",
            )
        ]
    )
    adapter = AnthropicMessagesAdapter(
        transport,
        model="claude-test",
        profile_id="anthropic-messages:stateless-test",
    )
    first = adapter.request(
        ModelRequest(
            prompt=RUNTIME_PROMPT,
            max_output_tokens=128,
            tools=(_tool("read_file"),),
        )
    )

    assert first.continuation is not None
    assert first.continuation.payload == {
        "version": "coda-anthropic-messages-continuation-v2",
        "original_prompt": RUNTIME_PROMPT,
        "messages": [
            {"role": "user", "content": RUNTIME_PROMPT},
            {"role": "assistant", "content": assistant_content},
        ],
    }
    json.dumps(first.continuation.to_dict(), allow_nan=False)

    legacy_transport = _QueueTransport([])
    legacy_adapter = AnthropicMessagesAdapter(
        legacy_transport,
        model="claude-test",
        profile_id="anthropic-messages:stateless-test",
    )
    legacy = ProviderContinuation(
        "anthropic-messages:stateless-test",
        {
            "version": "coda-anthropic-messages-continuation-v1",
            "assistant_content": assistant_content,
        },
    )

    with pytest.raises(AnthropicMessagesProtocolError, match="v1 is incomplete"):
        legacy_adapter.request(
            ModelRequest(
                prompt=RUNTIME_PROMPT,
                max_output_tokens=128,
                tools=(_tool("read_file"),),
                tool_results=(
                    ToolCallResult(
                        "toolu-read-1",
                        "read_file completed for README.md",
                    ),
                ),
                continuation=legacy,
            )
        )
    assert legacy_transport.requests == []
