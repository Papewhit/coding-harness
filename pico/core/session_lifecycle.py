"""Runtime session switching helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping

from ..features import memory as memorylib
from .plan_mode import PlanModeController
from ..providers.contracts import (
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
    ToolCallResult,
)
from .model_exchange import ModelExchangeEvent
from .session_events import SessionEventBus, SessionExchangeJournal
from .task_state import TaskState
from .todo_ledger import TodoLedger
from .worker_manager import WorkerManager
from .workspace import clip, now

if TYPE_CHECKING:
    from .runtime import Pico


class NativeSessionRecorder:
    """Persist native batch lifecycle and normalized session exchange events."""

    def __init__(self, agent: Pico, task_state: TaskState) -> None:
        profile = agent.session.get("provider_profile")
        if not isinstance(profile, Mapping):
            raise ValueError("native Runtime requires a locked provider_profile")
        self.agent = agent
        self.task_state = task_state
        self.profile = dict(profile)
        self.journal = SessionExchangeJournal(
            agent.session,
            self._save_session,
            lambda event: agent.session_event_bus.emit(
                "model_exchange", {"exchange": event}
            ),
        )
        self.batch_ids: dict[tuple[str, ...], str] = {}
        self.started_calls: set[str] = set()
        self.finished_calls: set[str] = set()
        self.events: list[dict[str, Any]] = []

    def latest_continuation(self) -> ProviderContinuation | None:
        return self.journal.latest_continuation(self.profile)

    def persist(self, snapshot: dict[str, Any]) -> None:
        response = _model_response(snapshot["response"])
        calls = {call.call_id: call for call in response.tool_calls}
        batch_key = tuple(calls)
        exchange_id = self.batch_ids.get(batch_key)
        if exchange_id is None:
            exchange_id = self._exchange_id(len(self.batch_ids) + 1)
            self.batch_ids[batch_key] = exchange_id
            self.journal.append(
                ModelExchangeEvent.assistant_tool_batch(
                    exchange_id=exchange_id,
                    profile=self.profile,
                    response=response,
                    created_at=now(),
                )
            )
        for state in snapshot["calls"]:
            call_id = str(state["call"]["call_id"])
            if state["status"] == "executing" and call_id not in self.started_calls:
                self._started(calls[call_id])
            if state.get("result") is not None and call_id not in self.finished_calls:
                self._finished(exchange_id, calls[call_id], state)
        native = self.agent.session.setdefault("native_runtime", {})
        native["active_batch"] = None if snapshot.get("complete") else snapshot
        native["last_batch"] = snapshot
        self.agent.session_path = self.agent.session_store.save(self.agent.session)

    def finish(self, response: ModelResponse) -> None:
        self.journal.append(
            ModelExchangeEvent.model_final(
                exchange_id=self._exchange_id(len(self.batch_ids) + 1),
                profile=self.profile,
                response=response,
                created_at=now(),
            )
        )
        self.agent.session.setdefault("native_runtime", {})["active_batch"] = None
        self.agent.session_path = self.agent.session_store.save(self.agent.session)

    def _exchange_id(self, number: int) -> str:
        return f"{self.task_state.run_id}:exchange-{number}"

    def _save_session(self, candidate: dict[str, Any]) -> None:
        self.agent.session_path = self.agent.session_store.save(candidate)

    def _started(self, call: ToolCall) -> None:
        self.started_calls.add(call.call_id)
        self.task_state.record_tool(call.name)
        payload = {
            "run_id": self.task_state.run_id,
            "tool_name": call.name,
            "call_id": call.call_id,
            "args": dict(call.arguments),
        }
        self.agent.session_event_bus.emit("tool_started", payload)
        self.events.append(
            {"type": "tool_call", "name": call.name, **payload}
        )
        self.agent.run_store.write_task_state(self.task_state)

    def _finished(
        self, exchange_id: str, call: ToolCall, state: Mapping[str, Any]
    ) -> None:
        result = _tool_result(state["result"])
        status = str(state["status"])
        self.journal.append(
            ModelExchangeEvent.tool_result(
                exchange_id=exchange_id,
                profile=self.profile,
                call=call,
                result=result,
                status={"completed": "completed", "rejected": "rejected", "uncertain": "error"}[status],
                created_at=now(),
            )
        )
        self.finished_calls.add(call.call_id)
        metadata = dict(state.get("result_metadata", {}) or {})
        rendered = _render_native_output(result.output)
        tool_status = str(metadata.get("tool_status", status))
        tool_error_code = str(metadata.get("tool_error_code", ""))
        self.agent.record(
            {
                "role": "tool",
                "name": call.name,
                "args": dict(call.arguments),
                "content": rendered,
                "tool_status": tool_status,
                "tool_error_code": tool_error_code,
                "provider_call_id": call.call_id,
                "created_at": now(),
            }
        )
        payload = {
            "run_id": self.task_state.run_id,
            "tool_name": call.name,
            "call_id": call.call_id,
            "status": tool_status,
            "tool_error_code": tool_error_code,
            "workspace_changed": bool(metadata.get("workspace_changed", False)),
            "affected_paths": list(metadata.get("affected_paths", [])),
        }
        self.agent.session_event_bus.emit("tool_finished", payload)
        self.agent.emit_trace(
            self.task_state,
            "tool_executed",
            {
                "name": call.name,
                "call_id": call.call_id,
                "args": dict(call.arguments),
                "result": clip(rendered, 500),
                **metadata,
            },
        )
        self.events.append(
            {
                "type": "tool_result",
                "run_id": self.task_state.run_id,
                "name": call.name,
                "call_id": call.call_id,
                "content": rendered,
                "metadata": metadata,
            }
        )


def _model_response(value: Mapping[str, Any]) -> ModelResponse:
    continuation = value.get("continuation")
    return ModelResponse(
        text=str(value.get("text", "")),
        tool_calls=tuple(
            ToolCall(str(call["call_id"]), str(call["name"]), call.get("arguments", {}))
            for call in value.get("tool_calls", [])
        ),
        stop_reason=StopReason(str(value["stop_reason"])),
        continuation=(
            ProviderContinuation(str(continuation["profile_id"]), continuation.get("payload"))
            if isinstance(continuation, Mapping)
            else None
        ),
        metadata=value.get("metadata", {}),
    )


def _tool_result(value: Mapping[str, Any]) -> ToolCallResult:
    return ToolCallResult(
        str(value["call_id"]), value.get("output"), bool(value.get("is_error", False))
    )


def _render_native_output(value: Any) -> str:
    return (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, ensure_ascii=False)
    )


def resume_runtime_session(runtime: Pico, session_id: str) -> str:
    _shutdown_workers(runtime)
    runtime.session = runtime.session_store.load(session_id)
    _rebind(runtime, emit_started=False)
    return runtime.session["id"]


def clear_runtime_session(runtime: Pico) -> str:
    _shutdown_workers(runtime)
    runtime.session = {
        "id": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
        "created_at": now(),
        "workspace_root": runtime.workspace.repo_root,
        "history": [],
        "memory": memorylib.default_memory_state(),
    }
    _rebind(runtime, emit_started=True)
    return runtime.session["id"]


def _rebind(runtime: Pico, emit_started: bool) -> None:
    runtime._ensure_session_shape()
    runtime.session_event_bus = SessionEventBus(
        runtime.session["id"],
        runtime.session_store.event_path(runtime.session["id"]),
        redact=runtime.redact_artifact,
    )
    if emit_started:
        runtime.session_event_bus.emit(
            "session_started", {"workspace_root": runtime.workspace.repo_root}
        )
    runtime.plan_mode = PlanModeController(runtime)
    runtime.memory = memorylib.LayeredMemory(
        runtime.session.setdefault("memory", memorylib.default_memory_state()),
        workspace_root=runtime.root,
    )
    runtime.session["memory"] = runtime.memory.to_dict()
    runtime.todo_ledger = TodoLedger(runtime)
    runtime.worker_manager = WorkerManager(runtime)
    runtime._active_tool_profile_name = (
        "plan"
        if runtime.runtime_mode == "plan"
        else "readonly"
        if runtime.read_only
        else "default"
    )
    runtime.resume_state = runtime.evaluate_resume_state()
    runtime.session_path = runtime.session_store.save(runtime.session)
    runtime.current_turn_id = ""
    runtime.current_run_id = ""
    runtime.current_run_dir = None
    runtime.current_task_state = None
    runtime.refresh_prefix(force=True)


def _shutdown_workers(runtime: Pico) -> None:
    manager = getattr(runtime, "worker_manager", None)
    shutdown = getattr(manager, "shutdown", None)
    if callable(shutdown):
        shutdown()
