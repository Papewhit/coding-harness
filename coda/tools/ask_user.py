"""User clarification tool definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.runtime import Coda

ASK_USER_TOOL_SPECS = {
    "ask_user": {
        "schema": {"question": "str", "choices": "list[str]=[]"},
        "risky": False,
        "description": "Ask the interactive user a real blocking clarification question.",
    },
}

ASK_USER_TOOL_EXAMPLES = {
    "ask_user": {
        "question": "Which target should I deploy?",
        "choices": ["staging", "production"],
    },
}


def tool_ask_user(agent: Coda, args: dict[str, Any]) -> str:
    return agent.ask_user(str(args["question"]), choices=args.get("choices", []) or [])
