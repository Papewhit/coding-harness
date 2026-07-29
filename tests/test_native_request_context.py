from pathlib import Path

from pico import Pico, SessionStore, WorkspaceContext
from pico.core.context_manager import ContextManager
from pico.core.request_context import RequestMessage
from pico.providers.contracts import ProviderContinuation, ToolCallResult
from tests.native_fixtures import scripted_client


def build_agent(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return Pico(
        model_client=scripted_client(),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".pico" / "sessions"),
        approval_policy="auto",
    )


def test_request_context_separates_system_messages_tools_and_continuation(tmp_path):
    agent = build_agent(tmp_path)
    continuation = ProviderContinuation("profile-1", {"private": "opaque"})
    native_call = RequestMessage(
        "assistant",
        "calling read_file",
        kind="native_tool_call",
        provider_call_id="call-1",
        compactable=False,
    )

    context = agent.request_context(
        "preserve this exactly",
        public_messages=(native_call,),
        continuation=continuation,
    )

    assert context.current_request.content == "preserve this exactly"
    assert context.current_request.compactable is False
    assert context.continuation is continuation
    assert context.native_turn_status == "awaiting_result"
    assert context.tools
    assert all(tool.description not in context.system_text for tool in context.tools)
    assert "<" + "tool>" not in context.system_text
    assert "<" + "final>" not in context.system_text

    completed = agent.request_context(
        "preserve this exactly",
        public_messages=(native_call,),
        tool_results=(ToolCallResult("call-1", "done"),),
        continuation=continuation,
    )
    assert completed.native_turn_status == "terminal"


def test_current_request_is_never_clipped_under_extreme_pressure(tmp_path):
    agent = build_agent(tmp_path)
    request = "REQUEST-KEEP-VERBATIM-" + ("x" * 200)
    agent.context_manager = ContextManager(
        agent,
        total_budget=40,
        section_budgets={
            "prefix": 10,
            "memory": 10,
            "skills": 10,
            "relevant_memory": 10,
            "history": 10,
        },
    )

    context = agent.request_context(request)

    assert context.current_request.content == request
    assert context.metadata["current_request"]["rendered_chars"] == len(request)


def test_all_context_assets_have_canonical_surface_attribution(tmp_path):
    context = build_agent(tmp_path).request_context("inspect")
    records = {item["asset_id"]: item for item in context.metadata["asset_records"]}

    assert set(records) == {
        "skills",
        "todo",
        "plan",
        "checkpoint",
        "worker",
        "durable",
        "compact",
        "pointer",
    }
    assert {
        records[item]["surface"]
        for item in ("skills", "todo", "plan", "checkpoint", "durable")
    } == {"system_text"}
    assert {records[item]["surface"] for item in ("worker", "compact", "pointer")} == {
        "messages"
    }


def test_tool_usage_is_measured_outside_system_prompt(tmp_path):
    context = build_agent(tmp_path).request_context("inspect")
    usage = context.metadata["context_usage"]["sections"]

    assert usage["tools"]["chars"] > 0
    assert (
        usage["prefix"]["chars"]
        == context.metadata["sections"]["prefix"]["rendered_chars"]
    )


def test_compaction_keeps_an_unfinished_native_turn_intact(tmp_path):
    agent = build_agent(tmp_path)
    agent.record({"role": "user", "content": "old", "turn_id": "turn-1"})
    agent.record({"role": "assistant", "content": "old answer", "turn_id": "turn-1"})
    agent.record(
        {
            "role": "assistant",
            "content": "native call",
            "kind": "native_tool_call",
            "provider_call_id": "call-open",
            "native_turn_status": "awaiting_result",
            "turn_id": "turn-2",
        }
    )
    agent.record({"role": "user", "content": "latest", "turn_id": "turn-3"})

    agent.compact_history(keep_recent_turns=1)

    history = agent.session["history"]
    assert history[0]["kind"] == "compact_summary"
    assert any(item.get("provider_call_id") == "call-open" for item in history)
    assert any(item.get("turn_id") == "turn-3" for item in history)


def test_formal_runtime_source_has_no_text_envelope_instructions():
    source = (
        Path(__file__).resolve().parents[1] / "pico" / "core" / "runtime.py"
    ).read_text(encoding="utf-8")
    assert "<" + "tool>" not in source
    assert "<" + "final>" not in source
