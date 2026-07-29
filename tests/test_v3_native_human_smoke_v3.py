from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.run_v3_native_human_smoke_v3 import (
    DEFAULT_MANIFEST,
    FakeProvider,
    _events,
    _observed_calls,
    load_manifest,
    main,
    run_manifest,
)


def test_v3_manifest_has_semantic_order_and_non_leaking_denial_fixture() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    b = manifest["scenarios"][1]
    assert b["expected_postcondition"]["semantic_order"] == ["run_shell", "read_file"]
    assert "test" not in json.dumps(b["fixture"]).lower()
    assert "den" not in b["prompt"].lower()


def test_fake_run_binds_exchange_call_ids_to_runtime_events_and_file_provenance(tmp_path) -> None:
    summary = run_manifest(DEFAULT_MANIFEST, tmp_path)
    assert summary["status"] == "PASS"
    assert summary["http_attempts"] == 0
    for scenario in summary["scenarios"]:
        evidence = scenario["verification"]
        assert evidence["workspace_before"] and evidence["workspace_after"] and evidence["diff"]
        assert all(call["call_id"] and call["runtime"] for call in evidence["observed_calls"])
    b = summary["scenarios"][1]["verification"]
    assert {check["name"] for check in b["checks"]} >= {"runtime_denial_on_observed_call_id", "safe_continuation_after_denial"}


def test_v3_live_api_and_cli_fail_closed(tmp_path) -> None:
    with pytest.raises(ValueError, match="authorized-live"):
        run_manifest(DEFAULT_MANIFEST, tmp_path, execution_mode="authorized_live")
    with pytest.raises(SystemExit) as error:
        main(["--authorized-live", "--output-dir", str(tmp_path)])
    assert error.value.code == 2


def test_observed_calls_binds_reversed_same_name_runtime_events_by_call_id() -> None:
    agent = SimpleNamespace(session={"model_exchange": {"events": [{"event": "assistant_tool_batch", "tool_calls": [{"call_id": "call-read-a", "name": "read_file", "arguments": {"path": "a.md"}}, {"call_id": "call-read-b", "name": "read_file", "arguments": {"path": "b.md"}}]}]}})
    events = [
        {"event": "tool_finished", "call_id": "call-read-b", "tool_name": "read_file"},
        {"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"},
    ]

    observed = _observed_calls(agent, events)

    assert observed[0]["runtime"]["call_id"] == "call-read-a"
    assert observed[1]["runtime"]["call_id"] == "call-read-b"


def test_events_preserve_reversed_runtime_call_ids_without_positional_rewrite(tmp_path) -> None:
    event_path = tmp_path / "events.jsonl"
    event_path.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {"event": "tool_finished", "call_id": "call-read-b", "tool_name": "read_file"},
                {"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"},
            ]
        ) + "\n",
        encoding="utf-8",
    )
    agent = SimpleNamespace(session_event_bus=SimpleNamespace(path=event_path))

    events = _events(agent)
    exchange_agent = SimpleNamespace(session={"model_exchange": {"events": [{"event": "assistant_tool_batch", "tool_calls": [{"call_id": "call-read-a", "name": "read_file", "arguments": {}}, {"call_id": "call-read-b", "name": "read_file", "arguments": {}}]}]}})
    observed = _observed_calls(exchange_agent, events)

    assert [event["call_id"] for event in events] == ["call-read-b", "call-read-a"]
    assert observed[0]["runtime"]["call_id"] == "call-read-a"
    assert observed[1]["runtime"]["call_id"] == "call-read-b"


@pytest.mark.parametrize(
    "events",
    [
        [{"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"}],
        [{"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"}, {"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"}],
        [{"event": "tool_finished", "call_id": "unknown", "tool_name": "read_file"}, {"event": "tool_finished", "call_id": "call-read-a", "tool_name": "read_file"}],
    ],
)
def test_observed_calls_fails_closed_for_non_bijective_runtime_call_ids(events) -> None:
    agent = SimpleNamespace(session={"model_exchange": {"events": [{"event": "assistant_tool_batch", "tool_calls": [{"call_id": "call-read-a", "name": "read_file", "arguments": {}}, {"call_id": "call-read-b", "name": "read_file", "arguments": {}}]}]}})

    with pytest.raises(ValueError, match="call_id"):
        _observed_calls(agent, events)


def test_fake_mode_rejects_live_inputs_and_nonzero_http_attempts(tmp_path) -> None:
    profile = {"profile_id": "live"}
    with pytest.raises(ValueError, match="fake_provider"):
        run_manifest(DEFAULT_MANIFEST, tmp_path, provider_factory=lambda _: None)
    with pytest.raises(ValueError, match="fake_provider"):
        run_manifest(DEFAULT_MANIFEST, tmp_path, profile=profile)
    with pytest.raises(SystemExit) as error:
        main(["--fake-provider", "--provider", "x", "--output-dir", str(tmp_path)])
    assert error.value.code == 2


def test_fake_artifact_rejects_nonzero_http_attempts(monkeypatch, tmp_path) -> None:
    def contaminated_factory(_scenario):
        provider = FakeProvider([])
        provider.http_attempts = 1
        return provider

    monkeypatch.setattr("scripts.run_v3_native_human_smoke_v3._fake_factory", contaminated_factory)
    with pytest.raises(ValueError, match="nonzero http_attempts"):
        run_manifest(DEFAULT_MANIFEST, tmp_path)
