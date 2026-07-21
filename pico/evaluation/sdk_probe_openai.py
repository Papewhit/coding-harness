"""OpenAI Responses SDK plugin for the provider-neutral viability probe.

The SDK is imported lazily so it remains a temporary ``uv run --with openai``
probe dependency.  This module only sends Responses API operations; it never
executes a function call or delegates tool execution to an SDK runner.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pico.evaluation.sdk_probe import (
    HttpAttempt,
    ParsedResponse,
    ProbeCase,
    ProbeProfile,
    RawResponse,
    ToolCall,
    ToolResult,
    TransportExchange,
)


OPENAI_RESPONSES_DIALECT = "openai-responses"


class OpenAIResponsesDialect:
    """Map probe contracts to native OpenAI Responses request items."""

    name = OPENAI_RESPONSES_DIALECT

    def __init__(self) -> None:
        self._reasoning_items: tuple[Mapping[str, Any], ...] = ()

    def build_request(
        self,
        case: ProbeCase,
        profile: ProbeProfile,
        tool_results: Sequence[ToolResult],
    ) -> Mapping[str, Any]:
        if not tool_results:
            self._reasoning_items = ()

        request: dict[str, Any] = {
            "model": profile.model,
            "input": self._input(case, tool_results),
            "stream": False,
            "store": False,
            "parallel_tool_calls": False,
        }
        if case.tool is not None:
            request["tools"] = [_function_tool(case.tool)]
            request["tool_choice"] = "none" if tool_results else "required"
        if profile.capabilities.get("opaque_continuation_support") is True:
            request["include"] = ["reasoning.encrypted_content"]
        return request

    def parse_response(self, response: RawResponse) -> ParsedResponse:
        payload = _as_mapping(response.payload)
        output = payload.get("output", [])
        if not isinstance(output, list):
            raise ValueError("OpenAI Responses output must be a list")

        final_parts: list[str] = []
        calls: list[ToolCall] = []
        reasoning_items: list[Mapping[str, Any]] = []
        unknown_types: list[str] = []
        for raw_item in output:
            item = _as_mapping(raw_item)
            item_type = item.get("type")
            if item_type == "function_call":
                calls.append(
                    ToolCall(
                        call_id=_required_string(item, "call_id"),
                        name=_required_string(item, "name"),
                        arguments=item.get("arguments", ""),
                    )
                )
            elif item_type == "message":
                final_parts.extend(_message_text(item))
            elif item_type == "reasoning":
                reasoning_items.append(dict(item))
            else:
                unknown_types.append(str(item_type or "missing"))

        self._reasoning_items = tuple(reasoning_items)
        continuation = _reasoning_summary(reasoning_items)
        final_text = "".join(final_parts) if final_parts else None
        return ParsedResponse(
            final_text=final_text,
            tool_calls=tuple(calls),
            opaque_continuation=continuation,
            unknown_block_types=tuple(unknown_types),
        )

    def _input(
        self,
        case: ProbeCase,
        tool_results: Sequence[ToolResult],
    ) -> str | list[Mapping[str, Any]]:
        if not tool_results:
            return case.prompt
        items = [dict(item) for item in self._reasoning_items]
        items.extend(
            {
                "type": "function_call_output",
                "call_id": result.call_id,
                "output": _result_output(result),
            }
            for result in tool_results
        )
        return items


class OpenAIResponsesTransport:
    """Send one SDK Responses operation with auditable retry/HTTP evidence."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        response_mode: str = "typed",
        max_retries: int = 0,
        http_transport: Any = None,
    ) -> None:
        if response_mode not in {"typed", "raw"}:
            raise ValueError("response_mode must be 'typed' or 'raw'")
        if max_retries != 0:
            raise ValueError("OpenAI SDK probe requires max_retries=0")

        try:
            import httpx
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised without uv --with
            raise RuntimeError("run the OpenAI probe with 'uv run --with openai'") from exc

        self.response_mode = response_mode
        self.max_retries = max_retries
        self._attempts: list[HttpAttempt] = []
        self._http_client = httpx.Client(
            transport=http_transport,
            event_hooks={"request": [self._record_request]},
        )
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
            http_client=self._http_client,
        )

    def send(self, request: Mapping[str, Any]) -> TransportExchange:
        self._attempts = []
        if self.response_mode == "raw":
            raw_sdk_response = self.client.responses.with_raw_response.create(**dict(request))
            typed_response = raw_sdk_response.parse()
            raw_bytes = bytes(raw_sdk_response.content)
            status_code = raw_sdk_response.status_code
        else:
            typed_response = self.client.responses.create(**dict(request))
            raw_bytes = _json_bytes(_as_mapping(typed_response))
            status_code = 200

        attempts = tuple(
            HttpAttempt(item.attempt, status_code=status_code) for item in self._attempts
        )
        return TransportExchange(
            response=RawResponse(payload=typed_response, raw_bytes=raw_bytes),
            http_attempts=attempts,
            sdk_retry_count=max(0, len(attempts) - 1),
        )

    def close(self) -> None:
        self.client.close()

    def _record_request(self, request: Any) -> None:
        del request
        self._attempts.append(HttpAttempt(len(self._attempts) + 1))


def _function_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    name = _required_string(tool, "name")
    parameters = tool.get("parameters", {"type": "object", "properties": {}})
    if not isinstance(parameters, Mapping):
        raise ValueError("OpenAI function tool parameters must be a mapping")
    result: dict[str, Any] = {
        "type": "function",
        "name": name,
        "parameters": dict(parameters),
    }
    for key in ("description", "strict"):
        if key in tool:
            result[key] = tool[key]
    return result


def _result_output(result: ToolResult) -> str:
    if isinstance(result.output, str):
        return result.output
    return json.dumps(result.output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _message_text(message: Mapping[str, Any]) -> list[str]:
    content = message.get("content", [])
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for raw_part in content:
        part = _as_mapping(raw_part)
        if part.get("type") == "output_text" and isinstance(part.get("text"), str):
            parts.append(part["text"])
    return parts


def _reasoning_summary(items: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    if not items:
        return None
    digest = hashlib.sha256(_json_bytes(list(items))).hexdigest()
    return {"hash": f"sha256:{digest}", "type": "openai-reasoning", "count": len(items)}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=False)
        if isinstance(dumped, Mapping):
            return dumped
    raise TypeError(f"OpenAI SDK value must be mapping-like, got {type(value).__name__}")


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"OpenAI response field {key} must be a non-empty string")
    return item


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
