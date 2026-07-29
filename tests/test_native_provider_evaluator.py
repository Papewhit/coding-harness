from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from coda.evaluation.native_provider import (
    ADJUDICATION_SCHEMA_VERSION_V2,
    FROZEN_INPUT_HASHES,
    NATIVE_SAFETY_EVIDENCE_VERSION,
    NATIVE_SAFETY_STAGES,
    ORACLE_SCHEMA_VERSION_V2,
    REQUIRED_SCENARIOS,
    STOCHASTIC_LIVE_PREDICATES,
    adjudicate_native_provider_rows_v2,
    aggregate_native_provider_rows,
    evaluate_native_provider_case,
    load_case_set,
    preflight_failure_artifact,
    run_native_provider_conformance,
    write_native_provider_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "cases.json"
CASE_V2_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "cases-v2.json"
PROFILE = {
    "provider": "synthetic",
    "model": "fixture",
    "wire_dialect": "fixture-native",
    "adapter_mode": "scripted",
    "sdk": {"package": "none", "version": "0"},
    "base_url_fingerprint": "sha256:fixture",
    "capabilities": {"native_tools": True},
    "retry": {"sdk_max_retries": 0, "coda_provider_attempts": 1},
}


def _assistant(*calls, text="", continuation=None):
    event = {
        "type": "assistant",
        "text": text,
        "stop_reason": "tool_calls" if calls else "end_turn",
        "tool_calls": [
            {"call_id": call_id, "name": name, "arguments": arguments}
            for call_id, name, arguments in calls
        ],
    }
    if continuation is not None:
        event["opaque_continuation"] = continuation
    return event


def _results(*items):
    return {
        "type": "tool_results",
        "results": [
            {"call_id": call_id, "is_error": error_code is not None, "error_code": error_code}
            for call_id, error_code in items
        ],
    }


def _passing_observation(case, repetition=1):
    scenario = case["scenario"]
    attempt = {"type": "http_attempt", "attempt": 1, "outcome": "response"}
    final = _assistant(text="done")
    if scenario == "final":
        return {"events": [attempt, final], "eligible": True}
    if scenario == "single_call":
        events = [_assistant(("c1", "read_file", {"path": "README.md"})), _results(("c1", None))]
    elif scenario == "unicode":
        events = [
            _assistant(("u1", "write_file", {"content": "雪山 🚀 café"})),
            _results(("u1", None)),
        ]
    elif scenario == "invalid_args_repair":
        events = [
            _assistant(("bad", "read_file", {})),
            _results(("bad", "invalid_arguments")),
            _assistant(("fixed", "read_file", {"path": "README.md"})),
            _results(("fixed", None)),
        ]
    elif scenario == "permission_denial":
        events = [
            _assistant(("deny", "run_shell", {"command": "echo hi"})),
            _results(("deny", "approval_denied")),
        ]
    elif scenario == "multi_round_patch_verify":
        events = [
            _assistant(("read", "read_file", {"path": "a.py"})),
            _results(("read", None)),
            _assistant(
                ("patch", "apply_patch", {"patch": "fixture"}),
                ("verify", "run_shell", {"command": "pytest"}),
            ),
            _results(("patch", None), ("verify", None)),
        ]
    elif scenario == "unexpected_multi_call":
        events = [
            _assistant(
                ("one", "read_file", {"path": "a"}),
                ("two", "read_file", {"path": "b"}),
            ),
            _results(("one", None), ("two", None)),
        ]
    else:
        continuation = {"hash": "sha256:opaque", "type": "reasoning", "count": 1}
        events = [
            _assistant(
                ("opaque", "read_file", {"path": "README.md"}),
                continuation=continuation,
            ),
            _results(("opaque", None)),
            {"type": "request", "opaque_continuation": continuation},
        ]
    all_events = [attempt, *events, final]
    return {
        "events": all_events,
        "eligible": True,
        "audit": {
            "safety_chain_evidence": _safety_evidence(
                case["id"], repetition, all_events
            )
        },
    }


def _runner():
    repetitions = {}

    def run(case, _profile):
        case_id = case["id"]
        repetitions[case_id] = repetitions.get(case_id, 0) + 1
        return _passing_observation(case, repetitions[case_id])

    return run


def _safety_evidence(case_id, repetition, events):
    calls = [
        call
        for event in events
        if event.get("type") == "assistant"
        for call in event.get("tool_calls", [])
    ]
    results = {
        result["call_id"]: result
        for event in events
        if event.get("type") == "tool_results"
        for result in event.get("results", [])
    }
    evidence = []
    sequence = 0
    rejection_stage = {
        "invalid_arguments": "validate",
        "approval_denied": "permission",
    }
    for call in calls:
        result = results[call["call_id"]]
        error_code = result.get("error_code")
        terminal = rejection_stage.get(error_code, "execute")
        for stage_index, stage in enumerate(NATIVE_SAFETY_STAGES, start=1):
            sequence += 1
            outcome = "passed"
            if stage == terminal:
                outcome = (
                    "rejected"
                    if terminal != "execute"
                    else "failed"
                    if error_code
                    else "completed"
                )
            evidence.append(
                {
                    "schema_version": NATIVE_SAFETY_EVIDENCE_VERSION,
                    "case_id": case_id,
                    "repetition": repetition,
                    "call_id": call["call_id"],
                    "tool_name": call["name"],
                    "stage": stage,
                    "stage_index": stage_index,
                    "outcome": outcome,
                    "reason": error_code or "",
                    "sequence": sequence,
                }
            )
            if stage == terminal:
                break
    return evidence


def test_frozen_manifest_has_exactly_the_eight_required_non_restart_cases():
    case_set = load_case_set(CASE_PATH)

    assert tuple(case["scenario"] for case in case_set["cases"]) == REQUIRED_SCENARIOS
    assert case_set["frozen_hashes"] == FROZEN_INPUT_HASHES
    assert "restart" not in json.dumps(case_set).lower()


def test_oracle_v2_manifest_freezes_ownership_denominator_and_hash_basis():
    case_set = load_case_set(CASE_V2_PATH)

    assert case_set["oracle"]["version"] == ORACLE_SCHEMA_VERSION_V2
    assert case_set["oracle"]["execution_denominator"] == "calls entering runtime.run_tool"
    assert case_set["oracle"]["safety_owner"] == "runtime_snapshot"
    assert case_set["oracle"]["hash_basis"] == "UTF-8 file bytes"
    assert case_set["oracle"]["stochastic_live_predicates"] == list(
        STOCHASTIC_LIVE_PREDICATES
    )
    assert case_set["oracle"]["stochastic_live_predicates_are_hard_eligibility"] is False
    assert case_set["oracle"]["historical_adjudication_can_promote_profile"] is False
    assert case_set["source_v1"]["immutable"] is True


def test_synthetic_eight_case_suite_emits_rows_and_aggregate_inputs():
    case_set = load_case_set(CASE_PATH)

    artifact = run_native_provider_conformance(
        case_set=case_set,
        profile=PROFILE,
        runner=_runner(),
    )

    assert len(artifact["rows"]) == len(artifact["aggregate_input"]) == 8
    assert [row["row_id"] for row in artifact["rows"][:2]] == [
        "NP01-final::r001",
        "NP02-single-call::r001",
    ]
    assert artifact["summary"]["passed"] == 8
    assert artifact["summary"]["failed"] == 0
    assert artifact["summary"]["infrastructure_failure"] == 0
    assert artifact["summary"]["call_id_result_match"]["value"] == 1.0
    assert artifact["summary"]["batch_completeness"]["value"] == 1.0
    assert artifact["summary"]["http_attempts"] == 8
    assert artifact["summary"]["safety_chain_bypass_count"] == 0
    single_call = artifact["rows"][1]
    assert single_call["safety_chain"][0]["case_id"] == "NP02-single-call"
    assert single_call["safety_chain"][0]["repetition"] == 1
    assert single_call["safety_chain"][0]["call_id"] == "c1"
    assert [stage["stage"] for stage in single_call["safety_chain"][0]["stages"]] == list(
        NATIVE_SAFETY_STAGES
    )
    opaque = artifact["rows"][-1]
    assert opaque["native_protocol"]["opaque_continuation"] == {
        "hash": "sha256:opaque",
        "type": "reasoning",
        "count": 1,
    }


def test_duplicate_after_result_mismatch_protocol_error_and_text_envelope_are_explicit():
    case = load_case_set(CASE_PATH)["cases"][1]
    observation = {
        "eligible": True,
        "sdk_retry_count": 1,
        "events": [
            {"type": "http_attempt", "attempt": 1, "outcome": "timeout"},
            {"type": "http_attempt", "attempt": 2, "outcome": "response"},
            _assistant(("same", "read_file", {"path": "README.md"})),
            _results(("same", None), ("orphan", None)),
            _assistant(("same", "read_file", {"path": "README.md"}), text="<tool>legacy</tool>"),
            _assistant(text="done"),
        ],
    }

    row = evaluate_native_provider_case(case, observation)

    assert row["status"] == "failed"
    assert row["native_protocol"]["duplicate_call_after_result"] == 1
    assert row["native_protocol"]["call_id_result_match"] == {
        "numerator": 1,
        "denominator": 2,
        "excluded": 0,
        "value": 0.5,
    }
    assert {error["code"] for error in row["native_protocol"]["protocol_errors"]} >= {
        "duplicate_call_id",
        "duplicate_call_after_result",
        "implicit_sdk_retry",
        "orphan_tool_result",
        "text_protocol_envelope",
    }
    assert row["text_envelope_seen"] is True
    assert row["http_attempt_evidence"] == [
        {"event_index": 0, "attempt": 1, "outcome": "timeout"},
        {"event_index": 1, "attempt": 2, "outcome": "response"},
    ]
    assert row["implicit_sdk_retry_seen"] is True


def test_infrastructure_failures_and_runner_exceptions_remain_rows():
    case_set = load_case_set(CASE_PATH)

    artifact = run_native_provider_conformance(
        case_set=case_set,
        profile=PROFILE,
        case_ids=["NP01-final", "NP02-single-call"],
        runner=lambda case, _profile: (
            {"eligible": True, "events": [], "infrastructure_failure": {"type": "TimeoutError"}}
            if case["scenario"] == "final"
            else (_ for _ in ()).throw(ConnectionError("fixture offline"))
        ),
    )

    assert [row["status"] for row in artifact["rows"]] == [
        "infrastructure_failure",
        "infrastructure_failure",
    ]
    assert artifact["summary"]["total"] == artifact["summary"]["eligible"] == 2
    assert artifact["summary"]["infrastructure_failure"] == 2
    failure = artifact["aggregate_input"][1]["infrastructure_failure"]
    assert failure == {
        "type": "ConnectionError",
        "code": "infrastructure_failure",
    }


def test_ineligible_row_is_excluded_but_not_deleted():
    case = load_case_set(CASE_PATH)["cases"][0]
    row = evaluate_native_provider_case(case, {"eligible": False, "events": []})

    summary = aggregate_native_provider_rows([row])

    assert row["status"] == "excluded"
    assert summary["total"] == 1
    assert summary["excluded"] == 1
    assert summary["conformance"]["value"] is None


def test_missing_reordered_and_unbound_safety_evidence_are_bypasses():
    case = load_case_set(CASE_PATH)["cases"][1]
    observation = _passing_observation(case)
    evidence = observation["audit"]["safety_chain_evidence"]
    evidence[0], evidence[1] = evidence[1], evidence[0]
    evidence.append(
        {
            **evidence[-1],
            "call_id": "not-a-native-call",
            "sequence": 999,
        }
    )

    row = evaluate_native_provider_case(case, observation)

    assert row["status"] == "failed"
    assert row["safety_chain_bypass_count"] == 1
    assert row["safety_chain"][0]["complete"] is False
    assert row["safety_chain"][0]["bypass"] is True
    assert {item["code"] for item in row["native_protocol"]["protocol_errors"]} >= {
        "safety_chain_bypass",
        "unbound_safety_chain_evidence",
    }


def test_oracle_v2_excludes_pre_runtime_rejection_and_accepts_nonzero_execute():
    case = load_case_set(CASE_PATH)["cases"][1]
    completed_error = _passing_observation(case)
    result = completed_error["events"][2]["results"][0]
    result.update(
        {
            "is_error": True,
            "error_code": "tool_failed",
            "tool_status": "error",
            "tool_error_code": "tool_failed",
        }
    )
    completed_error["audit"]["safety_chain_evidence"][-1]["outcome"] = "completed"
    completed_error_row = evaluate_native_provider_case(case, completed_error)
    assert completed_error_row["safety_chain_bypass_count"] == 1

    pre_runtime = _passing_observation(case)
    pre_runtime_result = pre_runtime["events"][2]["results"][0]
    pre_runtime_result.update(
        {
            "is_error": True,
            "error_code": "tool_choice_none_violation",
            "tool_status": "rejected",
            "tool_error_code": "tool_choice_none_violation",
        }
    )
    pre_runtime["audit"]["safety_chain_evidence"] = []
    pre_runtime_row = evaluate_native_provider_case(case, pre_runtime)

    adjudication = adjudicate_native_provider_rows_v2(
        [completed_error_row, pre_runtime_row],
        source_snapshot_sha="a" * 40,
    )

    assert adjudication["schema_version"] == ADJUDICATION_SCHEMA_VERSION_V2
    assert adjudication["runtime_snapshot"] == {
        "status": "passed",
        "execution_denominator": 1,
        "complete_execution_chains": 1,
        "pre_runtime_rejection_count": 1,
        "runtime_chain_violation_count": 0,
        "sdk_managed_execution_violation_count": 0,
        "sdk_managed_execution_evidence": "rows",
        "execute_completed_semantics": (
            "tool implementation returned; operation outcome is read from "
            "tool_status/tool_error_code"
        ),
    }
    first_call = adjudication["rows"][0]["safety_calls"][0]
    assert first_call["runtime_chain_complete"] is True
    assert first_call["tool_status"] == "error"
    assert first_call["tool_error_code"] == "tool_failed"
    assert adjudication["profile_metrics"]["status"] == "eligible"
    assert adjudication["reselection_or_promotion_permitted"] is False


def test_oracle_v2_true_runtime_chain_violation_blocks_snapshot_not_profile():
    case = load_case_set(CASE_PATH)["cases"][1]
    observation = _passing_observation(case)
    observation["audit"]["safety_chain_evidence"] = []
    row = evaluate_native_provider_case(case, observation)

    adjudication = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="b" * 40,
    )

    assert adjudication["runtime_snapshot"]["status"] == "blocked"
    assert adjudication["runtime_snapshot"]["runtime_chain_violation_count"] == 1
    assert adjudication["profile_metrics"]["status"] == "eligible"


@pytest.mark.parametrize(
    ("runtime_started", "status", "denominator", "pre_runtime", "violations"),
    [
        (False, "passed", 0, 1, 0),
        (True, "blocked", 1, 0, 1),
    ],
)
def test_oracle_v2_classifies_unmatched_call_from_runtime_entry_evidence(
    runtime_started,
    status,
    denominator,
    pre_runtime,
    violations,
):
    case = load_case_set(CASE_PATH)["cases"][1]
    observation = _passing_observation(case)
    assistant = next(
        event
        for event in observation["events"]
        if event["type"] == "assistant" and event["tool_calls"]
    )
    assistant["tool_calls"][0]["runtime_started"] = runtime_started
    observation["events"] = [
        event
        for event in observation["events"]
        if event["type"] != "tool_results"
    ]
    observation["audit"]["safety_chain_evidence"] = []

    row = evaluate_native_provider_case(case, observation)
    adjudication = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="c" * 40,
    )

    assert row["call_evidence"][0]["runtime_started"] is runtime_started
    assert row["result_evidence"] == []
    call_metric = row["native_protocol"]["call_id_result_match"]
    batch_metric = row["native_protocol"]["batch_completeness"]
    assert (
        call_metric["numerator"],
        call_metric["denominator"],
        call_metric["value"],
    ) == (0, 1, 0.0)
    assert (
        batch_metric["numerator"],
        batch_metric["denominator"],
        batch_metric["value"],
    ) == (0, 1, 0.0)
    assert adjudication["profile_metrics"]["status"] == "ineligible"
    profile_call_metric = adjudication["profile_metrics"][
        "call_id_result_match"
    ]
    profile_batch_metric = adjudication["profile_metrics"][
        "batch_completeness"
    ]
    assert (
        profile_call_metric["numerator"],
        profile_call_metric["denominator"],
        profile_call_metric["value"],
    ) == (0, 1, 0.0)
    assert (
        profile_batch_metric["numerator"],
        profile_batch_metric["denominator"],
        profile_batch_metric["value"],
    ) == (0, 1, 0.0)
    assert adjudication["runtime_snapshot"]["status"] == status
    assert adjudication["runtime_snapshot"]["execution_denominator"] == denominator
    assert (
        adjudication["runtime_snapshot"]["pre_runtime_rejection_count"]
        == pre_runtime
    )
    assert (
        adjudication["runtime_snapshot"]["runtime_chain_violation_count"]
        == violations
    )


def test_oracle_v2_sdk_managed_execution_is_snapshot_hard_failure():
    case = load_case_set(CASE_PATH)["cases"][1]
    observation = _passing_observation(case)
    observation["audit"]["sdk_managed_coda_tool_execution_used"] = True
    row = evaluate_native_provider_case(case, observation)

    adjudication = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="d" * 40,
    )

    assert adjudication["runtime_snapshot"]["status"] == "blocked"
    assert (
        adjudication["runtime_snapshot"][
            "sdk_managed_execution_violation_count"
        ]
        == 1
    )
    assert adjudication["profile_metrics"]["status"] == "eligible"


def test_oracle_v2_stochastic_case_predicates_are_descriptive_only():
    case = load_case_set(CASE_PATH)["cases"][3]
    observation = _passing_observation(case)
    observation["events"] = [
        observation["events"][0],
        _assistant(text="done"),
    ]
    observation["audit"]["safety_chain_evidence"] = []
    row = evaluate_native_provider_case(case, observation)
    assert {error["code"] for error in row["case_errors"]} >= {
        "too_few_calls",
        "missing_expected_error",
        "missing_successful_repair",
    }

    adjudication = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="c" * 40,
    )

    assert adjudication["profile_metrics"]["status"] == "eligible"
    assert adjudication["rows"][0]["source_case_errors_retained_descriptive"]


def test_oracle_v2_never_treats_missing_metric_evidence_as_zero():
    case = load_case_set(CASE_PATH)["cases"][1]
    row = evaluate_native_provider_case(case, _passing_observation(case))
    row.pop("unknown_block_loss_count")
    row.pop("sdk_managed_execution_seen")

    missing = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="e" * 40,
    )
    assert missing["profile_metrics"]["status"] == "not_computable"
    assert missing["profile_metrics"]["unknown_block_loss_count"] is None
    assert missing["runtime_snapshot"]["status"] == "not_computable"

    bound = adjudicate_native_provider_rows_v2(
        [row],
        source_snapshot_sha="e" * 40,
        source_bindings={
            "unknown_block_loss_count_from_accepted_handoff": 0,
            "sdk_managed_execution_from_accepted_handoff": False,
        },
    )
    assert bound["profile_metrics"]["status"] == "eligible"
    assert (
        bound["profile_metrics"]["unknown_block_loss_evidence"]
        == "accepted_handoff_binding"
    )
    assert bound["runtime_snapshot"]["status"] == "passed"


def test_repetition_is_case_major_and_row_ids_are_unique():
    artifact = run_native_provider_conformance(
        case_set=load_case_set(CASE_PATH),
        profile=PROFILE,
        case_ids=["NP01-final", "NP02-single-call"],
        repetitions=3,
        runner=_runner(),
    )

    assert [
        (row["case_id"], row["repetition"], row["row_id"])
        for row in artifact["rows"]
    ] == [
        ("NP01-final", 1, "NP01-final::r001"),
        ("NP01-final", 2, "NP01-final::r002"),
        ("NP01-final", 3, "NP01-final::r003"),
        ("NP02-single-call", 1, "NP02-single-call::r001"),
        ("NP02-single-call", 2, "NP02-single-call::r002"),
        ("NP02-single-call", 3, "NP02-single-call::r003"),
    ]
    assert len({row["row_id"] for row in artifact["rows"]}) == 6


def test_wire_dialects_share_row_schema_metrics_and_safety_validation():
    case_set = load_case_set(CASE_PATH)
    profiles = [
        {**PROFILE, "wire_dialect": "openai-responses"},
        {**PROFILE, "wire_dialect": "anthropic-messages"},
    ]

    artifacts = [
        run_native_provider_conformance(
            case_set=case_set,
            profile=profile,
            case_ids=["NP02-single-call"],
            runner=_runner(),
        )
        for profile in profiles
    ]

    assert artifacts[0]["rows"] == artifacts[1]["rows"]
    assert artifacts[0]["summary"] == artifacts[1]["summary"]
    assert set(artifacts[0]["rows"][0]) == set(artifacts[1]["rows"][0])


def test_atomic_bundle_preserves_public_rows_and_redacts_credentials(tmp_path):
    artifact = run_native_provider_conformance(
        case_set=load_case_set(CASE_PATH),
        profile={**PROFILE, "api_key": "sk-fixture-secret-value"},
        case_ids=["NP01-final"],
        runner=_runner(),
    )
    destination = tmp_path / "native-bundle"

    hashes = write_native_provider_bundle(destination, artifact)
    files = {path.name for path in destination.iterdir()}
    written = "\n".join(
        path.read_text(encoding="utf-8") for path in destination.iterdir()
    )

    assert "sk-fixture-secret-value" not in written
    assert files == {
        "manifest.json",
        "rows.jsonl",
        "evidence-index.json",
        "summary.json",
    }
    assert set(hashes) == files
    for name, digest in hashes.items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
    row = json.loads((destination / "rows.jsonl").read_text(encoding="utf-8"))
    assert row["row_id"] == "NP01-final::r001"
    evidence = json.loads(
        (destination / "evidence-index.json").read_text(encoding="utf-8")
    )
    assert evidence["entries"] == []
    with pytest.raises(FileExistsError, match="already exists"):
        write_native_provider_bundle(destination, artifact)


def test_bundle_verifier_rejects_self_reported_safety_verdict(tmp_path):
    artifact = run_native_provider_conformance(
        case_set=load_case_set(CASE_PATH),
        profile=PROFILE,
        case_ids=["NP02-single-call"],
        runner=_runner(),
    )
    artifact["rows"][0]["safety_chain"][0]["complete"] = False
    artifact["rows"][0]["safety_chain"][0]["bypass"] = True

    with pytest.raises(ValueError, match="safety chain verdict mismatch"):
        write_native_provider_bundle(tmp_path / "tampered", artifact)


def test_preflight_failure_bundle_has_zero_rows_and_is_not_computable(tmp_path):
    artifact = preflight_failure_artifact(
        bindings={"cases_sha256": "a" * 64},
        error=ValueError("https://secret.example.test/path?api_key=hidden"),
    )
    destination = tmp_path / "preflight"

    write_native_provider_bundle(destination, artifact)

    assert (destination / "rows.jsonl").read_bytes() == b""
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
    serialized = json.dumps([manifest, summary])
    assert manifest["row_count"] == 0
    assert manifest["computability"] == "not_computable"
    assert summary["computability"] == "not_computable"
    assert "secret.example.test" not in serialized
    assert "api_key" not in serialized


def test_manifest_rejects_restart_or_wrong_frozen_hash(tmp_path):
    payload = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    payload["cases"][0]["expectations"]["process_restart"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="process restart"):
        load_case_set(path)

    payload["cases"][0]["expectations"].pop("process_restart")
    payload["frozen_hashes"]["native_contract"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen input hashes"):
        load_case_set(path)
