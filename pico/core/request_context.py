"""Structured, provider-neutral context prepared for one model request."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..features import skills as skillslib
from ..providers.contracts import ProviderContinuation, ToolCallResult, ToolDefinition


@dataclass(frozen=True)
class RequestMessage:
    """One public message; opaque provider state never belongs here."""

    role: str
    content: str
    kind: str = "message"
    provider_call_id: str | None = None
    compactable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in {"user", "assistant", "tool", "system"}:
            raise ValueError(f"unsupported request message role: {self.role!r}")
        if not isinstance(self.content, str):
            raise TypeError("request message content must be a string")
        if self.provider_call_id is not None and not str(self.provider_call_id).strip():
            raise ValueError("provider_call_id must be non-empty when supplied")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "kind": self.kind,
            "compactable": self.compactable,
        }
        if self.provider_call_id is not None:
            payload["provider_call_id"] = self.provider_call_id
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class ModelRequestContext:
    """Four explicit surfaces consumed by the native Runtime integration."""

    system_text: str
    messages: Sequence[RequestMessage]
    tools: Sequence[ToolDefinition]
    continuation: ProviderContinuation | None = None
    tool_results: Sequence[ToolCallResult] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.system_text, str):
            raise TypeError("system_text must be a string")
        messages = tuple(self.messages)
        tools = tuple(self.tools)
        results = tuple(self.tool_results)
        if not all(isinstance(item, RequestMessage) for item in messages):
            raise TypeError("messages must contain RequestMessage values")
        if not all(isinstance(item, ToolDefinition) for item in tools):
            raise TypeError("tools must contain provider ToolDefinition values")
        if not all(isinstance(item, ToolCallResult) for item in results):
            raise TypeError("tool_results must contain ToolCallResult values")
        if self.continuation is not None and not isinstance(
            self.continuation, ProviderContinuation
        ):
            raise TypeError("continuation must be a ProviderContinuation")
        request_messages = [item for item in messages if item.kind == "current_request"]
        if len(request_messages) != 1 or request_messages[0].compactable:
            raise ValueError("context requires exactly one non-compactable current request")
        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "tools", tools)
        object.__setattr__(self, "tool_results", results)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def current_request(self) -> RequestMessage:
        return next(item for item in self.messages if item.kind == "current_request")

    @property
    def native_turn_status(self) -> str:
        call_ids = {
            item.provider_call_id
            for item in self.messages
            if item.kind == "native_tool_call" and item.provider_call_id
        }
        result_ids = {item.call_id for item in self.tool_results}
        return "awaiting_result" if call_ids - result_ids else "terminal"

    def legacy_prompt(self) -> str:
        """Render the compatibility view used until native Runtime wiring lands."""

        sections = [self.system_text]
        sections.extend(
            item.content for item in self.messages if item.kind != "current_request"
        )
        sections.append(f"Current user request:\n{self.current_request.content}")
        return "\n\n".join(item for item in sections if item).strip()

    def surface_hashes(self) -> dict[str, str]:
        payloads = {
            "system_text": self.system_text,
            "messages": _canonical_json([item.to_dict() for item in self.messages]),
            "tools": _canonical_json([item.to_dict() for item in self.tools]),
        }
        return {
            name: hashlib.sha256(value.encode("utf-8")).hexdigest()
            for name, value in payloads.items()
        }


def provider_tool_definitions(tools: Mapping[str, Any]) -> tuple[ToolDefinition, ...]:
    """Export the active registry without copying schemas into system text."""

    return tuple(
        ToolDefinition(
            name=name,
            description=str(tool.description),
            input_schema=tool.input_schema,
        )
        for name, tool in sorted(tools.items())
    )


def build_model_request_context(
    agent: Any,
    prompt: str,
    metadata: Mapping[str, Any],
    *,
    public_messages: tuple[RequestMessage, ...] = (),
    tool_results: tuple[ToolCallResult, ...] = (),
    continuation: ProviderContinuation | None = None,
) -> ModelRequestContext:
    """Split the budgeted compatibility prompt into canonical request surfaces."""

    request = str(metadata.get("current_request", {}).get("text", ""))
    request_section = f"Current user request:\n{request}"
    if not prompt.endswith(request_section):
        raise ValueError("budgeted prompt does not preserve the current request")
    prior = prompt[: -len(request_section)].removesuffix("\n\n")
    history_chars = int(
        metadata.get("sections", {}).get("history", {}).get("rendered_chars", 0)
    )
    if history_chars:
        system_text = prior[:-history_chars].removesuffix("\n\n")
        history_body = prior[-history_chars:]
        messages = (
            RequestMessage("system", history_body, kind="history"),
            *public_messages,
        )
    else:
        system_text, messages = prior, public_messages
    messages = (
        *messages,
        RequestMessage(
            "user",
            request,
            kind="current_request",
            compactable=False,
            metadata={"drop_action": "kept_verbatim"},
        ),
    )
    context_metadata = dict(metadata)
    context_metadata["asset_records"] = _asset_records(agent, system_text, messages)
    context = ModelRequestContext(
        system_text,
        messages,
        provider_tool_definitions(agent.available_tools()),
        continuation,
        tool_results,
        context_metadata,
    )
    context_metadata["surface_hashes"] = context.surface_hashes()
    context_metadata["native_turn_status"] = context.native_turn_status
    call_ids = [
        item.provider_call_id
        for item in context.messages
        if item.kind == "native_tool_call" and item.provider_call_id
    ]
    context_metadata["native_turn"] = {
        "status": context.native_turn_status,
        "call_ids": call_ids,
        "result_call_ids": [item.call_id for item in context.tool_results],
        "continuation_evidence": (
            {
                "type": type(context.continuation).__name__,
                "count": 1,
                "hash": context.continuation.stable_hash(),
            }
            if context.continuation is not None
            else None
        ),
    }
    surface_chars = {
        "system_text": len(context.system_text),
        "messages": len(_canonical_json([item.to_dict() for item in context.messages])),
        "tools": len(_canonical_json([item.to_dict() for item in context.tools])),
    }
    context_metadata["surface_usage"] = {
        name: {"chars": chars, "tokens": (chars + 3) // 4}
        for name, chars in surface_chars.items()
    }
    return ModelRequestContext(
        context.system_text,
        context.messages,
        context.tools,
        context.continuation,
        context.tool_results,
        context_metadata,
    )


def _asset_records(
    agent: Any, system_text: str, messages: tuple[RequestMessage, ...]
) -> list[dict[str, Any]]:
    history = list(getattr(agent, "session", {}).get("history", []))
    surfaces = {
        "skills": "system_text",
        "todo": "system_text",
        "plan": "system_text",
        "checkpoint": "system_text",
        "worker": "messages",
        "durable": "system_text",
        "compact": "messages",
        "pointer": "messages",
    }
    todo = getattr(agent, "todo_ledger", None)
    active = {
        "skills": bool(getattr(agent, "skills", {})),
        "todo": bool(todo and todo.state.get("items", [])),
        "plan": str(getattr(agent, "runtime_mode", "default")) == "plan",
        "checkpoint": "Task checkpoint:" in system_text,
        "worker": any(
            item.get("source") == "worker" or item.get("kind") == "worker_notification"
            for item in history
        ) or any(item.kind == "worker_notification" for item in messages),
        "durable": "# Auto Memory" in system_text,
        "compact": any(item.get("kind") == "compact_summary" for item in history)
        or any(item.kind == "compact_summary" for item in messages),
        "pointer": any(
            item.get("kind") == "artifact_pointer" or item.get("pointer_kind")
            for item in history
        ) or any(item.kind == "artifact_pointer" for item in messages),
    }
    sizes = {
        "system_text": len(system_text),
        "messages": sum(len(item.content) for item in messages),
    }
    return [
        {
            "asset_id": asset_id,
            "surface": surface,
            "activation_state": "active" if active[asset_id] else "inactive",
            "rendered_chars": sizes[surface],
            "drop_action": "kept" if active[asset_id] else "not_activated",
        }
        for asset_id, surface in surfaces.items()
    ]


def stable_system_text(agent: Any) -> str:
    """Build stable behavior/workspace instructions with no text tool protocol."""

    rules = [
        "You are pico, a small local coding agent working inside a local repository.",
        "",
        "Rules:",
        "- Use available native tools instead of guessing about the workspace.",
        "- Never invent tool results.",
        "- Keep answers concise and concrete.",
        "- If a requested file path is clear, edit it instead of repeatedly listing files.",
        "- Before writing tests for existing code, read the implementation first.",
        "- Match current behavior unless the user explicitly requests a behavior change.",
        "- New files should be complete and runnable, including obvious imports.",
        "- Do not repeat an unhelpful tool call with identical arguments.",
        "- Required tool arguments must not be empty.",
        "- Use bounded workers; read-only workers must not write.",
        "- Continue an existing worker when it already owns the needed context.",
        f"- {skillslib.SKILL_FILE_CREATION_GUIDE}",
    ]
    mode_text = str(agent.runtime_mode_text()).strip()
    workspace_text = str(agent.workspace.text()).strip()
    return "\n".join(
        [*rules, "", mode_text, "", workspace_text]
    ).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
