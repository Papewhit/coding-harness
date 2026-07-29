"""Pydantic argument models for all registered tools.

Each model is the single source of truth for a tool's argument structure,
defaults, and pure value-level constraints (type, range, non-empty).
Workspace-aware checks (path safety, file existence, patch uniqueness) still
live in validate_tool() since they require access to the agent.
"""

from __future__ import annotations

import json
import types
from hashlib import sha256
from typing import Any, List, Optional, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


class ToolArgs(BaseModel):
    """Strict base model for arguments crossing the tool execution boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ListFilesArgs(ToolArgs):
    path: str = "."


class ReadFileArgs(ToolArgs):
    path: str
    start: int = 1
    end: int = 200

    @field_validator("start")
    @classmethod
    def start_ge_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("start must be >= 1")
        return v

    @model_validator(mode="after")
    def end_ge_start(self) -> "ReadFileArgs":
        if self.end < self.start:
            raise ValueError("invalid line range")
        return self


class SearchArgs(ToolArgs):
    pattern: str
    path: str = "."

    @field_validator("pattern")
    @classmethod
    def pattern_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("pattern must not be empty")
        return v


class RunShellArgs(ToolArgs):
    command: str
    timeout: int = 20

    @field_validator("command")
    @classmethod
    def command_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("command must not be empty")
        return v

    @field_validator("timeout")
    @classmethod
    def timeout_in_range(cls, v: int) -> int:
        if v < 1 or v > 120:
            raise ValueError("timeout must be in [1, 120]")
        return v


class WriteFileArgs(ToolArgs):
    path: str
    content: str


class PatchFileArgs(ToolArgs):
    path: str
    old_text: str
    new_text: str

    @field_validator("old_text")
    @classmethod
    def old_text_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("old_text must not be empty")
        return v


class TodoAddArgs(ToolArgs):
    content: str
    status: str = "pending"
    priority: str = "normal"
    note: str = ""

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class TodoUpdateArgs(ToolArgs):
    todo_id: str
    status: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None

    @field_validator("todo_id")
    @classmethod
    def todo_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("todo_id must not be empty")
        return v


class TodoListArgs(ToolArgs):
    pass


class AgentArgs(ToolArgs):
    description: str
    prompt: str
    subagent_type: str = "worker"
    write_scope: Union[List[str], str, None] = None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description must not be empty")
        return v

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be empty")
        return v

    @field_validator("subagent_type")
    @classmethod
    def valid_subagent_type(cls, v: str) -> str:
        if v not in {"worker", "Explore"}:
            raise ValueError("subagent_type must be worker or Explore")
        return v

    @field_validator("write_scope", mode="before")
    @classmethod
    def valid_write_scope(cls, v: object) -> object:
        if v is not None and not isinstance(v, (list, str)):
            raise ValueError("write_scope must be a list of workspace paths")
        return v


class SendMessageArgs(ToolArgs):
    to: str
    message: str

    @field_validator("to")
    @classmethod
    def to_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("to must not be empty")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        return v


class TaskStopArgs(ToolArgs):
    task_id: str

    @field_validator("task_id")
    @classmethod
    def task_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task_id must not be empty")
        return v


class EnterPlanModeArgs(ToolArgs):
    topic: str
    path: Optional[str] = None

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be empty")
        return v


class ExitPlanModeArgs(ToolArgs):
    pass


class AskUserArgs(ToolArgs):
    question: str
    choices: Optional[List[str]] = None

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty")
        return v

    @field_validator("choices", mode="before")
    @classmethod
    def choices_must_be_list(cls, v: object) -> object:
        if v is not None and not isinstance(v, list):
            raise ValueError("choices must be a list")
        return v


def first_error_message(exc: "ValidationError") -> str:  # type: ignore[name-defined]
    """Extract a clean single-line message from a Pydantic ValidationError."""
    errors = exc.errors(include_url=False)
    if not errors:
        return str(exc)
    err = errors[0]
    msg = str(err.get("msg", "")).removeprefix("Value error, ")
    # For missing required fields, reproduce the old KeyError repr: "'fieldname'"
    # so callers that checked for that format continue to work.
    if err.get("type") == "missing":
        loc = err.get("loc", ())
        field = loc[-1] if loc else ""
        if field:
            return f"'{field}'"
    return msg


def normalized_json_schema(args_model: type[BaseModel]) -> dict[str, Any]:
    """Return a deterministic, provider-neutral schema for a tool model.

    Pydantic remains the local validation authority.  The exported schema is
    deliberately explicit about object boundaries and omits generated titles,
    which otherwise make equivalent schemas depend on Python class names.
    """

    schema = _normalize_schema_node(args_model.model_json_schema(mode="validation"))
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise TypeError("tool argument models must export an object JSON Schema")
    return schema


def human_readable_schema(args_model: type[BaseModel]) -> dict[str, str]:
    """Render the compact field notation consumed by the legacy prompt path."""

    rendered: dict[str, str] = {}
    for name, field in args_model.model_fields.items():
        annotation = _format_annotation(field.annotation)
        if field.is_required():
            rendered[name] = annotation
        elif field.default is None and _annotation_allows_none(field.annotation):
            rendered[name] = f"{annotation}?"
        else:
            rendered[name] = f"{annotation}={field.default!r}"
    return rendered


def schema_fingerprint(args_model: type[BaseModel]) -> str:
    """Hash the canonical provider-neutral schema for checkpoint signatures."""

    payload = json.dumps(
        normalized_json_schema(args_model),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _normalize_schema_node(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {
            key: _normalize_schema_node(item)
            for key, item in sorted(value.items())
            if key != "title"
        }
        if normalized.get("type") == "object" or "properties" in normalized:
            normalized.setdefault("properties", {})
            normalized.setdefault("required", [])
            normalized.setdefault("additionalProperties", False)
            normalized["required"] = sorted(normalized["required"])
        return normalized
    if isinstance(value, list):
        return [_normalize_schema_node(item) for item in value]
    return value


def _format_annotation(annotation: Any) -> str:
    origin = get_origin(annotation)
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if origin in (Union, types.UnionType):
        rendered = " | ".join(_format_annotation(arg) for arg in args)
        return f"({rendered})" if len(args) > 1 else rendered
    if origin is list:
        item = _format_annotation(args[0]) if args else "any"
        return f"list[{item}]"
    if origin is dict:
        key = _format_annotation(args[0]) if args else "any"
        item = _format_annotation(args[1]) if len(args) > 1 else "any"
        return f"dict[{key}, {item}]"
    if annotation is Any:
        return "any"
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


def _annotation_allows_none(annotation: Any) -> bool:
    return type(None) in get_args(annotation)
