import json

import pytest

from pico.core.model_exchange import (
    ModelExchangeEvent,
    ProfileMismatchError,
    assert_profile_matches,
)
from pico.core.run_store import RunStore
from pico.core.session_events import SessionEventBus, SessionExchangeJournal
from pico.core.task_state import TaskState
from pico.providers.contracts import (
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
    ToolCallResult,
)


def _profile(**changes):
    value = {
        "profile_id": "profile:test",
        "profile": "test-provider",
        "model": "test-model",
        "wire_dialect": "test-native",
        "base_url_fingerprint": "sha256:base",
        "sdk_max_retries": 0,
    }
    value.update(changes)
    return value


def _tool_response(call, continuation=None):
    return ModelResponse(
        text="",
        tool_calls=[call],
        stop_reason=StopReason.TOOL_CALLS,
        continuation=continuation,
    )


def test_assistant_batch_is_persisted_before_publication_or_tool_execution():
    session = {"id": "session-1", "provider_profile": _profile(), "history": []}
    order = []

    def persist(candidate):
        calls = candidate["model_exchange"]["events"][0]["tool_calls"]
        assert calls[0]["status"] == "pending"
        order.append("persisted")

    def publish(record):
        assert session["model_exchange"]["events"][0]["event"] == "assistant_tool_batch"
        order.append("published")

    call = ToolCall("call-1", "read_file", {"path": "README.md"})
    journal = SessionExchangeJournal(session, persist, publish)
    event = ModelExchangeEvent.assistant_tool_batch(
        exchange_id="exchange-1",
        profile=_profile(),
        response=_tool_response(call),
    )

    public = journal.append(event)

    assert order == ["persisted", "published"]
    assert public["tool_calls"] == [
        {
            "call_id": "call-1",
            "name": "read_file",
            "arguments": {"path": "README.md"},
            "status": "pending",
        }
    ]


def test_tool_result_requires_persisted_batch_and_is_one_to_one():
    session = {"id": "session-2", "provider_profile": _profile(), "history": []}
    journal = SessionExchangeJournal(session, lambda candidate: None)
    call = ToolCall("call-2", "read_file", {"path": "README.md"})
    result = ToolCallResult("call-2", {"content": "hello"})
    result_event = ModelExchangeEvent.tool_result(
        exchange_id="exchange-2",
        profile=_profile(),
        call=call,
        result=result,
    )

    with pytest.raises(ValueError, match="persisted assistant_tool_batch"):
        journal.append(result_event)

    journal.append(
        ModelExchangeEvent.assistant_tool_batch(
            exchange_id="exchange-2",
            profile=_profile(),
            response=_tool_response(call),
        )
    )
    public = journal.append(result_event)

    assert public["call_id"] == "call-2"
    assert public["name"] == "read_file"
    assert public["arguments"] == {"path": "README.md"}
    assert public["status"] == "completed"
    with pytest.raises(ValueError, match="terminal result"):
        journal.append(result_event)


def test_model_final_follows_terminal_results_with_monotonic_sequence():
    session = {"id": "session-final", "provider_profile": _profile(), "history": []}
    journal = SessionExchangeJournal(session, lambda candidate: None)
    call = ToolCall("call-final", "list_files", {})
    journal.append(
        ModelExchangeEvent.assistant_tool_batch(
            exchange_id="exchange-final",
            profile=_profile(),
            response=_tool_response(call),
        )
    )
    final_event = ModelExchangeEvent.model_final(
        exchange_id="exchange-final",
        profile=_profile(),
        response=ModelResponse(
            text="done",
            tool_calls=[],
            stop_reason=StopReason.END_TURN,
        ),
    )

    with pytest.raises(ValueError, match="terminal results"):
        journal.append(final_event)

    journal.append(
        ModelExchangeEvent.tool_result(
            exchange_id="exchange-final",
            profile=_profile(),
            call=call,
            result=ToolCallResult("call-final", {"files": []}),
        )
    )
    public = journal.append(final_event)

    assert public["event"] == "model_final"
    assert public["text"] == "done"
    assert [event["sequence"] for event in session["model_exchange"]["events"]] == [
        1,
        2,
        3,
    ]


def test_private_continuation_roundtrips_but_public_trace_and_report_hold_hash_only(tmp_path):
    private = "PRIVATE-REASONING-SENTINEL"
    continuation = ProviderContinuation(
        "profile:test", {"type": "reasoning", "content": private}
    )
    call = ToolCall("call-3", "list_files", {})
    event = ModelExchangeEvent.assistant_tool_batch(
        exchange_id="exchange-3",
        profile=_profile(),
        response=_tool_response(call, continuation),
    )
    session = {"id": "session-3", "provider_profile": _profile(), "history": []}
    journal = SessionExchangeJournal(session, lambda candidate: None)
    public = journal.append(event)

    restored = journal.latest_continuation(_profile())
    assert restored is not None
    assert restored.to_dict() == continuation.to_dict()
    assert private in json.dumps(session)
    assert private not in json.dumps(public)
    assert public["continuation_evidence"] == {
        "hash": continuation.stable_hash(),
        "type": "ProviderContinuation",
        "count": 1,
    }

    state = TaskState.create("task", "request", run_id="run")
    store = RunStore(tmp_path / "runs")
    store.start_run(state)
    store.append_trace(state, event.private_dict())
    store.write_report(state, {"exchange": event.private_dict()})

    assert private not in store.trace_path("run").read_text(encoding="utf-8")
    assert private not in store.report_path("run").read_text(encoding="utf-8")


def test_session_event_bus_never_writes_private_exchange_payload(tmp_path):
    private = "PRIVATE-THINKING-SENTINEL"
    continuation = ProviderContinuation("profile:test", {"thinking": private})
    call = ToolCall("call-4", "list_files", {})
    event = ModelExchangeEvent.assistant_tool_batch(
        exchange_id="exchange-4",
        profile=_profile(),
        response=_tool_response(call, continuation),
    )
    bus = SessionEventBus("session-4", tmp_path / "events.jsonl")

    record = bus.emit("model_exchange", {"exchange": event.private_dict()})

    assert private not in json.dumps(record)
    assert private not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"profile": "other-provider"}, "provider"),
        ({"model": "other-model"}, "model"),
        ({"wire_dialect": "other-dialect"}, "wire_dialect"),
    ],
)
def test_provider_model_and_dialect_mismatch_are_detected(changes, field):
    with pytest.raises(ProfileMismatchError, match=field):
        assert_profile_matches(_profile(), _profile(**changes))


def test_continuation_profile_mismatch_fails_before_persistence():
    continuation = ProviderContinuation("profile:other", {"opaque": True})
    call = ToolCall("call-5", "list_files", {})

    with pytest.raises(ProfileMismatchError, match="continuation profile_id"):
        ModelExchangeEvent.assistant_tool_batch(
            exchange_id="exchange-5",
            profile=_profile(),
            response=_tool_response(call, continuation),
        )


def test_sdk_objects_and_private_metadata_are_rejected():
    class SDKObject:
        pass

    with pytest.raises(TypeError, match="JSON-safe"):
        ModelExchangeEvent.tool_result(
            exchange_id="exchange-6",
            profile=_profile(),
            call=ToolCall("call-6", "tool", {}),
            result=ToolCallResult("call-6", {"ok": True}),
            created_at=SDKObject(),
        )

    response = ModelResponse(
        text="done",
        tool_calls=[],
        stop_reason=StopReason.END_TURN,
        metadata={"reasoning": "must remain private"},
    )
    with pytest.raises(ValueError, match="private continuation fields"):
        ModelExchangeEvent.model_final(
            exchange_id="exchange-6", profile=_profile(), response=response
        )
