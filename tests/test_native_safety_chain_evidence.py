from __future__ import annotations

import json
from pathlib import Path

import pytest

from coda import Coda, SessionStore, WorkspaceContext
from coda.evaluation.native_provider_live import (
    NATIVE_SAFETY_EVIDENCE_VERSION,
    NATIVE_SAFETY_STAGES,
    bind_native_safety_evidence,
)
from tests.native_fixtures import lock_scripted_provider_profile, scripted_client


def _agent(tmp_path: Path, *, approval_policy: str = "auto") -> Coda:
    (tmp_path / "README.md").write_text("evidence\n", encoding="utf-8")
    return lock_scripted_provider_profile(
        Coda(
            model_client=scripted_client(),
            workspace=WorkspaceContext.build(tmp_path),
            session_store=SessionStore(tmp_path / ".coda" / "sessions"),
            approval_policy=approval_policy,
        )
    )


def _arm_call(
    agent: Coda,
    *,
    call_id: str,
    name: str,
    arguments: dict,
    case_id: str = "NP-evidence",
    repetition: int = 2,
) -> None:
    agent.session["native_runtime"] = {
        "active_batch": {
            "calls": [
                {
                    "call": {
                        "call_id": call_id,
                        "name": name,
                        "arguments": arguments,
                    },
                    "status": "executing",
                }
            ]
        }
    }
    bind_native_safety_evidence(
        agent,
        case_id=case_id,
        repetition=repetition,
    )


def _evidence(agent: Coda) -> list[dict]:
    return [
        record
        for line in agent.session_event_bus.path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
        and (record := json.loads(line)).get("event")
        == "native_safety_stage"
    ]


@pytest.mark.parametrize(
    ("name", "arguments", "approval_policy", "history", "expected"),
    [
        (
            "read_file",
            {"path": "README.md"},
            "auto",
            [],
            [
                ("validate", "passed"),
                ("repetition", "passed"),
                ("permission", "passed"),
                ("policy", "passed"),
                ("execute", "completed"),
            ],
        ),
        (
            "write_file",
            {},
            "auto",
            [],
            [("validate", "rejected")],
        ),
        (
            "write_file",
            {"path": "new.txt", "content": "x"},
            "auto",
            [
                {
                    "role": "tool",
                    "name": "write_file",
                    "args": {"path": "new.txt", "content": "x"},
                    "tool_status": "ok",
                }
            ],
            [("validate", "passed"), ("repetition", "rejected")],
        ),
        (
            "run_shell",
            {"command": "echo denied", "timeout": 20},
            "never",
            [],
            [
                ("validate", "passed"),
                ("repetition", "passed"),
                ("permission", "rejected"),
            ],
        ),
        (
            "patch_file",
            {
                "path": "README.md",
                "old_text": "evidence",
                "new_text": "changed",
            },
            "auto",
            [],
            [
                ("validate", "passed"),
                ("repetition", "passed"),
                ("permission", "passed"),
                ("policy", "rejected"),
            ],
        ),
    ],
)
def test_production_executor_emits_ordered_native_safety_evidence(
    tmp_path: Path,
    name: str,
    arguments: dict,
    approval_policy: str,
    history: list[dict],
    expected: list[tuple[str, str]],
) -> None:
    agent = _agent(tmp_path, approval_policy=approval_policy)
    agent.session["history"].extend(history)
    _arm_call(
        agent,
        call_id="provider-call-42",
        name=name,
        arguments=arguments,
    )

    agent.run_tool(name, arguments)

    evidence = _evidence(agent)
    assert [(item["stage"], item["outcome"]) for item in evidence] == expected
    assert [item["stage_index"] for item in evidence] == list(
        range(1, len(expected) + 1)
    )
    assert [item["sequence"] for item in evidence] == list(
        range(1, len(expected) + 1)
    )
    assert {
        (
            item["schema_version"],
            item["case_id"],
            item["repetition"],
            item["call_id"],
            item["tool_name"],
        )
        for item in evidence
    } == {
        (
            NATIVE_SAFETY_EVIDENCE_VERSION,
            "NP-evidence",
            2,
            "provider-call-42",
            name,
        )
    }
    assert [item["stage"] for item in evidence] == list(
        NATIVE_SAFETY_STAGES[: len(evidence)]
    )
