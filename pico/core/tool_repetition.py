"""Repeated tool-call guardrails."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tools.base import RegisteredTool

FILE_MUTATION_TOOLS = {"write_file", "patch_file"}
WORKSPACE_PATH_TOOLS = {
    "list_files",
    "read_file",
    "search",
    *FILE_MUTATION_TOOLS,
}


def is_repeated_tool_call(
    history: list[dict[str, Any]],
    name: str,
    args: dict[str, Any],
    *,
    workspace_root: str | Path | None = None,
) -> bool:
    current_turn = _current_turn_history(history)
    tool_events = [
        (index, item)
        for index, item in enumerate(current_turn)
        if item.get("role") == "tool"
    ]
    fingerprint = _fingerprint_args(name, args, workspace_root)
    matches = [
        (index, item)
        for index, item in tool_events
        if item.get("name") == name
        and _fingerprint_args(name, item.get("args"), workspace_root) == fingerprint
    ]
    if name in FILE_MUTATION_TOOLS:
        if not matches:
            return False
        last_index, last_match = matches[-1]
        return not _prior_read_required_retry_is_now_informed(
            current_turn,
            last_index,
            last_match,
            workspace_root=workspace_root,
        )
    return len(matches) >= 2


def repeated_tool_call_metadata(tool: RegisteredTool) -> dict[str, Any]:
    return {
        "tool_status": "rejected",
        "tool_error_code": "repeated_identical_call",
        "security_event_type": "",
        "risk_level": "high" if tool.risky else "low",
        "read_only": tool.read_only,
        "affected_paths": [],
        "workspace_changed": False,
        "diff_summary": [],
    }


def _prior_read_required_retry_is_now_informed(
    current_turn: list[dict[str, Any]],
    last_index: int,
    last_match: dict[str, Any],
    *,
    workspace_root: str | Path | None,
) -> bool:
    if (
        last_match.get("tool_status") != "rejected"
        or last_match.get("tool_error_code") != "prior_read_required"
    ):
        return False
    path = str((last_match.get("args") or {}).get("path", ""))
    if not path:
        return False
    path_fingerprint = _fingerprint_path(path, workspace_root)
    for item in current_turn[last_index + 1 :]:
        if item.get("role") != "tool" or item.get("name") != "read_file":
            continue
        args = item.get("args") or {}
        if (
            _fingerprint_path(args.get("path"), workspace_root) == path_fingerprint
            and item.get("tool_status") == "ok"
            and not item.get("tool_error_code")
        ):
            return True
    return False


def _fingerprint_args(
    name: str,
    args: Any,
    workspace_root: str | Path | None,
) -> Any:
    if not isinstance(args, dict) or name not in WORKSPACE_PATH_TOOLS:
        return args
    fingerprint = dict(args)
    if "path" in fingerprint:
        fingerprint["path"] = _fingerprint_path(
            fingerprint["path"],
            workspace_root,
        )
    return fingerprint


def _fingerprint_path(
    raw_path: Any,
    workspace_root: str | Path | None,
) -> Any:
    if workspace_root is None or not isinstance(raw_path, (str, os.PathLike)):
        return raw_path
    root = Path(workspace_root).resolve()
    path = Path(raw_path)
    candidate = path if path.is_absolute() else root / path
    # This is identity normalization only. Validation remains the sole owner of
    # workspace containment, and permission/policy checks still run afterwards.
    return os.path.normcase(str(candidate.resolve()))


def _current_turn_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history = list(history)
    for index in range(len(history) - 1, -1, -1):
        if history[index].get("role") == "user":
            return history[index + 1 :]
    return history
