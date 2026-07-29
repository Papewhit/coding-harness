"""Narrow official-SDK transport boundary for native provider requests.

This module constructs clients and sends exactly one provider operation.  It
does not interpret tool calls and never delegates Coda tool execution to an
SDK runner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .sdk_imports import load_anthropic_sdk, load_httpx, load_openai_sdk


@dataclass(frozen=True)
class HttpAttempt:
    """Sanitized evidence for one observed HTTP request attempt."""

    number: int
    method: str
    url: str
    status_code: int | None = None
    request_id: str | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class ProviderTransportResponse:
    """JSON-safe provider payload plus raw wire and HTTP evidence."""

    payload: Mapping[str, Any]
    raw_bytes: bytes
    status_code: int
    request_id: str | None
    http_attempts: tuple[HttpAttempt, ...]
    sdk_retry_count: int


class _AttemptRecorder:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    @property
    def count(self) -> int:
        return len(self._items)

    def on_request(self, request: Any) -> None:
        self._items.append(
            {
                "number": len(self._items) + 1,
                "method": str(request.method),
                "url": str(request.url),
                "status_code": None,
                "request_id": None,
                "error_type": None,
            }
        )

    def on_response(self, response: Any) -> None:
        if not self._items:
            return
        item = self._items[-1]
        item["status_code"] = int(response.status_code)
        item["request_id"] = _request_id_from_headers(response.headers)

    def mark_error(self, start: int, exc: Exception) -> None:
        if len(self._items) > start:
            self._items[-1]["error_type"] = type(exc).__name__

    def since(self, start: int) -> tuple[HttpAttempt, ...]:
        return tuple(HttpAttempt(**item) for item in self._items[start:])


class _SDKTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float,
        max_retries: int,
        http_transport: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url must not be empty")
        if not api_key:
            raise ValueError("api_key must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries != 0:
            raise ValueError("native provider transport requires max_retries=0")

        httpx = load_httpx()
        self.max_retries = max_retries
        self.timeout = timeout
        self._recorder = _AttemptRecorder()
        self._last_start = 0
        self._http_client = httpx.Client(
            timeout=timeout,
            transport=http_transport,
            event_hooks={
                "request": [self._recorder.on_request],
                "response": [self._recorder.on_response],
            },
        )
        self._client_args = {
            "api_key": api_key,
            "base_url": base_url,
            "max_retries": max_retries,
            "http_client": self._http_client,
        }

    @property
    def last_http_attempts(self) -> tuple[HttpAttempt, ...]:
        """Return attempts from the latest operation, including a failed one."""

        return self._recorder.since(self._last_start)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> _SDKTransport:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _begin_operation(self) -> int:
        self._last_start = self._recorder.count
        return self._last_start

    def _operation_failed(self, start: int, exc: Exception) -> None:
        self._recorder.mark_error(start, exc)


class OpenAIResponsesTransport(_SDKTransport):
    """OpenAI Responses typed-SDK transport with raw HTTP evidence."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        max_retries: int = 0,
        http_transport: Any = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            http_transport=http_transport,
        )
        try:
            openai = load_openai_sdk()
            self._client = openai.OpenAI(**self._client_args)
        except Exception:
            self._http_client.close()
            raise

    def create(self, request: Mapping[str, Any]) -> ProviderTransportResponse:
        """Send one typed Responses API create operation."""

        start = self._begin_operation()
        try:
            raw = self._client.responses.with_raw_response.create(**dict(request))
            typed = raw.parse()
            payload = _model_payload(typed, provider="OpenAI")
            return _response(raw, payload, self._recorder.since(start))
        except Exception as exc:
            self._operation_failed(start, exc)
            raise


class AnthropicMessagesTransport(_SDKTransport):
    """Anthropic Messages SDK raw-response transport."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        max_retries: int = 0,
        http_transport: Any = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            http_transport=http_transport,
        )
        try:
            anthropic = load_anthropic_sdk()
            self._client = anthropic.Anthropic(**self._client_args)
        except Exception:
            self._http_client.close()
            raise

    def create(self, request: Mapping[str, Any]) -> ProviderTransportResponse:
        """Send one raw Messages API create operation without lossy SDK parsing."""

        start = self._begin_operation()
        try:
            raw = self._client.messages.with_raw_response.create(**dict(request))
            raw_bytes = bytes(raw.content)
            payload = _json_payload(raw_bytes, provider="Anthropic")
            return _response(raw, payload, self._recorder.since(start))
        except Exception as exc:
            self._operation_failed(start, exc)
            raise


def _response(
    raw: Any,
    payload: Mapping[str, Any],
    attempts: tuple[HttpAttempt, ...],
) -> ProviderTransportResponse:
    raw_bytes = bytes(raw.content)
    request_id = _request_id_from_raw(raw) or (attempts[-1].request_id if attempts else None)
    return ProviderTransportResponse(
        payload=payload,
        raw_bytes=raw_bytes,
        status_code=int(raw.status_code),
        request_id=request_id,
        http_attempts=attempts,
        sdk_retry_count=max(0, len(attempts) - 1),
    )


def _model_payload(value: Any, *, provider: str) -> Mapping[str, Any]:
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        raise TypeError(f"{provider} SDK response is not model-dump compatible")
    payload = dump(mode="json", exclude_none=False)
    if not isinstance(payload, Mapping):
        raise TypeError(f"{provider} SDK response did not produce a mapping")
    return dict(payload)


def _json_payload(raw_bytes: bytes, *, provider: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{provider} SDK raw response is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise TypeError(f"{provider} SDK raw response must contain a JSON object")
    return dict(payload)


def _request_id_from_raw(raw: Any) -> str | None:
    request_id = getattr(raw, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return _request_id_from_headers(getattr(raw, "headers", {}))


def _request_id_from_headers(headers: Any) -> str | None:
    for name in ("request-id", "x-request-id", "anthropic-request-id"):
        value = headers.get(name) if hasattr(headers, "get") else None
        if isinstance(value, str) and value:
            return value
    return None
