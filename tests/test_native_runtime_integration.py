from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pico import Pico, SessionStore, WorkspaceContext
from pico import cli
from pico.config import ProviderCapabilities, ProviderConfig
from pico.testing import (
    ScriptedNativeModelClient,
    native_continuation,
    native_final_response,
    native_tool_call_response,
)


PROFILE_ID = "scripted-native:test-profile"


def _profile(tool_schema: str) -> dict:
    return {
        "profile_id": PROFILE_ID,
        "profile": "scripted",
        "model": "scripted-model",
        "wire_dialect": "scripted-native",
        "base_url_fingerprint": "sha256:test",
        "capabilities": {"native_tools": True},
        "adapter_mode": "scripted",
        "sdk_package": "none",
        "sdk_version": "0",
        "sdk_max_retries": 0,
        "provider_attempts": 1,
        "tool_schema": tool_schema,
    }


def _agent(tmp_path, responses, **kwargs) -> Pico:
    (tmp_path / "README.md").write_text("native runtime\n", encoding="utf-8")
    agent = Pico(
        model_client=ScriptedNativeModelClient(responses),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".pico" / "sessions"),
        approval_policy=kwargs.pop("approval_policy", "auto"),
        auto_dream=False,
        **kwargs,
    )
    agent.session["provider_profile"] = _profile(agent.tool_signature())
    agent.session_path = agent.session_store.save(agent.session)
    return agent


def test_active_runtime_uses_native_tools_results_and_session_exchange(tmp_path) -> None:
    continuation = native_continuation({"response_id": "one"})
    agent = _agent(
        tmp_path,
        [
            native_tool_call_response(
                "call-read",
                "read_file",
                {"path": "README.md", "start": 1, "end": 1},
                continuation=continuation,
            ),
            native_final_response("Read complete.", continuation=continuation),
        ],
    )
    agent.parse = lambda _value: pytest.fail("legacy text parser must be unreachable")

    assert agent.ask("Read the repository file.") == "Read complete."

    requests = agent.model_client.requests
    assert requests[0].tools
    assert "<tool>" not in requests[0].prompt
    assert [item.call_id for item in requests[1].tool_results] == ["call-read"]
    assert requests[1].tool_results[0].is_error is False
    assert requests[1].continuation == continuation
    assert [event["event"] for event in agent.session["model_exchange"]["events"]] == [
        "assistant_tool_batch",
        "tool_result",
        "model_final",
    ]
    assert agent.session["native_runtime"]["active_batch"] is None
    assert agent.last_completion_metadata["sdk_max_retries"] == 0


def test_native_runtime_keeps_rejections_in_the_safety_chain(tmp_path) -> None:
    continuation = native_continuation({"response_id": "rejected"})
    agent = _agent(
        tmp_path,
        [
            native_tool_call_response(
                "call-denied",
                "run_shell",
                {"command": "echo unsafe", "timeout": 20},
                continuation=continuation,
            ),
            native_final_response("Denied safely.", continuation=continuation),
        ],
        approval_policy="never",
    )

    assert agent.ask("Run a command.") == "Denied safely."
    result = agent.model_client.requests[1].tool_results[0]
    assert result.call_id == "call-denied"
    assert result.is_error is True
    assert result.output["error"]["code"] == "approval_denied"
    journal_result = agent.session["model_exchange"]["events"][1]
    assert journal_result["call_id"] == "call-denied"
    assert journal_result["status"] == "rejected"


def test_cli_factory_selects_native_adapter_and_exposes_retry_configuration() -> None:
    config = ProviderConfig(
        name="local",
        wire_dialect="openai-responses",
        api_key="secret",
        base_url="https://example.test/v1",
        model="coding-model",
        capabilities=ProviderCapabilities(native_tools=True),
    )
    args = SimpleNamespace(temperature=0.2, openai_timeout=42)
    marker = object()

    with patch("pico.cli.build_native_model_client", return_value=marker) as factory:
        assert cli._build_model_client(args, config) is marker

    factory.assert_called_once_with(
        wire_dialect="openai-responses",
        model="coding-model",
        base_url="https://example.test/v1",
        api_key="secret",
        profile_id=config.public_identity()["profile_id"],
        timeout=42,
        max_retries=0,
    )
    inspected = cli.inspect_provider_config(config)
    assert inspected["sdk_max_retries"] == 0
    assert inspected["provider_attempts"] == 1
    assert inspected["sdk_package"] == "openai"
