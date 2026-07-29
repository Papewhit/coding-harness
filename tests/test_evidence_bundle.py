import hashlib
import json
from pathlib import Path

import pytest

from coda.evaluation.evidence_bundle import (
    ARTIFACT_CONTRACT_SHA256,
    MANIFEST_SCHEMA_VERSION,
    build_evidence_bundle,
    canonical_json_bytes,
    sha256_path,
    validate_claim_registry,
)


FIXTURES = Path(__file__).parent / "fixtures" / "evidence_bundle"
GATE_HASH = "a" * 64


def _manifest() -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_contract_sha256": ARTIFACT_CONTRACT_SHA256,
        "sources": [
            {"id": "native", "kind": "native_conformance", "path": "native-rows.json"},
            {"id": "resume", "kind": "resume", "path": "resume-rows.json"},
        ],
        "claims": [
            {
                "id": "native-pass-rate",
                "kind": "native_tool_calling",
                "source_ids": ["native"],
                "gate": {"ticket_id": "TOOL-050-S", "sha256": GATE_HASH},
                "formula": {
                    "operation": "ratio",
                    "numerator_where": {"status": "passed"},
                    "denominator_where": {},
                    "exclude_where": {"status": "excluded"},
                },
                "limitations": ["Synthetic rows; no live provider conclusion."],
            },
            {
                "id": "resume-pass-rate",
                "kind": "resume",
                "source_ids": ["resume"],
                "gate": {"ticket_id": "TOOL-062-G", "sha256": GATE_HASH},
                "formula": {
                    "operation": "ratio",
                    "numerator_where": {"status": "passed"},
                },
                "limitations": [],
            },
            {
                "id": "context-ablation",
                "kind": "context",
                "source_ids": [],
                "optional_missing": True,
                "formula": {"operation": "count"},
                "limitations": ["Optional Context Ablation artifact not available."],
            },
            {
                "id": "multi-agent",
                "kind": "multi_agent",
                "source_ids": ["native"],
                "experimental_only": True,
                "formula": {"operation": "count"},
                "limitations": ["Experimental only."],
            },
        ],
    }


def test_bundle_traces_numbers_to_rows_hashes_formulas_and_preserves_failures() -> None:
    bundle = build_evidence_bundle(_manifest(), base_dir=FIXTURES)

    native_source = bundle["sources"][0]
    assert native_source["row_count"] == 3
    assert [row["data"]["status"] for row in native_source["rows"]] == [
        "passed",
        "failed",
        "excluded",
    ]
    claim = bundle["claim_registry"]["claims"][0]
    assert claim["source_hashes"]["native"]["sha256"] == sha256_path(
        FIXTURES / "native-rows.json"
    )
    assert claim["row_refs"] == ["native:native-pass", "native:native-fail", "native:native-excluded"]
    assert claim["result"] == {
        "numerator": 1,
        "denominator": 2,
        "excluded": 1,
        "value": 0.5,
        "numerator_row_refs": ["native:native-pass"],
        "denominator_row_refs": ["native:native-pass", "native:native-fail"],
        "excluded_row_refs": ["native:native-excluded"],
    }
    validate_claim_registry(bundle)


def test_claim_policy_requires_gate_bindings_and_experimental_multi_agent() -> None:
    manifest = _manifest()
    manifest["claims"][0]["gate"]["ticket_id"] = "TOOL-049"
    with pytest.raises(ValueError, match="TOOL-050-S"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)

    manifest = _manifest()
    manifest["claims"][1]["gate"]["ticket_id"] = "TOOL-050-S"
    with pytest.raises(ValueError, match="TOOL-062-G"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)

    manifest = _manifest()
    manifest["claims"][3]["experimental_only"] = False
    with pytest.raises(ValueError, match="experimental_only"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)


def test_optional_context_ablation_is_explicitly_missing() -> None:
    bundle = build_evidence_bundle(_manifest(), base_dir=FIXTURES)
    claim = bundle["claim_registry"]["claims"][2]
    assert claim["status"] == "optional_missing"
    assert claim["result"] is None
    assert claim["row_refs"] == []
    assert claim["limitations"]


def test_all_claim_kinds_can_bind_synthetic_evidence() -> None:
    manifest = _manifest()
    for kind in ("sdk_transport", "selected_profile", "auto_dream", "local_task"):
        manifest["claims"].append(
            {
                "id": kind,
                "kind": kind,
                "source_ids": ["native"],
                "formula": {"operation": "count", "where": {"status": "failed"}},
                "limitations": ["Synthetic evidence."],
            }
        )
    bundle = build_evidence_bundle(manifest, base_dir=FIXTURES)
    claims = {claim["kind"]: claim for claim in bundle["claim_registry"]["claims"]}
    assert claims["sdk_transport"]["result"]["value"] == 1
    assert claims["selected_profile"]["result"]["row_refs"] == ["native:native-fail"]
    assert {"auto_dream", "local_task"}.issubset(claims)
    assert bundle["claim_registry"]["claims"][1]["result"]["denominator"] == 2
    validate_claim_registry(bundle)


def test_registry_validation_recomputes_claim_result() -> None:
    bundle = build_evidence_bundle(_manifest(), base_dir=FIXTURES)
    bundle["claim_registry"]["claims"][0]["result"]["numerator"] = 2
    with pytest.raises(ValueError, match="does not match"):
        validate_claim_registry(bundle)


def test_hash_bases_are_explicit_and_artifact_contract_is_frozen(tmp_path: Path) -> None:
    payload = {"unicode": "Coda 工具", "rows": []}
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    expected = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    assert sha256_path(path, hash_basis="canonical_json_sort_keys_compact_ascii") == expected

    manifest = _manifest()
    manifest["artifact_contract_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="incompatible"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)


def test_source_hash_mismatch_and_path_escape_fail_closed(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["sources"][0]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source hash mismatch"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)

    manifest = _manifest()
    manifest["sources"][0]["path"] = "../outside.json"
    with pytest.raises(ValueError, match="escapes"):
        build_evidence_bundle(manifest, base_dir=FIXTURES)
