from __future__ import annotations

from copy import deepcopy

import pytest

from pico import Pico, SessionStore, WorkspaceContext
from pico.core.tool_call_batch import NativeModelProtocolError
from pico.providers.contracts import (
    ModelRequest,
    ToolChoiceMode,
)
from pico.testing import (
    ScriptedNativeModelClient,
    native_continuation,
    native_final_response,
    native_multi_tool_call_response,
    native_protocol_error_response,
    native_tool_call,
    native_tool_call_response,
)


def build_agent(tmp_path, responses, **kwargs):
    (tmp_path / "README.md").write_text("hello world\n", encoding="utf-8")
    return Pico(
        model_client=ScriptedNativeModelClient(responses),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".pico" / "sessions"),
        approval_policy=kwargs.pop("approval_policy", "auto"),
        **kwargs,
    )


def request():
    return ModelRequest(prompt="inspect the workspace", max_output_tokens=128)


def persisted_snapshots():
    snapshots = []

    def persist(snapshot):
        snapshots.append(deepcopy(snapshot))

    return snapshots, persist


def test_native_batch_is_persisted_before_execution_and_results_are_complete(tmp_path):
    continuation = native_continuation({"response_id": "response-1"})
    responses = [
        native_multi_tool_call_response(
            native_tool_call(
                "call-read", "read_file", {"path": "README.md", "start": 1, "end": 1}
            ),
            native_tool_call("call-missing", "missing_tool", {}),
            text="I will inspect both inputs.",
            continuation=continuation,
        ),
        native_final_response("Inspection complete."),
    ]
    agent = build_agent(tmp_path, responses)
    snapshots, persist = persisted_snapshots()
    original_run_tool = agent.run_tool
    statuses_seen_before_execution = []

    def guarded_run_tool(name, args):
        statuses_seen_before_execution.append(snapshots[-1]["calls"][0]["status"])
        return original_run_tool(name, args)

    agent.run_tool = guarded_run_tool
    agent.parse = lambda _raw: pytest.fail("legacy model-output parser was called")

    result = agent.engine.run_native_tool_loop(request(), persist_hook=persist)

    assert result.final_text == "Inspection complete."
    assert result.interim_text == ("I will inspect both inputs.",)
    assert statuses_seen_before_execution == ["executing", "completed"]
    assert [item["status"] for item in snapshots[0]["calls"]] == [
        "received",
        "received",
    ]
    assert [item["status"] for item in snapshots[1]["calls"]] == [
        "persisted",
        "persisted",
    ]
    followup = agent.model_client.requests[1]
    assert [tool_result.call_id for tool_result in followup.tool_results] == [
        "call-read",
        "call-missing",
    ]
    assert [tool_result.is_error for tool_result in followup.tool_results] == [
        False,
        True,
    ]
    assert followup.tool_results[1].output["error"]["code"] == "unknown_tool"
    assert followup.continuation == continuation
    assert result.batches[0].complete


@pytest.mark.parametrize(
    ("call", "approval_policy", "expected_code"),
    [
        (native_tool_call("bad-args", "read_file", {}), "auto", "invalid_arguments"),
        (
            native_tool_call(
                "denied", "run_shell", {"command": "echo hi", "timeout": 20}
            ),
            "never",
            "approval_denied",
        ),
        (
            native_tool_call(
                "policy", "run_shell", {"command": "grep -R hello .", "timeout": 20}
            ),
            "auto",
            "shell_search_should_use_tool",
        ),
    ],
)
def test_native_rejections_are_matching_error_results(
    tmp_path, call, approval_policy, expected_code
):
    agent = build_agent(
        tmp_path,
        [native_multi_tool_call_response(call), native_final_response("handled")],
        approval_policy=approval_policy,
    )
    _, persist = persisted_snapshots()

    result = agent.engine.run_native_tool_loop(request(), persist_hook=persist)

    tool_result = agent.model_client.requests[1].tool_results[0]
    assert tool_result.call_id == call.call_id
    assert tool_result.is_error is True
    assert tool_result.output["error"]["code"] == expected_code
    assert result.batches[0].calls[0].status.value == "rejected"


def test_batch_budget_rejection_still_returns_one_result_per_call(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            native_multi_tool_call_response(
                native_tool_call("first", "read_file", {"path": "README.md"}),
                native_tool_call("second", "read_file", {"path": "README.md"}),
            ),
            native_final_response("One call completed; continue next turn."),
        ],
        max_steps=1,
    )
    _, persist = persisted_snapshots()

    result = agent.engine.run_native_tool_loop(request(), persist_hook=persist)

    summary_request = agent.model_client.requests[1]
    assert summary_request.tool_choice.mode is ToolChoiceMode.NONE
    assert [item.call_id for item in summary_request.tool_results] == [
        "first",
        "second",
    ]
    assert (
        summary_request.tool_results[1].output["error"]["code"] == "step_limit_exceeded"
    )
    assert result.step_limit_reached is True


def test_tool_exception_becomes_uncertain_matching_result(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            native_tool_call_response("boom", "read_file", {"path": "README.md"}),
            native_final_response("noted"),
        ],
    )
    agent.run_tool = lambda _name, _args: (_ for _ in ()).throw(RuntimeError("boom"))
    _, persist = persisted_snapshots()

    result = agent.engine.run_native_tool_loop(request(), persist_hook=persist)

    state = result.batches[0].calls[0]
    assert state.status.value == "uncertain"
    assert state.result.call_id == "boom"
    assert state.result.is_error is True


def test_protocol_error_response_is_not_sent_to_legacy_parser(tmp_path):
    agent = build_agent(
        tmp_path, [native_protocol_error_response("bad provider payload")]
    )
    agent.parse = lambda _raw: pytest.fail("legacy model-output parser was called")
    _, persist = persisted_snapshots()

    with pytest.raises(NativeModelProtocolError, match="bad provider payload"):
        agent.engine.run_native_tool_loop(request(), persist_hook=persist)


def test_persist_failure_prevents_first_tool_execution(tmp_path):
    agent = build_agent(
        tmp_path,
        [native_tool_call_response("never", "read_file", {"path": "README.md"})],
    )
    executed = []
    agent.run_tool = lambda name, args: executed.append((name, args))

    with pytest.raises(OSError, match="checkpoint unavailable"):
        agent.engine.run_native_tool_loop(
            request(),
            persist_hook=lambda _snapshot: (_ for _ in ()).throw(
                OSError("checkpoint unavailable")
            ),
        )

    assert executed == []


def test_summary_tool_call_is_a_protocol_error(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            native_tool_call_response("one", "read_file", {"path": "README.md"}),
            native_tool_call_response("forbidden", "read_file", {"path": "README.md"}),
        ],
        max_steps=1,
    )
    snapshots, persist = persisted_snapshots()

    with pytest.raises(NativeModelProtocolError, match="tool_choice was none"):
        agent.engine.run_native_tool_loop(request(), persist_hook=persist)

    rejected = snapshots[-1]["calls"][0]
    assert rejected["status"] == "rejected"
    assert rejected["result"]["call_id"] == "forbidden"
    assert rejected["result"]["is_error"] is True
