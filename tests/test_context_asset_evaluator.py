from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pico.evaluation.context_eval import (
    ARTIFACT_SCHEMA_VERSION,
    CASES_SCHEMA_VERSION,
    FRAGMENT_SCHEMA_VERSION,
    evaluate_context_case,
    load_cases,
    merge_fragments,
    run_context_asset_evaluation,
)
from pico.providers.contracts import ModelRequest, ProviderContinuation, ToolDefinition


SKILLS_SENTINEL = "CTX_SKILLS_91A7"
WORKER_SENTINEL = "CTX_WORKER_63D2"
POINTER_SENTINEL = "CTX_POINTER_BODY_44F0"
CURRENT_REQUEST = "Please preserve CTX_CURRENT_F00D verbatim."


def _asset_record(asset_id: str, surface: str, metadata: dict | None = None, **changes) -> dict:
    record = {
        "asset_id": asset_id,
        "producer": "fixture",
        "activation_state": "active",
        "surface": surface,
        "priority": "high",
        "floor_satisfied": True,
        "raw_size": 20,
        "rendered_size": 20,
        "content_hash": f"sha256:{'1' * 64}",
        "drop_action": "none",
        "metadata": metadata or {"fixture_id": asset_id},
    }
    record.update(changes)
    return record


def _request(continuation: ProviderContinuation | None = None) -> ModelRequest:
    return ModelRequest(
        prompt="legacy aggregate is not used for attribution",
        max_output_tokens=256,
        tools=[
            ToolDefinition(
                name="read_file",
                description="Read one file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            )
        ],
        continuation=continuation,
    )


def _case(pointer_hash: str, *, case_id: str = "C01") -> dict:
    return {
        "id": case_id,
        "request_id": f"request-{case_id}",
        "surfaces": {
            "system_text": f"Skills catalog: {SKILLS_SENTINEL}",
            "messages": [
                {"role": "assistant", "content": f"Worker update: {WORKER_SENTINEL}"},
                {"role": "user", "content": CURRENT_REQUEST},
                {
                    "role": "assistant",
                    "content": "Large result externalized; pointer metadata is authoritative.",
                },
            ],
            "asset_records": [
                _asset_record("skills", "system_text", {"fixture_id": "skills"}),
                _asset_record("worker", "messages", {"fixture_id": "worker"}),
                _asset_record(
                    "pointer",
                    "messages",
                    {
                        "fixture_id": "pointer",
                        "target_path": "artifacts/result.txt",
                        "content_hash": pointer_hash,
                        "resolvable": True,
                    },
                    drop_action="externalized_to_pointer",
                    rendered_size=0,
                ),
            ],
            "native_turn_status": "complete",
        },
        "oracle": {
            "current_request": CURRENT_REQUEST,
            "assets": [
                {
                    "asset_id": "skills",
                    "sentinel": SKILLS_SENTINEL,
                    "surface": "system_text",
                    "required_metadata": ["fixture_id"],
                },
                {
                    "asset_id": "worker",
                    "sentinel": WORKER_SENTINEL,
                    "surface": "messages",
                    "required_metadata": ["fixture_id"],
                },
                {
                    "asset_id": "pointer",
                    "sentinel": POINTER_SENTINEL,
                    "surface": "messages",
                    "disposition": "pointer",
                    "required_metadata": [
                        "target_path",
                        "content_hash",
                        "resolvable",
                    ],
                    "metadata": {"resolvable": True},
                },
            ],
        },
    }


def _write_pointer(workspace: Path) -> str:
    target = workspace / "artifacts" / "result.txt"
    target.parent.mkdir(parents=True)
    target.write_text("externalized result\n", encoding="utf-8")
    return f"sha256:{hashlib.sha256(target.read_bytes()).hexdigest()}"


def _serialized_case(case: dict, request: ModelRequest) -> dict:
    serialized = dict(case)
    serialized["model_request"] = request.to_dict()
    return serialized


def test_evaluates_each_asset_surface_pointer_and_current_request_hard_gate(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    row = evaluate_context_case(_case(pointer_hash), _request(), workspace_root=tmp_path)

    assert row["status"] == "pass"
    assert row["activated_asset_ids"] == ["skills", "worker", "pointer"]
    assert row["hard_gates"]["current_request_preservation"]["passed"] is True
    by_id = {record["asset_id"]: record for record in row["asset_records"]}
    assert by_id["skills"]["surfaces_present"] == ["system_text"]
    assert by_id["worker"]["surfaces_present"] == ["messages"]
    assert by_id["pointer"]["pointer_check"]["hash_matches"] is True
    assert by_id["pointer"]["occurrences"] == {
        "system_text": 0,
        "messages": 0,
        "tools": 0,
    }


def test_current_request_preservation_is_an_independent_hard_gate(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    case = _case(pointer_hash)
    case["surfaces"]["messages"][-2]["content"] = CURRENT_REQUEST[:-1]

    row = evaluate_context_case(case, _request(), workspace_root=tmp_path)

    assert row["hard_gates"]["current_request_preservation"]["passed"] is False
    assert "hard_gate:current_request_preservation" in row["failures"]


def test_detects_cross_surface_duplication_and_wrong_attribution(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    case = _case(pointer_hash)
    case["surfaces"]["messages"][0]["content"] += f" copied {SKILLS_SENTINEL}"

    row = evaluate_context_case(case, _request(), workspace_root=tmp_path)
    skills = row["asset_records"][0]

    assert skills["checks"]["attribution"] is False
    assert skills["checks"]["duplication"] is False
    assert row["duplication_findings"][0]["asset_id"] == "skills"


@pytest.mark.parametrize("pointer_mutation", ["missing", "outside", "bad_hash"])
def test_pointer_gate_requires_a_real_in_workspace_file_with_matching_hash(tmp_path, pointer_mutation):
    pointer_hash = _write_pointer(tmp_path)
    case = _case(pointer_hash)
    metadata = case["surfaces"]["asset_records"][2]["metadata"]
    if pointer_mutation == "missing":
        metadata["target_path"] = "artifacts/missing.txt"
    elif pointer_mutation == "outside":
        metadata["target_path"] = "../outside.txt"
    else:
        metadata["content_hash"] = f"sha256:{'0' * 64}"

    row = evaluate_context_case(case, _request(), workspace_root=tmp_path)

    assert row["asset_records"][2]["checks"]["pointer"] is False
    assert "asset:pointer:pointer" in row["failures"]


def test_tools_are_measured_separately_and_schema_copy_in_system_fails(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    request = _request()
    case = _case(pointer_hash)
    case["surfaces"]["system_text"] += json.dumps(
        request.tools[0].input_schema, separators=(",", ":"), sort_keys=True
    )

    row = evaluate_context_case(case, request, workspace_root=tmp_path)

    metrics = row["tool_metrics"]
    assert metrics["tool_count"] == 1
    assert metrics["tools_utf8_bytes"] > 0
    assert metrics["system_text_utf8_bytes"] > 0
    assert metrics["system_text_tool_definition_match_count"] == 1
    assert row["hard_gates"]["tool_schema_separation"]["passed"] is False


def test_continuation_evidence_contains_no_opaque_payload(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    secret_marker = "opaque-private-thinking-must-not-appear"
    request = _request(ProviderContinuation("profile-a", {"thinking": secret_marker}))

    row = evaluate_context_case(_case(pointer_hash), request, workspace_root=tmp_path)

    evidence = row["continuation_evidence"]
    assert set(evidence) == {"type", "count", "hash"}
    assert secret_marker not in json.dumps(row)


def test_loader_runner_selection_and_fragment_persistence(tmp_path):
    pointer_hash = _write_pointer(tmp_path)
    cases = [
        _serialized_case(_case(pointer_hash, case_id=case_id), _request())
        for case_id in ("C01", "C02")
    ]
    manifest_path = tmp_path / "cases.json"
    manifest_path.write_text(
        json.dumps({"schema_version": CASES_SCHEMA_VERSION, "cases": cases}), encoding="utf-8"
    )
    destination = tmp_path / "fragment.json"

    assert load_cases(manifest_path)["schema_version"] == CASES_SCHEMA_VERSION
    fragment = run_context_asset_evaluation(
        manifest_path,
        workspace_root=tmp_path,
        artifact_path=destination,
        case_ids=["C02"],
        shard_id="context-b",
        repetition=2,
    )

    assert fragment["schema_version"] == FRAGMENT_SCHEMA_VERSION
    assert [(row["case_id"], row["repetition"]) for row in fragment["rows"]] == [("C02", 2)]
    assert json.loads(destination.read_text(encoding="utf-8")) == fragment


def test_fragment_merge_is_deterministic_and_rejects_overlap():
    def fragment(shard_id: str, case_id: str, passed: bool = True) -> dict:
        return {
            "schema_version": FRAGMENT_SCHEMA_VERSION,
            "shard_id": shard_id,
            "rows": [
                {
                    "case_id": case_id,
                    "repetition": 1,
                    "passed": passed,
                    "failures": [] if passed else ["asset:skills:retention_or_drop"],
                }
            ],
        }

    merged = merge_fragments([fragment("b", "C02", False), fragment("a", "C01")])

    assert merged["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert merged["shard_ids"] == ["a", "b"]
    assert [row["case_id"] for row in merged["rows"]] == ["C01", "C02"]
    assert merged["summary"]["failure_counts"] == {"asset:skills:retention_or_drop": 1}
    with pytest.raises(ValueError, match="duplicate case repetition"):
        merge_fragments([fragment("a", "C01"), fragment("b", "C01")])
