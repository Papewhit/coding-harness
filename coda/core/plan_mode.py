"""Plan mode policy for sessions."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import Coda


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "plan"


class PlanModeManager:
    def __init__(self, runtime: Coda) -> None:
        self.runtime = runtime

    @property
    def state(self) -> dict[str, Any]:
        return self.runtime.session.setdefault("runtime_mode", {"mode": "default"})

    @property
    def mode(self) -> str:
        return str(self.state.get("mode", "default") or "default")

    @property
    def plan_path(self) -> str:
        return str(self.state.get("plan_path", "") or "")

    def enter(self, topic: str, path: str | None = None) -> str:
        plan_path = _plan_path(topic, path)
        self.runtime.session["runtime_mode"] = {
            "mode": "plan",
            "topic": str(topic or ""),
            "plan_path": plan_path,
        }
        self.runtime.set_tool_profile("plan")
        self.runtime.session_path = self.runtime.session_store.save(
            self.runtime.session
        )
        self.runtime.refresh_prefix(force=True)
        self.runtime.session_event_bus.emit(
            "runtime_mode_changed",
            {"mode": "plan", "plan_path": plan_path, "topic": str(topic or "")},
        )
        return plan_path

    def exit(self) -> None:
        previous = dict(self.state)
        self.runtime.session["runtime_mode"] = {"mode": "default"}
        self.runtime.set_tool_profile("default")
        self.runtime.session_path = self.runtime.session_store.save(
            self.runtime.session
        )
        self.runtime.refresh_prefix(force=True)
        self.runtime.session_event_bus.emit(
            "runtime_mode_changed",
            {
                "mode": "default",
                "previous_mode": previous.get("mode", "default"),
                "plan_path": previous.get("plan_path", ""),
            },
        )

    def can_finish(self) -> bool:
        if self.mode != "plan":
            return True
        path = self.runtime.path(self.plan_path)
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())

    def final_notice(self) -> str:
        return f"Plan mode requires writing the active plan artifact before final answer: {self.plan_path}"

    def prompt_text(self) -> str:
        if self.mode != "plan":
            return ""
        return (
            "Runtime mode: plan\n"
            f"- Active plan artifact: {self.plan_path}\n"
            "- You may inspect files, but writes must target only the active plan artifact.\n"
            "- You may launch Explore subagents, but not write-capable worker subagents.\n"
            "- Use todo tools to keep the task ledger current.\n"
            "- Return a final answer only after the active plan artifact has been written."
        )


PlanModeController = PlanModeManager


_PLAN_DIR_MARKER = "/.coda/plans/"


def _plan_path(topic: str, path: str | None = None) -> str:
    if path:
        value = str(path).strip()
        # 模型有时给绝对路径，如 /Users/u/repo/.coda/plans/foo；自动把它相对化。
        if value.startswith("/") and _PLAN_DIR_MARKER in value:
            value = value[value.index(_PLAN_DIR_MARKER) + 1 :]
        if value.startswith("./"):
            value = value[2:]
    else:
        value = f".coda/plans/{_slug(topic)}-plan.md"
    if (
        not value.startswith(".coda/plans/")
        or value.endswith("/")
        or ".." in value.split("/")
    ):
        raise ValueError("plan path must stay under .coda/plans/")
    return value
