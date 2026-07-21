from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from pico.evaluation.sdk_probe import ProbeCase, ProbeProfile, RawResponse, run_sdk_viability_probe
from pico.evaluation.sdk_probe_openai import (
    OpenAIResponsesDialect,
    OpenAIResponsesTransport,
)


def _profile() -> ProbeProfile:
    return ProbeProfile.from_mapping(
        {
            "provider": "openai-compatible",
            "model": "probe-model",
            "wire_dialect": "openai-responses",
            "adapter_mode": "sdk",
            "sdk": {"package": "openai", "version": "probe"},
            "base_url_fingerprint": "sha256:fake-endpoint",
            "capabilities": {"native_tools": True, "opaque_continuation_support": True},
            "retry": {"sdk_max_retries": 0, "pico_attempts": 1},
        }
    )


def _case() -> ProbeCase:
    return ProbeCase.from_mapping(
        {
            "id": "openai-roundtrip",
            "kind": "result_roundtrip",
            "prompt": "Call echo once.",
            "tool": {
                "name": "echo",
                "description": "Echo one value.",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            "tool_result": {"value": "工具"},
        }
    )


def _response(output: list[dict[str, Any]], response_id: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": "probe-model",
        "output": output,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "metadata": {},
    }


@pytest.mark.parametrize("response_mode", ["typed", "raw"])
def test_responses_sdk_records_typed_and_raw_roundtrip_without_executing_tools(
    response_mode: str,
) -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://probe.invalid/custom/v1/responses")
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            assert body["tools"][0]["name"] == "echo"
            assert body["tool_choice"] == "required"
            return httpx.Response(
                200,
                json=_response(
                    [
                        {
                            "type": "reasoning",
                            "id": "rs_1",
                            "summary": [],
                            "encrypted_content": "opaque-reasoning-do-not-persist",
                        },
                        {
                            "type": "function_call",
                            "id": "fc_1",
                            "call_id": "call_1",
                            "name": "echo",
                            "arguments": '{"value":"工具"}',
                            "status": "completed",
                        },
                    ],
                    "resp_1",
                ),
            )

        reasoning, result = body["input"]
        assert reasoning["id"] == "rs_1"
        assert reasoning["encrypted_content"] == "opaque-reasoning-do-not-persist"
        assert result == {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": '{"value":"工具"}',
        }
        assert body["tool_choice"] == "none"
        return httpx.Response(
            200,
            json=_response(
                [
                    {
                        "type": "message",
                        "id": "msg_1",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "handled",
                                "annotations": [],
                                "logprobs": [],
                            }
                        ],
                    }
                ],
                "resp_2",
            ),
        )

    transport = OpenAIResponsesTransport(
        base_url="https://probe.invalid/custom/v1",
        api_key="sk-fake-not-a-live-key",
        response_mode=response_mode,
        max_retries=0,
        http_transport=httpx.MockTransport(handler),
    )
    try:
        artifact = run_sdk_viability_probe(
            cases=[_case()],
            profile=_profile(),
            dialect=OpenAIResponsesDialect(),
            transport=transport,
        )
    finally:
        transport.close()

    assert len(requests) == 2
    assert artifact["summary"] == {"case_count": 1, "passed": 1, "failed": 0}
    row = artifact["rows"][0]
    assert row["matched_tool_result_count"] == 1
    assert row["roundtrip_complete"] is True
    assert row["turns"][0]["tool_call_ids"] == ["call_1"]
    assert row["http_attempt_count"] == 2
    assert row["sdk_retry_count"] == 0
    rendered = json.dumps(artifact, ensure_ascii=False)
    assert "opaque-reasoning-do-not-persist" not in rendered


def test_dialect_records_reasoning_and_unknown_items_without_losing_type_evidence() -> None:
    dialect = OpenAIResponsesDialect()
    parsed = dialect.parse_response(
        RawResponse.from_json(
            _response(
                [
                    {
                        "type": "reasoning",
                        "id": "rs_private",
                        "summary": [],
                        "encrypted_content": "private",
                    },
                    {"type": "future_output", "private": "must-not-be-copied"},
                ],
                "resp_unknown",
            )
        )
    )

    assert parsed.opaque_continuation is not None
    assert parsed.opaque_continuation["type"] == "openai-reasoning"
    assert parsed.opaque_continuation["count"] == 1
    assert parsed.unknown_block_types == ("future_output",)
    assert "private" not in json.dumps(parsed.opaque_continuation)


def test_transport_rejects_sdk_retries_and_makes_only_one_failed_http_attempt() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, json={"error": {"message": "fake failure"}})

    with pytest.raises(ValueError, match="max_retries=0"):
        OpenAIResponsesTransport(
            base_url="https://probe.invalid/v1",
            api_key="sk-fake-not-a-live-key",
            max_retries=1,
            http_transport=httpx.MockTransport(handler),
        )

    transport = OpenAIResponsesTransport(
        base_url="https://probe.invalid/v1",
        api_key="sk-fake-not-a-live-key",
        max_retries=0,
        http_transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception, match="fake failure"):
            transport.send({"model": "probe-model", "input": "fail", "stream": False})
    finally:
        transport.close()
    assert attempts == 1
