from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico.evaluation.evaluation_v2_evidence import checksums
from pico.evaluation.evaluation_v2_row_capture import write_json
from pico.evaluation.pilot_audit import AUDIT_SCHEMA, DECISION_SCHEMA
from pico.evaluation.pilot_report import (
    build_pilot_report,
    finalize_pilot,
    initialize_pilot,
    verify_pilot,
)
from scripts import finalize_evaluation_v2_pilot as cli
from tests.evaluation_v2_helpers import write_config


GENERATOR = {
    "commit": "d" * 40,
    "script": "scripts/finalize_evaluation_v2_pilot.py",
    "script_sha256": "e" * 64,
}


def _make_row(
    root: Path,
    task_id: str,
    *,
    verifier_passed: bool = True,
    measurement_valid: bool = True,
    client_failure: str = "",
) -> Path:
    row_id = f"pilot-v1-{task_id}-r1"
    row = root / "public" / "rows" / row_id
    verifier = row / "verifier"
    run = row / "original" / ".pico" / "runs" / f"runtime-{task_id}"
    verifier.mkdir(parents=True)
    run.mkdir(parents=True)
    request_count = 0 if client_failure == "task" else 1
    failure = (
        {
            "origin": "runtime" if client_failure == "task" else "provider",
            "stage": "pre_request" if client_failure == "task" else "request",
            "category": client_failure,
            "error_type": (
                "ValueError"
                if client_failure == "task"
                else "ServiceUnavailable"
            ),
            "provider_request_count": request_count,
            "provider_request_count_exact": True,
            "exit_code": 1,
        }
        if client_failure
        else None
    )
    write_json(
        row / "run-record.json",
        {
            "measurement_status": "complete" if measurement_valid else "invalid",
            "measurement_errors": [] if measurement_valid else ["synthetic defect"],
            "provider_requests": {"count": request_count, "exact": True},
            "credential_scan": {
                "source_originals": {"passed": True},
                "persisted_artifacts": {"passed": True},
            },
            "failure": failure,
        },
    )
    write_json(
        row / "evidence-view.json",
        {
            "protocol_errors": [] if measurement_valid else ["call mismatch"],
            "provider_requests": {"count": request_count, "exact": True},
            "verifier": {"passed": verifier_passed, "returncode": 0 if verifier_passed else 1},
        },
    )
    write_json(
        verifier / "result.json",
        {"passed": verifier_passed, "returncode": 0 if verifier_passed else 1},
    )
    write_json(run / "report.json", {"tool_steps": 3})
    trace = [
        {
            "event": "tool_executed",
            "name": "read_file",
            "args": {"path": "package/code.py"},
            "tool_status": "completed",
        },
        {
            "event": "tool_executed",
            "name": "read_file",
            "args": {"path": "package/code.py"},
            "tool_status": "completed",
        },
        {"event": "run_finished", "run_duration_ms": 1250},
    ]
    (run / "trace.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in trace),
        encoding="utf-8",
    )
    write_json(row / "checksums.json", checksums(row))
    return row


def _audit(
    path: Path,
    task_id: str,
    *,
    product: str = "passed",
    category: str = "none",
    measurement: str = "valid",
    decision: str = "not_required",
) -> Path:
    final = (
        "pending decision"
        if decision == "required"
        else "invalid"
        if measurement == "invalid"
        else f"valid + {product}"
    )
    write_json(
        path,
        {
            "schema_version": AUDIT_SCHEMA,
            "row_id": f"pilot-v1-{task_id}-r1",
            "auditor": "Codex",
            "evidence_sufficient": measurement == "valid",
            "measurement_result": measurement,
            "product_result": "not_determined" if measurement == "invalid" else product,
            "final_classification": final,
            "failure_category": "measurement" if measurement == "invalid" else category,
            "reason": "Synthetic audit reason.",
            "evidence_refs": [
                {"path": "run-record.json", "pointer": "/measurement_status"},
                {"path": "evidence-view.json", "pointer": "/verifier"},
            ],
            "user_decision": decision,
        },
    )
    return path


def _decision(path: Path, task_id: str) -> Path:
    write_json(
        path,
        {
            "schema_version": DECISION_SCHEMA,
            "row_id": f"pilot-v1-{task_id}-r1",
            "decided_by": "evaluation owner",
            "final_classification": "valid + failed",
            "failure_category": "model_behavior",
            "reason": "The deterministic verifier failure is accepted.",
        },
    )
    return path


def test_partial_pilot_passes_g0_and_rebuilds_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01")
    audit = _audit(tmp_path / "audit-t01.json", "T01")

    result = finalize_pilot(
        config,
        audit_inputs=[audit],
        sensitive_values=("never-persist-this",),
        generator=GENERATOR,
    )

    assert result["g0_status"] == "passed"
    assert result["rows"]["valid_passed"] == 1
    assert result["rows"]["no_result"] == 2
    report = json.loads((root / "reports" / "pilot-report.json").read_text())
    assert report["metrics"]["valid_run_rate"]["value"] == 1.0
    assert report["metrics"]["verified_run_success"]["value"] == 1.0
    assert report["metrics"]["repeated_reads"]["total"] == 1
    assert report["metrics"]["elapsed_time_ms"]["mean"] == 1250
    assert verify_pilot(config)["markdown_rebuilt"] is True


def test_pilot_v2_report_uses_new_cohort_and_row_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="pilot-v2",
    )

    report = build_pilot_report(config, generator=GENERATOR)

    assert report["cohort_id"] == "pilot-v2"
    assert report["g0"] == {
        "status": "pending",
        "rule": "T01 measurement valid under evidence protocol rules 1-5",
        "row_id": "pilot-v2-T01-r1",
    }
    assert [row["row_id"] for row in report["rows"]] == [
        "pilot-v2-T01-r1",
        "pilot-v2-T04-r1",
        "pilot-v2-T07-r1",
    ]


def test_initialize_pilot_reports_all_rows_as_no_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="pilot-v2",
    )

    result = initialize_pilot(config, generator=GENERATOR)

    assert result["g0_status"] == "pending"
    assert result["rows"]["no_result"] == 3
    assert (root / "reports" / "pilot-report.json").is_file()
    assert verify_pilot(config)["markdown_rebuilt"] is True


def test_full_pilot_reports_valid_failure_and_provider_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01")
    _make_row(root, "T04", verifier_passed=False)
    _make_row(root, "T07", verifier_passed=False, client_failure="provider")
    audits = [
        _audit(tmp_path / "a1.json", "T01"),
        _audit(
            tmp_path / "a4.json",
            "T04",
            product="failed",
            category="model_behavior",
        ),
        _audit(
            tmp_path / "a7.json",
            "T07",
            product="failed",
            category="provider",
        ),
    ]

    finalize_pilot(config, audit_inputs=audits, generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())

    assert report["counts"]["final_classified"] == 3
    assert report["counts"]["valid_failed"] == 2
    assert report["metrics"]["failure_category_counts"] == {
        "model_behavior": 1,
        "provider": 1,
    }
    assert report["metrics"]["provider_requests"]["total"] == 3


def test_runtime_pre_request_failure_passes_g0_as_valid_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01", verifier_passed=True, client_failure="task")
    audit = _audit(
        tmp_path / "runtime-failure.json",
        "T01",
        product="failed",
        category="product_behavior",
    )

    finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())

    assert report["g0"]["status"] == "passed"
    assert report["counts"]["valid_failed"] == 1
    assert report["metrics"]["failure_category_counts"] == {
        "product_behavior": 1
    }
    assert report["metrics"]["provider_requests"]["total"] == 0


def test_invalid_t01_fails_g0_without_classifying_missing_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01", measurement_valid=False)
    audit = _audit(
        tmp_path / "invalid.json",
        "T01",
        measurement="invalid",
    )

    finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())

    assert report["g0"]["status"] == "failed"
    assert report["counts"]["invalid"] == 1
    assert report["counts"]["no_result"] == 2
    assert report["metrics"]["tool_steps"]["valid_samples"] == 0


def test_codex_can_reject_mechanically_complete_but_insufficient_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01", verifier_passed=False, client_failure="provider")
    audit = _audit(
        tmp_path / "insufficient.json",
        "T01",
        measurement="invalid",
    )

    finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())

    assert report["g0"]["status"] == "failed"
    assert report["rows"][0]["final_classification"] == "invalid"
    assert report["metrics"]["provider_requests"]["total"] == 1


def test_pending_decision_can_be_appended_without_overwriting_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    row = _make_row(root, "T01", verifier_passed=False)
    audit = _audit(
        tmp_path / "pending.json",
        "T01",
        product="failed",
        category="model_behavior",
        decision="required",
    )

    finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())
    assert report["counts"]["pending_decision"] == 1

    decision = _decision(tmp_path / "decision.json", "T01")
    finalize_pilot(config, decision_inputs=[decision], generator=GENERATOR)
    report = json.loads((root / "reports" / "pilot-report.json").read_text())
    assert report["counts"]["valid_failed"] == 1
    assert (row / "user-decision.json").is_file()

    with pytest.raises(ValueError, match="already exists"):
        finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)


def test_finalizer_rejects_tampering_identity_and_sensitive_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    row = _make_row(root, "T01")
    audit = _audit(tmp_path / "audit.json", "T01")
    (row / "extra.txt").write_text("not inventoried", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory is incomplete"):
        finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    (row / "extra.txt").unlink()

    payload = json.loads(audit.read_text())
    payload["row_id"] = "pilot-v1-T04-r1"
    write_json(audit, payload)
    with pytest.raises(ValueError, match="has not started"):
        finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)

    payload["row_id"] = "pilot-v1-T01-r1"
    payload["reason"] = "secret-sentinel"
    write_json(audit, payload)
    with pytest.raises(ValueError, match="sensitive"):
        finalize_pilot(
            config,
            audit_inputs=[audit],
            sensitive_values=("secret-sentinel",),
            generator=GENERATOR,
        )


def test_cli_verify_only_does_not_resolve_provider_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01")
    audit = _audit(tmp_path / "audit.json", "T01")
    finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)
    before = {
        path: path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        cli,
        "_sensitive_values",
        lambda _path: pytest.fail("verify-only must not resolve provider config"),
    )

    assert cli.main(["--run-config", str(config), "--verify-only"]) == 0
    after = {
        path: path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_cli_initializes_no_result_report_without_provider_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="pilot-v2",
    )
    monkeypatch.setattr(cli, "_generator_identity", lambda: GENERATOR)
    monkeypatch.setattr(
        cli,
        "_sensitive_values",
        lambda _path: pytest.fail(
            "report initialization must not resolve provider config"
        ),
    )

    assert (
        cli.main(
            [
                "--run-config",
                str(config),
                "--initialize-report",
            ]
        )
        == 0
    )
    assert verify_pilot(config)["rows"]["no_result"] == 3


def test_finalizer_does_not_rebuild_frozen_client_with_control_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, root = write_config(tmp_path, monkeypatch)
    _make_row(root, "T01")
    audit = _audit(tmp_path / "audit.json", "T01")
    monkeypatch.setattr(
        "pico.evaluation.pilot_report.verify_run_config",
        lambda path: {"cohort_id": "pilot-v1", "path": str(path)},
    )

    result = finalize_pilot(config, audit_inputs=[audit], generator=GENERATOR)

    assert result["g0_status"] == "passed"
