"""Session compaction boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import Coda
from .context_usage import estimate_tokens
from .workspace import now


class CompactManager:
    def __init__(self, agent: Coda) -> None:
        self.agent = agent

    def compact(
        self, trigger: str = "manual", keep_recent_turns: int = 2
    ) -> dict[str, Any]:
        history = list(self.agent.session.get("history", []))
        groups = self._group(history)
        if len(groups) <= keep_recent_turns:
            summary = self._summary(trigger, history, history, "")
            self.agent.session_event_bus.emit("compaction_created", summary)
            return summary

        cutoff = len(groups) - keep_recent_turns
        cutoff = self._native_safe_cutoff(groups, cutoff)
        if cutoff <= 0:
            summary = self._summary(trigger, history, history, "")
            summary["compaction_action"] = "kept_unfinished_native_turn"
            self.agent.session_event_bus.emit("compaction_created", summary)
            return summary
        compacted_turns = groups[:cutoff]
        kept_turns = groups[cutoff:]
        compacted_items = [item for _, items in compacted_turns for item in items]
        kept_items = [item for _, items in kept_turns for item in items]
        summary_text = self._summary_text(compacted_items)
        summary_item = self.agent.turn_history.enrich(
            {
                "role": "system",
                "kind": "compact_summary",
                "content": summary_text,
                "created_at": now(),
                "source": "compact",
            }
        )
        self.agent.session["history"] = [summary_item, *kept_items]
        summary = self._summary(trigger, history, self.agent.session["history"], summary_text)
        self.agent.session.setdefault("compactions", []).append(summary)
        self.agent.session_path = self.agent.session_store.save(self.agent.session)
        self.agent.session_event_bus.emit("compaction_created", summary)
        if self.agent.current_task_state:
            self.agent.emit_trace(self.agent.current_task_state, "compaction_started", {"trigger": trigger, "pre_tokens": summary["pre_tokens"]})
            self.agent.emit_trace(self.agent.current_task_state, "compaction_finished", summary)
        return summary

    @staticmethod
    def _group(
        history: list[dict[str, Any]],
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        groups = []
        by_id: dict[str, list[dict[str, Any]]] = {}
        for item in history:
            turn_id = str(item.get("turn_id") or "legacy")
            if turn_id not in by_id:
                by_id[turn_id] = []
                groups.append((turn_id, by_id[turn_id]))
            by_id[turn_id].append(item)
        return groups

    def _summary(
        self,
        trigger: str,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        summary_text: str,
    ) -> dict[str, Any]:
        pre_chars = sum(len(str(item.get("content", ""))) for item in before)
        post_chars = sum(len(str(item.get("content", ""))) for item in after)
        return {
            "trigger": str(trigger),
            "created_at": now(),
            "pre_tokens": estimate_tokens(pre_chars),
            "post_tokens": estimate_tokens(post_chars),
            "pre_items": len(before),
            "post_items": len(after),
            "summary_chars": len(summary_text),
        }

    @staticmethod
    def _native_safe_cutoff(
        groups: list[tuple[str, list[dict[str, Any]]]], cutoff: int
    ) -> int:
        calls: dict[str, int] = {}
        results: dict[str, int] = {}
        awaiting = []
        for index, (_, items) in enumerate(groups):
            for item in items:
                status = str(item.get("native_turn_status", ""))
                if status in {"awaiting_result", "incomplete", "pending"}:
                    awaiting.append(index)
                call_id = str(
                    item.get("provider_call_id")
                    or item.get("tool_call_id")
                    or item.get("call_id")
                    or ""
                ).strip()
                kind = str(item.get("kind", ""))
                if call_id and kind in {"native_tool_call", "tool_call"}:
                    calls.setdefault(call_id, index)
                if call_id and kind in {"native_tool_result", "tool_result"}:
                    results.setdefault(call_id, index)
                for call in item.get("tool_calls", []) or []:
                    if isinstance(call, dict) and str(call.get("call_id", "")).strip():
                        calls.setdefault(str(call["call_id"]), index)
        for call_id, call_index in calls.items():
            result_index = results.get(call_id)
            if result_index is None or call_index < cutoff <= result_index:
                cutoff = min(cutoff, call_index)
        if awaiting:
            cutoff = min(cutoff, min(awaiting))
        return cutoff

    def _summary_text(self, items: list[dict[str, Any]]) -> str:
        files_read = []
        files_modified = []
        user_requests = []
        assistant_notes = []
        for item in items:
            if item.get("role") == "user":
                user_requests.append(str(item.get("content", "")).strip())
            elif item.get("role") == "assistant":
                assistant_notes.append(str(item.get("content", "")).strip())
            elif item.get("role") == "tool":
                path = str(item.get("args", {}).get("path", "")).strip()
                if item.get("name") == "read_file" and path:
                    files_read.append(path)
                if item.get("name") in {"write_file", "patch_file"} and path:
                    files_modified.append(path)
        return "\n".join(
            [
                "Compacted session summary:",
                f"- Goal: {user_requests[-1] if user_requests else '-'}",
                "- Constraints and preferences: -",
                f"- Files read: {', '.join(sorted(set(files_read))) or '-'}",
                f"- Files modified: {', '.join(sorted(set(files_modified))) or '-'}",
                f"- Key decisions: {assistant_notes[-1] if assistant_notes else '-'}",
                f"- Current progress: compacted {len(items)} history items",
                "- Open blockers: -",
                "- Next step: continue from the latest preserved turn",
                "- Critical context: earlier turns were compacted; use preserved latest turns for exact wording",
            ]
        )
