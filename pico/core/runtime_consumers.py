"""Derived runtime state consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .artifacts import build_artifact_graph, build_verifier_suggestions
from .workspace import clip

if TYPE_CHECKING:
    from ..core.runtime import Pico
    from ..core.task_state import TaskState


class ArtifactGraphConsumer:
    def handle(self, runtime: Pico, task_state: TaskState, event: dict[str, Any]) -> None:
        if event.get("event") not in {"tool_executed", "run_finished", "checkpoint_created"}:
            return
        if not task_state.changed_paths and not event.get("artifact_paths"):
            return
        graph = build_artifact_graph(runtime.root, task_state.changed_paths)
        task_state.artifact_graph = graph


class VerifierSuggestionConsumer:
    def handle(self, runtime: Pico, task_state: TaskState, event: dict[str, Any]) -> None:
        if event.get("event") not in {"tool_executed", "run_finished", "checkpoint_created"}:
            return
        graph = task_state.artifact_graph or build_artifact_graph(runtime.root, task_state.changed_paths)
        task_state.verifier_suggestions = build_verifier_suggestions(runtime.root, graph)


class ReminderConsumer:
    def handle(self, runtime: Pico, task_state: TaskState, event: dict[str, Any]) -> None:
        if event.get("event") != "tool_executed":
            return
        status = str(event.get("status", ""))
        if status in {"", "ok"}:
            return
        reminder = {
            "event": "tool_executed",
            "tool": str(event.get("name", "")),
            "status": status,
            "error_type": str(event.get("error_type", "")),
            "message": clip(str(event.get("result", "")), 240),
            "created_at": event.get("created_at", ""),
        }
        task_state.runtime_reminders.append(reminder)


def default_runtime_consumers() -> list[Any]:
    return [ArtifactGraphConsumer(), VerifierSuggestionConsumer(), ReminderConsumer()]
