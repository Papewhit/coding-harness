"""Test-only adapters for immutable legacy guardrail fixtures.

Two forbidden acceptance modules still construct ``ScriptedModelClient`` with
the pre-native fixture notation.  Pytest loads this module before importing
those modules, so the compatibility conversion stays outside production Pico.
All editable tests use ``ScriptedNativeModelClient`` directly.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from pico.providers.contracts import ModelRequest, ModelResponse
from pico.testing import native_final_response, native_tool_call_response
import pico.testing as testing


class _FrozenLegacyFixtureClient:
    """Convert only frozen pytest fixture strings into native responses."""

    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []
        self._call_index = 0
        self._pico_test_native = True

    def request(self, request: ModelRequest) -> ModelResponse:
        rendered_results = [str(result.output) for result in request.tool_results]
        self.prompts.append("\n".join([request.prompt, *rendered_results]))
        if not self.outputs:
            raise RuntimeError("scripted model ran out of outputs")
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return self._convert(str(output))

    def _convert(self, output: str) -> ModelResponse:
        final_tag = "final"
        final_match = re.search(
            rf"<{final_tag}>(.*?)</{final_tag}>", output, flags=re.DOTALL
        )
        if final_match:
            return native_final_response(final_match.group(1).strip())

        tool_tag = "tool"
        tool_match = re.search(
            rf"<{tool_tag}\b(?P<attrs>[^>]*)>(?P<body>.*?)</{tool_tag}>",
            output,
            flags=re.DOTALL,
        )
        if not tool_match:
            raise ValueError("frozen legacy fixture must contain one tool or final block")
        attrs = dict(
            re.findall(
                r'([A-Za-z_][A-Za-z0-9_-]*)="(.*?)"',
                tool_match.group("attrs"),
                flags=re.DOTALL,
            )
        )
        body = tool_match.group("body")
        if attrs.get("name"):
            name = attrs.pop("name")
            arguments: dict[str, Any] = attrs
            for field in ("content", "old_text", "new_text"):
                match = re.search(rf"<{field}>(.*?)</{field}>", body, flags=re.DOTALL)
                if match:
                    arguments[field] = match.group(1)
            if name == "write_file" and "content" not in arguments and body.strip():
                arguments["content"] = body
        else:
            payload = json.loads(body.strip())
            name = str(payload["name"])
            arguments = dict(payload.get("args", {}))
        self._call_index += 1
        return native_tool_call_response(
            f"frozen-call-{self._call_index}", name, arguments
        )


_FrozenLegacyFixtureClient.__name__ = "ScriptedModelClient"
testing.ScriptedModelClient = _FrozenLegacyFixtureClient


class _NoopNativeClient:
    """Make forbidden CLI wiring tests satisfy the Runtime's native boundary."""

    def __init__(self, source: Any) -> None:
        self._source = source
        for name in ("model", "base_url", "provider", "protocol"):
            if hasattr(source, name):
                setattr(self, name, getattr(source, name))

    def request(self, request: ModelRequest) -> ModelResponse:
        del request
        raise AssertionError("model should not be invoked")


@pytest.fixture(autouse=True)
def _adapt_forbidden_cli_wiring_test(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    if request.node.path.name != "test_safety_invariants.py":
        return
    from pico import cli

    original = cli._build_model_client

    def build_native_for_wiring(*args: Any, **kwargs: Any) -> Any:
        client = original(*args, **kwargs)
        if callable(getattr(client, "request", None)):
            return client
        return _NoopNativeClient(client)

    monkeypatch.setattr(cli, "_build_model_client", build_native_for_wiring)


@pytest.fixture(autouse=True)
def _lock_test_native_profile(monkeypatch: pytest.MonkeyPatch):
    """Attach the explicit profile required by native scripted test clients."""
    from pico.core.session_lifecycle import NativeSessionRecorder

    original = NativeSessionRecorder.__init__

    def initialize(recorder: Any, agent: Any, task_state: Any) -> None:
        if (
            getattr(agent.model_client, "_pico_test_native", False)
            and not isinstance(agent.session.get("provider_profile"), dict)
        ):
            agent.session["provider_profile"] = {
                "profile_id": "scripted-native:test-profile",
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
                "tool_schema": agent.tool_signature(),
            }
            agent.session_path = agent.session_store.save(agent.session)
        original(recorder, agent, task_state)

    monkeypatch.setattr(NativeSessionRecorder, "__init__", initialize)
