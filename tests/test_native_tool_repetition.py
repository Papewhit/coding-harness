"""Structured native tool repetition policy tests."""

from types import SimpleNamespace

import pytest

from coda.core.runtime import Coda
from coda.core.session_lifecycle import NativeSessionRecorder
from coda.core.tool_repetition import is_repeated_tool_call
from coda.providers.contracts import ToolCall


PATCH_ARGS = {
    "path": "README.md",
    "old_text": "world",
    "new_text": "coda",
}


def _tool_event(
    name: str,
    args: dict[str, object],
    *,
    status: str,
    error_code: str = "",
    content: str = "ignored display text",
) -> dict[str, object]:
    return {
        "role": "tool",
        "name": name,
        "args": args,
        "content": content,
        "tool_status": status,
        "tool_error_code": error_code,
    }


def test_prior_read_required_retry_is_unlocked_by_successful_same_path_read() -> None:
    history = [
        {"role": "user", "content": "update the file"},
        _tool_event(
            "patch_file",
            PATCH_ARGS,
            status="rejected",
            error_code="prior_read_required",
            content="display text deliberately has no error prefix",
        ),
        _tool_event(
            "read_file",
            {"path": "README.md"},
            status="ok",
            content="error: valid file content is not internal status",
        ),
    ]

    assert not is_repeated_tool_call(history, "patch_file", PATCH_ARGS)


def test_workspace_path_aliases_share_repetition_fingerprint(tmp_path) -> None:
    target = tmp_path / "docs" / "guide.md"
    relative_args = {**PATCH_ARGS, "path": "docs/guide.md"}
    dotted_args = {**PATCH_ARGS, "path": "docs/./guide.md"}
    absolute_args = {**PATCH_ARGS, "path": str(target)}
    history = [
        _tool_event("patch_file", relative_args, status="ok"),
    ]

    assert is_repeated_tool_call(
        history,
        "patch_file",
        dotted_args,
        workspace_root=tmp_path,
    )
    assert is_repeated_tool_call(
        history,
        "patch_file",
        absolute_args,
        workspace_root=tmp_path,
    )


def test_read_path_aliases_count_toward_same_repetition_limit(tmp_path) -> None:
    target = tmp_path / "docs" / "guide.md"
    history = [
        _tool_event("read_file", {"path": "docs/guide.md"}, status="ok"),
        _tool_event("read_file", {"path": "docs/./guide.md"}, status="ok"),
    ]

    assert is_repeated_tool_call(
        history,
        "read_file",
        {"path": str(target)},
        workspace_root=tmp_path,
    )


def test_runtime_anchors_repetition_fingerprint_to_workspace_root(tmp_path) -> None:
    history = [
        _tool_event(
            "patch_file",
            {**PATCH_ARGS, "path": "docs/guide.md"},
            status="ok",
        ),
    ]
    agent = SimpleNamespace(
        root=tmp_path,
        session={"history": history},
    )

    assert Coda.repeated_tool_call(
        agent,
        "patch_file",
        {**PATCH_ARGS, "path": str(tmp_path / "docs" / "guide.md")},
    )


def test_distinct_workspace_paths_do_not_share_repetition_fingerprint(
    tmp_path,
) -> None:
    history = [
        _tool_event(
            "patch_file",
            {**PATCH_ARGS, "path": "docs/first.md"},
            status="ok",
        ),
    ]

    assert not is_repeated_tool_call(
        history,
        "patch_file",
        {**PATCH_ARGS, "path": str(tmp_path / "docs" / "second.md")},
        workspace_root=tmp_path,
    )


def test_retry_after_read_accepts_same_path_alias_with_structured_metadata(
    tmp_path,
) -> None:
    target = tmp_path / "docs" / "guide.md"
    history = [
        _tool_event(
            "patch_file",
            {**PATCH_ARGS, "path": str(target)},
            status="rejected",
            error_code="prior_read_required",
        ),
        _tool_event(
            "read_file",
            {"path": "docs/./guide.md"},
            status="ok",
        ),
    ]

    assert not is_repeated_tool_call(
        history,
        "patch_file",
        {**PATCH_ARGS, "path": "docs/guide.md"},
        workspace_root=tmp_path,
    )


@pytest.mark.parametrize(
    ("mutation_status", "mutation_error", "read_path", "read_status", "read_error"),
    [
        ("rejected", "prior_read_required", "README.md", "error", "read_failed"),
        ("rejected", "prior_read_required", "OTHER.md", "ok", ""),
        ("rejected", "permission_denied", "README.md", "ok", ""),
        ("ok", "", "README.md", "ok", ""),
        ("uncertain", "execution_uncertain", "README.md", "ok", ""),
    ],
)
def test_mutation_retry_stays_blocked_without_qualifying_read(
    mutation_status: str,
    mutation_error: str,
    read_path: str,
    read_status: str,
    read_error: str,
) -> None:
    history = [
        _tool_event(
            "patch_file",
            PATCH_ARGS,
            status=mutation_status,
            error_code=mutation_error,
            content="error: display text must not control policy",
        ),
        _tool_event(
            "read_file",
            {"path": read_path},
            status=read_status,
            error_code=read_error,
            content="ordinary display text",
        ),
    ]

    assert is_repeated_tool_call(history, "patch_file", PATCH_ARGS)


def test_rendered_text_cannot_substitute_for_structured_metadata() -> None:
    history = [
        {
            "role": "tool",
            "name": "patch_file",
            "args": PATCH_ARGS,
            "content": "error: prior_read_required",
        },
        {
            "role": "tool",
            "name": "read_file",
            "args": {"path": "README.md"},
            "content": "file contents",
        },
    ]

    assert is_repeated_tool_call(history, "patch_file", PATCH_ARGS)


def test_native_recorder_persists_structured_status_in_internal_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history: list[dict[str, object]] = []
    monkeypatch.setattr(
        "coda.core.session_lifecycle.ModelExchangeEvent.tool_result",
        lambda **kwargs: {},
    )
    recorder = object.__new__(NativeSessionRecorder)
    recorder.journal = SimpleNamespace(append=lambda event: None)
    recorder.profile = {}
    recorder.finished_calls = set()
    recorder.events = []
    recorder.task_state = SimpleNamespace(run_id="run-1")
    recorder.agent = SimpleNamespace(
        record=history.append,
        session_event_bus=SimpleNamespace(emit=lambda name, payload: None),
        emit_trace=lambda task_state, event, payload: None,
    )
    call = ToolCall("call-1", "patch_file", PATCH_ARGS)

    recorder._finished(
        "exchange-1",
        call,
        {
            "status": "rejected",
            "result": {
                "call_id": "call-1",
                "output": "arbitrary rendered output",
                "is_error": True,
            },
            "result_metadata": {
                "tool_status": "rejected",
                "tool_error_code": "prior_read_required",
            },
        },
    )

    assert history[0]["tool_status"] == "rejected"
    assert history[0]["tool_error_code"] == "prior_read_required"
