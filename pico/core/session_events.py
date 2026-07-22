"""Session-level event bus.

The run trace is per-task and diagnostic. The session event bus is the durable,
coarse-grained timeline for the interactive session itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .model_exchange import (
    EXCHANGE_SCHEMA_VERSION,
    ModelExchangeEvent,
    assert_profile_matches,
    normalize_profile_identity,
    public_artifact,
    restore_continuation,
)
from ..providers.contracts import ProviderContinuation
from .workspace import now


class SessionEventBus:
    def __init__(self, session_id: str, path: str | Path, redact: Callable[[Any], Any] | None = None):
        self.session_id = str(session_id)
        self.path = Path(path)
        self.redact = redact or (lambda value: value)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        record = dict(payload or {})
        record["event"] = str(event)
        record["session_id"] = self.session_id
        record["created_at"] = now()
        record = public_artifact(self.redact(record))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # append-only，数据完整性要求不如 session.json 高，没有原子写入
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record


class SessionExchangeJournal:
    """Persist private native exchange state before publishing audit evidence."""

    def __init__(
        self,
        session: dict[str, Any],
        persist: Callable[[dict[str, Any]], Any],
        publish: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.session = session
        self.persist = persist
        self.publish = publish

    def append(self, event: ModelExchangeEvent) -> dict[str, Any]:
        if not isinstance(event, ModelExchangeEvent):
            raise TypeError("session exchange journal requires a ModelExchangeEvent")
        candidate = json.loads(json.dumps(self.session, ensure_ascii=False))
        record = event.private_dict()
        state = self._state(candidate, record["profile"])
        record["sequence"] = len(state["events"]) + 1
        self._validate_order(state, record)
        state["events"].append(record)
        if "continuation" in record:
            state["continuation"] = record["continuation"]
        self.persist(candidate)
        self.session.clear()
        self.session.update(candidate)
        public = event.public_dict()
        public["sequence"] = record["sequence"]
        if self.publish is not None:
            self.publish(public)
        return public

    def latest_continuation(
        self, profile: Mapping[str, Any]
    ) -> ProviderContinuation | None:
        state = self.session.get("model_exchange")
        if not isinstance(state, dict) or state.get("continuation") is None:
            return None
        assert_profile_matches(state["profile"], profile)
        return restore_continuation(state["continuation"])

    def _state(
        self, session: dict[str, Any], profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized = normalize_profile_identity(profile)
        locked_session_profile = session.get("provider_profile")
        if locked_session_profile is not None:
            assert_profile_matches(locked_session_profile, normalized)
        state = session.get("model_exchange")
        if state is None:
            state = {
                "schema_version": EXCHANGE_SCHEMA_VERSION,
                "profile": normalized,
                "events": [],
            }
            session["model_exchange"] = state
            return state
        if not isinstance(state, dict):
            raise ValueError("session model_exchange state must be an object")
        if state.get("schema_version") != EXCHANGE_SCHEMA_VERSION:
            raise ValueError("unsupported session model_exchange schema")
        assert_profile_matches(state.get("profile", {}), normalized)
        if not isinstance(state.get("events"), list):
            raise ValueError("session model_exchange events must be a list")
        return state

    def _validate_order(
        self, state: dict[str, Any], record: dict[str, Any]
    ) -> None:
        calls: dict[str, dict[str, Any]] = {}
        for prior in state["events"]:
            if prior.get("event") == "assistant_tool_batch":
                for call in prior.get("tool_calls", []):
                    calls[str(call.get("call_id", ""))] = {
                        "exchange_id": prior.get("exchange_id"),
                        "name": call.get("name"),
                        "arguments": call.get("arguments"),
                        "status": "pending",
                    }
            elif prior.get("event") == "tool_result":
                calls[str(prior.get("call_id", ""))]["status"] = str(
                    prior.get("status", "")
                )
        event = record["event"]
        if event == "assistant_tool_batch":
            duplicate = [
                call["call_id"] for call in record["tool_calls"] if call["call_id"] in calls
            ]
            if duplicate:
                raise ValueError(f"duplicate provider call_id in session: {duplicate[0]}")
            return
        if event == "tool_result":
            call_id = record["call_id"]
            if call_id not in calls:
                raise ValueError("tool_result must follow a persisted assistant_tool_batch")
            expected = calls[call_id]
            if expected["status"] != "pending":
                raise ValueError(f"tool call {call_id!r} already has a terminal result")
            for field in ("exchange_id", "name", "arguments"):
                if record[field] != expected[field]:
                    raise ValueError(f"tool_result {field} does not match persisted tool call")
            return
        pending = sorted(
            call_id for call_id, call in calls.items() if call["status"] == "pending"
        )
        if pending:
            raise ValueError("model_final cannot precede terminal results for: " + ", ".join(pending))
