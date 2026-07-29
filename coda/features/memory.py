"""多步 agent 运行时使用的记忆兼容入口与维护编排。

持久记忆与会话内工作记忆分别实现在 ``memory_durable`` 和
``memory_working``；本模块保留原有导入路径和依赖 Coda 的运行时编排。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from ..core.runtime import Coda

from ..core.workspace import WorkspaceContext, clip
from .memory_durable import (
    DREAM_MIN_NEW_TOKENS,
    DREAM_SESSION_CAP,
    DURABLE_MEMORY_INTENT_PATTERN,
    DURABLE_MEMORY_INTENT_ZH_PATTERN,
    DURABLE_MEMORY_LINE_PATTERNS,
    DURABLE_MEMORY_LIST_PREFIX_PATTERN,
    DURABLE_TOPIC_DEFAULTS,
    ENTRYPOINT_NAME,
    HOLDER_STALE_S,
    LOCK_FILE_NAME,
    MAX_ENTRYPOINT_LINES,
    MAX_MEMORY_INDEX_CHARS,
    SECRET_SHAPED_TEXT_PATTERN,
    DurableMemoryStore,
    _lock_path,
    _parse_timestamp,
    _tokenize,
    append_to_daily_log,
    build_dream_prompt,
    build_memory_system_section,
    daily_log_path,
    ensure_memory_dir,
    evaluate_auto_dream_gate,
    extract_durable_promotions,
    extract_memory_tags,
    list_sessions_since,
    load_memory_index_text,
    read_last_consolidated_at,
    record_consolidation,
    reject_durable_reason,
    release_lock,
    should_auto_dream,
    try_acquire_lock,
)
from .memory_working import (
    EPISODIC_NOTE_LIMIT,
    FILE_SUMMARY_LIMIT,
    WORKING_FILE_LIMIT,
    LayeredMemory,
    _dedupe_preserve_order,
    _ensure_list,
    _normalize_note,
    append_note,
    canonicalize_path,
    default_memory_state,
    file_freshness,
    invalidate_file_summary,
    invalidate_stale_file_summaries,
    is_effectively_empty,
    normalize_memory_state,
    remember_file,
    render_memory_text,
    resolve_workspace_path,
    retrieval_candidates,
    retrieval_view,
    set_file_summary,
    set_task_summary,
    summarize_read_result,
)

# Keep the original module-level compatibility surface explicit without
# changing wildcard-import behavior through a newly introduced ``__all__``.
_COMPATIBILITY_EXPORTS = (
    DREAM_SESSION_CAP,
    DURABLE_MEMORY_INTENT_PATTERN,
    DURABLE_MEMORY_INTENT_ZH_PATTERN,
    DURABLE_MEMORY_LINE_PATTERNS,
    DURABLE_MEMORY_LIST_PREFIX_PATTERN,
    DURABLE_TOPIC_DEFAULTS,
    ENTRYPOINT_NAME,
    HOLDER_STALE_S,
    MAX_ENTRYPOINT_LINES,
    MAX_MEMORY_INDEX_CHARS,
    SECRET_SHAPED_TEXT_PATTERN,
    DurableMemoryStore,
    _lock_path,
    _parse_timestamp,
    _tokenize,
    build_memory_system_section,
    daily_log_path,
    list_sessions_since,
    load_memory_index_text,
    reject_durable_reason,
    should_auto_dream,
    EPISODIC_NOTE_LIMIT,
    FILE_SUMMARY_LIMIT,
    WORKING_FILE_LIMIT,
    LayeredMemory,
    _dedupe_preserve_order,
    _ensure_list,
    _normalize_note,
    append_note,
    canonicalize_path,
    default_memory_state,
    file_freshness,
    invalidate_file_summary,
    invalidate_stale_file_summaries,
    is_effectively_empty,
    remember_file,
    render_memory_text,
    resolve_workspace_path,
    retrieval_candidates,
    retrieval_view,
    set_file_summary,
    set_task_summary,
    summarize_read_result,
)


class MemoryTagAudit(TypedDict):
    source: str
    path: str
    chars: int


class AutoDreamAudit(TypedDict, total=False):
    enabled: bool
    triggered: bool
    skip_reason: str
    session_count: int
    session_ids: list[str]
    changed_files: list[str]
    status: str


class MemoryMaintenanceAudit(TypedDict):
    memory_tags_appended: list[MemoryTagAudit]
    auto_dream: AutoDreamAudit
    errors: list[str]

def default_memory_maintenance_audit(auto_dream: bool = True) -> MemoryMaintenanceAudit:
    return {
        "memory_tags_appended": [],
        "auto_dream": {
            "enabled": bool(auto_dream),
            "triggered": False,
            "skip_reason": "",
            "session_count": 0,
            "session_ids": [],
            "changed_files": [],
        },
        "errors": [],
    }


def _agent_relative_path(agent: Coda, path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(agent.root).as_posix()
    except ValueError:
        return str(path)


def _memory_file_snapshot(agent: Coda) -> dict[str, str]:
    memory_dir = Path(agent.memory_dir)
    if not memory_dir.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in memory_dir.rglob("*"):
        if not path.is_file() or path.name == LOCK_FILE_NAME:
            continue
        relative = _agent_relative_path(agent, path)
        try:
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return snapshot


def _changed_memory_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _emit_memory_trace(agent: Coda, event: str, payload: Any) -> Any:
    task_state = getattr(agent, "current_task_state", None)
    if task_state is None:
        return None
    return agent.emit_trace(task_state, event, payload)


def _write_memory_maintenance_report(
    agent: Coda,
    task_state: Any,
    audit: MemoryMaintenanceAudit,
) -> None:
    try:
        if agent.run_store.report_path(task_state).exists():
            report = agent.run_store.load_report(task_state)
        else:
            report = agent.build_report(task_state)
    except (OSError, json.JSONDecodeError):
        report = agent.build_report(task_state)
    report["memory_maintenance"] = dict(audit)
    agent.run_store.write_report(task_state, agent.redact_artifact(report))


def promote_durable_memory(agent: Coda, user_message: str, final_answer: str) -> tuple[list[str], list[str], list[str]]:
    promotions, rejections = extract_durable_promotions(user_message, final_answer)
    promoted, superseded = agent.memory.promote_durable(promotions)
    agent.session["memory"] = agent.memory.to_dict()
    agent.last_durable_promotions = promoted
    agent.last_durable_rejections = rejections
    agent.last_durable_superseded = superseded
    return promoted, rejections, superseded


def run_dream(agent: Coda, quiet: bool = False, session_ids: list[str] | None = None) -> str:
    from ..core.runtime import Coda

    ensure_memory_dir(agent.memory_dir)
    session_ids = list(session_ids or [])
    before_snapshot = _memory_file_snapshot(agent)
    dream_prompt = build_dream_prompt(agent.memory_dir, transcript_dir=str(agent.session_store.root), session_ids=session_ids)
    try:
        memory_scope = Path(agent.memory_dir).resolve().relative_to(agent.root)
    except ValueError:
        memory_scope = Path(".coda") / "memory"
    dream_agent = Coda(
        model_client=agent.model_client,
        workspace=WorkspaceContext.build(agent.root),
        session_store=agent.session_store,
        approval_policy="auto",
        max_steps=max(agent.max_steps, 20),
        max_new_tokens=max(agent.max_new_tokens, DREAM_MIN_NEW_TOKENS),
        secret_env_names=agent.secret_env_names,
        feature_flags={**agent.feature_flags, "memory": False, "relevant_memory": False},
        write_scope=[str(memory_scope)],
        memory_dir=agent.memory_dir,
        auto_dream=False,
    )
    dream_agent.set_tool_profile("dream")
    parent_profile = agent.session.get("provider_profile")
    if not isinstance(parent_profile, Mapping):
        raise ValueError("dream parent requires a locked provider_profile")
    dream_agent.session["provider_profile"] = {
        **{
            key: value
            for key, value in parent_profile.items()
            if key != "tool_schema"
        },
        "tool_schema": dream_agent.tool_signature(),
    }
    dream_agent.session_path = dream_agent.session_store.save(dream_agent.session)
    dream_agent.refresh_prefix(force=True)
    result = dream_agent.ask(dream_prompt)
    record_consolidation(agent.memory_dir)
    changed_files = _changed_memory_files(before_snapshot, _memory_file_snapshot(agent))
    agent.last_dream_changed_files = changed_files
    agent.session_event_bus.emit(
        "dream_consolidated",
        {"quiet": bool(quiet), "session_ids": session_ids, "memory_dir": str(agent.memory_dir), "changed_files": changed_files},
    )
    agent.memory.state = normalize_memory_state(agent.memory.state, agent.root)
    agent.session["memory"] = agent.memory.to_dict()
    return result


def maintain_memory_after_turn(agent: Coda, final_answer: str) -> MemoryMaintenanceAudit:
    audit = default_memory_maintenance_audit(auto_dream=agent.auto_dream)
    agent.last_memory_maintenance = audit
    for entry in extract_memory_tags(final_answer):
        path = append_to_daily_log(agent.memory_dir, entry)
        payload = {"source": "final_answer", "path": _agent_relative_path(agent, path), "chars": len(entry)}
        audit["memory_tags_appended"].append(payload)
        agent.session_event_bus.emit("memory_note_appended", payload)
    if not agent.auto_dream:
        audit["auto_dream"]["skip_reason"] = "disabled"
        _emit_memory_trace(agent, "memory_auto_dream_skipped", dict(audit["auto_dream"]))
        return audit
    gate = evaluate_auto_dream_gate(
        agent.memory_dir,
        min_hours=agent.dream_interval_hours,
        min_sessions=agent.dream_min_sessions,
        current_session_id=agent.session["id"],
        sessions_dir=agent.session_store.root,
    )
    audit["auto_dream"]["session_count"] = gate["session_count"]
    audit["auto_dream"]["session_ids"] = list(gate["session_ids"])
    if not gate["should_run"]:
        audit["auto_dream"]["skip_reason"] = gate["skip_reason"]
        _emit_memory_trace(agent, "memory_auto_dream_skipped", dict(audit["auto_dream"]))
        return audit
    previous_mtime = read_last_consolidated_at(agent.memory_dir)
    if not try_acquire_lock(agent.memory_dir):
        audit["auto_dream"]["skip_reason"] = "lock_held"
        _emit_memory_trace(agent, "memory_auto_dream_skipped", dict(audit["auto_dream"]))
        return audit
    session_ids = list(gate["session_ids"])
    task_state = getattr(agent, "current_task_state", None)
    audit["auto_dream"]["triggered"] = True
    audit["auto_dream"]["status"] = "submitted"
    started_payload = {"session_ids": session_ids, "session_count": len(session_ids), "status": "submitted"}
    agent.session_event_bus.emit("auto_dream_started", started_payload)
    _emit_memory_trace(agent, "memory_auto_dream_started", started_payload)

    def _background_dream() -> None:
        try:
            run_dream(agent, quiet=True, session_ids=session_ids)
            audit["auto_dream"]["status"] = "finished"
            audit["auto_dream"]["changed_files"] = list(getattr(agent, "last_dream_changed_files", []))
            _emit_memory_trace(agent, "memory_auto_dream_finished", dict(audit["auto_dream"]))
            release_lock(agent.memory_dir)
        except Exception as exc:
            audit["auto_dream"]["status"] = "failed"
            audit["errors"].append(str(exc))
            lock_path = Path(agent.memory_dir) / LOCK_FILE_NAME
            if lock_path.exists():
                try:
                    os.utime(lock_path, (previous_mtime, previous_mtime))
                except OSError:
                    pass
            agent.session_event_bus.emit("memory_auto_dream_failed", {"error": clip(str(exc), 300), "session_ids": session_ids})
            _emit_memory_trace(agent, "memory_auto_dream_failed", {"error": clip(str(exc), 300), "session_ids": session_ids})
        finally:
            if getattr(agent, "current_task_state", None) is task_state:
                agent.last_memory_maintenance = audit
            if task_state is not None:
                _write_memory_maintenance_report(agent, task_state, audit)

    thread = threading.Thread(target=_background_dream, name="coda-auto-dream", daemon=True)
    agent._memory_maintenance_thread = thread
    thread.start()
    return audit
