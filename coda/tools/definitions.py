"""Canonical metadata and parameter models for Coda's registered tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .schemas import (
    AgentArgs,
    AskUserArgs,
    EnterPlanModeArgs,
    ExitPlanModeArgs,
    ListFilesArgs,
    PatchFileArgs,
    ReadFileArgs,
    RunShellArgs,
    SearchArgs,
    SendMessageArgs,
    TaskStopArgs,
    TodoAddArgs,
    TodoListArgs,
    TodoUpdateArgs,
    WriteFileArgs,
    human_readable_schema,
    normalized_json_schema,
    schema_fingerprint,
)


@dataclass(frozen=True)
class ToolDefinition:
    """Static tool contract shared by validation, prompts, and providers."""

    name: str
    args_model: type[BaseModel]
    description: str
    risky: bool

    @property
    def schema(self) -> dict[str, str]:
        """Legacy human-readable schema used by the current prompt builder."""

        return human_readable_schema(self.args_model)

    @property
    def input_schema(self) -> dict[str, Any]:
        """Provider-neutral JSON Schema derived from ``args_model``."""

        return normalized_json_schema(self.args_model)

    @property
    def schema_fingerprint(self) -> str:
        return schema_fingerprint(self.args_model)


TOOL_DEFINITIONS = {
    definition.name: definition
    for definition in (
        ToolDefinition("list_files", ListFilesArgs, "List files in the workspace.", False),
        ToolDefinition("read_file", ReadFileArgs, "Read a UTF-8 file by line range.", False),
        ToolDefinition(
            "search",
            SearchArgs,
            "Search the workspace with rg or a simple fallback.",
            False,
        ),
        ToolDefinition("run_shell", RunShellArgs, "Run a shell command in the repo root.", True),
        ToolDefinition("write_file", WriteFileArgs, "Write a text file.", True),
        ToolDefinition(
            "patch_file",
            PatchFileArgs,
            "Replace one exact text block in a file.",
            True,
        ),
        ToolDefinition(
            "todo_add",
            TodoAddArgs,
            "Add an item to the session task ledger.",
            False,
        ),
        ToolDefinition(
            "todo_update",
            TodoUpdateArgs,
            "Update an item in the session task ledger.",
            False,
        ),
        ToolDefinition(
            "todo_list",
            TodoListArgs,
            "List the session task ledger.",
            False,
        ),
        ToolDefinition(
            "agent",
            AgentArgs,
            "Launch a bounded worker or read-only Explore subagent.",
            False,
        ),
        ToolDefinition(
            "send_message",
            SendMessageArgs,
            "Continue an existing idle worker by id.",
            False,
        ),
        ToolDefinition("task_stop", TaskStopArgs, "Stop a worker by id.", False),
        ToolDefinition(
            "enter_plan_mode",
            EnterPlanModeArgs,
            "Enter plan mode for a named planning topic.",
            False,
        ),
        ToolDefinition(
            "exit_plan_mode",
            ExitPlanModeArgs,
            "Exit plan mode and return to default runtime mode.",
            False,
        ),
        ToolDefinition(
            "ask_user",
            AskUserArgs,
            "Ask the interactive user a real blocking clarification question.",
            False,
        ),
    )
}
