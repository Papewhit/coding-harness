"""Provider-neutral native tool-calling conformance evaluation.

The evaluator consumes normalized event traces rather than provider SDK
objects.  A transport-specific runner may produce these events, but it must
not execute Pico tools itself.  Every input case produces a row, including
infrastructure failures, so later aggregates cannot silently improve their
denominator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from pico.evaluation.contracts import (
    ARTIFACT_CONTRACT_VERSION,
    native_protocol_metadata,
    profile_identity,
    ratio,
    sanitize_public_artifact,
)


CASESET_SCHEMA_VERSION = "pico-native-provider-cases-v1"
CASESET_SCHEMA_VERSION_V2 = "pico-native-provider-cases-v2"
ORACLE_SCHEMA_VERSION_V2 = "pico-native-provider-oracle-v2"
ADJUDICATION_SCHEMA_VERSION_V2 = "pico-native-provider-adjudication-v2"
ARTIFACT_SCHEMA_VERSION = "pico-native-provider-conformance-bundle-v2"
REQUIRED_SCENARIOS = (
    "final",
    "single_call",
    "unicode",
    "invalid_args_repair",
    "permission_denial",
    "multi_round_patch_verify",
    "unexpected_multi_call",
    "opaque_block_roundtrip",
)
TEXT_ENVELOPE_MARKERS = ("<tool>", "</tool>", "<final>", "</final>")
FROZEN_INPUT_HASHES = {
    "artifact_contract": "2add016fdfdd3ca9a0f80146097b470fbc7f8afd082a2799bd891b6b5c3ce8d1",
    "native_contract": "cf961b5f72b06a024abadaff48dbccb4520fb93a9a1665fc66742652db5a79eb",
    "tool_schema": "994a17e9f5c37d275f303176a67bf776324f972914d2b451df785b8205d7818f",
    "sdk_transport_decision": "9e404083771a23e4bb05e1b3a19b085156f062ac1c76fef43f6c2653a3cb1215",
}
NATIVE_SAFETY_EVIDENCE_VERSION = "pico-native-safety-chain-evidence-v1"
NATIVE_SAFETY_STAGES = (
    "validate",
    "repetition",
    "permission",
    "policy",
    "execute",
)
PRE_RUNTIME_REJECTION_ERROR_CODES = frozenset({"tool_choice_none_violation"})
SAFETY_ORACLE_ERROR_CODES = frozenset(
    {
        "safety_chain_bypass",
        "malformed_safety_chain_evidence",
        "unbound_safety_chain_evidence",
    }
)
STOCHASTIC_LIVE_PREDICATES = (
    "invalid_arguments_observed",
    "repair_after_invalid_arguments",
    "unexpected_multi_call_observed",
)

CaseRunner = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


def load_case_set(path: str | Path) -> dict[str, Any]:
    """Load and validate the frozen eight-case conformance manifest."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("native provider case set must be an object")
    normalized = deepcopy(dict(payload))
    _validate_case_set(normalized)
    return normalized


def run_native_provider_conformance(
    *,
    case_set: Mapping[str, Any],
    profile: Mapping[str, Any],
    runner: CaseRunner,
    case_ids: Sequence[str] | None = None,
    repetitions: int = 1,
    bindings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run selected cases and return rows plus auditable aggregate inputs."""

    _validate_case_set(case_set)
    if not isinstance(profile, Mapping):
        raise TypeError("profile must be an object")
    repetitions = _positive_int("repetitions", repetitions)
    selected = _select_cases(case_set["cases"], case_ids)
    rows: list[dict[str, Any]] = []
    for case in selected:
        for repetition in range(1, repetitions + 1):
            try:
                observation = runner(deepcopy(case), deepcopy(dict(profile)))
                if not isinstance(observation, Mapping):
                    raise TypeError("case runner must return an observation object")
                rows.append(
                    evaluate_native_provider_case(
                        case,
                        observation,
                        repetition=repetition,
                    )
                )
            except Exception as exc:  # Case-start failures remain in the denominator.
                rows.append(
                    evaluate_native_provider_case(
                        case,
                        {
                            "eligible": True,
                            "events": [],
                            "infrastructure_failure": _public_exception(exc),
                        },
                        repetition=repetition,
                    )
                )
    aggregate_input = [_aggregate_input(row) for row in rows]
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "run_status": "complete",
        "computability": "computable",
        "case_set": {
            "schema_version": case_set["schema_version"],
            "id": case_set["id"],
            "case_ids": [case["id"] for case in selected],
        },
        "repetitions": repetitions,
        "frozen_hashes": deepcopy(case_set["frozen_hashes"]),
        "bindings": sanitize_public_artifact(dict(bindings or {})),
        "profile": profile_identity(profile),
        "rows": rows,
        "aggregate_input": aggregate_input,
        "summary": aggregate_native_provider_rows(rows),
    }


def evaluate_native_provider_case(
    case: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    repetition: int = 1,
) -> dict[str, Any]:
    """Evaluate a single normalized event trace without provider-specific code."""

    case = deepcopy(dict(case))
    _validate_case(case)
    repetition = _positive_int("repetition", repetition)
    eligible = _strict_bool("eligible", observation.get("eligible", True))
    events = observation.get("events", [])
    if not isinstance(events, list) or not all(isinstance(event, Mapping) for event in events):
        raise ValueError("observation events must be a list of objects")

    calls: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    protocol_errors: list[dict[str, Any]] = []
    http_attempts: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    duplicate_after_result = 0
    text_envelope_seen = False
    final_text_seen = False
    continuation_received: list[dict[str, Any]] = []
    continuation_sent: list[dict[str, Any]] = []

    for event_index, event_value in enumerate(events):
        event = dict(event_value)
        event_type = event.get("type")
        if event_type == "http_attempt":
            http_attempts.append(
                sanitize_public_artifact(
                    {
                        "event_index": event_index,
                        "attempt": event.get("attempt", len(http_attempts) + 1),
                        "outcome": event.get("outcome", "observed"),
                    }
                )
            )
            continue
        if event_type == "protocol_error":
            protocol_errors.append(
                sanitize_public_artifact(
                    {
                        "event_index": event_index,
                        "code": event.get("code", "provider_protocol_error"),
                        "message": event.get("message", ""),
                    }
                )
            )
            continue
        if event_type == "request":
            descriptor = event.get("opaque_continuation")
            if descriptor is not None:
                continuation_sent.append(_continuation_descriptor(descriptor, event_index))
            continue
        if event_type == "assistant":
            text = event.get("text", "")
            if not isinstance(text, str):
                protocol_errors.append(_error(event_index, "non_string_text"))
                text = ""
            text_envelope_seen |= any(marker in text.lower() for marker in TEXT_ENVELOPE_MARKERS)
            raw_calls = event.get("tool_calls", [])
            if not isinstance(raw_calls, list):
                protocol_errors.append(_error(event_index, "invalid_tool_call_batch"))
                raw_calls = []
            batch_call_ids: list[str] = []
            batch_index = len(batches)
            for item in raw_calls:
                if not isinstance(item, Mapping):
                    protocol_errors.append(_error(event_index, "invalid_tool_call"))
                    continue
                call_id = item.get("call_id")
                name = item.get("name")
                if not isinstance(call_id, str) or not call_id:
                    protocol_errors.append(_error(event_index, "missing_call_id"))
                    continue
                if call_id in completed_ids:
                    duplicate_after_result += 1
                call_evidence = {
                    "call_id": call_id,
                    "name": name if isinstance(name, str) else "",
                    "batch_index": batch_index,
                    "event_index": event_index,
                }
                runtime_started = item.get("runtime_started")
                if type(runtime_started) is bool:
                    call_evidence["runtime_started"] = runtime_started
                calls.append(call_evidence)
                batch_call_ids.append(call_id)
            if raw_calls:
                batches.append({"batch_index": batch_index, "call_ids": batch_call_ids})
            else:
                final_text_seen |= bool(text)
            descriptor = event.get("opaque_continuation")
            if descriptor is not None:
                continuation_received.append(_continuation_descriptor(descriptor, event_index))
            continue
        if event_type == "tool_results":
            raw_results = event.get("results", [])
            if not isinstance(raw_results, list):
                protocol_errors.append(_error(event_index, "invalid_tool_results"))
                continue
            for item in raw_results:
                if not isinstance(item, Mapping):
                    protocol_errors.append(_error(event_index, "invalid_tool_result"))
                    continue
                call_id = item.get("call_id")
                if not isinstance(call_id, str) or not call_id:
                    protocol_errors.append(_error(event_index, "missing_result_call_id"))
                    continue
                result = {
                    "call_id": call_id,
                    "is_error": _strict_bool("tool result is_error", item.get("is_error", False)),
                    "error_code": _error_code(item),
                    "tool_status": _tool_status(item),
                    "tool_error_code": _error_code(item),
                    "execution_scope": _execution_scope(item),
                    "event_index": event_index,
                }
                results.append(result)
                completed_ids.add(call_id)
            continue
        if event_type == "infrastructure_failure":
            continue
        protocol_errors.append(_error(event_index, "unknown_event_type", str(event_type)))

    infrastructure_failure = observation.get("infrastructure_failure")
    event_failures = [event for event in events if event.get("type") == "infrastructure_failure"]
    if infrastructure_failure is None and event_failures:
        infrastructure_failure = dict(event_failures[-1])
        infrastructure_failure.pop("type", None)
    if infrastructure_failure is not None and not isinstance(infrastructure_failure, Mapping):
        raise ValueError("infrastructure_failure must be an object")

    call_counts = _counts(item["call_id"] for item in calls)
    result_counts = _counts(item["call_id"] for item in results)
    matched = sum(min(count, result_counts.get(call_id, 0)) for call_id, count in call_counts.items())
    match_denominator = max(len(calls), len(results))
    for call_id, count in call_counts.items():
        if count != 1:
            protocol_errors.append(_error(None, "duplicate_call_id", call_id))
        result_count = result_counts.get(call_id, 0)
        if result_count != 1:
            protocol_errors.append(_error(None, "call_result_cardinality", f"{call_id}:{result_count}"))
    for call_id in result_counts.keys() - call_counts.keys():
        protocol_errors.append(_error(None, "orphan_tool_result", call_id))

    safety_chain, safety_evidence, safety_errors = _evaluate_safety_chain(
        case_id=case["id"],
        repetition=repetition,
        calls=calls,
        results=results,
        audit=observation.get("audit"),
    )
    protocol_errors.extend(safety_errors)
    audit = observation.get("audit")
    audit_value = dict(audit) if isinstance(audit, Mapping) else {}
    unknown_block_loss_count = _non_negative_int(
        "unknown_block_loss_count",
        audit_value.get("unknown_block_loss_count", 0),
    )
    sdk_managed_execution_seen = any(
        audit_value.get(key) is True
        for key in (
            "sdk_tool_runner_used",
            "sdk_agent_runner_used",
            "sdk_managed_pico_tool_execution_used",
        )
    )
    if unknown_block_loss_count:
        protocol_errors.append(_error(None, "unknown_block_loss"))

    complete_batches = 0
    batch_evidence: list[dict[str, Any]] = []
    for batch in batches:
        ids = batch["call_ids"]
        complete = bool(ids) and all(call_counts[item] == 1 and result_counts.get(item) == 1 for item in ids)
        complete_batches += int(complete)
        batch_evidence.append({**batch, "complete": complete})

    case_errors = _case_expectation_errors(
        case,
        calls=calls,
        results=results,
        batches=batch_evidence,
        final_text_seen=final_text_seen,
        continuation_received=continuation_received,
        continuation_sent=continuation_sent,
        trace_text=json.dumps(events, ensure_ascii=False, sort_keys=True),
    )
    sdk_retry_count = _non_negative_int("sdk_retry_count", observation.get("sdk_retry_count", 0))
    pico_retry_count = _non_negative_int(
        "pico_retry_count", observation.get("pico_retry_count", 0)
    )
    if duplicate_after_result:
        protocol_errors.append(_error(None, "duplicate_call_after_result"))
    if text_envelope_seen:
        protocol_errors.append(_error(None, "text_protocol_envelope"))
    if sdk_retry_count:
        protocol_errors.append(_error(None, "implicit_sdk_retry"))
    if eligible and infrastructure_failure is None and not http_attempts:
        protocol_errors.append(_error(None, "missing_http_attempt_evidence"))
    protocol = native_protocol_metadata(
        eligible=eligible,
        native_tool_call_observed=bool(calls),
        call_id_result_match=ratio(matched, match_denominator),
        batch_completeness=ratio(complete_batches, len(batches)),
        duplicate_call_after_result=duplicate_after_result,
        protocol_errors=protocol_errors,
        http_attempts=len(http_attempts),
        sdk_retry_count=sdk_retry_count,
        pico_retry_count=pico_retry_count,
        opaque_continuation=_roundtrip_summary(continuation_received, continuation_sent),
    )
    if not eligible:
        status = "excluded"
    elif infrastructure_failure is not None:
        status = "infrastructure_failure"
    elif protocol_errors or case_errors:
        status = "failed"
    else:
        status = "passed"
    return sanitize_public_artifact(
        {
            "row_id": _row_id(case["id"], repetition),
            "case_id": case["id"],
            "repetition": repetition,
            "scenario": case["scenario"],
            "status": status,
            "eligible": eligible,
            "native_protocol": protocol,
            "call_evidence": calls,
            "result_evidence": results,
            "batch_evidence": batch_evidence,
            "http_attempt_evidence": http_attempts,
            "safety_chain": safety_chain,
            "safety_chain_evidence": safety_evidence,
            "safety_chain_bypass_count": sum(
                bool(entry["bypass"]) for entry in safety_chain
            ),
            "text_envelope_seen": text_envelope_seen,
            "implicit_sdk_retry_seen": sdk_retry_count > 0,
            "unknown_block_loss_count": unknown_block_loss_count,
            "sdk_managed_execution_seen": sdk_managed_execution_seen,
            "continuation_received": continuation_received,
            "continuation_sent": continuation_sent,
            "case_errors": case_errors,
            "infrastructure_failure": dict(infrastructure_failure)
            if infrastructure_failure is not None
            else None,
        }
    )


def aggregate_native_provider_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate conformance rows while preserving every status denominator."""

    statuses = ("passed", "failed", "infrastructure_failure", "excluded")
    counts = {status: sum(row.get("status") == status for row in rows) for status in statuses}
    eligible = [row for row in rows if row.get("eligible") is True]
    call_num = sum(row["native_protocol"]["call_id_result_match"]["numerator"] for row in eligible)
    call_den = sum(
        row["native_protocol"]["call_id_result_match"]["denominator"] for row in eligible
    )
    batch_num = sum(row["native_protocol"]["batch_completeness"]["numerator"] for row in eligible)
    batch_den = sum(
        row["native_protocol"]["batch_completeness"]["denominator"] for row in eligible
    )
    safety_total = sum(len(row.get("safety_chain", [])) for row in rows)
    safety_bypasses = sum(
        row.get("safety_chain_bypass_count", 0) for row in rows
    )
    return {
        "computability": "computable" if rows else "not_computable",
        "total": len(rows),
        **counts,
        "eligible": len(eligible),
        "conformance": ratio(counts["passed"], len(eligible)),
        "call_id_result_match": ratio(call_num, call_den),
        "batch_completeness": ratio(batch_num, batch_den),
        "duplicate_call_after_result": sum(
            row["native_protocol"]["duplicate_call_after_result"] for row in rows
        ),
        "protocol_error_count": sum(len(row["native_protocol"]["protocol_errors"]) for row in rows),
        "http_attempts": sum(row["native_protocol"]["http_attempts"] for row in rows),
        "text_envelope_seen_count": sum(bool(row["text_envelope_seen"]) for row in rows),
        "implicit_sdk_retry_seen": any(bool(row["implicit_sdk_retry_seen"]) for row in rows),
        "unknown_block_loss_count": sum(
            row.get("unknown_block_loss_count", 0) for row in rows
        ),
        "sdk_managed_execution_seen": any(
            bool(row.get("sdk_managed_execution_seen")) for row in rows
        ),
        "safety_chain_completeness": ratio(
            safety_total - safety_bypasses, safety_total
        ),
        "safety_chain_bypass_count": safety_bypasses,
    }


def adjudicate_native_provider_rows_v2(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_snapshot_sha: str,
    source_bindings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reinterpret immutable v1 rows under the Oracle v2 responsibility boundary.

    The returned object is an adjudication, never a replacement row set or a
    profile promotion. Runtime safety is computed once for the source snapshot;
    profile metrics exclude Runtime/oracle-owned evidence and stochastic case
    predicates.
    """

    if not isinstance(source_snapshot_sha, str) or not source_snapshot_sha:
        raise ValueError("source_snapshot_sha must be a non-empty string")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError("rows must be a sequence of objects")

    adjudicated_rows: list[dict[str, Any]] = []
    execution_denominator = 0
    execution_complete = 0
    pre_runtime_rejections = 0
    runtime_chain_violations = 0
    sdk_managed_execution_violations = 0
    profile_failed_rows = 0
    eligible_rows = 0
    call_num = 0
    call_den = 0
    batch_num = 0
    batch_den = 0
    unknown_block_loss_values: list[int] = []
    sdk_managed_execution_values: list[bool] = []
    binding_value = dict(source_bindings or {})

    for row_value in rows:
        if not isinstance(row_value, Mapping):
            raise ValueError("each native provider row must be an object")
        row = dict(row_value)
        native_protocol = row.get("native_protocol", {})
        if not isinstance(native_protocol, Mapping):
            raise ValueError("row native_protocol must be an object")
        eligible = row.get("eligible") is True
        eligible_rows += int(eligible)

        profile_errors = [
            sanitize_public_artifact(dict(error))
            for error in native_protocol.get("protocol_errors", [])
            if isinstance(error, Mapping)
            and error.get("code") not in SAFETY_ORACLE_ERROR_CODES
        ]
        profile_status = (
            "excluded"
            if not eligible
            else "failed"
            if profile_errors
            else "passed"
        )
        profile_failed_rows += int(profile_status == "failed")
        if "unknown_block_loss_count" in row:
            unknown_block_loss_values.append(
                _non_negative_int(
                    "unknown_block_loss_count",
                    row.get("unknown_block_loss_count"),
                )
            )
        if "sdk_managed_execution_seen" in row:
            sdk_managed_execution_values.append(
                row.get("sdk_managed_execution_seen") is True
            )
        if eligible:
            call_metric = native_protocol.get("call_id_result_match", {})
            batch_metric = native_protocol.get("batch_completeness", {})
            if isinstance(call_metric, Mapping):
                call_num += _non_negative_int(
                    "call match numerator", call_metric.get("numerator", 0)
                )
                call_den += _non_negative_int(
                    "call match denominator", call_metric.get("denominator", 0)
                )
            if isinstance(batch_metric, Mapping):
                batch_num += _non_negative_int(
                    "batch numerator", batch_metric.get("numerator", 0)
                )
                batch_den += _non_negative_int(
                    "batch denominator", batch_metric.get("denominator", 0)
                )

        calls = row.get("call_evidence", [])
        results = row.get("result_evidence", [])
        chains = row.get("safety_chain", [])
        evidence = row.get("safety_chain_evidence", [])
        if not all(
            isinstance(value, list) for value in (calls, results, chains, evidence)
        ):
            raise ValueError("row safety evidence fields must be lists")
        result_by_call = {
            str(result.get("call_id", "")): result
            for result in results
            if isinstance(result, Mapping)
        }
        chain_by_call = {
            str(chain.get("call_id", "")): chain
            for chain in chains
            if isinstance(chain, Mapping)
        }
        safety_calls: list[dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, Mapping):
                raise ValueError("call evidence entries must be objects")
            call_id = str(call.get("call_id", ""))
            tool_name = str(call.get("name", ""))
            result = result_by_call.get(call_id)
            chain = chain_by_call.get(call_id, {})
            stages = chain.get("stages", []) if isinstance(chain, Mapping) else []
            if not isinstance(stages, list):
                stages = []
            error_code = _historical_tool_error_code(result)
            tool_status = _historical_tool_status(result)
            runtime_started = call.get("runtime_started")
            if result is None:
                is_pre_runtime = runtime_started is False and not stages
            else:
                execution_scope = result.get("execution_scope")
                is_pre_runtime = (
                    execution_scope == "pre_runtime_rejection"
                    or (
                        execution_scope is None
                        and not stages
                        and error_code in PRE_RUNTIME_REJECTION_ERROR_CODES
                    )
                )
            if is_pre_runtime:
                classification = "pre_runtime_rejection"
                pre_runtime_rejections += 1
                complete = None
            else:
                classification = "runtime_execution"
                execution_denominator += 1
                complete = _valid_safety_chain_v2(
                    stages,
                    case_id=str(row.get("case_id", "")),
                    repetition=row.get("repetition"),
                    call_id=call_id,
                    tool_name=tool_name,
                    result=result,
                )
                execution_complete += int(complete)
                runtime_chain_violations += int(not complete)
            safety_calls.append(
                {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "classification": classification,
                    "runtime_chain_complete": complete,
                    "runtime_started": runtime_started
                    if type(runtime_started) is bool
                    else None,
                    "tool_status": tool_status,
                    "tool_error_code": error_code,
                }
            )

        adjudicated_rows.append(
            sanitize_public_artifact(
                {
                    "row_id": row.get("row_id"),
                    "case_id": row.get("case_id"),
                    "scenario": row.get("scenario"),
                    "source_status": row.get("status"),
                    "profile_status_v2": profile_status,
                    "profile_error_codes": [
                        error.get("code", "") for error in profile_errors
                    ],
                    "source_case_errors_retained_descriptive": deepcopy(
                        row.get("case_errors", [])
                    ),
                    "safety_calls": safety_calls,
                }
            )
        )

    if len(unknown_block_loss_values) == len(rows):
        unknown_block_loss_count: int | None = sum(
            unknown_block_loss_values
        )
        unknown_block_loss_evidence = "rows"
    elif type(
        binding_value.get("unknown_block_loss_count_from_accepted_handoff")
    ) is int:
        unknown_block_loss_count = _non_negative_int(
            "unknown_block_loss_count_from_accepted_handoff",
            binding_value["unknown_block_loss_count_from_accepted_handoff"],
        )
        unknown_block_loss_evidence = "accepted_handoff_binding"
    else:
        unknown_block_loss_count = None
        unknown_block_loss_evidence = "missing"

    if len(sdk_managed_execution_values) == len(rows):
        sdk_managed_execution_seen: bool | None = any(
            sdk_managed_execution_values
        )
        sdk_managed_execution_evidence = "rows"
    elif type(
        binding_value.get("sdk_managed_execution_from_accepted_handoff")
    ) is bool:
        sdk_managed_execution_seen = binding_value[
            "sdk_managed_execution_from_accepted_handoff"
        ]
        sdk_managed_execution_evidence = "accepted_handoff_binding"
    else:
        sdk_managed_execution_seen = None
        sdk_managed_execution_evidence = "missing"
    sdk_managed_execution_violations = int(
        sdk_managed_execution_seen is True
    )

    snapshot_status = (
        "not_computable"
        if sdk_managed_execution_seen is None
        else
        "blocked"
        if runtime_chain_violations or sdk_managed_execution_violations
        else "passed"
    )
    profile_status = (
        "not_computable"
        if (
            not rows
            or not eligible_rows
            or unknown_block_loss_count is None
        )
        else "ineligible"
        if profile_failed_rows or unknown_block_loss_count
        else "eligible"
    )
    return sanitize_public_artifact(
        {
            "schema_version": ADJUDICATION_SCHEMA_VERSION_V2,
            "oracle_version": ORACLE_SCHEMA_VERSION_V2,
            "source_snapshot_sha": source_snapshot_sha,
            "source_bindings": dict(source_bindings or {}),
            "historical_adjudication_only": True,
            "reselection_or_promotion_permitted": False,
            "metric_ownership": {
                "runtime_snapshot": [
                    "safety_chain_order_and_completeness",
                    "runtime_execution_bypass",
                    "sdk_or_harness_managed_tool_execution",
                ],
                "live_profile": [
                    "native_wire",
                    "call_result_cardinality",
                    "batch_completeness_if_observed",
                    "opaque_continuation_roundtrip",
                    "retry_counts",
                    "text_protocol_envelope",
                    "unknown_block_loss",
                ],
                "deterministic_only": list(STOCHASTIC_LIVE_PREDICATES),
            },
            "runtime_snapshot": {
                "status": snapshot_status,
                "execution_denominator": execution_denominator,
                "complete_execution_chains": execution_complete,
                "pre_runtime_rejection_count": pre_runtime_rejections,
                "runtime_chain_violation_count": runtime_chain_violations,
                "sdk_managed_execution_violation_count": (
                    sdk_managed_execution_violations
                ),
                "sdk_managed_execution_evidence": (
                    sdk_managed_execution_evidence
                ),
                "execute_completed_semantics": (
                    "tool implementation returned; operation outcome is read from "
                    "tool_status/tool_error_code"
                ),
            },
            "profile_metrics": {
                "status": profile_status,
                "eligible_rows": eligible_rows,
                "failed_rows": profile_failed_rows,
                "call_id_result_match": ratio(call_num, call_den),
                "batch_completeness": ratio(batch_num, batch_den),
                "duplicate_call_after_result_count": sum(
                    row.get("native_protocol", {}).get(
                        "duplicate_call_after_result", 0
                    )
                    for row in rows
                    if isinstance(row, Mapping)
                    and isinstance(row.get("native_protocol"), Mapping)
                ),
                "text_envelope_seen_count": sum(
                    bool(row.get("text_envelope_seen"))
                    for row in rows
                    if isinstance(row, Mapping)
                ),
                "implicit_sdk_retry_seen": any(
                    bool(row.get("implicit_sdk_retry_seen"))
                    for row in rows
                    if isinstance(row, Mapping)
                ),
                "unknown_block_loss_count": unknown_block_loss_count,
                "unknown_block_loss_evidence": (
                    unknown_block_loss_evidence
                ),
                "stochastic_predicates_required": False,
            },
            "rows": adjudicated_rows,
        }
    )


def preflight_failure_artifact(
    *,
    bindings: Mapping[str, Any],
    error: BaseException,
) -> dict[str, Any]:
    """Build a zero-row, non-computable run artifact for preflight failure."""

    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "run_status": "preflight_failure",
        "computability": "not_computable",
        "case_set": None,
        "repetitions": None,
        "frozen_hashes": {},
        "bindings": sanitize_public_artifact(dict(bindings)),
        "profile": None,
        "rows": [],
        "aggregate_input": [],
        "summary": {
            **aggregate_native_provider_rows([]),
            "preflight_failure": _public_exception(error),
        },
    }


def write_native_provider_bundle(
    artifact_dir: str | Path,
    artifact: Mapping[str, Any],
) -> dict[str, str]:
    """Atomically publish the versioned four-file conformance bundle."""

    destination = Path(artifact_dir)
    if destination.exists():
        raise FileExistsError(f"artifact directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-",
            dir=destination.parent,
        )
    )
    try:
        public = sanitize_public_artifact(dict(artifact))
        rows = public.get("rows")
        if not isinstance(rows, list):
            raise ValueError("artifact rows must be a list")
        for row in rows:
            _verify_row_safety_chain(row)
        rows_bytes = b"".join(_canonical_json_bytes(row) for row in rows)
        summary_bytes = _pretty_json_bytes(public.get("summary", {}))
        evidence = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "rows": [
                {
                    "row_id": row["row_id"],
                    "case_id": row["case_id"],
                    "repetition": row["repetition"],
                    "status": row["status"],
                    "sha256": _sha256(_canonical_json_bytes(row)),
                }
                for row in rows
            ],
            "entries": [
                {
                    "row_id": row["row_id"],
                    "case_id": row["case_id"],
                    "repetition": row["repetition"],
                    "call_id": entry["call_id"],
                    "tool_name": entry["tool_name"],
                    "result_error_code": entry["result_error_code"],
                    "stages": entry["stages"],
                    "complete": entry["complete"],
                    "bypass": entry["bypass"],
                    "sha256": _sha256(_canonical_json_bytes(entry)),
                }
                for row in rows
                for entry in row["safety_chain"]
            ],
        }
        evidence_bytes = _pretty_json_bytes(evidence)
        manifest = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact_contract_version": public.get("artifact_contract_version"),
            "run_status": public.get("run_status"),
            "computability": public.get("computability"),
            "case_set": public.get("case_set"),
            "repetitions": public.get("repetitions"),
            "frozen_hashes": public.get("frozen_hashes"),
            "bindings": public.get("bindings"),
            "profile": public.get("profile"),
            "row_count": len(rows),
            "files": {
                "rows.jsonl": _sha256(rows_bytes),
                "evidence-index.json": _sha256(evidence_bytes),
                "summary.json": _sha256(summary_bytes),
            },
        }
        payloads = {
            "manifest.json": _pretty_json_bytes(manifest),
            "rows.jsonl": rows_bytes,
            "evidence-index.json": evidence_bytes,
            "summary.json": summary_bytes,
        }
        for name, content in payloads.items():
            _write_bytes(staging / name, content)
        _verify_written_bundle(staging, payloads)
        os.rename(staging, destination)
        _verify_written_bundle(destination, payloads)
        return {name: _sha256(content) for name, content in payloads.items()}
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _validate_case_set(case_set: Mapping[str, Any]) -> None:
    schema_version = case_set.get("schema_version")
    if schema_version not in (CASESET_SCHEMA_VERSION, CASESET_SCHEMA_VERSION_V2):
        raise ValueError("unsupported native provider case-set schema")
    if not isinstance(case_set.get("id"), str) or not case_set["id"]:
        raise ValueError("case set id must be a non-empty string")
    cases = case_set.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("native provider conformance requires exactly eight cases")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each native provider case must be an object")
        _validate_case(case)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("native provider case ids must be unique")
    scenarios = tuple(case["scenario"] for case in cases)
    if scenarios != REQUIRED_SCENARIOS:
        raise ValueError("native provider cases must contain the frozen ordered scenario set")
    if case_set.get("frozen_hashes") != FROZEN_INPUT_HASHES:
        raise ValueError("native provider case set has incompatible frozen input hashes")
    if schema_version == CASESET_SCHEMA_VERSION_V2:
        oracle = case_set.get("oracle")
        if not isinstance(oracle, Mapping):
            raise ValueError("Oracle v2 case set requires an oracle object")
        if oracle.get("version") != ORACLE_SCHEMA_VERSION_V2:
            raise ValueError("unsupported native provider oracle version")
        if oracle.get("pre_runtime_rejection_error_codes") != sorted(
            PRE_RUNTIME_REJECTION_ERROR_CODES
        ):
            raise ValueError("Oracle v2 pre-Runtime rejection codes changed")
        if oracle.get("stochastic_live_predicates") != list(
            STOCHASTIC_LIVE_PREDICATES
        ):
            raise ValueError("Oracle v2 stochastic live predicates changed")
        if oracle.get("hash_basis") != "UTF-8 file bytes":
            raise ValueError("Oracle v2 hash basis must be explicit")


def _validate_case(case: Mapping[str, Any]) -> None:
    if not isinstance(case.get("id"), str) or not case["id"]:
        raise ValueError("case id must be a non-empty string")
    if case.get("scenario") not in REQUIRED_SCENARIOS:
        raise ValueError(f"unsupported native provider scenario: {case.get('scenario')}")
    if not isinstance(case.get("prompt"), str):
        raise ValueError("case prompt must be a string")
    expectations = case.get("expectations")
    if not isinstance(expectations, Mapping):
        raise ValueError("case expectations must be an object")
    if case.get("process_restart") is not None or expectations.get("process_restart") is not None:
        raise ValueError("process restart belongs to Gate N2, not native provider conformance")


def _select_cases(cases: list[Mapping[str, Any]], case_ids: Sequence[str] | None) -> list[dict[str, Any]]:
    indexed = {case["id"]: dict(case) for case in cases}
    if case_ids is None:
        return list(indexed.values())
    unknown = [case_id for case_id in case_ids if case_id not in indexed]
    if unknown:
        raise ValueError(f"unknown native provider cases: {', '.join(unknown)}")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("selected case ids must be unique")
    return [indexed[case_id] for case_id in case_ids]


def _case_expectation_errors(
    case: Mapping[str, Any],
    *,
    calls: list[dict[str, Any]],
    results: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    final_text_seen: bool,
    continuation_received: list[dict[str, Any]],
    continuation_sent: list[dict[str, Any]],
    trace_text: str,
) -> list[dict[str, Any]]:
    expected = case["expectations"]
    errors: list[dict[str, Any]] = []
    if expected.get("final_text") is True and not final_text_seen:
        errors.append({"code": "missing_final_text"})
    if len(calls) < expected.get("min_calls", 0):
        errors.append({"code": "too_few_calls"})
    if len(batches) < expected.get("min_batches", 0):
        errors.append({"code": "too_few_batches"})
    if batches and max(len(batch["call_ids"]) for batch in batches) < expected.get("min_batch_size", 0):
        errors.append({"code": "batch_too_small"})
    error_codes = {result["error_code"] for result in results if result["error_code"]}
    required_error = expected.get("required_error_code")
    if required_error is not None and required_error not in error_codes:
        errors.append({"code": "missing_expected_error", "expected": required_error})
    if expected.get("successful_result_after_error") is True:
        error_positions = [index for index, result in enumerate(results) if result["is_error"]]
        if not error_positions or not any(
            not result["is_error"] for result in results[error_positions[0] + 1 :]
        ):
            errors.append({"code": "missing_successful_repair"})
    if expected.get("opaque_roundtrip") is True:
        received_hashes = {item["hash"] for item in continuation_received}
        sent_hashes = {item["hash"] for item in continuation_sent}
        if not received_hashes or not received_hashes <= sent_hashes:
            errors.append({"code": "opaque_continuation_not_roundtripped"})
    required_fragments = expected.get("required_trace_fragments", [])
    if not isinstance(required_fragments, list) or not all(
        isinstance(fragment, str) for fragment in required_fragments
    ):
        raise ValueError("required_trace_fragments must be a list of strings")
    for fragment in required_fragments:
        if fragment not in trace_text:
            errors.append({"code": "missing_trace_fragment", "expected": fragment})
    return errors


def _aggregate_input(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row["row_id"],
        "case_id": row["case_id"],
        "repetition": row["repetition"],
        "status": row["status"],
        "eligible": row["eligible"],
        "native_protocol": deepcopy(row["native_protocol"]),
        "text_envelope_seen": row["text_envelope_seen"],
        "implicit_sdk_retry_seen": row["implicit_sdk_retry_seen"],
        "unknown_block_loss_count": row.get("unknown_block_loss_count", 0),
        "sdk_managed_execution_seen": row.get(
            "sdk_managed_execution_seen", False
        ),
        "safety_chain_bypass_count": row["safety_chain_bypass_count"],
        "infrastructure_failure": deepcopy(row["infrastructure_failure"]),
    }


def _evaluate_safety_chain(
    *,
    case_id: str,
    repetition: int,
    calls: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    audit: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    audit_value = dict(audit) if isinstance(audit, Mapping) else {}
    raw_evidence = audit_value.get("safety_chain_evidence", [])
    malformed = not isinstance(raw_evidence, list)
    if malformed:
        raw_evidence = []
    evidence: list[dict[str, Any]] = []
    for item in raw_evidence:
        if not isinstance(item, Mapping):
            malformed = True
            continue
        evidence.append(
            sanitize_public_artifact(
                {
                    "schema_version": item.get("schema_version", ""),
                    "case_id": item.get("case_id", ""),
                    "repetition": item.get("repetition"),
                    "call_id": item.get("call_id", ""),
                    "tool_name": item.get("tool_name", ""),
                    "stage": item.get("stage", ""),
                    "stage_index": item.get("stage_index"),
                    "outcome": item.get("outcome", ""),
                    "reason": item.get("reason", ""),
                    "sequence": item.get("sequence"),
                }
            )
        )

    result_by_call = {
        str(result.get("call_id", "")): result for result in results
    }
    call_ids = {
        str(call.get("call_id", "")) for call in calls if call.get("call_id")
    }
    errors: list[dict[str, Any]] = []
    chains: list[dict[str, Any]] = []
    sequences = [item.get("sequence") for item in evidence]
    globally_ordered = (
        all(type(sequence) is int and sequence >= 0 for sequence in sequences)
        and sequences == sorted(sequences)
        and len(sequences) == len(set(sequences))
    )
    for call in calls:
        call_id = str(call.get("call_id", ""))
        tool_name = str(call.get("name", ""))
        stages = [item for item in evidence if item["call_id"] == call_id]
        result = result_by_call.get(call_id)
        complete = globally_ordered and _valid_safety_chain(
            stages,
            case_id=case_id,
            repetition=repetition,
            call_id=call_id,
            tool_name=tool_name,
            result=result,
        )
        entry = {
            "schema_version": NATIVE_SAFETY_EVIDENCE_VERSION,
            "case_id": case_id,
            "repetition": repetition,
            "call_id": call_id,
            "tool_name": tool_name,
            "result_error_code": ""
            if result is None
            else str(result.get("error_code", "")),
            "stages": stages,
            "complete": complete,
            "bypass": not complete,
        }
        chains.append(entry)
        if not complete:
            errors.append(_error(None, "safety_chain_bypass", call_id))

    if malformed:
        errors.append(_error(None, "malformed_safety_chain_evidence"))
    for item in evidence:
        if (
            item["case_id"] != case_id
            or item["repetition"] != repetition
            or item["call_id"] not in call_ids
        ):
            errors.append(
                _error(None, "unbound_safety_chain_evidence", str(item["call_id"]))
            )
    return chains, evidence, errors


def _valid_safety_chain(
    stages: Sequence[Mapping[str, Any]],
    *,
    case_id: str,
    repetition: int,
    call_id: str,
    tool_name: str,
    result: Mapping[str, Any] | None,
) -> bool:
    if not stages or result is None:
        return False
    if any(
        item.get("schema_version") != NATIVE_SAFETY_EVIDENCE_VERSION
        or item.get("case_id") != case_id
        or item.get("repetition") != repetition
        or item.get("call_id") != call_id
        or item.get("tool_name") != tool_name
        for item in stages
    ):
        return False
    names = tuple(str(item.get("stage", "")) for item in stages)
    if names != NATIVE_SAFETY_STAGES[: len(names)]:
        return False
    if [item.get("stage_index") for item in stages] != list(
        range(1, len(stages) + 1)
    ):
        return False
    sequences = [item.get("sequence") for item in stages]
    if (
        not all(type(sequence) is int and sequence >= 0 for sequence in sequences)
        or sequences != sorted(sequences)
        or len(sequences) != len(set(sequences))
    ):
        return False
    if any(item.get("outcome") != "passed" for item in stages[:-1]):
        return False
    final = stages[-1]
    is_error = result.get("is_error") is True
    if final["stage"] == "execute":
        return (
            len(stages) == len(NATIVE_SAFETY_STAGES)
            and (
                (final.get("outcome") == "completed" and not is_error)
                or (final.get("outcome") == "failed" and is_error)
            )
        )
    return (
        len(stages) < len(NATIVE_SAFETY_STAGES)
        and final.get("outcome") == "rejected"
        and is_error
        and bool(result.get("error_code"))
    )


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _error(event_index: int | None, code: str, detail: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code}
    if event_index is not None:
        payload["event_index"] = event_index
    if detail:
        payload["detail"] = detail
    return payload


def _error_code(item: Mapping[str, Any]) -> str:
    value = item.get("error_code")
    if value is None and isinstance(item.get("output"), Mapping):
        error = item["output"].get("error")
        if isinstance(error, Mapping):
            value = error.get("code")
    return value if isinstance(value, str) else ""


def _tool_status(item: Mapping[str, Any]) -> str:
    value = item.get("tool_status")
    if isinstance(value, str) and value:
        return value
    return "error" if item.get("is_error") is True else "ok"


def _execution_scope(item: Mapping[str, Any]) -> str:
    value = item.get("execution_scope")
    if value in {"runtime_execution", "pre_runtime_rejection"}:
        return str(value)
    if _error_code(item) in PRE_RUNTIME_REJECTION_ERROR_CODES:
        return "pre_runtime_rejection"
    return "runtime_execution"


def _historical_tool_error_code(result: Mapping[str, Any] | None) -> str:
    if not isinstance(result, Mapping):
        return ""
    value = result.get("tool_error_code", result.get("error_code", ""))
    return value if isinstance(value, str) else ""


def _historical_tool_status(result: Mapping[str, Any] | None) -> str:
    if not isinstance(result, Mapping):
        return "missing"
    value = result.get("tool_status")
    if isinstance(value, str) and value:
        return value
    return "error" if result.get("is_error") is True else "ok"


def _valid_safety_chain_v2(
    stages: Sequence[Mapping[str, Any]],
    *,
    case_id: str,
    repetition: Any,
    call_id: str,
    tool_name: str,
    result: Mapping[str, Any] | None,
) -> bool:
    if not stages or result is None:
        return False
    if any(
        item.get("schema_version") != NATIVE_SAFETY_EVIDENCE_VERSION
        or item.get("case_id") != case_id
        or item.get("repetition") != repetition
        or item.get("call_id") != call_id
        or item.get("tool_name") != tool_name
        for item in stages
    ):
        return False
    names = tuple(str(item.get("stage", "")) for item in stages)
    if names != NATIVE_SAFETY_STAGES[: len(names)]:
        return False
    if [item.get("stage_index") for item in stages] != list(
        range(1, len(stages) + 1)
    ):
        return False
    sequences = [item.get("sequence") for item in stages]
    if (
        not all(type(sequence) is int and sequence >= 0 for sequence in sequences)
        or sequences != sorted(sequences)
        or len(sequences) != len(set(sequences))
    ):
        return False
    if any(item.get("outcome") != "passed" for item in stages[:-1]):
        return False
    final = stages[-1]
    if final["stage"] == "execute":
        return (
            len(stages) == len(NATIVE_SAFETY_STAGES)
            and final.get("outcome") in {"completed", "failed"}
        )
    return (
        len(stages) < len(NATIVE_SAFETY_STAGES)
        and final.get("outcome") == "rejected"
        and result.get("is_error") is True
        and bool(_historical_tool_error_code(result))
    )


def _continuation_descriptor(value: Any, event_index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("opaque continuation descriptor must be an object")
    return {
        "hash": value.get("hash", ""),
        "type": value.get("type", ""),
        "count": _non_negative_int("opaque continuation count", value.get("count", 0)),
        "event_index": event_index,
    }


def _roundtrip_summary(received: list[dict[str, Any]], sent: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = {item["hash"] for item in received} & {item["hash"] for item in sent}
    types = {item["type"] for item in received if item["hash"] in hashes}
    return {
        "hash": sorted(hashes)[0] if len(hashes) == 1 else "",
        "type": sorted(types)[0] if len(types) == 1 else "multiple" if types else "",
        "count": len(hashes),
    }


def _strict_bool(name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _non_negative_int(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(name: str, value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _row_id(case_id: str, repetition: int) -> str:
    return f"{case_id}::r{repetition:03d}"


def _public_exception(error: BaseException) -> dict[str, str]:
    return {
        "type": type(error).__name__,
        "code": "infrastructure_failure",
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            sanitize_public_artifact(value),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            sanitize_public_artifact(value),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_bytes(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _verify_written_bundle(
    directory: Path,
    expected_payloads: Mapping[str, bytes],
) -> None:
    actual = {
        name: (directory / name).read_bytes() for name in expected_payloads
    }
    if actual != dict(expected_payloads):
        raise ValueError("native provider bundle bytes changed after write")
    manifest = json.loads(actual["manifest.json"])
    summary = json.loads(actual["summary.json"])
    evidence = json.loads(actual["evidence-index.json"])
    rows = [
        json.loads(line)
        for line in actual["rows.jsonl"].decode("utf-8").splitlines()
        if line
    ]
    if not all(isinstance(value, dict) for value in (manifest, summary, evidence)):
        raise ValueError("native provider JSON files must contain objects")
    if manifest.get("row_count") != len(rows):
        raise ValueError("native provider manifest row count mismatch")
    for row in rows:
        _verify_row_safety_chain(row)
    computed_summary = aggregate_native_provider_rows(rows)
    if any(summary.get(key) != value for key, value in computed_summary.items()):
        raise ValueError("native provider summary aggregate mismatch")
    expected_hashes = {
        name: _sha256(actual[name])
        for name in ("rows.jsonl", "evidence-index.json", "summary.json")
    }
    if manifest.get("files") != expected_hashes:
        raise ValueError("native provider manifest file hash mismatch")
    row_index = evidence.get("rows")
    if not isinstance(row_index, list) or len(row_index) != len(rows):
        raise ValueError("native provider evidence row index mismatch")
    for row, item in zip(rows, row_index, strict=True):
        if (
            item.get("row_id") != row.get("row_id")
            or item.get("case_id") != row.get("case_id")
            or item.get("repetition") != row.get("repetition")
            or item.get("sha256") != _sha256(_canonical_json_bytes(row))
        ):
            raise ValueError("native provider evidence row hash mismatch")
    entries = evidence.get("entries")
    expected_entries = [
        (row, entry) for row in rows for entry in row.get("safety_chain", [])
    ]
    if not isinstance(entries, list) or len(entries) != len(expected_entries):
        raise ValueError("native provider safety evidence index mismatch")
    for indexed, (row, chain) in zip(entries, expected_entries, strict=True):
        if (
            indexed.get("row_id") != row.get("row_id")
            or indexed.get("case_id") != row.get("case_id")
            or indexed.get("repetition") != row.get("repetition")
            or indexed.get("call_id") != chain.get("call_id")
            or indexed.get("stages") != chain.get("stages")
            or indexed.get("complete") != chain.get("complete")
            or indexed.get("bypass") != chain.get("bypass")
            or indexed.get("sha256") != _sha256(_canonical_json_bytes(chain))
        ):
            raise ValueError("native provider safety evidence hash mismatch")


def _verify_row_safety_chain(row: Mapping[str, Any]) -> None:
    calls = row.get("call_evidence", [])
    results = row.get("result_evidence", [])
    chains = row.get("safety_chain", [])
    evidence = row.get("safety_chain_evidence", [])
    if not all(
        isinstance(value, list) for value in (calls, results, chains, evidence)
    ):
        raise ValueError("native provider row safety evidence must be lists")
    if len(chains) != len(calls):
        raise ValueError("native provider safety chain call cardinality mismatch")
    result_by_call = {
        str(result.get("call_id", "")): result
        for result in results
        if isinstance(result, Mapping)
    }
    sequences = [
        item.get("sequence") for item in evidence if isinstance(item, Mapping)
    ]
    globally_ordered = (
        all(type(sequence) is int and sequence >= 0 for sequence in sequences)
        and sequences == sorted(sequences)
        and len(sequences) == len(set(sequences))
    )
    bypass_count = 0
    for call, chain in zip(calls, chains, strict=True):
        if not isinstance(call, Mapping) or not isinstance(chain, Mapping):
            raise ValueError("native provider safety chain entries must be objects")
        call_id = str(call.get("call_id", ""))
        stages = [
            item
            for item in evidence
            if isinstance(item, Mapping) and item.get("call_id") == call_id
        ]
        valid = (
            chain.get("case_id") == row.get("case_id")
            and chain.get("repetition") == row.get("repetition")
            and chain.get("call_id") == call_id
            and chain.get("tool_name") == call.get("name")
            and chain.get("stages") == stages
            and globally_ordered
            and _valid_safety_chain(
                stages,
                case_id=str(row.get("case_id", "")),
                repetition=row.get("repetition"),
                call_id=call_id,
                tool_name=str(call.get("name", "")),
                result=result_by_call.get(call_id),
            )
        )
        if chain.get("complete") is not valid or chain.get("bypass") is valid:
            raise ValueError("native provider safety chain verdict mismatch")
        bypass_count += int(not valid)
    if row.get("safety_chain_bypass_count") != bypass_count:
        raise ValueError("native provider safety chain bypass aggregate mismatch")
    error_codes = {
        error.get("code")
        for error in row.get("native_protocol", {}).get("protocol_errors", [])
        if isinstance(error, Mapping)
    }
    if bypass_count and "safety_chain_bypass" not in error_codes:
        raise ValueError("native provider safety bypass is not a protocol error")


__all__ = [
    "ADJUDICATION_SCHEMA_VERSION_V2",
    "ARTIFACT_SCHEMA_VERSION",
    "CASESET_SCHEMA_VERSION",
    "CASESET_SCHEMA_VERSION_V2",
    "FROZEN_INPUT_HASHES",
    "NATIVE_SAFETY_EVIDENCE_VERSION",
    "NATIVE_SAFETY_STAGES",
    "ORACLE_SCHEMA_VERSION_V2",
    "PRE_RUNTIME_REJECTION_ERROR_CODES",
    "REQUIRED_SCENARIOS",
    "STOCHASTIC_LIVE_PREDICATES",
    "adjudicate_native_provider_rows_v2",
    "aggregate_native_provider_rows",
    "evaluate_native_provider_case",
    "load_case_set",
    "preflight_failure_artifact",
    "run_native_provider_conformance",
    "write_native_provider_bundle",
]
