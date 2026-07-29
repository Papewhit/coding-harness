"""Anthropic Messages SDK plugin for the native-tool viability probe.

The SDK is imported only by :func:`create_anthropic_messages_transport`, so it
can remain an isolated ``uv run --with anthropic`` probe dependency.  Private
thinking blocks are retained in memory solely for an exact Messages roundtrip;
the provider-neutral parsed response exposes only hash metadata.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from coda.evaluation.sdk_probe import (
    HttpAttempt,
    ParsedResponse,
    ProbeCase,
    ProbeProfile,
    RawResponse,
    ToolCall,
    ToolResult,
    TransportExchange,
)


class AnthropicMessagesDialect:
    """Map probe cases to Anthropic Messages native tool payloads."""

    name = "anthropic-messages"

    def __init__(self) -> None:
        self._assistant_blocks: list[dict[str, Any]] = []

    def build_request(
        self,
        case: ProbeCase,
        profile: ProbeProfile,
        tool_results: Sequence[ToolResult],
    ) -> Mapping[str, Any]:
        if profile.retry.get("sdk_max_retries") != 0:
            raise ValueError("Anthropic probe profile requires sdk_max_retries=0")
        if not tool_results:
            self._assistant_blocks = []
        messages: list[dict[str, Any]] = [{"role": "user", "content": case.prompt}]
        if tool_results:
            if not self._assistant_blocks:
                raise ValueError("tool results require a preceding Anthropic assistant turn")
            call_ids = [
                str(block["id"])
                for block in self._assistant_blocks
                if block.get("type") == "tool_use"
            ]
            result_ids = [result.call_id for result in tool_results]
            if len(call_ids) != len(set(call_ids)) or sorted(call_ids) != sorted(result_ids):
                raise ValueError("each Anthropic tool_use_id must have exactly one tool result")
            result_blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": result.call_id,
                    "content": _result_content(result.output),
                    "is_error": result.is_error,
                }
                for result in tool_results
            ]
            messages.extend(
                [
                    {"role": "assistant", "content": self._assistant_blocks},
                    {"role": "user", "content": result_blocks},
                ]
            )

        request: dict[str, Any] = {
            "model": profile.model,
            "max_tokens": int(profile.capabilities.get("max_tokens", 256)),
            "messages": messages,
            "stream": False,
        }
        if case.tool is not None:
            request["tools"] = [_tool_definition(case.tool)]
        thinking = profile.capabilities.get("thinking")
        if isinstance(thinking, Mapping):
            request["thinking"] = dict(thinking)
        return request

    def parse_response(self, response: RawResponse) -> ParsedResponse:
        payload = _mapping(response.payload)
        content = payload.get("content", [])
        if not isinstance(content, list):
            raise ValueError("Anthropic response content must be a list")

        assistant_blocks: list[dict[str, Any]] = []
        calls: list[ToolCall] = []
        text: list[str] = []
        private_blocks: list[dict[str, Any]] = []
        unknown: list[str] = []
        for value in content:
            block = _mapping(value)
            block_type = block.get("type")
            if block_type == "text":
                text.append(str(block.get("text", "")))
                assistant_blocks.append(block)
            elif block_type == "tool_use":
                assistant_blocks.append(block)
                calls.append(
                    ToolCall(
                        call_id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        arguments=block.get("input", {}),
                    )
                )
            elif block_type in {"thinking", "redacted_thinking"}:
                assistant_blocks.append(block)
                private_blocks.append(block)
            else:
                unknown.append(str(block_type or "missing"))

        self._assistant_blocks = assistant_blocks
        opaque = _opaque_metadata(private_blocks) if private_blocks else None
        final_text = "".join(text) if text else None
        return ParsedResponse(
            final_text=final_text,
            tool_calls=tuple(calls),
            opaque_continuation=opaque,
            unknown_block_types=tuple(unknown),
        )


class AnthropicMessagesTransport:
    """Use the SDK raw-response surface without any SDK-managed tool runner."""

    def __init__(self, client: Any, attempt_log: list[dict[str, Any]]) -> None:
        if client.max_retries != 0:
            raise ValueError("Anthropic probe requires max_retries=0")
        self._client = client
        self._attempt_log = attempt_log

    def send(self, request: Mapping[str, Any]) -> TransportExchange:
        start = len(self._attempt_log)
        try:
            raw = self._client.messages.with_raw_response.create(**dict(request))
        except Exception as exc:
            if len(self._attempt_log) > start:
                self._attempt_log[-1]["error_type"] = type(exc).__name__
            raise
        attempts = self._attempt_log[start:]
        if not attempts:
            attempts = [{"status_code": raw.status_code, "error_type": None}]
        parsed = raw.parse()
        payload = _mapping(parsed)
        return TransportExchange(
            response=RawResponse(payload=payload, raw_bytes=bytes(raw.content)),
            http_attempts=tuple(
                HttpAttempt(
                    attempt=index,
                    status_code=item.get("status_code"),
                    error_type=item.get("error_type"),
                )
                for index, item in enumerate(attempts, start=1)
            ),
            sdk_retry_count=max(0, len(attempts) - 1),
        )


def create_anthropic_messages_transport(
    *,
    base_url: str,
    api_key: str = "probe-placeholder",
    http_transport: Any = None,
) -> AnthropicMessagesTransport:
    """Create an isolated SDK transport with retries explicitly disabled."""

    import anthropic
    import httpx

    attempts: list[dict[str, Any]] = []

    def record_request(_request: Any) -> None:
        attempts.append({"status_code": None, "error_type": None})

    def record_response(response: Any) -> None:
        attempts[-1]["status_code"] = response.status_code

    http_client = httpx.Client(
        transport=http_transport,
        event_hooks={"request": [record_request], "response": [record_response]},
    )
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
        http_client=http_client,
    )
    return AnthropicMessagesTransport(client, attempts)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(exclude_none=True)
        if isinstance(result, Mapping):
            return dict(result)
    raise TypeError("Anthropic SDK value must be mapping-compatible")


def _tool_definition(tool: Mapping[str, Any]) -> dict[str, Any]:
    schema = tool.get("input_schema", tool.get("parameters"))
    if not isinstance(schema, Mapping):
        schema = {"type": "object", "additionalProperties": True}
    return {
        "name": str(tool["name"]),
        "description": str(tool.get("description", "SDK viability probe tool")),
        "input_schema": dict(schema),
    }


def _result_content(output: Any) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _opaque_metadata(blocks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    material = json.dumps(list(blocks), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {
        "hash": f"sha256:{hashlib.sha256(material).hexdigest()}",
        "type": "anthropic-thinking",
        "count": len(blocks),
    }
