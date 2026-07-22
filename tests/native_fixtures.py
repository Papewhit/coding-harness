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
