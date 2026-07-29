"""Build auditable evidence bundles and claim registries.

The builder is deliberately independent from live providers.  It consumes JSON
artifacts, preserves every input row, and records enough information to
recompute each numeric claim from immutable source hashes and row references.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


BUNDLE_SCHEMA_VERSION = "coda-evidence-bundle-v1"
MANIFEST_SCHEMA_VERSION = "coda-evidence-bundle-manifest-v1"
CLAIM_REGISTRY_SCHEMA_VERSION = "coda-native-claim-registry-v1"
ARTIFACT_CONTRACT_SHA256 = "a4882493c07ae7582c8286882d22f5da495482e34070f60bae8fa1daef258dea"

_SHA256_LENGTH = 64
_HASH_BASES = frozenset({"file_bytes", "git_blob_bytes", "canonical_json_sort_keys_compact_ascii"})
_CLAIM_KINDS = frozenset(
    {
        "native_tool_calling",
        "sdk_transport",
        "selected_profile",
        "auto_dream",
        "local_task",
        "resume",
        "context",
        "multi_agent",
    }
)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the frozen compact, sorted, ASCII JSON representation."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sha256_path(path: str | Path, *, hash_basis: str = "file_bytes") -> str:
    """Hash a JSON artifact using a named, recorded compatibility basis.

    ``git_blob_bytes`` means the exact bytes supplied by the artifact checkout;
    no newline conversion is performed by this function.
    """

    path = Path(path)
    if hash_basis not in _HASH_BASES:
        raise ValueError(f"unsupported hash basis: {hash_basis}")
    if hash_basis == "canonical_json_sort_keys_compact_ascii":
        payload = json.loads(path.read_text(encoding="utf-8"))
        content = canonical_json_bytes(payload)
    else:
        content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def build_evidence_bundle(manifest: Mapping[str, Any], *, base_dir: str | Path = ".") -> dict[str, Any]:
    """Build and validate an evidence bundle from a synthetic or live manifest."""

    _require_version(manifest, MANIFEST_SCHEMA_VERSION, "manifest")
    artifact_contract_hash = _sha256(
        manifest.get("artifact_contract_sha256"), "artifact_contract_sha256"
    )
    if artifact_contract_hash != ARTIFACT_CONTRACT_SHA256:
        raise ValueError("artifact contract hash is incompatible with EVAL-001")

    root = Path(base_dir).resolve()
    bundled_sources: list[dict[str, Any]] = []
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    hashes_by_source: dict[str, dict[str, str]] = {}
    source_ids: set[str] = set()
    for source in _mapping_list(manifest.get("sources"), "sources"):
        source_id = _identifier(source.get("id"), "source id")
        if source_id in source_ids:
            raise ValueError(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        path = _resolve_source_path(root, source.get("path"))
        hash_basis = str(source.get("hash_basis", "file_bytes"))
        actual_hash = sha256_path(path, hash_basis=hash_basis)
        expected_hash = source.get("sha256")
        if expected_hash is not None and actual_hash != _sha256(expected_hash, f"{source_id} sha256"):
            raise ValueError(f"source hash mismatch: {source_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_rows = payload.get("rows", []) if isinstance(payload, Mapping) else []
        if not isinstance(raw_rows, list):
            raise ValueError(f"source rows must be a list: {source_id}")
        rows = [_bundle_row(source_id, index, row) for index, row in enumerate(raw_rows)]
        row_refs = [row["row_ref"] for row in rows]
        if len(row_refs) != len(set(row_refs)):
            raise ValueError(f"source row ids must be unique: {source_id}")
        rows_by_source[source_id] = rows
        hashes_by_source[source_id] = {"sha256": actual_hash, "hash_basis": hash_basis}
        bundled_sources.append(
            {
                "id": source_id,
                "kind": _identifier(source.get("kind"), f"{source_id} kind"),
                "path": path.relative_to(root).as_posix(),
                "sha256": actual_hash,
                "hash_basis": hash_basis,
                "row_count": len(rows),
                "rows": rows,
            }
        )

    claims = [
        _build_claim(claim, rows_by_source=rows_by_source, hashes_by_source=hashes_by_source)
        for claim in _mapping_list(manifest.get("claims"), "claims")
    ]
    claim_ids = [claim["id"] for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("claim ids must be unique")
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "artifact_contract": {
            "sha256": artifact_contract_hash,
            "hash_basis": "git_blob_bytes",
            "source_ticket": "EVAL-001",
        },
        "sources": bundled_sources,
        "claim_registry": {
            "schema_version": CLAIM_REGISTRY_SCHEMA_VERSION,
            "claims": claims,
        },
    }


def build_evidence_bundle_file(
    manifest_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    """Build a bundle beside a manifest and write stable JSON output."""

    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must contain a JSON object")
    bundle = build_evidence_bundle(manifest, base_dir=manifest_path.parent)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return bundle


def validate_claim_registry(bundle: Mapping[str, Any]) -> None:
    """Validate gate bindings and row/hash/formula traceability in a bundle."""

    _require_version(bundle, BUNDLE_SCHEMA_VERSION, "bundle")
    sources = _mapping_list(bundle.get("sources"), "sources")
    source_rows: dict[str, dict[str, Mapping[str, Any]]] = {}
    source_hashes: dict[str, dict[str, str]] = {}
    for source in sources:
        source_id = _identifier(source.get("id"), "source id")
        if source_id in source_rows:
            raise ValueError(f"duplicate source id: {source_id}")
        rows = _mapping_list(source.get("rows"), "rows")
        indexed_rows = {_identifier(row.get("row_ref"), "row_ref"): row for row in rows}
        if len(indexed_rows) != len(rows):
            raise ValueError(f"source row refs must be unique: {source_id}")
        if any(not row_ref.startswith(f"{source_id}:") for row_ref in indexed_rows):
            raise ValueError(f"source {source_id} contains a foreign row_ref")
        source_rows[source_id] = indexed_rows
        source_hashes[source_id] = {
            "sha256": _sha256(source.get("sha256"), f"source {source_id} sha256"),
            "hash_basis": str(source.get("hash_basis")),
        }
    registry = bundle.get("claim_registry")
    if not isinstance(registry, Mapping):
        raise ValueError("bundle claim_registry must be an object")
    _require_version(registry, CLAIM_REGISTRY_SCHEMA_VERSION, "claim registry")
    for claim in _mapping_list(registry.get("claims"), "claims"):
        _validate_claim_policy(claim)
        formula = claim.get("formula")
        if not isinstance(formula, Mapping):
            raise ValueError(f"claim {claim.get('id')} must record a formula")
        recorded_hashes = claim.get("source_hashes")
        if not isinstance(recorded_hashes, Mapping):
            raise ValueError(f"claim {claim.get('id')} must record source hashes")
        claim_source_ids = claim.get("source_ids")
        if (
            not isinstance(claim_source_ids, list)
            or not all(isinstance(source_id, str) for source_id in claim_source_ids)
            or len(claim_source_ids) != len(set(claim_source_ids))
        ):
            raise ValueError(f"claim {claim.get('id')} source_ids must be a unique string list")
        unknown_sources = set(claim_source_ids) - source_rows.keys()
        if unknown_sources:
            raise ValueError(f"claim {claim.get('id')} references unknown sources")
        row_refs = claim.get("row_refs", [])
        if not isinstance(row_refs, list) or len(row_refs) != len(set(row_refs)):
            raise ValueError(f"claim {claim.get('id')} row_refs must be a unique list")
        expected_row_refs = [
            row_ref for source_id in claim_source_ids for row_ref in source_rows[source_id]
        ]
        if row_refs != expected_row_refs:
            raise ValueError(f"claim {claim.get('id')} must retain every source row in order")
        claim_rows = []
        for row_ref in row_refs:
            if not isinstance(row_ref, str) or ":" not in row_ref:
                raise ValueError("claim row_ref is invalid")
            source_id = row_ref.rsplit(":", 1)[0]
            if row_ref not in source_rows.get(source_id, {}):
                raise ValueError(f"claim references unknown row: {row_ref}")
            if source_id not in claim_source_ids:
                raise ValueError(f"claim row {row_ref} is not covered by source_ids")
            claim_rows.append(source_rows[source_id][row_ref])
        if set(recorded_hashes) != set(claim_source_ids):
            raise ValueError(f"claim {claim.get('id')} source hashes do not match source_ids")
        for source_id in claim_source_ids:
            if recorded_hashes[source_id] != source_hashes[source_id]:
                raise ValueError(f"claim {claim.get('id')} has an incompatible source hash")
        expected_result = (
            None
            if claim.get("status") == "optional_missing"
            else _evaluate_formula(formula, claim_rows)
        )
        if claim.get("result") != expected_result:
            raise ValueError(f"claim {claim.get('id')} result does not match its rows and formula")


def _build_claim(
    claim: Mapping[str, Any],
    *,
    rows_by_source: Mapping[str, list[dict[str, Any]]],
    hashes_by_source: Mapping[str, dict[str, str]],
) -> dict[str, Any]:
    claim_id = _identifier(claim.get("id"), "claim id")
    kind = _identifier(claim.get("kind"), f"claim {claim_id} kind")
    if kind not in _CLAIM_KINDS:
        raise ValueError(f"unsupported claim kind: {kind}")
    selected_ids = claim.get("source_ids", [])
    if not isinstance(selected_ids, list) or not all(isinstance(item, str) for item in selected_ids):
        raise ValueError(f"claim {claim_id} source_ids must be a list of strings")
    unknown = sorted(set(selected_ids) - rows_by_source.keys())
    if unknown:
        raise ValueError(f"claim {claim_id} references unknown sources: {', '.join(unknown)}")
    optional_missing = claim.get("optional_missing", False)
    if type(optional_missing) is not bool:
        raise ValueError(f"claim {claim_id} optional_missing must be a boolean")
    if optional_missing and (kind != "context" or selected_ids):
        raise ValueError("optional_missing is only valid for a source-less Context claim")
    if not optional_missing and not selected_ids:
        raise ValueError(f"claim {claim_id} must reference evidence sources")

    all_rows = [row for source_id in selected_ids for row in rows_by_source[source_id]]
    formula = claim.get("formula")
    if not isinstance(formula, Mapping):
        raise ValueError(f"claim {claim_id} formula must be an object")
    result = _evaluate_formula(formula, all_rows) if not optional_missing else None
    limitations = claim.get("limitations", [])
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise ValueError(f"claim {claim_id} limitations must be a list of strings")
    output = {
        "id": claim_id,
        "kind": kind,
        "status": "optional_missing" if optional_missing else str(claim.get("status", "supported")),
        "experimental_only": claim.get("experimental_only", False),
        "gate": deepcopy(claim.get("gate")),
        "source_ids": list(selected_ids),
        "source_hashes": {source_id: hashes_by_source[source_id] for source_id in selected_ids},
        "row_refs": [row["row_ref"] for row in all_rows],
        "formula": deepcopy(dict(formula)),
        "result": result,
        "limitations": list(limitations),
    }
    _validate_claim_policy(output)
    return output


def _evaluate_formula(formula: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    operation = formula.get("operation")
    if operation == "count":
        matching = [row for row in rows if _matches(row["data"], formula.get("where", {}))]
        return {"value": len(matching), "row_refs": [row["row_ref"] for row in matching]}
    if operation != "ratio":
        raise ValueError(f"unsupported formula operation: {operation}")
    excluded = (
        [row for row in rows if _matches(row["data"], formula["exclude_where"])]
        if "exclude_where" in formula
        else []
    )
    excluded_refs = {row["row_ref"] for row in excluded}
    denominator = [
        row
        for row in rows
        if row["row_ref"] not in excluded_refs
        and _matches(row["data"], formula.get("denominator_where", {}))
    ]
    numerator = [row for row in denominator if _matches(row["data"], formula.get("numerator_where", {}))]
    return {
        "numerator": len(numerator),
        "denominator": len(denominator),
        "excluded": len(excluded),
        "value": len(numerator) / len(denominator) if denominator else None,
        "numerator_row_refs": [row["row_ref"] for row in numerator],
        "denominator_row_refs": [row["row_ref"] for row in denominator],
        "excluded_row_refs": [row["row_ref"] for row in excluded],
    }


def _matches(data: Mapping[str, Any], selector: Any) -> bool:
    if selector in (None, {}):
        return True
    if not isinstance(selector, Mapping):
        raise ValueError("formula selector must be an object")
    for dotted_key, expected in selector.items():
        value: Any = data
        for part in str(dotted_key).split("."):
            if not isinstance(value, Mapping) or part not in value:
                return False
            value = value[part]
        if value != expected:
            return False
    return True


def _bundle_row(source_id: str, index: int, row: Any) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ValueError(f"source {source_id} row {index} must be an object")
    row_id = row.get("row_id", row.get("id", str(index)))
    if not isinstance(row_id, (str, int)) or isinstance(row_id, bool):
        raise ValueError(f"source {source_id} row {index} has an invalid row id")
    return {"row_ref": f"{source_id}:{row_id}", "data": deepcopy(dict(row))}


def _validate_claim_policy(claim: Mapping[str, Any]) -> None:
    claim_id = claim.get("id", "<unknown>")
    experimental = claim.get("experimental_only", False)
    if type(experimental) is not bool:
        raise ValueError(f"claim {claim_id} experimental_only must be a boolean")
    kind = claim.get("kind")
    if kind == "multi_agent" and experimental is not True:
        raise ValueError("Multi-agent claims must be experimental_only")
    required_gate = {"native_tool_calling": "TOOL-050-S", "resume": "TOOL-062-G"}.get(str(kind))
    if required_gate:
        gate = claim.get("gate")
        if not isinstance(gate, Mapping) or gate.get("ticket_id") != required_gate:
            raise ValueError(f"{kind} claims must bind {required_gate}")
        _sha256(gate.get("sha256"), f"claim {claim_id} gate sha256")


def _resolve_source_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("source path must be a non-empty string")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("source path escapes manifest directory") from exc
    if not path.is_file():
        raise ValueError(f"source artifact does not exist: {value}")
    return path


def _mapping_list(value: Any, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"{name} must be a list of objects")
    return value


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hash")
    return value


def _require_version(value: Mapping[str, Any], expected: str, name: str) -> None:
    if value.get("schema_version") != expected:
        raise ValueError(f"unsupported {name} schema version")


__all__ = [
    "ARTIFACT_CONTRACT_SHA256",
    "BUNDLE_SCHEMA_VERSION",
    "CLAIM_REGISTRY_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "build_evidence_bundle",
    "build_evidence_bundle_file",
    "canonical_json_bytes",
    "sha256_path",
    "validate_claim_registry",
]
