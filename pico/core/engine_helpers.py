"""Helper routines for Engine control-loop side effects."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Generator

from ..providers.contracts import ModelRequest
from ..providers.errors import ProviderError
from .model_errors import finish_model_error
from .request_context import build_model_request_context
from .session_lifecycle import NativeSessionRecorder
from .task_state import TaskState
from .workspace import clip, now

if TYPE_CHECKING:
    from .engine import Engine
    from .runtime import Pico


def run_native_turn(
    engine: Engine, user_message: str
) -> Generator[dict[str, Any], None, None]:
    """Run the active structured Runtime path with no text-envelope parser."""

    agent = engine.runtime
    run_started_at = time.monotonic()
    task_state = TaskState.create(
        run_id=agent.new_run_id(),
        task_id=agent.new_task_id(),
        user_request=user_message,
    )
    task_state.resume_status = agent.resume_state.get("status", "no-checkpoint")
    agent.current_task_state = task_state
    agent.current_turn_id = task_state.task_id
    agent.current_run_id = task_state.run_id
    agent.current_run_dir = agent.run_store.start_run(task_state)
    agent.session_event_bus.emit(
        "turn_started",
        {
            "run_id": task_state.run_id,
            "task_id": task_state.task_id,
            "runtime_mode": agent.runtime_mode,
        },
    )
    yield {
        "type": "turn_started",
        "run_id": task_state.run_id,
        "task_id": task_state.task_id,
    }
    agent.memory.set_task_summary(user_message)
    agent.record({"role": "user", "content": user_message, "created_at": now()})
    agent.session_event_bus.emit(
        "user_message",
        {"run_id": task_state.run_id, "content": clip(user_message, 300)},
    )
    agent.emit_trace(
        task_state,
        "run_started",
        {"task_id": task_state.task_id, "user_request": clip(user_message, 300)},
    )
    recorder = NativeSessionRecorder(agent, task_state)
    continuation = recorder.latest_continuation()
    prompt_started_at = time.monotonic()
    prompt, prompt_metadata = agent._build_prompt_and_metadata(user_message)
    context = build_model_request_context(
        agent, prompt, prompt_metadata, continuation=continuation
    )
    prompt_metadata = dict(context.metadata)
    prompt_metadata["provider_profile"] = dict(recorder.profile)
    agent.last_prompt_metadata = prompt_metadata
    agent.emit_trace(
        task_state,
        "prompt_built",
        {
            "prompt_metadata": prompt_metadata,
            "duration_ms": int((time.monotonic() - prompt_started_at) * 1000),
        },
    )
    _checkpoint_for_prompt_state(agent, task_state, user_message, prompt_metadata)
    request = ModelRequest(
        prompt=context.legacy_prompt(),
        max_output_tokens=agent.max_new_tokens,
        tools=context.tools,
        continuation=context.continuation,
    )
    task_state.record_attempt()
    agent.run_store.write_task_state(task_state)
    agent.emit_trace(
        task_state,
        "model_requested",
        {
            "attempts": task_state.attempts,
            "tool_steps": task_state.tool_steps,
            "native_tools": len(request.tools),
            "sdk_max_retries": recorder.profile.get("sdk_max_retries"),
        },
    )
    agent.session_event_bus.emit(
        "model_requested",
        {
            "run_id": task_state.run_id,
            "attempts": task_state.attempts,
            "tool_steps": task_state.tool_steps,
        },
    )
    yield {
        "type": "model_requested",
        "run_id": task_state.run_id,
        "attempts": task_state.attempts,
        "tool_steps": task_state.tool_steps,
    }
    model_started_at = time.monotonic()
    provider_retries: dict[str, int] = {}
    worker_events: list[dict[str, Any]] = []

    def on_native_event(event: dict[str, Any]) -> None:
        if event.get("event") == "native_tool_call_state" and event.get("status") in {
            "completed",
            "rejected",
            "uncertain",
        }:
            for notification in engine.drain_worker_notifications():
                worker_events.append(
                    {
                        "type": "worker_notification",
                        "run_id": task_state.run_id,
                        "content": notification,
                    }
                )

    while True:
        try:
            result = engine.run_native_tool_loop(
                request,
                persist_hook=recorder.persist,
                event_hook=on_native_event,
            )
            break
        except Exception as exc:
            if should_retry_model_error(exc, provider_retries):
                code = str(getattr(exc, "code", type(exc).__name__))
                provider_retries[code] = provider_retries.get(code, 0) + 1
                task_state.record_attempt()
                agent.run_store.write_task_state(task_state)
                payload = {
                    "run_id": task_state.run_id,
                    "code": code,
                    "attempts": task_state.attempts,
                    "retry_count": provider_retries[code],
                }
                agent.session_event_bus.emit("model_retry_scheduled", payload)
                agent.emit_trace(task_state, "model_retry_scheduled", payload)
                continue
            yield from finish_model_error(
                engine,
                task_state,
                user_message,
                prompt_metadata,
                exc,
                int((time.monotonic() - model_started_at) * 1000),
                int((time.monotonic() - run_started_at) * 1000),
            )
            return

    policy_attempts = 0
    while agent.runtime_mode == "plan" and not agent.plan_mode.can_finish():
        notice = agent.plan_mode.final_notice()
        agent.record({"role": "assistant", "content": notice, "created_at": now()})
        agent.session_event_bus.emit(
            "assistant_message",
            {
                "run_id": task_state.run_id,
                "kind": "runtime_notice",
                "content": notice,
            },
        )
        yield {"type": "runtime_notice", "run_id": task_state.run_id, "content": notice}
        policy_attempts += 1
        if policy_attempts >= agent.max_steps + 2:
            final = "Stopped after too many final answers before the plan artifact was written."
            task_state.stop_retry_limit(final)
            yield from finish_limited_run(
                engine, task_state, user_message, final, run_started_at
            )
            return
        request = ModelRequest(
            prompt=f"{prompt}\n\nRuntime notice:\n{notice}",
            max_output_tokens=agent.max_new_tokens,
            tools=context.tools,
            continuation=result.responses[-1].continuation,
        )
        try:
            result = engine.run_native_tool_loop(
                request,
                persist_hook=recorder.persist,
                event_hook=on_native_event,
            )
        except Exception as exc:
            yield from finish_model_error(
                engine,
                task_state,
                user_message,
                prompt_metadata,
                exc,
                int((time.monotonic() - model_started_at) * 1000),
                int((time.monotonic() - run_started_at) * 1000),
            )
            return

    try:
        recorder.finish(result.responses[-1])
    except Exception as exc:
        yield from finish_model_error(
            engine,
            task_state,
            user_message,
            prompt_metadata,
            exc,
            int((time.monotonic() - model_started_at) * 1000),
            int((time.monotonic() - run_started_at) * 1000),
        )
        return
    task_state.attempts = len(result.responses)
    yield from recorder.events
    yield from worker_events
    final = result.final_text
    completion_metadata = dict(result.responses[-1].metadata)
    completion_metadata.update(
        {
            "provider_attempts": len(result.responses),
            "provider_retry_count": sum(
                int(response.metadata.get("sdk_retry_count", 0))
                for response in result.responses
            ),
            "sdk_max_retries": recorder.profile.get("sdk_max_retries", 0),
        }
    )
    agent.last_completion_metadata = completion_metadata
    prompt_metadata.update(completion_metadata)
    agent.last_prompt_metadata = prompt_metadata
    if result.step_limit_reached:
        if final != "Stopped after reaching the step limit.":
            final += (
                "\n\n— 已达本轮 step 预算上限（max_steps）。以上是当前进展总结。"
                "继续工作：在 REPL 输入 /resume 续接本会话，或直接说「继续」让我接着干。"
            )
        task_state.stop_step_limit(final)
        yield from finish_limited_run(
            engine, task_state, user_message, final, run_started_at
        )
        return
    yield from finish_successful_run(
        engine, task_state, user_message, final, run_started_at
    )


def _checkpoint_for_prompt_state(
    agent: Pico,
    task_state: TaskState,
    user_message: str,
    prompt_metadata: dict[str, Any],
) -> None:
    trigger = ""
    if prompt_metadata.get("resume_status") == "partial-stale":
        trigger = "freshness_mismatch"
    elif prompt_metadata.get("resume_status") == "workspace-mismatch":
        trigger = "workspace_mismatch"
        agent.emit_trace(
            task_state,
            "runtime_identity_mismatch",
            {
                "fields": list(
                    prompt_metadata.get("runtime_identity_mismatch_fields", [])
                )
            },
        )
    elif prompt_metadata.get("budget_reductions"):
        trigger = "context_reduction"
    if not trigger:
        return
    checkpoint = agent.create_checkpoint(task_state, user_message, trigger=trigger)
    agent.run_store.write_task_state(task_state)
    agent.emit_trace(
        task_state,
        "checkpoint_created",
        {"checkpoint_id": checkpoint["checkpoint_id"], "trigger": trigger},
    )


def finish_successful_run(
    engine: Engine,
    task_state: TaskState,
    user_message: str,
    final: str,
    run_started_at: float,
) -> Generator[dict[str, Any], None, None]:
    """Finalize the shared native and migration control-loop success path."""

    agent = engine.runtime
    agent.record({"role": "assistant", "content": final, "created_at": now()})
    if agent.runtime_mode == "plan":
        agent.exit_plan_mode()
    agent.session_event_bus.emit(
        "assistant_message",
        {"run_id": task_state.run_id, "kind": "final", "content": clip(final, 500)},
    )
    task_state.finish_success(final)
    agent.promote_durable_memory(user_message, final)
    maintain_memory_safely(agent, task_state, final)
    checkpoint = agent.create_checkpoint(
        task_state, user_message, trigger="run_finished"
    )
    agent.run_store.write_task_state(task_state)
    agent.emit_trace(
        task_state,
        "checkpoint_created",
        {"checkpoint_id": checkpoint["checkpoint_id"], "trigger": "run_finished"},
    )
    agent.emit_trace(
        task_state,
        "run_finished",
        {
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "final_answer": final,
            "run_duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.session_event_bus.emit(
        "turn_finished",
        {
            "run_id": task_state.run_id,
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.run_store.write_report(
        task_state, agent.redact_artifact(agent.build_report(task_state))
    )
    yield from engine._drain_worker_notification_events()
    agent.current_turn_id = ""
    agent.current_run_id = ""
    yield {"type": "final", "run_id": task_state.run_id, "content": final}
    yield {
        "type": "turn_finished",
        "run_id": task_state.run_id,
        "status": task_state.status,
        "stop_reason": task_state.stop_reason,
    }


def execute_tool_payload(
    engine: Engine, task_state: TaskState, user_message: str, payload: dict[str, Any]
) -> Generator[dict[str, Any], None, None]:
    agent = engine.runtime
    name = payload.get("name", "")
    args = payload.get("args", {})
    task_state.record_tool(name)
    tool_started_at = time.monotonic()
    agent.session_event_bus.emit(
        "tool_started", {"run_id": task_state.run_id, "tool_name": name, "args": args}
    )
    yield {"type": "tool_call", "run_id": task_state.run_id, "name": name, "args": args}

    tool_result = agent.run_tool(name, args)
    tool_metadata = dict(agent._last_tool_result_metadata or {})
    tool_duration_ms = int((time.monotonic() - tool_started_at) * 1000)
    agent.session_event_bus.emit(
        "tool_finished",
        {
            "run_id": task_state.run_id,
            "tool_name": name,
            "status": tool_metadata.get("tool_status", ""),
            "tool_error_code": tool_metadata.get("tool_error_code", ""),
            "workspace_changed": bool(tool_metadata.get("workspace_changed", False)),
            "affected_paths": list(tool_metadata.get("affected_paths", [])),
            "duration_ms": tool_duration_ms,
        },
    )
    agent.record(
        {
            "role": "tool",
            "name": name,
            "args": args,
            "content": tool_result,
            "created_at": now(),
        }
    )
    for notification in engine.drain_worker_notifications():
        yield {
            "type": "worker_notification",
            "run_id": getattr(agent, "current_run_id", ""),
            "content": notification,
        }
    agent.run_store.write_task_state(task_state)
    agent.emit_trace(
        task_state,
        "tool_executed",
        {
            "name": name,
            "args": args,
            "result": clip(tool_result, 500),
            "duration_ms": tool_duration_ms,
            **tool_metadata,
        },
    )
    checkpoint = agent.create_checkpoint(
        task_state, user_message, trigger="tool_executed"
    )
    agent.run_store.write_task_state(task_state)
    agent.emit_trace(
        task_state,
        "checkpoint_created",
        {"checkpoint_id": checkpoint["checkpoint_id"], "trigger": "tool_executed"},
    )
    yield {
        "type": "tool_result",
        "run_id": task_state.run_id,
        "name": name,
        "content": tool_result,
        "metadata": tool_metadata,
    }


def finish_stopped_run(
    engine: Engine,
    task_state: TaskState,
    user_message: str,
    final: str,
    stop_reason: str,
    run_started_at: float,
) -> Generator[dict[str, Any], None, None]:
    agent = engine.runtime
    task_state.stop(stop_reason, final_answer=final)
    agent.abort_requested = False
    agent.record({"role": "assistant", "content": final, "created_at": now()})
    agent.session_event_bus.emit(
        "assistant_message",
        {"run_id": task_state.run_id, "kind": "stop", "content": clip(final, 500)},
    )
    agent.run_store.write_task_state(task_state)
    checkpoint = agent.create_checkpoint(task_state, user_message, trigger=stop_reason)
    agent.emit_trace(
        task_state,
        "checkpoint_created",
        {"checkpoint_id": checkpoint["checkpoint_id"], "trigger": stop_reason},
    )
    agent.emit_trace(
        task_state,
        "run_finished",
        {
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "final_answer": final,
            "run_duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.session_event_bus.emit(
        "turn_finished",
        {
            "run_id": task_state.run_id,
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.run_store.write_report(
        task_state, agent.redact_artifact(agent.build_report(task_state))
    )
    agent.current_turn_id = ""
    agent.current_run_id = ""
    yield {"type": "stop", "run_id": task_state.run_id, "content": final}
    yield {
        "type": "turn_finished",
        "run_id": task_state.run_id,
        "status": task_state.status,
        "stop_reason": task_state.stop_reason,
    }


def finish_limited_run(
    engine: Engine,
    task_state: TaskState,
    user_message: str,
    final: str,
    run_started_at: float,
) -> Generator[dict[str, Any], None, None]:
    agent = engine.runtime
    agent.record({"role": "assistant", "content": final, "created_at": now()})
    agent.session_event_bus.emit(
        "assistant_message",
        {"run_id": task_state.run_id, "kind": "stop", "content": clip(final, 500)},
    )
    agent.promote_durable_memory(user_message, final)
    maintain_memory_safely(agent, task_state, final)
    agent.run_store.write_task_state(task_state)
    checkpoint = agent.create_checkpoint(
        task_state, user_message, trigger=task_state.stop_reason or "run_stopped"
    )
    agent.emit_trace(
        task_state,
        "checkpoint_created",
        {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "trigger": task_state.stop_reason or "run_stopped",
        },
    )
    agent.emit_trace(
        task_state,
        "run_finished",
        {
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "final_answer": final,
            "run_duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.session_event_bus.emit(
        "turn_finished",
        {
            "run_id": task_state.run_id,
            "status": task_state.status,
            "stop_reason": task_state.stop_reason,
            "duration_ms": int((time.monotonic() - run_started_at) * 1000),
        },
    )
    agent.run_store.write_report(
        task_state, agent.redact_artifact(agent.build_report(task_state))
    )
    agent.current_turn_id = ""
    agent.current_run_id = ""
    yield {"type": "stop", "run_id": task_state.run_id, "content": final}
    yield {
        "type": "turn_finished",
        "run_id": task_state.run_id,
        "status": task_state.status,
        "stop_reason": task_state.stop_reason,
    }


def should_retry_model_error(exc: Exception, provider_retries: dict[str, int]) -> bool:
    if not isinstance(exc, ProviderError):
        return False
    code = str(getattr(exc, "code", "") or "")
    if code not in {"empty_response"}:
        return False
    return provider_retries.get(code, 0) < 1


def maintain_memory_safely(
    agent: Pico, task_state: TaskState, final_answer: str
) -> None:
    try:
        agent.maintain_memory_after_turn(final_answer)
    except Exception as exc:
        audit = getattr(agent, "last_memory_maintenance", {"errors": []})
        errors = audit.setdefault("errors", [])
        errors.append(str(exc))
        agent.last_memory_maintenance = audit
        agent.session_event_bus.emit(
            "memory_maintenance_failed",
            {"run_id": task_state.run_id, "error": clip(str(exc), 300)},
        )
        agent.emit_trace(
            task_state, "memory_maintenance_failed", {"error": clip(str(exc), 300)}
        )


def request_step_limit_summary(
    engine: Engine, task_state: TaskState, user_message: str
) -> str | None:
    """Legacy Engine hook retained as an unreachable compatibility tombstone.

    Native turns request their structured step-limit summary in tool_call_batch.
    """
    del engine, task_state, user_message
    return None
