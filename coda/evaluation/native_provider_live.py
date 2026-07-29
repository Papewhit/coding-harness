"""Fixed production-Runtime runner for native-provider conformance cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
from typing import Any

from coda import Coda, SessionStore, WorkspaceContext
from coda.config import ProviderConfig, resolve_provider_config
from coda.core.model_exchange import continuation_evidence
from coda.providers import build_native_model_client
from coda.providers.contracts import ModelRequest, ModelResponse

from .native_provider_profiles import (
    assert_provider_profile_matches,
    provider_session_identity,
)


WORKSPACE_FIXTURE_VERSION = "coda-native-provider-live-workspace-v1"
NATIVE_SAFETY_EVIDENCE_VERSION = "coda-native-safety-chain-evidence-v1"
NATIVE_SAFETY_STAGES = (
    "validate",
    "repetition",
    "permission",
    "policy",
    "execute",
)
PRE_RUNTIME_REJECTION_ERROR_CODES = frozenset(
    {
        "model_protocol_error",
        "step_limit_exceeded",
        "tool_choice_none_violation",
    }
)
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
LiveModelClientFactory = Callable[[ProviderConfig, Mapping[str, Any]], Any]


class LiveProviderAttemptError(RuntimeError):
    """Stop Coda from retrying one failed fixed-attempt provider operation."""


@dataclass
class NativeProviderLiveRunner:
    """Callable bound to a named local profile and the production Coda Runtime."""

    provider: str
    start: str | Path = "."
    config_path: str | None = None
    client_factory: LiveModelClientFactory | None = None
    workspace_parent: str | Path | None = None
    _case_repetitions: dict[str, int] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __call__(
        self, case: Mapping[str, Any], expected_profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        case_id = _case_id(case)
        repetition = self._case_repetitions.get(case_id, 0) + 1
        self._case_repetitions[case_id] = repetition
        return run_native_provider_live_case(
            case=case,
            expected_profile=expected_profile,
            provider=self.provider,
            start=self.start,
            config_path=self.config_path,
            client_factory=self.client_factory,
            workspace_parent=self.workspace_parent,
            repetition=repetition,
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
    repetition: int = 1,
) -> dict[str, Any]:
    """Run one isolated case and return only structured, sanitized evidence."""

    case_id = _case_id(case)
    if type(repetition) is not int or repetition < 1:
        raise ValueError("native provider live repetition must be a positive integer")
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
    client._coda_profile_identity = provider_session_identity(config)
    parent = None if workspace_parent is None else str(Path(workspace_parent))

    try:
        with tempfile.TemporaryDirectory(
            prefix="coda-native-provider-",
            dir=parent,
        ) as directory:
            workspace_root = Path(directory)
            _build_workspace(workspace_root)
            agent = Coda(
                model_client=client,
                workspace=WorkspaceContext.build(workspace_root),
                session_store=SessionStore(workspace_root / ".coda" / "sessions"),
                approval_policy=APPROVAL_POLICIES[scenario],
                max_steps=12,
                max_new_tokens=1024,
                auto_dream=False,
            )
            bind_native_safety_evidence(
                agent,
                case_id=case_id,
                repetition=repetition,
            )
            list(agent.engine.run_turn(prompt))
            observation = _build_observation(
                agent=agent,
                client=client,
                scenario=scenario,
                case_id=case_id,
                repetition=repetition,
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


def bind_native_safety_evidence(
    agent: Coda,
    *,
    case_id: str,
    repetition: int,
) -> None:
    """Bind structured native safety evidence to one production Runtime case."""

    if not case_id:
        raise ValueError("native safety evidence case_id must be non-empty")
    if type(repetition) is not int or repetition < 1:
        raise ValueError("native safety evidence repetition must be positive")
    sequence = 0

    def emit(
        tool_name: str,
        stage: str,
        outcome: str,
        reason: str,
    ) -> None:
        nonlocal sequence
        call_id = _executing_native_call_id(agent)
        if not call_id:
            return
        sequence += 1
        agent.session_event_bus.emit(
            "native_safety_stage",
            {
                "schema_version": NATIVE_SAFETY_EVIDENCE_VERSION,
                "case_id": case_id,
                "repetition": repetition,
                "call_id": call_id,
                "tool_name": tool_name,
                "stage": stage,
                "stage_index": NATIVE_SAFETY_STAGES.index(stage) + 1,
                "outcome": outcome,
                "reason": reason,
                "sequence": sequence,
            },
        )

    agent._native_safety_evidence_hook = emit


def _executing_native_call_id(agent: Coda) -> str:
    native = agent.session.get("native_runtime", {})
    active = native.get("active_batch") if isinstance(native, dict) else None
    calls = active.get("calls", []) if isinstance(active, dict) else []
    executing = [
        call
        for call in calls
        if isinstance(call, dict) and call.get("status") == "executing"
    ]
    if len(executing) != 1:
        return ""
    call = executing[0].get("call", {})
    call_id = call.get("call_id") if isinstance(call, dict) else None
    return call_id if isinstance(call_id, str) else ""


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
        self._coda_profile_identity: dict[str, Any] = {}

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
    agent: Coda,
    client: _AuditedModelClient,
    scenario: str,
    case_id: str,
    repetition: int,
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
    finished_by_call = {
        str(event.get("call_id", "")): event
        for event in session_events
        if event.get("event") == "tool_finished"
    }
    runtime_started_call_ids = {
        str(event.get("call_id", ""))
        for event in session_events
        if event.get("event") == "tool_started"
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
            "tool_calls": [
                {
                    **call.to_dict(),
                    "runtime_started": call.call_id in runtime_started_call_ids,
                }
                for call in response.tool_calls
            ],
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
                finished = finished_by_call.get(call.call_id, {})
                error_code = _result_error_code(result)
                results.append(
                    {
                        "call_id": call.call_id,
                        "is_error": bool(result.get("is_error", False)),
                        "error_code": error_code,
                        "tool_status": str(
                            finished.get(
                                "status",
                                "error" if result.get("is_error") else "ok",
                            )
                        ),
                        "tool_error_code": str(
                            finished.get(
                                "tool_error_code",
                                error_code,
                            )
                        ),
                        "execution_scope": _execution_scope(
                            call_id=call.call_id,
                            error_code=error_code,
                            runtime_started_call_ids=runtime_started_call_ids,
                        ),
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
        case_id=case_id,
        repetition=repetition,
    )
    safety_evidence = _native_safety_evidence(
        session_events,
        case_id=case_id,
        repetition=repetition,
    )
    coda_retry_count = sum(
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
        "coda_retry_count": coda_retry_count,
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
            "safety_chain_evidence": safety_evidence,
            "safety_chain_bypass_count": bypass_count,
            "sdk_tool_runner_used": False,
            "sdk_agent_runner_used": False,
            "sdk_managed_coda_tool_execution_used": False,
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
    case_id: str,
    repetition: int,
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
        stages = [
            event
            for event in _native_safety_evidence(
                session_events,
                case_id=case_id,
                repetition=repetition,
            )
            if event["call_id"] == call_id
        ]
        result = results.get(call_id, {})
        result_payload = result.get("result", {})
        error_code = (
            _result_error_code(result_payload)
            if isinstance(result_payload, Mapping)
            else ""
        )
        valid = bool(result) and _valid_safety_stage_prefix(stages, error_code)
        bypass_count += int(not valid)
        outcomes = {event["stage"]: event["outcome"] for event in stages}
        audit.append(
            {
                "call_id": call_id,
                "case_id": case_id,
                "repetition": repetition,
                "result_error_code": error_code,
                "stages": stages,
                "validate": outcomes.get("validate", "not_reached"),
                "repetition_guard": outcomes.get("repetition", "not_reached"),
                "permission": outcomes.get("permission", "not_reached"),
                "policy": outcomes.get("policy", "not_reached"),
                "execute": outcomes.get("execute", "not_reached"),
                "bypass": not valid,
            }
        )
    return audit, bypass_count


def _native_safety_evidence(
    events: Sequence[Mapping[str, Any]],
    *,
    case_id: str,
    repetition: int,
) -> list[dict[str, Any]]:
    evidence = []
    for event in events:
        if (
            event.get("event") != "native_safety_stage"
            or event.get("schema_version") != NATIVE_SAFETY_EVIDENCE_VERSION
            or event.get("case_id") != case_id
            or event.get("repetition") != repetition
        ):
            continue
        evidence.append(
            {
                "schema_version": NATIVE_SAFETY_EVIDENCE_VERSION,
                "case_id": case_id,
                "repetition": repetition,
                "call_id": str(event.get("call_id", "")),
                "tool_name": str(event.get("tool_name", "")),
                "stage": str(event.get("stage", "")),
                "stage_index": event.get("stage_index"),
                "outcome": str(event.get("outcome", "")),
                "reason": str(event.get("reason", "")),
                "sequence": event.get("sequence"),
            }
        )
    return sorted(
        evidence,
        key=lambda event: _non_negative_int(event["sequence"]),
    )


def _valid_safety_stage_prefix(
    stages: Sequence[Mapping[str, Any]],
    error_code: str,
) -> bool:
    if not stages:
        return False
    names = tuple(str(event.get("stage", "")) for event in stages)
    if names != NATIVE_SAFETY_STAGES[: len(names)]:
        return False
    if [event.get("stage_index") for event in stages] != list(
        range(1, len(stages) + 1)
    ):
        return False
    sequences = [event.get("sequence") for event in stages]
    if (
        not all(type(sequence) is int for sequence in sequences)
        or sequences != sorted(sequences)
        or len(set(sequences)) != len(sequences)
    ):
        return False
    if any(event.get("outcome") != "passed" for event in stages[:-1]):
        return False
    final_stage = stages[-1]
    if final_stage["stage"] == "execute":
        return final_stage["outcome"] in {"completed", "failed"}
    return bool(error_code) and final_stage["outcome"] == "rejected"


def _result_error_code(result: Mapping[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, Mapping):
        return ""
    error = output.get("error")
    if not isinstance(error, Mapping):
        return ""
    code = error.get("code")
    return code if isinstance(code, str) else ""


def _execution_scope(
    *,
    call_id: str,
    error_code: str,
    runtime_started_call_ids: set[str],
) -> str:
    if call_id in runtime_started_call_ids:
        return "runtime_execution"
    if error_code in PRE_RUNTIME_REJECTION_ERROR_CODES:
        return "pre_runtime_rejection"
    return "runtime_execution"


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


def _case_id(case: Mapping[str, Any]) -> str:
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("native provider live case id must be a non-empty string")
    return case_id


__all__ = [
    "APPROVAL_POLICIES",
    "NATIVE_SAFETY_EVIDENCE_VERSION",
    "NATIVE_SAFETY_STAGES",
    "NativeProviderLiveRunner",
    "WORKSPACE_FIXTURE_VERSION",
    "bind_native_safety_evidence",
    "run_native_provider_live_case",
]
