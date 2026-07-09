"""Session-scoped worker lifecycle for subagents."""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .worker_execution import run_worker
from .worker_runtime import build_child_runtime
from .workspace import now
if TYPE_CHECKING:
    from .runtime import Pico


@dataclass
class WorkerTask:
    id: str
    description: str
    subagent_type: str
    write_scope: tuple[str, ...]
    runtime: object
    thread: threading.Thread | None = None
    stop_requested: bool = False
    state: dict = field(default_factory=dict)


class WorkerManager:
    def __init__(self, runtime: Pico) -> None:
        self.runtime = runtime
        self.runtime.session.setdefault("workers", {"next_id": 1, "items": []})
        self._tasks: dict[str, WorkerTask] = {}
        self._lock = threading.Lock()
        self._notifications: queue.Queue[tuple[str, str]] = queue.Queue()

    @property
    def state(self) -> dict[str, Any]:
        return self.runtime.session.setdefault("workers", {"next_id": 1, "items": []})

    def spawn(self, description: str, prompt: str, subagent_type: str = "worker", write_scope: list[str] | None = None) -> dict[str, Any]:
        subagent_type = _clean_type(subagent_type)
        if self.runtime.runtime_mode == "plan" and subagent_type != "Explore":
            raise ValueError("plan mode only allows Explore agents")
        task = self._new_task(description, subagent_type, write_scope)
        self._tasks[task.id] = task
        if self._can_run_background():
            self._start_background(task, prompt, action="spawn")
            return self._public_payload(task, status="started")
        run_worker(self, task, prompt, action="spawn")
        return self._public_payload(task)

    def continue_task(self, task_id: str, message: str) -> dict[str, Any]:
        task = self._get_active_task(task_id)
        item = self._get_item(task_id)
        if item.get("status") in {"running", "stopping"}:
            raise ValueError(f"worker is running: {task_id}")
        if self.runtime.runtime_mode == "plan" and task.subagent_type != "Explore":
            raise ValueError("plan mode only allows Explore agents")
        if self._can_run_background():
            self._start_background(task, message, action="continue")
            return self._public_payload(task, status="started")
        run_worker(self, task, message, action="continue")
        return self._public_payload(task)

    def stop_task(self, task_id: str) -> dict[str, Any]:
        item = self._get_item(task_id)
        if item["status"] == "running":
            task = self._tasks.get(str(task_id))
            if task is not None:
                self._request_stop(task)
            item["status"] = "stopping"
            item["updated_at"] = now()
            self.runtime.session_event_bus.emit(
                "worker_stop_requested", {"worker_id": item["id"], "status": "stopping"}
            )
            self._save()
        return {
            "task_id": item["id"],
            "status": item["status"],
            "description": item["description"],
        }

    def shutdown(self, timeout: float = 2.0) -> dict[str, Any]:
        tasks = list(self._tasks.values())
        for task in tasks:
            item = self._get_item(task.id)
            if item.get("status") in {"running", "stopping"}:
                self._request_stop(task)
                with self._lock:
                    item["status"] = "stopping"
                    item["updated_at"] = now()
                self.runtime.session_event_bus.emit(
                    "worker_stop_requested",
                    {"worker_id": item["id"], "status": "stopping"},
                )
        if tasks:
            self._save()
        deadline = time.monotonic() + float(timeout)
        for task in tasks:
            thread = task.thread
            if thread is None or not thread.is_alive():
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining:
                thread.join(remaining)
        return {"stopped": sum(1 for task in tasks if task.stop_requested)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_id": int(self.state.get("next_id", 1)),
            "items": [dict(item) for item in self.state.get("items", [])],
        }

    def _new_task(self, description: str, subagent_type: str, write_scope: Any) -> WorkerTask:
        with self._lock:
            worker_id = f"agent_{int(self.state.get('next_id', 1))}"
            self.state["next_id"] = int(self.state.get("next_id", 1)) + 1
        scope = tuple(_clean_scope(write_scope))
        child = build_child_runtime(self.runtime, subagent_type, scope)
        item = {
            "id": worker_id,
            "description": str(description or "").strip() or "Worker task",
            "subagent_type": subagent_type,
            "write_scope": list(scope),
            "status": "idle",
            "result": "",
            "tool_steps": 0,
            "attempts": 0,
            "duration_ms": 0,
            "notification_drained": False,
            "created_at": now(),
            "updated_at": now(),
        }
        with self._lock:
            self.state.setdefault("items", []).append(item)
            self._save()
        return WorkerTask(worker_id, item["description"], subagent_type, scope, child)

    def _can_run_background(self) -> bool:
        return getattr(self.runtime, "model_client_factory", None) is not None

    def _start_background(self, task: WorkerTask, prompt: str, action: str) -> None:
        thread = threading.Thread(
            target=run_worker,
            args=(self, task, prompt, action),
            daemon=True,
            name=f"pico-worker-{task.id}",
        )
        task.thread = thread
        thread.start()

    def _request_stop(self, task: WorkerTask) -> None:
        task.stop_requested = True
        abort = getattr(task.runtime, "abort_current_turn", None)
        if callable(abort):
            abort()

    def drain_notifications(self) -> list[Any]:
        drained = []
        while True:
            try:
                task_id, notification = self._notifications.get_nowait()
            except queue.Empty:
                break
            item = self._get_item(task_id)
            with self._lock:
                if item.get("notification_drained"):
                    continue
                item["notification_drained"] = True
                item["updated_at"] = now()
            drained.append(notification)
        if drained:
            self._save()
        return drained

    def _get_active_task(self, task_id: str) -> WorkerTask:
        task = self._tasks.get(str(task_id))
        if task is None:
            raise ValueError(f"unknown or inactive worker: {task_id}")
        return task

    def _get_item(self, task_id: str) -> dict[str, Any]:
        for item in self.state.setdefault("items", []):
            if item.get("id") == str(task_id):
                return item
        raise ValueError(f"unknown worker: {task_id}")

    def _public_payload(self, task: WorkerTask, status: str | None = None) -> dict[str, Any]:
        item = self._get_item(task.id)
        return {
            "task_id": task.id,
            "status": status or item["status"],
            "description": task.description,
        }

    def _save(self) -> None:
        self.runtime.session_path = self.runtime.session_store.save(
            self.runtime.session
        )


def _clean_type(value: Any) -> str:
    subagent_type = str(value or "worker").strip()
    if subagent_type not in {"worker", "Explore"}:
        raise ValueError("subagent_type must be worker or Explore")
    return subagent_type


def _clean_scope(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("write_scope must be a list of workspace paths")
    return [str(item).strip() for item in value if str(item).strip()]


def dumps_payload(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
