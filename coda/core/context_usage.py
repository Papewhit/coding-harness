"""Context usage estimation for prompt transparency."""

from __future__ import annotations

import json
from typing import Any

from .request_context import provider_tool_definitions


DEFAULT_CONTEXT_WINDOW = 200_000
TOKEN_ESTIMATION_METHOD = "chars_div_4"


def estimate_tokens(chars: int) -> int:
    return max(0, (int(chars) + 3) // 4)


class ContextUsageAnalyzer:
    def __init__(self, agent: Any):
        self.agent = agent

    def analyze(self, rendered: dict[str, Any]) -> dict[str, Any]:
        tools_chars = self._tools_chars()
        sections = {}
        for name, section in rendered.items():
            key = "current_request" if name == "current_request" else name
            chars = int(section.rendered_chars)
            sections[key] = {
                "chars": chars,
                "tokens": estimate_tokens(chars),
            }
        sections["tools"] = {
            "chars": tools_chars,
            "tokens": estimate_tokens(tools_chars),
        }
        total = sum(section["tokens"] for section in sections.values())
        window = self._context_window()
        reserved = int(getattr(self.agent, "max_new_tokens", 0) or 0)
        return {
            "estimation_method": TOKEN_ESTIMATION_METHOD,
            "model": str(getattr(getattr(self.agent, "model_client", None), "model", "")),
            "context_window": window,
            "reserved_output_tokens": reserved,
            "total_estimated_tokens": total,
            "sections": sections,
            "free_tokens": window - total - reserved,
            "auto_compact_threshold": int(window * 0.8),
        }

    def _context_window(self) -> int:
        model = str(getattr(getattr(self.agent, "model_client", None), "model", "")).lower()
        if "1m" in model or "1000000" in model:
            return 1_000_000
        return DEFAULT_CONTEXT_WINDOW

    def _tools_chars(self) -> int:
        payload = [
            tool.to_dict()
            for tool in provider_tool_definitions(self.agent.available_tools())
        ]
        return len(
            json.dumps(
                payload,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
