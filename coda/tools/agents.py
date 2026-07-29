"""Coordinator subagent tool definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.runtime import Coda
from ..core.worker_manager import dumps_payload

AGENT_TOOL_NAMES = {"agent", "send_message", "task_stop"}

AGENT_TOOL_SPECS = {
    "agent": {
        "schema": {
            "description": "str",
            "prompt": "str",
            "subagent_type": "str='worker'",
            "write_scope": "list[str]=[]",
        },
        "risky": False,
        "description": "Launch a bounded worker or read-only Explore subagent.",
    },
    "send_message": {
        "schema": {"to": "str", "message": "str"},
        "risky": False,
        "description": "Continue an existing idle worker by id.",
    },
    "task_stop": {
        "schema": {"task_id": "str"},
        "risky": False,
        "description": "Stop a worker by id.",
    },
}

AGENT_TOOL_EXAMPLES = {
    "agent": {
        "description": "Inspect auth",
        "prompt": "Find auth entry points",
        "subagent_type": "Explore",
    },
    "send_message": {"to": "agent_1", "message": "Now patch the bug in src/auth.py"},
    "task_stop": {"task_id": "agent_1"},
}


def validate_agent_runtime(agent: Coda, name: str, args: dict[str, Any]) -> None:
    """Runtime-aware checks that can't be expressed in the Pydantic schema."""
    if name == "agent":
        subagent_type = str(args.get("subagent_type", "worker")).strip()
        if agent.runtime_mode == "plan" and subagent_type != "Explore":
            raise ValueError("plan mode only allows Explore agents")


def tool_agent(agent: Coda, args: dict[str, Any]) -> str:
    return dumps_payload(
        agent.worker_manager.spawn(
            args["description"],
            args["prompt"],
            subagent_type=args.get("subagent_type", "worker"),
            write_scope=args.get("write_scope", []),
        )
    )


def tool_send_message(agent: Coda, args: dict[str, Any]) -> str:
    return dumps_payload(
        agent.worker_manager.continue_task(args["to"], args["message"])
    )


def tool_task_stop(agent: Coda, args: dict[str, Any]) -> str:
    return dumps_payload(agent.worker_manager.stop_task(args["task_id"]))
