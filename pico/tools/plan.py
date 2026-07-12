"""Runtime mode tool definitions."""

from __future__ import annotations

from typing import Any

from ..core.runtime import Pico

PLAN_TOOL_SPECS = {
    "enter_plan_mode": {
        "schema": {"topic": "str", "path": "str?"},
        "risky": False,
        "description": "Enter plan mode for a named planning topic.",
    },
    "exit_plan_mode": {
        "schema": {},
        "risky": False,
        "description": "Exit plan mode and return to default runtime mode.",
    },
}

PLAN_TOOL_EXAMPLES = {
    "enter_plan_mode": '<tool>{"name":"enter_plan_mode","args":{"topic":"Refactor auth"}}</tool>',
    "exit_plan_mode": '<tool>{"name":"exit_plan_mode","args":{}}</tool>',
}



def tool_enter_plan_mode(agent: Pico, args: dict[str, Any]) -> str:
    path = agent.enter_plan_mode(args["topic"], path=args.get("path"))
    return f"mode: plan\nplan path: {path}"


def tool_exit_plan_mode(agent: Pico, args: dict[str, Any]) -> str:
    agent.exit_plan_mode()
    return "mode: default"
