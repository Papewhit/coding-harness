from __future__ import annotations

import json
from importlib import metadata

import httpx
import pytest

from pico.providers import sdk_imports
from pico.providers.provider_transport import (
    AnthropicMessagesTransport,
    OpenAIResponsesTransport,
)
from pico.providers.sdk_imports import ProviderSDKConfigurationError


def _openai_response(output: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "resp_test",
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


def _anthropic_message(content: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "probe-model",
        "content": content,
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def test_frozen_sdk_versions_are_installed_from_providers_extra() -> None:
    assert metadata.version("openai") == sdk_imports.OPENAI_SDK_VERSION == "2.46.0"
    assert metadata.version("anthropic") == sdk_imports.ANTHROPIC_SDK_VERSION == "0.117.0"


def test_missing_provider_extra_has_actionable_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_import(name: str):
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(sdk_imports, "import_module", missing_import)
    with pytest.raises(ProviderSDKConfigurationError, match="uv sync --extra providers"):
        sdk_imports.load_openai_sdk()


def test_wrong_sdk_version_has_actionable_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sdk_imports.metadata, "version", lambda _package: "0.0.0")
    with pytest.raises(ProviderSDKConfigurationError, match="requires openai==2.46.0"):
        sdk_imports.load_openai_sdk()


def test_openai_typed_transport_records_request_id_timeout_and_no_tool_execution() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["tools"][0]["name"] == "echo"
        return httpx.Response(
            200,
            headers={"x-request-id": "req_openai"},
            json=_openai_response(
                [
                    {
                        "type": "function_call",
                        "id": "fc_1",
                        "call_id": "call_1",
                        "name": "echo",
                        "arguments": "{}",
                        "status": "completed",
                    }
                ]
            ),
        )

    with OpenAIResponsesTransport(
        base_url="https://probe.invalid/v1",
        api_key="sk-test",
        timeout=12.5,
        max_retries=0,
        http_transport=httpx.MockTransport(handler),
    ) as transport:
        result = transport.create(
            {
                "model": "probe-model",
                "input": "Call echo once",
                "stream": False,
                "parallel_tool_calls": False,
                "tools": [{"type": "function", "name": "echo", "parameters": {"type": "object"}}],
            }
        )

    assert len(requests) == 1
    assert set(requests[0].extensions["timeout"].values()) == {12.5}
    assert result.payload["output"][0]["call_id"] == "call_1"
    assert result.request_id == "req_openai"
    assert result.sdk_retry_count == 0
    assert result.http_attempts[0].status_code == 200
    assert result.http_attempts[0].request_id == "req_openai"


def test_anthropic_raw_transport_preserves_unknown_block_and_request_id() -> None:
    requests: list[httpx.Request] = []
    future_block = {"type": "future_private", "opaque": {"nested": [1, "two"]}}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"request-id": "req_anthropic"},
            json=_anthropic_message([future_block]),
        )

    with AnthropicMessagesTransport(
        base_url="https://probe.invalid",
        api_key="sk-test",
        max_retries=0,
        http_transport=httpx.MockTransport(handler),
    ) as transport:
        result = transport.create(
            {
                "model": "probe-model",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "Call echo"}],
                "stream": False,
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo",
                        "input_schema": {"type": "object"},
                    }
                ],
            }
        )

    assert len(requests) == 1
    assert result.payload["content"] == [future_block]
    assert json.loads(result.raw_bytes)["content"] == [future_block]
    assert result.request_id == "req_anthropic"
    assert result.sdk_retry_count == 0
    assert len(result.http_attempts) == 1


@pytest.mark.parametrize("transport_class", [OpenAIResponsesTransport, AnthropicMessagesTransport])
def test_transport_rejects_sdk_retries(transport_class: type) -> None:
    with pytest.raises(ValueError, match="max_retries=0"):
        transport_class(
            base_url="https://probe.invalid/v1",
            api_key="sk-test",
            max_retries=1,
        )


def test_failed_request_remains_observable_as_one_http_attempt() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"message": "fake failure"}})

    with OpenAIResponsesTransport(
        base_url="https://probe.invalid/v1",
        api_key="sk-test",
        max_retries=0,
        http_transport=httpx.MockTransport(handler),
    ) as transport:
        with pytest.raises(Exception, match="fake failure"):
            transport.create({"model": "probe-model", "input": "fail", "stream": False})
        attempts = transport.last_http_attempts

    assert calls == 1
    assert len(attempts) == 1
    assert attempts[0].status_code == 500
    assert attempts[0].error_type is not None
