"""Tool usage policy checks above raw permission gates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..features import memory as memorylib

if TYPE_CHECKING:
    from .runtime import Coda
    from ..tools.base import RegisteredTool

# 只在"主命令位置"禁这些工具——命令开头，或被 ; && || 串联起的开头。
# 管道 | 之后允许：模型常把 `... | tail -5` 用来截断输出，不是在搜索 workspace。
SHELL_SEARCH_RE = re.compile(
    r"(?:^|;|&&|\|\|)\s*(?:cat|less|head|tail|grep|rg|find|ls)(?:\s|$)"
)


@dataclass(frozen=True)
class ToolPolicyDecision:
    decision: str
    reason: str
    message: str = ""

    @classmethod
    def allow(cls, reason="policy_ok"):
        return cls("allow", reason)

    @classmethod
    def deny(cls, reason, message):
        return cls("deny", reason, message)

    @property
    def allowed(self):
        return self.decision == "allow"


class ToolPolicyChecker:
    def __init__(self, runtime: Coda):
        self.runtime = runtime

    def check(self, tool: RegisteredTool, args: dict[str, Any] | None) -> ToolPolicyDecision:
        args = args or {}
        if self.runtime.runtime_mode == "plan":
            return ToolPolicyDecision.allow("plan_mode")
        if tool.name == "patch_file" and not self._has_fresh_read(args.get("path", "")):
            return self._prior_read_required(tool.name, args.get("path", ""))
        if tool.name == "write_file":
            path = self.runtime.path(args.get("path", ""))
            if path.exists() and path.is_file() and not self._has_fresh_read(args.get("path", "")):
                return self._prior_read_required(tool.name, args.get("path", ""))
        if tool.name == "run_shell":
            command = str(args.get("command", "")).strip()
            if SHELL_SEARCH_RE.search(command):
                return ToolPolicyDecision.deny(
                    "shell_search_should_use_tool",
                    "error: run_shell is not for ordinary workspace search/read; use search, read_file, or list_files first",
                )
        return ToolPolicyDecision.allow()

    def _has_fresh_read(self, path: str) -> bool:
        canonical = self.runtime.memory.canonical_path(path)
        summary = self.runtime.memory.to_dict().get("file_summaries", {}).get(canonical, {})
        # TODO 编辑文件需要定位，summary 无法承载定位信息，但错误根源应该不在这里
        if summary and summary.get("freshness") == memorylib.file_freshness(canonical, self.runtime.root):
            return True
        freshness = self.runtime.self_authored_file_freshness.get(canonical)
        return bool(freshness and freshness == memorylib.file_freshness(canonical, self.runtime.root))

    @staticmethod
    def _prior_read_required(tool_name: str, path: str) -> ToolPolicyDecision:
        return ToolPolicyDecision.deny(
            "prior_read_required",
            f"error: {tool_name} requires a fresh read_file of {path} before modifying it",
        )
