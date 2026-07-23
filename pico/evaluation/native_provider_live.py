"""Fixed production-Runtime runner for native-provider conformance cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from pico import Pico, SessionStore, WorkspaceContext
from pico.config import ProviderConfig, resolve_provider_config
from pico.core.model_exchange import continuation_evidence
from pico.providers import build_native_model_client
from pico.providers.contracts import ModelRequest, ModelResponse

from .native_provider_profiles import (
    assert_provider_profile_matches,
    provider_session_identity,
)


WORKSPACE_FIXTURE_VERSION = "pico-native-provider-live-workspace-v1"
APPROVAL_POLICIES = {
    "final": "auto",
    "single_call": "auto",
    "unicode": "auto",
    "invalid_args_repair": "auto",
    "permission_denial": "never",
    "multi_round_patch_verify": "auto",
    "unexpected_multi_call": "auto",
    "opaque_block_roundtrip": "auto",
}
_EARLY_REJECTION_CODES = {
    "invalid_arguments",
    "repeated_identical_call",
    "unknown_tool",
}

LiveModelClientFactory = Callable[[ProviderConfig, Mapping[str, Any]], Any]


class LiveProviderAttemptError(RuntimeError):
    """Stop Pico from retrying one failed fixed-attempt provider operation."""


@dataclass
class NativeProviderLiveRunner:
    """Callable bound to a named local profile and the production Pico Runtime."""

    provider: str
    start: str | Path = "."
    config_path: str | None = None
    client_factory: LiveModelClientFactory | None = None
    workspace_parent: str | Path | None = None

    def __call__(
        self, case: Mapping[str, Any], expected_profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        return run_native_provider_live_case(
            case=case,
            expected_profile=expected_profile,
            provider=self.provider,
            start=self.start,
            config_path=self.config_path,
            client_factory=self.client_factory,
            workspace_parent=self.workspace_parent,
        )


def run_native_provider_live_case(
    *,
    case: Mapping[str, Any],
    expected_profile: Mapping[str, Any],
    provider: str,
    start: str | Path = ".",
    config_path: str | None = None,
    client_factory: LiveModelClientFactory | None = None,
    workspace_parent: str | Path | None = None,
) -> dict[str, Any]:
    """Run one isolated case and return only structured, sanitized evidence."""

    scenario = str(case.get("scenario", ""))
    if scenario not in APPROVAL_POLICIES:
        raise ValueError(f"unsupported native provider live scenario: {scenario}")
    prompt = case.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("native provider live case prompt must be a string")

    config = resolve_provider_config(
        provider,
        start=start,
        config_path=config_path,
    )
    assert_provider_profile_matches(config, expected_profile)
    if not config.api_key:
        raise ValueError("resolved provider profile has no API key")
    if not config.base_url:
        raise ValueError("resolved provider profile has no base URL")

    factory = client_factory or _production_client
    raw_client = factory(config, case)
    client = _AuditedModelClient(raw_client)
    client._pico_profile_identity = provider_session_identity(config)
    parent = None if workspace_parent is None else str(Path(workspace_parent))

    try:
        with tempfile.TemporaryDirectory(
            prefix="pico-native-provider-",
            dir=parent,
        ) as directory:
            workspace_root = Path(directory)
            _build_workspace(workspace_root)
            agent = Pico(
                model_client=client,
                workspace=WorkspaceContext.build(workspace_root),
                session_store=SessionStore(workspace_root / ".pico" / "sessions"),
                approval_policy=APPROVAL_POLICIES[scenario],
                max_steps=12,
                max_new_tokens=1024,
                auto_dream=False,
            )
            list(agent.engine.run_turn(prompt))
            observation = _build_observation(
                agent=agent,
                client=client,
                scenario=scenario,
            )
            _assert_no_secret_material(observation, config)
            return observation
    finally:
        client.close()


def _production_client(
    config: ProviderConfig, _case: Mapping[str, Any]
) -> Any:
    return build_native_model_client(
        wire_dialect=config.wire_dialect,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        profile_id=config.public_identity()["profile_id"],
        max_retries=0,
    )


class _AuditedModelClient:
    """Record provider-neutral requests/responses without changing tool execution."""

    def __init__(self, inner: Any) -> None:
        if not callable(getattr(inner, "request", None)):
            raise TypeError("live runner client must implement request(ModelRequest)")
        self.inner = inner
        self.model = str(getattr(inner, "model", ""))
        self.base_url = str(getattr(inner, "base_url", ""))
        self.requests: list[ModelRequest] = []
        self.responses: list[ModelResponse] = []
        self.attempts: list[list[dict[str, Any]]] = []
        self.failures: list[dict[str, Any]] = []
        self._pico_profile_identity: dict[str, Any] = {}

    def request(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("live runner requires structured ModelRequest values")
        self.requests.append(request)
        try:
            response = self.inner.request(request)
        except Exception as exc:
            attempts = _http_attempts(self.inner, None)
            self.failures.append(
                {
                    "type": type(exc).__name__,
                    "attempts": attempts,
                }
            )
            raise LiveProviderAttemptError(
                "fixed provider operation failed; automatic retry is disabled"
            ) from exc
        if not isinstance(response, ModelResponse):
            raise TypeError("live runner client returned a non-ModelResponse value")
        self.responses.append(response)
        self.attempts.append(_http_attempts(self.inner, response))
        return response

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if callable(close):
            close()


def _build_workspace(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "native provider conformance\nsecond line\n",
        encoding="utf-8",
    )
    (root / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "b.py").write_text("VALUE = 2\n", encoding="utf-8")


def _build_observation(
    *,
    agent: Pico,
    client: _AuditedModelClient,
    scenario: str,
) -> dict[str, Any]:
    session_events = _load_json_lines(agent.session_event_bus.path)
    exchange_events = list(
        agent.session.get("model_exchange", {}).get("events", [])
    )
    result_by_call = {
        str(event.get("call_id", "")): event
        for event in exchange_events
        if event.get("event") == "tool_result"
    }

    events: list[dict[str, Any]] = []
    unknown_blocks: list[dict[str, Any]] = []
    unknown_block_loss_count = 0
    continuation_observed: list[dict[str, Any]] = []
    sent_continuation_hashes = {
        request.continuation.stable_hash()
        for request in client.requests
        if request.continuation is not None
    }
    for index, response in enumerate(client.responses):
        request = client.requests[index]
        if request.continuation is not None:
            events.append(
                {
                    "type": "request",
                    "opaque_continuation": continuation_evidence(
                        request.continuation
                    ),
                }
            )
        for attempt in client.attempts[index]:
            events.append({"type": "http_attempt", **attempt})

        descriptor = (
            continuation_evidence(response.continuation)
            if response.continuation is not None
            else None
        )
        if descriptor is not None:
            continuation_observed.append(
                {"response_index": index, **descriptor}
            )
        assistant = {
            "type": "assistant",
            "text": response.text,
            "stop_reason": response.stop_reason.value,
            "tool_calls": [call.to_dict() for call in response.tool_calls],
        }
        if (
            descriptor is not None
            and descriptor["hash"] in sent_continuation_hashes
        ):
            assistant["opaque_continuation"] = descriptor
        events.append(assistant)

        for item in _unknown_block_evidence(response.metadata):
            unknown_blocks.append({"response_index": index, **item})
            if response.continuation is None:
                unknown_block_loss_count += 1

        if response.tool_calls:
            results = []
            for call in response.tool_calls:
                journal = result_by_call.get(call.call_id)
                if journal is None:
                    continue
                result = dict(journal.get("result", {}))
                results.append(
                    {
                        "call_id": call.call_id,
                        "is_error": bool(result.get("is_error", False)),
                        "error_code": _result_error_code(result),
                        "output": result.get("output"),
                    }
                )
            events.append({"type": "tool_results", "results": results})

    for failure in client.failures:
        for attempt in failure["attempts"]:
            events.append({"type": "http_attempt", **attempt})

    safety_chain, bypass_count = _audit_safety_chain(
        exchange_events=exchange_events,
        session_events=session_events,
    )
    pico_retry_count = sum(
        event.get("event") == "model_retry_scheduled" for event in session_events
    )
    sdk_retry_count = sum(
        _non_negative_int(response.metadata.get("sdk_retry_count", 0))
        for response in client.responses
    )
    observation: dict[str, Any] = {
        "eligible": True,
        "events": events,
        "sdk_retry_count": sdk_retry_count,
        "pico_retry_count": pico_retry_count,
        "workspace": {
            "fixture_version": WORKSPACE_FIXTURE_VERSION,
            "approval_policy": APPROVAL_POLICIES[scenario],
        },
        "audit": {
            "model_request_count": len(client.requests),
            "model_response_count": len(client.responses),
            "session_exchange_count": len(exchange_events),
            "unknown_blocks": unknown_blocks,
            "unknown_block_loss_count": unknown_block_loss_count,
            "continuations": continuation_observed,
            "safety_chain": safety_chain,
            "safety_chain_bypass_count": bypass_count,
            "sdk_tool_runner_used": False,
            "sdk_agent_runner_used": False,
            "sdk_managed_pico_tool_execution_used": False,
        },
    }
    if client.failures:
        observation["infrastructure_failure"] = {
            "type": client.failures[-1]["type"],
        }
    return observation


def _http_attempts(
    inner: Any, response: ModelResponse | None
) -> list[dict[str, Any]]:
    transport = getattr(inner, "_transport", None)
    raw_attempts = getattr(transport, "last_http_attempts", ())
    if raw_attempts:
        return [
            {
                "attempt": int(getattr(item, "number", index)),
                "outcome": _attempt_outcome(
                    status_code=getattr(item, "status_code", None),
                    error_type=getattr(item, "error_type", None),
                ),
            }
            for index, item in enumerate(raw_attempts, start=1)
        ]
    metadata = {} if response is None else response.metadata
    metadata_attempts = metadata.get("http_attempts", [])
    if isinstance(metadata_attempts, Sequence) and not isinstance(
        metadata_attempts, (str, bytes)
    ):
        attempts = []
        for index, item in enumerate(metadata_attempts, start=1):
            if not isinstance(item, Mapping):
                continue
            attempts.append(
                {
                    "attempt": _positive_int(item.get("number", index), index),
                    "outcome": _attempt_outcome(
                        status_code=item.get("status_code"),
                        error_type=item.get("error_type"),
                    ),
                }
            )
        if attempts:
            return attempts
    count = _non_negative_int(metadata.get("http_attempt_count", 0))
    return [
        {"attempt": number, "outcome": "observed"}
        for number in range(1, count + 1)
    ]


def _attempt_outcome(*, status_code: Any, error_type: Any) -> str:
    if isinstance(error_type, str) and error_type:
        return f"error:{error_type}"
    if type(status_code) is int:
        return f"http:{status_code}"
    return "observed"


def _unknown_block_evidence(
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    unknown_items = metadata.get("unknown_item_types", [])
    if isinstance(unknown_items, list):
        evidence.extend(
            {"dialect": "openai-responses", "type": item}
            for item in unknown_items
            if isinstance(item, str)
        )
    blocks = metadata.get("content_blocks", {})
    unknown_blocks = blocks.get("unknown_types", []) if isinstance(blocks, Mapping) else []
    if isinstance(unknown_blocks, list):
        evidence.extend(
            {"dialect": "anthropic-messages", "type": item}
            for item in unknown_blocks
            if isinstance(item, str)
        )
    return evidence


def _audit_safety_chain(
    *,
    exchange_events: Sequence[Mapping[str, Any]],
    session_events: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    results = {
        str(event.get("call_id", "")): event
        for event in exchange_events
        if event.get("event") == "tool_result"
    }
    calls = [
        call
        for event in exchange_events
        if event.get("event") == "assistant_tool_batch"
        for call in event.get("tool_calls", [])
        if isinstance(call, Mapping)
    ]
    audit: list[dict[str, Any]] = []
    bypass_count = 0
    for call in calls:
        call_id = str(call.get("call_id", ""))
        start, finish, segment = _call_event_segment(session_events, call_id)
        permissions = [
            event
            for event in segment
            if event.get("event") == "permission_decision"
        ]
        policies = [
            event
            for event in segment
            if event.get("event") == "tool_policy_decision"
        ]
        result = results.get(call_id, {})
        result_payload = result.get("result", {})
        error_code = (
            _result_error_code(result_payload)
            if isinstance(result_payload, Mapping)
            else ""
        )
        valid = start is not None and finish is not None and bool(result)
        if valid and error_code not in _EARLY_REJECTION_CODES:
            if permissions and permissions[-1].get("decision") == "deny":
                valid = True
            elif not permissions or permissions[-1].get("decision") != "allow":
                valid = False
            elif policies and policies[-1].get("decision") == "deny":
                valid = True
            elif not policies or policies[-1].get("decision") != "allow":
                valid = False
        bypass_count += int(not valid)
        audit.append(
            {
                "call_id": call_id,
                "result_error_code": error_code,
                "tool_started": start is not None,
                "permission": (
                    str(permissions[-1].get("decision")) if permissions else "not_reached"
                ),
                "policy": (
                    str(policies[-1].get("decision")) if policies else "not_reached"
                ),
                "tool_finished": finish is not None,
                "bypass": not valid,
            }
        )
    return audit, bypass_count


def _call_event_segment(
    events: Sequence[Mapping[str, Any]], call_id: str
) -> tuple[int | None, int | None, Sequence[Mapping[str, Any]]]:
    start = next(
        (
            index
            for index, event in enumerate(events)
            if event.get("event") == "tool_started"
            and event.get("call_id") == call_id
        ),
        None,
    )
    if start is None:
        return None, None, ()
    finish = next(
        (
            index
            for index, event in enumerate(events[start + 1 :], start=start + 1)
            if event.get("event") == "tool_finished"
            and event.get("call_id") == call_id
        ),
        None,
    )
    if finish is None:
        return start, None, events[start + 1 :]
    return start, finish, events[start + 1 : finish]


def _result_error_code(result: Mapping[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, Mapping):
        return ""
    error = output.get("error")
    if not isinstance(error, Mapping):
        return ""
    code = error.get("code")
    return code if isinstance(code, str) else ""


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _assert_no_secret_material(
    observation: Mapping[str, Any], config: ProviderConfig
) -> None:
    rendered = json.dumps(observation, ensure_ascii=False, sort_keys=True)
    for secret in (config.api_key, config.base_url):
        if secret and secret in rendered:
            raise RuntimeError(
                "native provider observation contained private configuration material"
            )


def _non_negative_int(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0


def _positive_int(value: Any, default: int) -> int:
    return value if type(value) is int and value > 0 else default


__all__ = [
    "APPROVAL_POLICIES",
    "NativeProviderLiveRunner",
    "WORKSPACE_FIXTURE_VERSION",
    "run_native_provider_live_case",
]
