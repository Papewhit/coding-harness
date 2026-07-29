from __future__ import annotations

import json
from typing import Any

from coda.core.tool_call_batch import run_native_tool_loop
from coda.providers.contracts import ModelRequest, ToolDefinition
from coda.providers.openai_responses import OpenAIResponsesAdapter
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
            "additionalProperties": True,
        },
    )


def _response(*output: dict[str, Any], response_id: str) -> ProviderTransportResponse:
    payload = {
        "id": response_id,
        "status": "completed",
        "model": "gpt-test",
        "output": list(output),
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


def _call(call_id: str, name: str) -> dict[str, Any]:
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": '{"path":"README.md"}',
    }


class _QueueTransport:
    def __init__(self, responses: list[ProviderTransportResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def create(self, request: Any) -> ProviderTransportResponse:
        self.requests.append(dict(request))
        return self.responses.pop(0)


class _Runtime:
    max_steps = 8

    def __init__(self, model_client: OpenAIResponsesAdapter) -> None:
        self.model_client = model_client
        self._last_tool_result_metadata: dict[str, Any] = {}

    def run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"{name} completed for {arguments['path']}"


def _adapter_with_responses(
    *responses: ProviderTransportResponse,
) -> tuple[OpenAIResponsesAdapter, _QueueTransport]:
    transport = _QueueTransport(list(responses))
    adapter = OpenAIResponsesAdapter(
        transport=transport,
        model="gpt-test",
        profile_id="openai-responses:stateless-test",
    )
    return adapter, transport


def _initial_request() -> ModelRequest:
    return ModelRequest(
        prompt=RUNTIME_PROMPT,
        max_output_tokens=128,
        tools=(_tool("read_file"), _tool("patch_file")),
    )


def _function_outputs(wire_input: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in wire_input if item.get("type") == "function_call_output"]


def test_second_request_replays_prompt_call_and_result_without_server_state() -> None:
    first_call = _call("call-read-1", "read_file")
    adapter, transport = _adapter_with_responses(
        _response(first_call, response_id="response-1"),
        _response(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "done"}],
            },
            response_id="response-2",
        ),
    )

    result = run_native_tool_loop(
        _Runtime(adapter),
        _initial_request(),
        persist_hook=lambda _batch: None,
    )

    assert result.final_text == "done"
    assert transport.requests[0]["store"] is False
    assert "previous_response_id" not in transport.requests[1]
    assert transport.requests[1]["input"] == [
        {"role": "user", "content": RUNTIME_PROMPT},
        first_call,
        {
            "type": "function_call_output",
            "call_id": "call-read-1",
            "output": "read_file completed for README.md",
        },
    ]


def test_three_tool_rounds_accumulate_complete_stateless_transcript() -> None:
    calls = [
        _call("call-read-1", "read_file"),
        _call("call-patch-1", "patch_file"),
        _call("call-read-2", "read_file"),
    ]
    adapter, transport = _adapter_with_responses(
        _response(calls[0], response_id="response-1"),
        _response(calls[1], response_id="response-2"),
        _response(calls[2], response_id="response-3"),
        _response(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "verified"}],
            },
            response_id="response-4",
        ),
    )

    result = run_native_tool_loop(
        _Runtime(adapter),
        _initial_request(),
        persist_hook=lambda _batch: None,
    )

    assert result.final_text == "verified"
    assert [state.call.name for batch in result.batches for state in batch.calls] == [
        "read_file",
        "patch_file",
        "read_file",
    ]
    for wire_request in transport.requests:
        assert wire_request["store"] is False
        assert "previous_response_id" not in wire_request

    final_input = transport.requests[3]["input"]
    assert final_input == [
        {"role": "user", "content": RUNTIME_PROMPT},
        calls[0],
        {
            "type": "function_call_output",
            "call_id": "call-read-1",
            "output": "read_file completed for README.md",
        },
        calls[1],
        {
            "type": "function_call_output",
            "call_id": "call-patch-1",
            "output": "patch_file completed for README.md",
        },
        calls[2],
        {
            "type": "function_call_output",
            "call_id": "call-read-2",
            "output": "read_file completed for README.md",
        },
    ]
    outputs = _function_outputs(final_input)
    assert [item["call_id"] for item in outputs] == [
        "call-read-1",
        "call-patch-1",
        "call-read-2",
    ]
    assert all(
        sum(item.get("call_id") == call_id for item in outputs) == 1
        for call_id in ("call-read-1", "call-patch-1", "call-read-2")
    )
