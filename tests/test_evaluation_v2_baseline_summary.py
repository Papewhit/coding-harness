from __future__ import annotations

import json
from pathlib import Path

import pytest

from coda.evaluation.baseline_summary import (
    build_baseline_summary,
    finalize_baseline,
    verify_baseline,
)
from coda.evaluation.evaluation_v2_evidence import checksums
from coda.evaluation.evaluation_v2_row_capture import write_json
from coda.evaluation.pilot_audit import AUDIT_SCHEMA, DECISION_SCHEMA
from scripts import finalize_evaluation_v2_baseline as cli
from scripts import run_local_coding_tasks as runner_cli
from tests.evaluation_v2_helpers import write_config


def _make_row(
    root: Path,
    task_id: str,
    repetition: int,
    *,
    verifier_passed: bool = True,
    measurement_valid: bool = True,
) -> Path:
    row_id = f"baseline-v1-{task_id}-r{repetition}"
    row = root / "public" / "rows" / row_id
    verifier = row / "verifier"
    run = row / "original" / ".coda" / "runs" / f"runtime-{task_id}-{repetition}"
    verifier.mkdir(parents=True)
    run.mkdir(parents=True)
    write_json(
        row / "run-record.json",
        {
            "measurement_status": "complete" if measurement_valid else "invalid",
            "measurement_errors": [] if measurement_valid else ["synthetic defect"],
            "provider_requests": {"count": repetition, "exact": True},
            "credential_scan": {
                "source_originals": {"passed": True},
                "persisted_artifacts": {"passed": True},
            },
            "failure": (
                None
                if verifier_passed
                else {
                    "origin": "verifier",
                    "stage": "verifier",
                    "category": "task",
                    "error_type": "VerifierFailure",
                    "provider_request_count": repetition,
                    "provider_request_count_exact": True,
                    "exit_code": 1,
                }
            ),
        },
    )
    write_json(
        row / "evidence-view.json",
        {
            "protocol_errors": [] if measurement_valid else ["call mismatch"],
            "provider_requests": {"count": repetition, "exact": True},
            "verifier": {
                "passed": verifier_passed,
                "returncode": 0 if verifier_passed else 1,
            },
        },
    )
    write_json(
        verifier / "result.json",
        {
            "passed": verifier_passed,
            "returncode": 0 if verifier_passed else 1,
        },
    )
    write_json(run / "report.json", {"tool_steps": repetition + 2})
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
        {"event": "run_finished", "run_duration_ms": repetition * 1000},
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
    repetition: int,
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
            "row_id": f"baseline-v1-{task_id}-r{repetition}",
            "auditor": "Codex",
            "evidence_sufficient": measurement == "valid",
            "measurement_result": measurement,
            "product_result": (
                "not_determined"
                if measurement == "invalid"
                else product
            ),
            "final_classification": final,
            "failure_category": (
                "measurement"
                if measurement == "invalid"
                else category
            ),
            "reason": "Synthetic baseline audit.",
            "evidence_refs": [
                {"path": "run-record.json", "pointer": "/measurement_status"},
                {"path": "evidence-view.json", "pointer": "/verifier"},
            ],
            "user_decision": decision,
        },
    )
    return path


def _decision(path: Path, task_id: str, repetition: int) -> Path:
    write_json(
        path,
        {
            "schema_version": DECISION_SCHEMA,
            "row_id": f"baseline-v1-{task_id}-r{repetition}",
            "decided_by": "evaluation owner",
            "final_classification": "valid + failed",
            "failure_category": "model_behavior",
            "reason": "The verifier failure is accepted.",
        },
    )
    return path


def test_partial_stage_metrics_and_stable_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="baseline-v1",
    )
    audits = []
    for repetition in range(1, 4):
        _make_row(root, "T01", repetition)
        audits.append(_audit(tmp_path / f"t01-r{repetition}.json", "T01", repetition))
    for repetition in range(1, 4):
        failed = repetition == 3
        _make_row(root, "T02", repetition, verifier_passed=not failed)
        audits.append(
            _audit(
                tmp_path / f"t02-r{repetition}.json",
                "T02",
                repetition,
                product="failed" if failed else "passed",
                category="model_behavior" if failed else "none",
            )
        )
    _make_row(root, "T03", 1, measurement_valid=False)
    audits.append(
        _audit(
            tmp_path / "t03-r1.json",
            "T03",
            1,
            measurement="invalid",
        )
    )

    result = finalize_baseline(
        config,
        stage="P4A",
        audit_inputs=audits,
        sensitive_values=("never-persist-this",),
    )

    counts = result["stage"]["counts"]
    metrics = result["stage"]["metrics"]
    assert counts == {
        "planned": 9,
        "started": 7,
        "final_classified": 7,
        "valid_passed": 5,
        "valid_failed": 1,
        "invalid": 1,
        "pending_audit": 0,
        "pending_decision": 0,
        "no_result": 2,
    }
    assert metrics["valid_run_rate"] == {
        "numerator": 6,
        "denominator": 7,
        "value": 6 / 7,
    }
    assert metrics["verified_run_success"] == {
        "numerator": 5,
        "denominator": 6,
        "value": 5 / 6,
    }
    assert metrics["stable_task_status"] == {
        "T01": "stable-pass",
        "T02": "mixed-valid",
        "T03": "insufficient-evidence",
    }
    assert metrics["failure_category_counts"] == {"model_behavior": 1}
    assert metrics["provider_requests"] == {
        "available_samples": 7,
        "started_samples": 7,
        "total": 13,
        "complete": True,
    }
    assert metrics["repeated_reads"]["total"] == 6
    assert result["cohort"]["counts"]["no_result"] == 20
    assert result["g1"]["status"] == "pending"
    assert verify_baseline(config, stage="P4A") == result


def test_all_final_rows_pass_g1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="baseline-v1",
    )
    audits = []
    for task_number in range(1, 10):
        task_id = f"T{task_number:02d}"
        for repetition in range(1, 4):
            _make_row(root, task_id, repetition)
            audits.append(
                _audit(
                    tmp_path / f"{task_id}-r{repetition}.json",
                    task_id,
                    repetition,
                )
            )

    result = finalize_baseline(
        config,
        stage="P4C",
        audit_inputs=audits,
    )

    assert result["cohort"]["counts"]["final_classified"] == 27
    assert result["cohort"]["counts"]["valid_passed"] == 27
    assert result["cohort"]["counts"]["no_result"] == 0
    assert result["g1"] == {
        "status": "passed",
        "final_classified": 27,
        "planned": 27,
    }


def test_pending_decision_is_append_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="baseline-v1",
    )
    _make_row(root, "T01", 1, verifier_passed=False)
    audit = _audit(
        tmp_path / "audit.json",
        "T01",
        1,
        product="failed",
        category="model_behavior",
        decision="required",
    )
    pending = finalize_baseline(config, stage="P4A", audit_inputs=[audit])
    assert pending["stage"]["counts"]["pending_decision"] == 1

    decision = _decision(tmp_path / "decision.json", "T01", 1)
    final = finalize_baseline(config, stage="P4A", decision_inputs=[decision])
    assert final["stage"]["counts"]["valid_failed"] == 1

    with pytest.raises(ValueError, match="already exists"):
        finalize_baseline(config, stage="P4A", decision_inputs=[decision])


def test_baseline_rejects_pilot_config_and_sensitive_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot_config, _ = write_config(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="baseline-v1"):
        build_baseline_summary(pilot_config, stage="P4A")

    config, root = write_config(
        tmp_path / "baseline",
        monkeypatch,
        cohort_id="baseline-v1",
    )
    _make_row(root, "T01", 1)
    audit = _audit(tmp_path / "sensitive.json", "T01", 1)
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["reason"] = "contains secret-sentinel"
    write_json(audit, payload)
    with pytest.raises(ValueError, match="sensitive"):
        finalize_baseline(
            config,
            stage="P4A",
            audit_inputs=[audit],
            sensitive_values=("secret-sentinel",),
        )


def test_cli_verify_only_does_not_resolve_provider_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="baseline-v1",
    )
    before = sorted(path.relative_to(root) for path in root.rglob("*"))
    monkeypatch.setattr(
        cli,
        "resolve_provider_config",
        lambda *_args, **_kwargs: pytest.fail("provider must not resolve"),
    )

    assert cli.main(
        [
            "--run-config",
            str(config),
            "--stage",
            "P4A",
            "--verify-only",
        ]
    ) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["stage"]["counts"]["no_result"] == 9
    assert output["cohort"]["counts"]["no_result"] == 27
    assert sorted(path.relative_to(root) for path in root.rglob("*")) == before


def test_user_guide_matches_baseline_cli_and_boundaries() -> None:
    guide = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "evaluation"
        / "evaluation-v2-user-guide.md"
    ).read_text(encoding="utf-8")
    finalizer_help = cli.build_parser().format_help()
    runner_help = runner_cli.build_parser().format_help()

    for option in (
        "--run-config",
        "--stage",
        "--audit-input",
        "--user-decision-input",
        "--verify-only",
    ):
        assert option in finalizer_help
        assert option in guide
    assert "--resume-missing" in runner_help
    assert "--resume-missing" in guide
    assert "不生成 P5 的 `evaluation-report.json`" in guide
    assert "不发起 provider HTTP" in guide
