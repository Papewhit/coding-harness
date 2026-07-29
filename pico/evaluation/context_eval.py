"""Deterministic evaluation of structured context assets in ``ModelRequest``.

The evaluator consumes explicit public request surfaces alongside Pico's
provider-neutral request contract.  Opaque continuation payloads are never
inspected; only the continuation's public type and stable hash are recorded.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pico.evaluation.contracts import sanitize_public_artifact
from pico.providers.contracts import (
    ModelRequest,
    ProviderContinuation,
    ToolCallResult,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
)


CASES_SCHEMA_VERSION = "pico-context-asset-cases-v1"
FRAGMENT_SCHEMA_VERSION = "pico-context-asset-fragment-v1"
ARTIFACT_SCHEMA_VERSION = "pico-context-asset-artifact-v1"
CONTRACT_VERSION = "pico-context-asset-contract-v1"
PUBLIC_SURFACES = ("system_text", "messages", "tools")
ASSET_RECORD_FIELDS = frozenset(
    {
        "asset_id",
        "producer",
        "activation_state",
        "surface",
        "priority",
        "floor_satisfied",
        "raw_size",
        "rendered_size",
        "content_hash",
        "drop_action",
        "metadata",
    }
)


def load_cases(path: str | Path) -> dict[str, Any]:
    """Load and validate a context-asset case manifest."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_cases(payload)
    return payload


def validate_cases(payload: Mapping[str, Any]) -> None:
    """Validate the stable, fixture-owned part of the evaluator input."""

    if not isinstance(payload, Mapping):
        raise ValueError("case manifest must be an object")
    if payload.get("schema_version") != CASES_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {CASES_SCHEMA_VERSION!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each case must be an object")
        case_id = _required_string(case, "id", "case")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        _request_from_mapping(_required_mapping(case, "model_request", f"case {case_id}"))
        surfaces = _required_mapping(case, "surfaces", f"case {case_id}")
        if not isinstance(surfaces.get("system_text"), str):
            raise ValueError(f"case {case_id} system_text must be a string")
        if not isinstance(surfaces.get("messages"), list):
            raise ValueError(f"case {case_id} messages must be a list")
        oracle = _required_mapping(case, "oracle", f"case {case_id}")
        _required_string(oracle, "current_request", f"case {case_id} oracle")
        assets = oracle.get("assets")
        if not isinstance(assets, list):
            raise ValueError(f"case {case_id} oracle assets must be a list")
        asset_ids: set[str] = set()
        for asset in assets:
            if not isinstance(asset, Mapping):
                raise ValueError(f"case {case_id} assets must contain objects")
            asset_id = _required_string(asset, "asset_id", f"case {case_id} asset")
            if asset_id in asset_ids:
                raise ValueError(f"case {case_id} has duplicate asset id: {asset_id}")
            asset_ids.add(asset_id)
            _required_string(asset, "sentinel", f"case {case_id} asset {asset_id}")
            if asset.get("disposition", "retain") not in {"retain", "drop", "pointer"}:
                raise ValueError(f"case {case_id} asset {asset_id} has invalid disposition")
            expected_surface = asset.get("surface")
            if expected_surface is not None and expected_surface not in PUBLIC_SURFACES:
                raise ValueError(f"case {case_id} asset {asset_id} has invalid surface")


def select_cases(
    cases: Sequence[Mapping[str, Any]], case_ids: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """Select cases in manifest order and reject unknown identifiers."""

    selected_ids = list(dict.fromkeys(case_ids or []))
    if not selected_ids:
        return [dict(case) for case in cases]
    available = {str(case.get("id")) for case in cases}
    unknown = set(selected_ids) - available
    if unknown:
        raise ValueError(f"unknown case ids: {', '.join(sorted(unknown))}")
    selected = set(selected_ids)
    return [dict(case) for case in cases if case.get("id") in selected]


def evaluate_context_case(
    case: Mapping[str, Any],
    request: ModelRequest,
    *,
    workspace_root: str | Path,
    repetition: int = 1,
) -> dict[str, Any]:
    """Evaluate one captured request against its sentinel oracle."""

    case_id = _required_string(case, "id", "case")
    if not isinstance(request, ModelRequest):
        raise TypeError("request must be a ModelRequest")
    if type(repetition) is not int or repetition < 1:
        raise ValueError("repetition must be a positive integer")
    surfaces = _required_mapping(case, "surfaces", f"case {case_id}")
    system_text = surfaces.get("system_text")
    messages = surfaces.get("messages")
    asset_records = surfaces.get("asset_records", [])
    if not isinstance(system_text, str) or not isinstance(messages, list):
        raise ValueError(f"case {case_id} has invalid public surfaces")
    if not isinstance(asset_records, list) or not all(
        isinstance(item, Mapping) for item in asset_records
    ):
        raise ValueError(f"case {case_id} asset_records must be a list of objects")
    oracle = _required_mapping(case, "oracle", f"case {case_id}")

    surface_text = {
        "system_text": system_text,
        "messages": _canonical_json(messages),
        "tools": _canonical_json([tool.to_dict() for tool in request.tools]),
    }
    current_request_gate = _current_request_gate(messages, str(oracle["current_request"]))
    records_by_id = _index_asset_records(asset_records)
    asset_results = [
        _evaluate_asset(
            asset,
            surface_text=surface_text,
            record=records_by_id.get(str(asset.get("asset_id"))),
            workspace_root=Path(workspace_root),
        )
        for asset in oracle.get("assets", [])
    ]
    duplication_findings = [
        {
            "asset_id": item["asset_id"],
            "occurrences": item["occurrences"],
            "surfaces": item["surfaces_present"],
        }
        for item in asset_results
        if not item["checks"]["duplication"]
    ]
    tool_metrics = _tool_metrics(request.tools, system_text)
    tool_gate = {
        "passed": tool_metrics["system_text_tool_definition_match_count"] == 0,
        **tool_metrics,
    }
    hard_gates = {
        "current_request_preservation": current_request_gate,
        "tool_schema_separation": tool_gate,
    }
    failures = [
        f"asset:{item['asset_id']}:{check}"
        for item in asset_results
        for check, passed in item["checks"].items()
        if not passed
    ]
    failures.extend(f"hard_gate:{name}" for name, gate in hard_gates.items() if not gate["passed"])
    passed = not failures
    continuation_evidence = _continuation_evidence(request.continuation)
    return {
        "case_id": case_id,
        "repetition": repetition,
        "status": "pass" if passed else "fail",
        "passed": passed,
        "contract_version": CONTRACT_VERSION,
        "request_id": str(case.get("request_id", case_id)),
        "surface_hashes": {
            surface: _sha256_text(text) for surface, text in surface_text.items()
        },
        "activated_asset_ids": [
            item["asset_id"] for item in asset_results if item["activated"]
        ],
        "asset_records": asset_results,
        "duplication_findings": duplication_findings,
        "native_turn_status": surfaces.get("native_turn_status", "not_observed"),
        "continuation_evidence": continuation_evidence,
        "tool_metrics": tool_metrics,
        "hard_gates": hard_gates,
        "failures": failures,
    }


def run_context_asset_evaluation(
    cases_path: str | Path,
    *,
    workspace_root: str | Path,
    artifact_path: str | Path | None = None,
    case_ids: Iterable[str] | None = None,
    shard_id: str = "local",
    repetition: int = 1,
) -> dict[str, Any]:
    """Evaluate selected serialized request captures and optionally write a fragment."""

    manifest = load_cases(cases_path)
    selected = select_cases(manifest["cases"], case_ids)
    rows = [
        evaluate_context_case(
            case,
            _request_from_mapping(case["model_request"]),
            workspace_root=workspace_root,
            repetition=repetition,
        )
        for case in selected
    ]
    fragment = {
        "schema_version": FRAGMENT_SCHEMA_VERSION,
        "shard_id": shard_id,
        "case_schema_version": manifest["schema_version"],
        "selected_case_ids": [case["id"] for case in selected],
        "rows": rows,
        "summary": summarize_rows(rows),
    }
    if artifact_path is not None:
        _write_json(artifact_path, fragment)
    return fragment


def merge_fragments(fragments: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Merge shard fragments deterministically and reject overlapping rows."""

    rows: list[dict[str, Any]] = []
    shard_ids: set[str] = set()
    seen: set[tuple[str, int]] = set()
    for fragment in fragments:
        if fragment.get("schema_version") != FRAGMENT_SCHEMA_VERSION:
            raise ValueError("cannot merge an incompatible context-asset fragment")
        shard_id = _required_string(fragment, "shard_id", "fragment")
        if shard_id in shard_ids:
            raise ValueError(f"duplicate shard id: {shard_id}")
        shard_ids.add(shard_id)
        fragment_rows = fragment.get("rows")
        if not isinstance(fragment_rows, list):
            raise ValueError(f"shard {shard_id} rows must be a list")
        for raw_row in fragment_rows:
            if not isinstance(raw_row, Mapping):
                raise ValueError(f"shard {shard_id} contains a non-object row")
            key = (str(raw_row.get("case_id", "")), raw_row.get("repetition"))
            if not key[0] or type(key[1]) is not int:
                raise ValueError(f"shard {shard_id} row identity is invalid")
            if key in seen:
                raise ValueError(f"duplicate case repetition: {key[0]}#{key[1]}")
            seen.add(key)
            rows.append(dict(raw_row))
    rows.sort(key=lambda row: (row["case_id"], row["repetition"]))
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "shard_ids": sorted(shard_ids),
        "rows": rows,
        "summary": summarize_rows(rows),
    }


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return auditable pass/failure counts for rows."""

    total = len(rows)
    passed = sum(row.get("passed") is True for row in rows)
    failures = Counter(failure for row in rows for failure in row.get("failures", []))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else None,
        "failure_counts": dict(sorted(failures.items())),
    }


def _evaluate_asset(
    oracle: Mapping[str, Any],
    *,
    surface_text: Mapping[str, str],
    record: Mapping[str, Any] | None,
    workspace_root: Path,
) -> dict[str, Any]:
    asset_id = str(oracle["asset_id"])
    sentinel = str(oracle["sentinel"])
    disposition = str(oracle.get("disposition", "retain"))
    occurrences = {
        surface: text.count(sentinel) for surface, text in surface_text.items()
    }
    surfaces_present = [surface for surface, count in occurrences.items() if count]
    total_occurrences = sum(occurrences.values())
    expected_surface = oracle.get("surface")
    expected_active = oracle.get("activated", True)
    activated = total_occurrences > 0 or bool(
        record and record.get("activation_state") in {True, "active", "activated"}
    )
    retention_ok = {
        "retain": total_occurrences == 1,
        "drop": total_occurrences == 0 and bool(record and record.get("drop_action")),
        "pointer": total_occurrences == 0,
    }[disposition]
    if disposition == "pointer" and not surfaces_present:
        attribution_ok = expected_surface is None or bool(
            record and record.get("surface") == expected_surface
        )
    else:
        attribution_ok = expected_surface is None or surfaces_present == [expected_surface]
    expected_count = oracle.get("expected_occurrences", 1 if disposition == "retain" else 0)
    duplication_ok = type(expected_count) is int and total_occurrences == expected_count
    activation_ok = type(expected_active) is bool and activated is expected_active
    metadata_ok, metadata_details = _metadata_check(oracle, record)
    pointer_result = _pointer_check(oracle, record, workspace_root)
    checks = {
        "activation": activation_ok,
        "attribution": attribution_ok,
        "retention_or_drop": retention_ok,
        "duplication": duplication_ok,
        "metadata": metadata_ok,
        "pointer": pointer_result["passed"],
    }
    return {
        "asset_id": asset_id,
        "sentinel_sha256": _sha256_text(sentinel),
        "activated": activated,
        "disposition": disposition,
        "expected_surface": expected_surface,
        "surfaces_present": surfaces_present,
        "occurrences": occurrences,
        "checks": checks,
        "record": _public_asset_record(record),
        "metadata_check": metadata_details,
        "pointer_check": pointer_result,
        "passed": all(checks.values()),
    }


def _current_request_gate(messages: Sequence[Any], expected: str) -> dict[str, Any]:
    exact_indices = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, Mapping)
        and message.get("role") == "user"
        and message.get("content") == expected
    ]
    rendered = [
        message.get("content")
        for message in messages
        if isinstance(message, Mapping) and message.get("role") == "user"
    ]
    return {
        "passed": len(exact_indices) == 1,
        "request_content_hash": _sha256_text(expected),
        "request_rendered_hash": _sha256_text(expected) if exact_indices else None,
        "message_indices": exact_indices,
        "user_message_count": len(rendered),
        "drop_action": "none" if exact_indices else "missing_or_modified",
    }


def _metadata_check(
    oracle: Mapping[str, Any], record: Mapping[str, Any] | None
) -> tuple[bool, dict[str, Any]]:
    if record is None:
        return False, {"missing_record": True, "missing_fields": sorted(ASSET_RECORD_FIELDS)}
    missing_fields = sorted(ASSET_RECORD_FIELDS - record.keys())
    metadata = record.get("metadata")
    required_keys = oracle.get("required_metadata", [])
    expected_metadata = oracle.get("metadata", {})
    valid_requirements = isinstance(required_keys, list) and all(
        isinstance(key, str) for key in required_keys
    )
    if not isinstance(metadata, Mapping):
        missing_keys = list(required_keys) if valid_requirements else []
        mismatches = sorted(str(key) for key in expected_metadata) if isinstance(expected_metadata, Mapping) else []
        return False, {
            "missing_record": False,
            "missing_fields": missing_fields,
            "missing_keys": missing_keys,
            "mismatches": mismatches,
        }
    missing_keys = [key for key in required_keys if key not in metadata] if valid_requirements else []
    mismatches = []
    if isinstance(expected_metadata, Mapping):
        mismatches = [key for key, value in expected_metadata.items() if metadata.get(key) != value]
    else:
        valid_requirements = False
    passed = not missing_fields and valid_requirements and not missing_keys and not mismatches
    return passed, {
        "missing_record": False,
        "missing_fields": missing_fields,
        "missing_keys": missing_keys,
        "mismatches": mismatches,
    }


def _pointer_check(
    oracle: Mapping[str, Any], record: Mapping[str, Any] | None, workspace_root: Path
) -> dict[str, Any]:
    if oracle.get("disposition", "retain") != "pointer":
        return {"required": False, "passed": True}
    metadata = record.get("metadata") if record else None
    target = metadata.get("target_path") if isinstance(metadata, Mapping) else None
    expected_hash = metadata.get("content_hash") if isinstance(metadata, Mapping) else None
    if not isinstance(target, str) or not target:
        return {"required": True, "passed": False, "reason": "target_path_missing"}
    root = workspace_root.resolve()
    candidate = (root / target).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return {"required": True, "passed": False, "reason": "target_outside_workspace"}
    if not candidate.is_file():
        return {"required": True, "passed": False, "reason": "target_not_file", "target_path": target}
    actual_hash = f"sha256:{hashlib.sha256(candidate.read_bytes()).hexdigest()}"
    normalized_expected = _normalize_sha256(expected_hash)
    return {
        "required": True,
        "passed": normalized_expected == actual_hash,
        "target_path": target.replace("\\", "/"),
        "content_hash": actual_hash,
        "hash_matches": normalized_expected == actual_hash,
    }


def _tool_metrics(tools: Sequence[ToolDefinition], system_text: str) -> dict[str, Any]:
    serialized = [_canonical_json(tool.to_dict()) for tool in tools]
    schema_serialized = [_canonical_json(tool.input_schema) for tool in tools]
    matches = sum(
        definition in system_text or schema in system_text
        for definition, schema in zip(serialized, schema_serialized)
    )
    catalog = _canonical_json([tool.to_dict() for tool in tools])
    return {
        "tool_count": len(tools),
        "tool_catalog_hash": _sha256_text(catalog),
        "tools_utf8_bytes": len(catalog.encode("utf-8")),
        "system_text_utf8_bytes": len(system_text.encode("utf-8")),
        "system_text_tool_definition_match_count": matches,
    }


def _continuation_evidence(continuation: ProviderContinuation | None) -> dict[str, Any] | None:
    if continuation is None:
        return None
    return {
        "type": type(continuation).__name__,
        "count": 1,
        "hash": continuation.stable_hash(),
    }


def _request_from_mapping(payload: Mapping[str, Any]) -> ModelRequest:
    tools_payload = payload.get("tools", [])
    results_payload = payload.get("tool_results", [])
    if not isinstance(tools_payload, list) or not isinstance(results_payload, list):
        raise ValueError("model_request tools and tool_results must be lists")
    tools = [
        ToolDefinition(
            name=_required_string(tool, "name", "tool"),
            description=str(tool.get("description", "")),
            input_schema=_required_mapping(tool, "input_schema", "tool"),
        )
        for tool in tools_payload
        if isinstance(tool, Mapping)
    ]
    if len(tools) != len(tools_payload):
        raise ValueError("model_request tools must contain objects")
    results = [
        ToolCallResult(
            call_id=_required_string(result, "call_id", "tool result"),
            output=result.get("output"),
            is_error=result.get("is_error", False),
        )
        for result in results_payload
        if isinstance(result, Mapping)
    ]
    if len(results) != len(results_payload):
        raise ValueError("model_request tool_results must contain objects")
    choice_payload = payload.get("tool_choice", {})
    if not isinstance(choice_payload, Mapping):
        raise ValueError("model_request tool_choice must be an object")
    choice = ToolChoice(
        mode=ToolChoiceMode(choice_payload.get("mode", "auto")),
        name=choice_payload.get("name"),
    )
    continuation_payload = payload.get("continuation")
    continuation = None
    if continuation_payload is not None:
        if not isinstance(continuation_payload, Mapping):
            raise ValueError("model_request continuation must be an object")
        continuation = ProviderContinuation(
            _required_string(continuation_payload, "profile_id", "continuation"),
            continuation_payload.get("payload"),
        )
    return ModelRequest(
        prompt=str(payload.get("prompt", "")),
        max_output_tokens=payload.get("max_output_tokens"),
        tools=tools,
        tool_choice=choice,
        tool_results=results,
        continuation=continuation,
    )


def _index_asset_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        asset_id = record.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset record asset_id must be a non-empty string")
        if asset_id in indexed:
            raise ValueError(f"duplicate asset record: {asset_id}")
        indexed[asset_id] = record
    return indexed


def _public_asset_record(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    sanitized = sanitize_public_artifact(record)
    if not isinstance(sanitized, dict):
        raise TypeError("sanitized asset record must be an object")
    return sanitized


def _required_mapping(mapping: Mapping[str, Any], key: str, label: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} {key} must be an object")
    return value


def _required_string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _normalize_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.lower()
    if normalized.startswith("sha256:"):
        return normalized
    if len(normalized) == 64:
        return f"sha256:{normalized}"
    return None


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
