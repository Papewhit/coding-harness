from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico.providers.base import complete_model
from pico.providers.contracts import (
    ModelRequest,
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
    ToolCallResult,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
)


def _weather_tool() -> ToolDefinition:
    return ToolDefinition(
        name="weather",
        description="Return the current weather.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
    )


def test_request_and_result_contracts_are_json_safe() -> None:
    continuation_source = {"response_id": "resp_1", "blocks": [{"type": "reasoning", "id": "r_1"}]}
    continuation = ProviderContinuation("openai-responses:test-profile", continuation_source)
    request = ModelRequest(
        prompt="What is the weather?",
        max_output_tokens=256,
        tools=[_weather_tool()],
        tool_choice=ToolChoice.named("weather"),
        tool_results=[ToolCallResult(call_id="call_1", output={"temperature": 21})],
        continuation=continuation,
    )

    continuation_source["response_id"] = "mutated"
    payload = request.to_dict()
    assert payload["continuation"]["payload"]["response_id"] == "resp_1"  # type: ignore[index]
    assert payload["tool_choice"] == {"mode": "named", "name": "weather"}
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload


def test_provider_continuation_is_opaque_detached_and_stably_hashable() -> None:
    first = ProviderContinuation("profile-1", {"b": [2, 3], "a": 1})
    second = ProviderContinuation("profile-1", {"a": 1, "b": [2, 3]})

    detached = first.payload
    assert isinstance(detached, dict)
    detached["a"] = 99
    assert first.payload == {"a": 1, "b": [2, 3]}
    assert first.stable_hash() == second.stable_hash()
    assert first.stable_hash().startswith("sha256:")


@pytest.mark.parametrize(
    "payload, error",
    [
        ({"bad": object()}, "non-JSON-safe"),
        ({"bad": float("nan")}, "non-finite"),
        ({1: "bad"}, "non-string"),
    ],
)
def test_json_contracts_reject_unsafe_values(payload: object, error: str) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        ProviderContinuation("profile-1", payload)


def test_tool_calls_require_non_empty_stable_call_ids() -> None:
    with pytest.raises(ValueError, match="call_id must be a non-empty string"):
        ToolCall(call_id=" ", name="weather", arguments={})
    with pytest.raises(ValueError, match="call_id must be a non-empty string"):
        ToolCallResult(call_id="", output="not executed", is_error=True)

    result = ToolCallResult(call_id="provider-call-42", output={"reason": "denied"}, is_error=True)
    assert result.to_dict() == {
        "call_id": "provider-call-42",
        "output": {"reason": "denied"},
        "is_error": True,
    }


def test_response_can_carry_text_tool_calls_and_stop_reason_together() -> None:
    response = ModelResponse(
        text="I will check that now.",
        tool_calls=[ToolCall(call_id="call_1", name="weather", arguments={"city": "Hong Kong"})],
        stop_reason=StopReason.TOOL_CALLS,
        metadata={"usage": {"input_tokens": 12, "output_tokens": 8}},
    )

    assert response.text == "I will check that now."
    assert response.tool_calls[0].call_id == "call_1"
    assert response.stop_reason is StopReason.TOOL_CALLS
    assert response.to_dict()["stop_reason"] == "tool_calls"


def test_request_and_response_reject_ambiguous_native_identifiers() -> None:
    tool = _weather_tool()
    with pytest.raises(ValueError, match="duplicate tool definition name"):
        ModelRequest(prompt="", max_output_tokens=10, tools=[tool, tool])
    with pytest.raises(ValueError, match="named tool choice must reference a declared tool"):
        ModelRequest(
            prompt="",
            max_output_tokens=10,
            tools=[tool],
            tool_choice=ToolChoice.named("missing"),
        )
    with pytest.raises(ValueError, match="duplicate tool call call_id"):
        ModelResponse(
            text="",
            tool_calls=[
                ToolCall("call_1", "weather", {}),
                ToolCall("call_1", "weather", {"city": "Kowloon"}),
            ],
            stop_reason=StopReason.TOOL_CALLS,
        )


def test_tool_choice_modes_are_explicit() -> None:
    assert ToolChoice().mode is ToolChoiceMode.AUTO
    assert ToolChoice(mode=ToolChoiceMode.NONE).to_dict() == {"mode": "none"}
    with pytest.raises(ValueError, match="valid only for named mode"):
        ToolChoice(mode=ToolChoiceMode.AUTO, name="weather")
    with pytest.raises(ValueError, match="required tool choice"):
        ModelRequest(
            prompt="",
            max_output_tokens=10,
            tool_choice=ToolChoice(mode=ToolChoiceMode.REQUIRED),
        )


def test_legacy_prompt_to_text_boundary_remains_active() -> None:
    class LegacyClient:
        last_completion_metadata = {"provider_attempts": 1}

        def complete(self, prompt: str, max_new_tokens: int, **kwargs: object) -> str:
            assert (prompt, max_new_tokens, kwargs) == ("legacy prompt", 32, {"prompt_cache_key": "cache"})
            return "legacy text"

    result = complete_model(LegacyClient(), "legacy prompt", 32, prompt_cache_key="cache")
    assert result.text == "legacy text"
    assert result.metadata == {"provider_attempts": 1}


def test_contract_module_has_no_sdk_or_text_envelope_dependency() -> None:
    source = (Path(__file__).resolve().parents[1] / "pico" / "providers" / "contracts.py").read_text(
        encoding="utf-8"
    )
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "<tool>" not in source
    assert "<final>" not in source
