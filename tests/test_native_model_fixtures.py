from __future__ import annotations

import pytest

from coda.providers.contracts import ModelRequest, StopReason, ToolCallResult
from coda.testing import (
    ScriptedNativeModelClient,
    native_continuation,
    native_final_response,
    native_multi_tool_call_response,
    native_protocol_error_response,
    native_tool_call,
    native_tool_call_response,
)


def request(**overrides: object) -> ModelRequest:
    values = {"prompt": "next", "max_output_tokens": 128, **overrides}
    return ModelRequest(**values)


def test_scripted_native_client_returns_model_response_and_logs_requests() -> None:
    response = native_final_response("done")
    client = ScriptedNativeModelClient([response])
    model_request = request()

    assert client.request(model_request) is response
    assert client.call_log == (model_request,)
    assert client.requests == [model_request]
    assert client.remaining_responses == 0


def test_call_log_exposes_tool_results_and_opaque_continuation() -> None:
    continuation = native_continuation(
        {"response_id": "opaque-1", "blocks": [{"type": "reasoning", "hash": "abc"}]},
        profile_id="scripted:test",
    )
    tool_result = ToolCallResult(call_id="call-1", output={"temperature": 21})
    client = ScriptedNativeModelClient([native_final_response("sunny")])

    client.request(request(tool_results=(tool_result,), continuation=continuation))

    logged = client.call_log[0]
    assert logged.tool_results == (tool_result,)
    assert logged.continuation is continuation
    assert logged.continuation.payload["response_id"] == "opaque-1"


def test_single_and_multiple_tool_call_fixtures_are_structured() -> None:
    single = native_tool_call_response("call-1", "read_file", {"path": "README.md"})
    multiple = native_multi_tool_call_response(
        native_tool_call("call-2", "read_file", {"path": "a.txt"}),
        native_tool_call("call-3", "read_file", {"path": "b.txt"}),
        text="I will inspect both files.",
    )

    assert single.stop_reason is StopReason.TOOL_CALLS
    assert single.tool_calls[0].to_dict() == {
        "call_id": "call-1",
        "name": "read_file",
        "arguments": {"path": "README.md"},
    }
    assert [call.call_id for call in multiple.tool_calls] == ["call-2", "call-3"]
    assert multiple.text == "I will inspect both files."


def test_final_fixture_supports_non_success_stop_reason() -> None:
    response = native_final_response("partial", stop_reason=StopReason.MAX_TOKENS)

    assert response.stop_reason is StopReason.MAX_TOKENS
    assert response.tool_calls == ()


def test_protocol_error_fixture_has_normalized_error_stop_reason() -> None:
    response = native_protocol_error_response("unknown response block", code="unknown_block")

    assert response.stop_reason is StopReason.ERROR
    assert response.metadata["protocol_error"] == {
        "code": "unknown_block",
        "message": "unknown response block",
    }


def test_scripted_native_client_logs_failed_calls_and_exhaustion() -> None:
    client = ScriptedNativeModelClient([ConnectionError("offline")])
    first_request = request(prompt="first")
    second_request = request(prompt="second")

    with pytest.raises(ConnectionError, match="offline"):
        client.request(first_request)
    with pytest.raises(RuntimeError, match="ran out of responses"):
        client.request(second_request)

    assert client.call_log == (first_request, second_request)


def test_multi_call_fixture_requires_at_least_one_call() -> None:
    with pytest.raises(ValueError, match="at least one"):
        native_multi_tool_call_response()
