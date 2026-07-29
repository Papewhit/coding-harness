"""Provider-neutral SDK viability probe harness.

The harness deliberately knows nothing about a product Runtime or a provider
SDK.  A transport plugin performs one SDK request and reports every underlying
HTTP attempt; a dialect plugin maps provider payloads to the small contracts in
this module.  This keeps temporary ``uv run --with`` SDKs at the probe boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from coda.evaluation.contracts import (
    extend_artifact_contract,
    native_protocol_metadata,
    ratio,
    sanitize_opaque_continuation,
    sanitize_public_artifact,
)


PROBE_SCHEMA_VERSION = "coda-sdk-viability-probe-v1"
CASE_SCHEMA_VERSION = "coda-sdk-viability-cases-v1"
CASE_KINDS = frozenset(
    {"final", "native_call", "result_roundtrip", "invalid_args", "unicode", "opaque_block"}
)

PROBE_CASE_SCHEMA: dict[str, Any] = {
    "schema_version": CASE_SCHEMA_VERSION,
    "required": ("id", "kind", "prompt"),
    "kinds": tuple(sorted(CASE_KINDS)),
    "optional": ("tool", "tool_result", "expected"),
}


@dataclass(frozen=True)
class ProbeCase:
    """One deterministic viability interaction; it never executes a real tool."""

    id: str
    kind: str
    prompt: str
    tool: Mapping[str, Any] | None = None
    tool_result: Any = None
    expected: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProbeCase":
        case_id = _required_text(value, "id")
        kind = _required_text(value, "kind")
        prompt = _required_text(value, "prompt")
        if kind not in CASE_KINDS:
            raise ValueError(f"unsupported probe case kind: {kind}")
        tool = value.get("tool")
        if tool is not None and not isinstance(tool, Mapping):
            raise ValueError("probe case tool must be a mapping")
        expected = value.get("expected", {})
        if not isinstance(expected, Mapping):
            raise ValueError("probe case expected must be a mapping")
        if kind in {"native_call", "result_roundtrip", "invalid_args"} and tool is None:
            raise ValueError(f"probe case kind {kind} requires a tool")
        return cls(
            id=case_id,
            kind=kind,
            prompt=prompt,
            tool=dict(tool) if tool is not None else None,
            tool_result=value.get("tool_result"),
            expected=dict(expected),
        )


@dataclass(frozen=True)
class ProbeProfile:
    """Reproducibility identity and declared endpoint capabilities."""

    provider: str
    model: str
    wire_dialect: str
    adapter_mode: str
    sdk_package: str
    sdk_version: str
    base_url_fingerprint: str
    capabilities: Mapping[str, Any] = field(default_factory=dict)
    retry: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProbeProfile":
        sdk = value.get("sdk", {})
        retry = value.get("retry", {})
        capabilities = value.get("capabilities", {})
        for name, item in (("sdk", sdk), ("retry", retry), ("capabilities", capabilities)):
            if not isinstance(item, Mapping):
                raise ValueError(f"probe profile {name} must be a mapping")
        return cls(
            provider=_required_text(value, "provider"),
            model=_required_text(value, "model"),
            wire_dialect=_required_text(value, "wire_dialect"),
            adapter_mode=_required_text(value, "adapter_mode"),
            sdk_package=_required_text(sdk, "package"),
            sdk_version=_required_text(sdk, "version"),
            base_url_fingerprint=_required_text(value, "base_url_fingerprint"),
            capabilities=dict(capabilities),
            retry=dict(retry),
        )

    def artifact_identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "wire_dialect": self.wire_dialect,
            "adapter_mode": self.adapter_mode,
            "sdk": {"package": self.sdk_package, "version": self.sdk_version},
            "base_url_fingerprint": self.base_url_fingerprint,
            "capabilities": dict(self.capabilities),
            "retry": dict(self.retry),
        }


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, Any] | str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    output: Any
    is_error: bool = False


@dataclass(frozen=True)
class ParsedResponse:
    """Provider response reduced to public, provider-neutral observations."""

    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    opaque_continuation: Mapping[str, Any] | None = None
    unknown_block_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawResponse:
    """Raw SDK response bytes plus the value the dialect plugin may inspect."""

    payload: Any
    raw_bytes: bytes

    @classmethod
    def from_json(cls, payload: Any) -> "RawResponse":
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return cls(payload=payload, raw_bytes=raw)


@dataclass(frozen=True)
class HttpAttempt:
    attempt: int
    status_code: int | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class TransportExchange:
    """One SDK operation and all HTTP attempts hidden underneath it."""

    response: RawResponse
    http_attempts: tuple[HttpAttempt, ...]
    sdk_retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.http_attempts:
            raise ValueError("transport exchange must report at least one HTTP attempt")
        if type(self.sdk_retry_count) is not int or self.sdk_retry_count < 0:
            raise ValueError("sdk_retry_count must be a non-negative integer")
        expected = list(range(1, len(self.http_attempts) + 1))
        observed = [item.attempt for item in self.http_attempts]
        if observed != expected:
            raise ValueError("HTTP attempt numbers must be contiguous and start at one")


class ProbeTransport(Protocol):
    def send(self, request: Mapping[str, Any]) -> TransportExchange:
        """Send one SDK operation without executing any Coda tool."""


class DialectPlugin(Protocol):
    name: str

    def build_request(
        self,
        case: ProbeCase,
        profile: ProbeProfile,
        tool_results: Sequence[ToolResult],
    ) -> Mapping[str, Any]:
        """Build the first request or the follow-up containing tool results."""

    def parse_response(self, response: RawResponse) -> ParsedResponse:
        """Reduce an SDK response without exposing private opaque contents."""


def load_probe_cases(path: str | Path) -> list[ProbeCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != CASE_SCHEMA_VERSION:
        raise ValueError(f"probe cases must use schema_version {CASE_SCHEMA_VERSION}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("probe cases must contain a non-empty cases list")
    normalized = [ProbeCase.from_mapping(item) for item in cases if isinstance(item, Mapping)]
    if len(normalized) != len(cases):
        raise ValueError("each probe case must be a mapping")
    ids = [case.id for case in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("probe case ids must be unique")
    return normalized


def load_probe_profile(path: str | Path) -> ProbeProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("probe profile must be a mapping")
    return ProbeProfile.from_mapping(payload)


def run_sdk_viability_probe(
    *,
    cases: Sequence[ProbeCase],
    profile: ProbeProfile,
    dialect: DialectPlugin,
    transport: ProbeTransport,
) -> dict[str, Any]:
    """Run deterministic probe cases and return a sanitized audit artifact."""

    if dialect.name != profile.wire_dialect:
        raise ValueError("dialect plugin name does not match profile wire_dialect")
    if not cases:
        raise ValueError("at least one probe case is required")

    eligible = profile.capabilities.get("native_tools") is True
    rows = [_run_case(case, profile, dialect, transport, eligible=eligible) for case in cases]
    all_calls = sum(row["tool_call_count"] for row in rows)
    matched = sum(row["matched_tool_result_count"] for row in rows)
    excluded_calls = sum(row["excluded_tool_call_count"] for row in rows)
    roundtrip_rows = [row for row in rows if row["roundtrip_expected"]]
    complete_roundtrips = sum(row["roundtrip_complete"] for row in roundtrip_rows)
    protocol_errors = [error for row in rows for error in row["protocol_errors"]]
    metadata = native_protocol_metadata(
        eligible=eligible,
        native_tool_call_observed=any(row["tool_call_count"] for row in rows),
        call_id_result_match=ratio(matched, all_calls - excluded_calls, excluded_calls),
        batch_completeness=ratio(complete_roundtrips, len(roundtrip_rows)),
        duplicate_call_after_result=sum(row["duplicate_call_after_result"] for row in rows),
        protocol_errors=protocol_errors,
        http_attempts=sum(row["http_attempt_count"] for row in rows),
        sdk_retry_count=sum(row["sdk_retry_count"] for row in rows),
        coda_retry_count=0,
        opaque_continuation=_aggregate_opaque(rows),
    )
    legacy = {
        "schema_version": PROBE_SCHEMA_VERSION,
        "case_schema": PROBE_CASE_SCHEMA,
        "summary": {
            "case_count": len(rows),
            "passed": sum(row["passed"] for row in rows),
            "failed": sum(not row["passed"] for row in rows),
        },
        "rows": rows,
    }
    return extend_artifact_contract(
        legacy,
        source={"harness": "coda.evaluation.sdk_probe", "mode": "sdk-native-viability"},
        profile=profile.artifact_identity(),
        native_protocol=metadata,
    )


def write_probe_artifact(path: str | Path, artifact: Mapping[str, Any]) -> None:
    sanitized = sanitize_public_artifact(dict(artifact))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _run_case(
    case: ProbeCase,
    profile: ProbeProfile,
    dialect: DialectPlugin,
    transport: ProbeTransport,
    *,
    eligible: bool,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": case.id,
        "kind": case.kind,
        "eligible": eligible,
        "passed": False,
        "turns": [],
        "tool_call_count": 0,
        "matched_tool_result_count": 0,
        "excluded_tool_call_count": 0,
        "invalid_argument_count": 0,
        "roundtrip_expected": case.kind in {"result_roundtrip", "invalid_args"},
        "roundtrip_complete": False,
        "duplicate_call_after_result": 0,
        "http_attempt_count": 0,
        "sdk_retry_count": 0,
        "protocol_errors": [],
        "opaque_continuations": [],
    }
    if not eligible:
        row["protocol_errors"].append({"code": "profile_ineligible", "detail": "native_tools not declared"})
        return row

    first = _exchange(case, profile, dialect, transport, ())
    _record_turn(row, first)
    parsed = first["parsed"]
    calls = parsed.tool_calls
    row["tool_call_count"] = len(calls)
    row["invalid_argument_count"] = sum(not _valid_arguments(call.arguments) for call in calls)
    duplicate_ids = len(calls) - len({call.call_id for call in calls})
    if duplicate_ids:
        row["protocol_errors"].append({"code": "duplicate_call_id", "count": duplicate_ids})

    if case.kind == "native_call":
        row["excluded_tool_call_count"] = len(calls)
        row["passed"] = _calls_match(case, calls) and duplicate_ids == 0
        return _public_row(row)

    if case.kind in {"result_roundtrip", "invalid_args"}:
        if not calls:
            row["protocol_errors"].append({"code": "missing_native_tool_call"})
            return _public_row(row)
        results = tuple(_tool_result(case, call) for call in calls)
        row["matched_tool_result_count"] = len(results)
        second = _exchange(case, profile, dialect, transport, results)
        _record_turn(row, second)
        follow_up = second["parsed"]
        result_ids = {result.call_id for result in results}
        row["duplicate_call_after_result"] = sum(
            call.call_id in result_ids for call in follow_up.tool_calls
        )
        row["roundtrip_complete"] = bool(follow_up.final_text) and not follow_up.tool_calls
        expected_invalid = case.kind == "invalid_args"
        row["passed"] = (
            _calls_match(case, calls)
            and row["roundtrip_complete"]
            and bool(row["invalid_argument_count"]) is expected_invalid
            and row["duplicate_call_after_result"] == 0
            and duplicate_ids == 0
        )
        return _public_row(row)

    row["passed"] = _final_matches(case, parsed)
    if case.kind == "opaque_block":
        row["passed"] = row["passed"] and bool(parsed.opaque_continuation)
    return _public_row(row)


def _exchange(
    case: ProbeCase,
    profile: ProbeProfile,
    dialect: DialectPlugin,
    transport: ProbeTransport,
    results: Sequence[ToolResult],
) -> dict[str, Any]:
    request = dialect.build_request(case, profile, results)
    if not isinstance(request, Mapping):
        raise TypeError("dialect build_request must return a mapping")
    exchange = transport.send(request)
    parsed = dialect.parse_response(exchange.response)
    if not isinstance(parsed, ParsedResponse):
        raise TypeError("dialect parse_response must return ParsedResponse")
    digest = hashlib.sha256(exchange.response.raw_bytes).hexdigest()
    attempts = [
        sanitize_public_artifact(
            {
                "attempt": attempt.attempt,
                "status_code": attempt.status_code,
                "error_type": attempt.error_type,
            }
        )
        for attempt in exchange.http_attempts
    ]
    return {
        "parsed": parsed,
        "artifact": {
            "raw_response": {"sha256": digest, "byte_count": len(exchange.response.raw_bytes)},
            "http_attempts": attempts,
            "sdk_retry_count": exchange.sdk_retry_count,
            "final_observed": parsed.final_text is not None,
            "tool_call_ids": [call.call_id for call in parsed.tool_calls],
            "tool_call_names": [call.name for call in parsed.tool_calls],
            "unknown_block_types": list(parsed.unknown_block_types),
        },
    }


def _record_turn(row: dict[str, Any], turn: Mapping[str, Any]) -> None:
    parsed: ParsedResponse = turn["parsed"]
    artifact = turn["artifact"]
    row["turns"].append(artifact)
    row["http_attempt_count"] += len(artifact["http_attempts"])
    row["sdk_retry_count"] += artifact["sdk_retry_count"]
    if parsed.opaque_continuation is not None:
        row["opaque_continuations"].append(sanitize_opaque_continuation(parsed.opaque_continuation))
    for block_type in parsed.unknown_block_types:
        row["protocol_errors"].append({"code": "unknown_block", "type": block_type})


def _public_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_public_artifact(dict(row))


def _tool_result(case: ProbeCase, call: ToolCall) -> ToolResult:
    valid = _valid_arguments(call.arguments)
    if valid:
        output = case.tool_result
    else:
        output = {"error": "invalid_arguments", "message": "arguments must be a JSON object"}
    return ToolResult(call_id=call.call_id, name=call.name, output=output, is_error=not valid)


def _valid_arguments(arguments: Mapping[str, Any] | str) -> bool:
    if isinstance(arguments, Mapping):
        return True
    if not isinstance(arguments, str):
        return False
    try:
        decoded = json.loads(arguments)
    except json.JSONDecodeError:
        return False
    return isinstance(decoded, Mapping)


def _calls_match(case: ProbeCase, calls: Sequence[ToolCall]) -> bool:
    if not calls:
        return False
    expected_name = case.expected.get("tool_name")
    if expected_name is None and case.tool is not None:
        expected_name = case.tool.get("name")
    return expected_name is None or all(call.name == expected_name for call in calls)


def _final_matches(case: ProbeCase, parsed: ParsedResponse) -> bool:
    if parsed.final_text is None or parsed.tool_calls:
        return False
    expected_text = case.expected.get("final_text")
    contains = case.expected.get("contains")
    if expected_text is not None and parsed.final_text != expected_text:
        return False
    if contains is not None and str(contains) not in parsed.final_text:
        return False
    return True


def _aggregate_opaque(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    continuations = [item for row in rows for item in row["opaque_continuations"]]
    if not continuations:
        return None
    material = json.dumps(continuations, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "hash": f"sha256:{hashlib.sha256(material).hexdigest()}",
        "type": "probe-continuation-summary",
        "count": sum(item["count"] for item in continuations),
    }


def _required_text(value: Mapping[str, Any], field_name: str) -> str:
    item = value.get(field_name)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return item.strip()
