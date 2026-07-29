"""Evaluation-only Runtime client instrumentation and shell isolation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

from coda.evaluation.live_tasks import (
    ClientResult,
    FailureCategory,
    FailureOrigin,
    FailureStage,
    HttpAttempt,
)
from coda.features.sandbox import SandboxConfig
from coda.features.sandbox.runner import SandboxRunner
from coda.providers.contracts import ModelRequest, ModelResponse


class AuditedNativeClient:
    """Count transport attempts without interpreting or executing Coda tools."""

    def __init__(
        self,
        inner: Any,
        *,
        persist_attempts: Callable[[tuple[HttpAttempt, ...]], None],
    ) -> None:
        if not callable(getattr(inner, "request", None)):
            raise TypeError("audited client requires request(ModelRequest)")
        self.inner = inner
        self.persist_attempts = persist_attempts
        self.requests: list[ModelRequest] = []
        self.responses: list[ModelResponse] = []
        self.http_attempts: list[HttpAttempt] = []
        self.failures: list[str] = []
        self._coda_profile_identity: dict[str, Any] = {}
        self.model = str(getattr(inner, "model", ""))
        self.base_url = str(getattr(inner, "base_url", ""))

    def request(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("audited client requires structured ModelRequest values")
        self.requests.append(request)
        started = time.monotonic()
        response = None
        try:
            response = self.inner.request(request)
            if not isinstance(response, ModelResponse):
                raise TypeError("native client returned a non-ModelResponse value")
            self.responses.append(response)
            return response
        except Exception as exc:
            self.failures.append(type(exc).__name__)
            raise
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            observed = _latest_attempts(self.inner, response, duration_ms)
            self.http_attempts.extend(observed)
            self.persist_attempts(tuple(self.http_attempts))

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if callable(close):
            close()


class NetworkIsolatedSandboxRunner(SandboxRunner):
    """Use bubblewrap's network namespace only for model-triggered shell tools."""

    def _bubblewrap_argv(
        self,
        backend_path: str,
        command: str,
        cwd: Any,
        config: SandboxConfig,
    ) -> list[str]:
        argv = super()._bubblewrap_argv(backend_path, command, cwd, config)
        argv.insert(1, "--unshare-net")
        return argv


def build_client_result(
    *,
    agent: Any,
    client: AuditedNativeClient,
    profile: Mapping[str, Any],
    native_gate_hash: str,
    final_answer: str,
) -> ClientResult:
    """Build provider-neutral facts from Runtime state and public metadata."""

    exchange_events = list(agent.session.get("model_exchange", {}).get("events", []))
    call_ids = tuple(
        str(call.get("call_id", ""))
        for event in exchange_events
        if event.get("event") == "assistant_tool_batch"
        for call in event.get("tool_calls", [])
    )
    result_ids = tuple(
        str(event.get("call_id", ""))
        for event in exchange_events
        if event.get("event") == "tool_result"
    )
    sdk_retries = sum(
        int(response.metadata.get("sdk_retry_count", 0))
        for response in client.responses
    )
    session_events = _load_session_events(agent.session_event_bus.path)
    coda_retries = sum(
        event.get("event") == "model_retry_scheduled" for event in session_events
    )
    task_state = getattr(agent, "current_task_state", None)
    runtime_run_id = str(getattr(task_state, "run_id", "") or "")
    failure = FailureCategory.PROVIDER if client.failures else FailureCategory.NONE
    return ClientResult(
        profile=dict(profile),
        native_gate_hash=native_gate_hash,
        call_ids=call_ids,
        result_call_ids=result_ids,
        http_attempts=tuple(client.http_attempts),
        sdk_retry_count=sdk_retries,
        coda_retry_count=coda_retries,
        error=client.failures[-1] if client.failures else "",
        error_type=client.failures[-1] if client.failures else "",
        failure_category=failure,
        failure_origin=(
            FailureOrigin.PROVIDER if client.failures else FailureOrigin.NONE
        ),
        failure_stage=(
            FailureStage.REQUEST if client.failures else FailureStage.NONE
        ),
        session_id=str(agent.session.get("id", "")),
        runtime_run_id=runtime_run_id,
        final_answer=final_answer,
        http_attempts_exact=True,
        original_state_paths=(
            f".coda/sessions/{agent.session.get('id', '')}.json",
            f".coda/sessions/{agent.session.get('id', '')}.events.jsonl",
            f".coda/runs/{runtime_run_id}",
        ),
    )


def required_network_sandbox(
    *,
    extra_readonly_paths: tuple[str, ...] = (),
) -> NetworkIsolatedSandboxRunner:
    return NetworkIsolatedSandboxRunner(
        SandboxConfig(
            mode="required",
            backend="bubblewrap",
            workspace_write=True,
            extra_readonly_paths=extra_readonly_paths,
        )
    )


def probe_required_network_sandbox() -> None:
    """Run the one allowed live-start bubblewrap writability probe."""

    sandbox = required_network_sandbox(
        extra_readonly_paths=(
            sys.prefix,
            str(Path(sys.base_prefix).parent),
        )
    )
    with tempfile.TemporaryDirectory(prefix="coda-eval-sandbox-probe-") as temporary:
        workspace = Path(temporary)
        marker = workspace / "marker"
        result = sandbox.run(
            "printf ready > marker",
            cwd=workspace,
            env={},
            timeout=10,
        )
        if (
            result.returncode != 0
            or not marker.is_file()
            or marker.read_text(encoding="utf-8") != "ready"
        ):
            raise RuntimeError("network-isolated bubblewrap probe failed")


def _latest_attempts(
    inner: Any,
    response: ModelResponse | None,
    duration_ms: int,
) -> tuple[HttpAttempt, ...]:
    transport = getattr(inner, "_transport", None)
    raw = tuple(getattr(transport, "last_http_attempts", ()) or ())
    if raw:
        return tuple(
            HttpAttempt(
                attempt=int(getattr(item, "number", index)),
                status_code=getattr(item, "status_code", None),
                duration_ms=duration_ms,
                error_type=str(getattr(item, "error_type", "") or ""),
            )
            for index, item in enumerate(raw, start=1)
        )
    metadata = {} if response is None else response.metadata
    values = metadata.get("http_attempts", [])
    if isinstance(values, list):
        return tuple(
            HttpAttempt(
                attempt=int(item.get("number", index)),
                status_code=item.get("status_code"),
                duration_ms=duration_ms,
                error_type=str(item.get("error_type", "") or ""),
            )
            for index, item in enumerate(values, start=1)
            if isinstance(item, Mapping)
        )
    return ()


def _load_session_events(path: Any) -> list[dict[str, Any]]:
    import json

    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


__all__ = [
    "AuditedNativeClient",
    "NetworkIsolatedSandboxRunner",
    "build_client_result",
    "probe_required_network_sandbox",
    "required_network_sandbox",
]
