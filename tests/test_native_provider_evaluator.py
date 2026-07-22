from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico.evaluation.native_provider import (
    FROZEN_INPUT_HASHES,
    REQUIRED_SCENARIOS,
    aggregate_native_provider_rows,
    evaluate_native_provider_case,
    load_case_set,
    run_native_provider_conformance,
    write_native_provider_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "cases.json"
PROFILE = {
    "provider": "synthetic",
    "model": "fixture",
    "wire_dialect": "fixture-native",
    "adapter_mode": "scripted",
    "sdk": {"package": "none", "version": "0"},
    "base_url_fingerprint": "sha256:fixture",
    "capabilities": {"native_tools": True},
    "retry": {"sdk_max_retries": 0, "pico_provider_attempts": 1},
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


def _passing_observation(case):
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
    return {"events": [attempt, *events, final], "eligible": True}


def synthetic_case_runner(case, _profile):
    return _passing_observation(case)


def test_frozen_manifest_has_exactly_the_eight_required_non_restart_cases():
    case_set = load_case_set(CASE_PATH)

    assert tuple(case["scenario"] for case in case_set["cases"]) == REQUIRED_SCENARIOS
    assert case_set["frozen_hashes"] == FROZEN_INPUT_HASHES
    assert "restart" not in json.dumps(case_set).lower()


def test_synthetic_eight_case_suite_emits_rows_and_aggregate_inputs():
    case_set = load_case_set(CASE_PATH)

    artifact = run_native_provider_conformance(
        case_set=case_set,
        profile=PROFILE,
        runner=synthetic_case_runner,
    )

    assert len(artifact["rows"]) == len(artifact["aggregate_input"]) == 8
    assert artifact["summary"]["passed"] == 8
    assert artifact["summary"]["failed"] == 0
    assert artifact["summary"]["infrastructure_failure"] == 0
    assert artifact["summary"]["call_id_result_match"]["value"] == 1.0
    assert artifact["summary"]["batch_completeness"]["value"] == 1.0
    assert artifact["summary"]["http_attempts"] == 8
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
    assert artifact["aggregate_input"][1]["infrastructure_failure"] == {
        "type": "ConnectionError",
        "message": "fixture offline",
    }


def test_ineligible_row_is_excluded_but_not_deleted():
    case = load_case_set(CASE_PATH)["cases"][0]
    row = evaluate_native_provider_case(case, {"eligible": False, "events": []})

    summary = aggregate_native_provider_rows([row])

    assert row["status"] == "excluded"
    assert summary["total"] == 1
    assert summary["excluded"] == 1
    assert summary["conformance"]["value"] is None


def test_artifact_writer_preserves_public_rows_and_redacts_credentials(tmp_path):
    artifact = run_native_provider_conformance(
        case_set=load_case_set(CASE_PATH),
        profile={**PROFILE, "api_key": "sk-fixture-secret-value"},
        case_ids=["NP01-final"],
        runner=synthetic_case_runner,
    )
    destination = tmp_path / "native.json"

    write_native_provider_artifact(destination, artifact)
    written = destination.read_text(encoding="utf-8")

    assert "sk-fixture-secret-value" not in written
    assert json.loads(written)["rows"][0]["row_id"] == "NP01-final"


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
