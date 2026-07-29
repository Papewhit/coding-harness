"""Concise provider-native fixtures shared by acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pico.providers.contracts import ModelRequest, ModelResponse
from pico.testing import (
    ScriptedNativeModelClient,
    native_final_response,
    native_multi_tool_call_response,
    native_tool_call,
    native_tool_call_response,
)


SCRIPTED_NATIVE_PROFILE_ID = "scripted-native:test-profile"


def scripted_provider_identity() -> dict[str, Any]:
    """Build the JSON-safe transport identity for deterministic native tests."""

    return {
        "profile_id": SCRIPTED_NATIVE_PROFILE_ID,
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
    }


def scripted_provider_profile(agent: Any) -> dict[str, Any]:
    """Bind the scripted transport identity to one Runtime tool schema."""

    return {
        **scripted_provider_identity(),
        "tool_schema": agent.tool_signature(),
    }


def lock_scripted_provider_profile(agent: Any) -> Any:
    """Persist the explicit native profile required by scripted Runtime tests."""

    agent.session["provider_profile"] = scripted_provider_profile(agent)
    agent.session_path = agent.session_store.save(agent.session)
    return agent


@dataclass(frozen=True)
class ToolStep:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class FinalStep:
    text: str


@dataclass(frozen=True)
class MultiToolStep:
    tools: tuple[ToolStep, ...]


def tool(name: str, arguments: dict[str, Any] | None = None, **kwargs: Any) -> ToolStep:
    merged = dict(arguments or {})
    merged.update(kwargs)
    return ToolStep(name=name, arguments=merged)


def final(text: str) -> FinalStep:
    return FinalStep(text=text)


def tools(*steps: ToolStep) -> MultiToolStep:
    return MultiToolStep(tools=steps)


class PromptLoggingNativeClient(ScriptedNativeModelClient):
    """Native scripted client retaining rendered request evidence for assertions."""

    def __init__(self, responses: list[ModelResponse | BaseException]) -> None:
        super().__init__(responses)
        self.prompts: list[str] = []
        self.last_completion_metadata: dict[str, Any] = {}
        self._pico_test_native = True
        self._pico_profile_identity = scripted_provider_identity()

    def request(self, request: ModelRequest) -> ModelResponse:
        rendered_results = [str(result.output) for result in request.tool_results]
        self.prompts.append("\n".join([request.prompt, *rendered_results]))
        response = super().request(request)
        if not self.last_completion_metadata:
            return response
        return ModelResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            stop_reason=response.stop_reason,
            continuation=response.continuation,
            metadata={**response.metadata, **self.last_completion_metadata},
        )


def scripted_client(
    steps: list[ToolStep | MultiToolStep | FinalStep | ModelResponse | BaseException]
    | None = None,
) -> PromptLoggingNativeClient:
    responses: list[ModelResponse | BaseException] = []
    for index, step in enumerate(steps or (), start=1):
        if isinstance(step, ToolStep):
            responses.append(
                native_tool_call_response(
                    f"scripted-call-{index}", step.name, step.arguments
                )
            )
        elif isinstance(step, MultiToolStep):
            responses.append(
                native_multi_tool_call_response(
                    *(
                        native_tool_call(
                            f"scripted-call-{index}-{tool_index}",
                            tool_step.name,
                            tool_step.arguments,
                        )
                        for tool_index, tool_step in enumerate(step.tools, start=1)
                    )
                )
            )
        elif isinstance(step, FinalStep):
            responses.append(native_final_response(step.text))
        elif isinstance(step, (ModelResponse, BaseException)):
            responses.append(step)
        else:
            raise TypeError(f"unsupported native fixture step: {type(step).__name__}")
    return PromptLoggingNativeClient(responses)
