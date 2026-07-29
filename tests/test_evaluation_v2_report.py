from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from pico.evaluation.baseline_summary import summarize_coding_rows
from pico.evaluation.evaluation_v2_config import canonical_json
from pico.evaluation import evaluation_report as reportlib
from scripts import verify_evaluation_v2_report as verify_cli


REPOSITORIES = {
    "T01": "tinyconfig",
    "T02": "tinyconfig",
    "T03": "tinyconfig",
    "T04": "miniqueue",
    "T05": "miniqueue",
    "T06": "miniqueue",
    "T07": "logslice",
    "T08": "logslice",
    "T09": "logslice",
}


def _scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summarize_coding_rows(rows).items()
        if key != "rows"
    }


def _formal_results() -> dict[str, Any]:
    rows = []
    request_counts = [24, *([10] * 26)]
    for task_number in range(1, 10):
        task_id = f"T{task_number:02d}"
        for repetition in range(1, 4):
            index = len(rows)
            failed = task_id == "T02" and repetition == 2
            row_id = f"baseline-v1-{task_id}-r{repetition}"
            rows.append(
                {
                    "row_id": row_id,
                    "task_id": task_id,
                    "repo_id": REPOSITORIES[task_id],
                    "repetition": repetition,
                    "status": "final",
                    "final_classification": (
                        "valid + failed" if failed else "valid + passed"
                    ),
                    "failure_category": "model_behavior" if failed else "none",
                    "reason": "Synthetic evidence-backed result.",
                    "result_summary": (
                        "隐藏检查失败，测量有效。"
                        if failed
                        else "隐藏检查通过，测量有效。"
                    ),
                    "facts": {
                        "provider_requests": {
                            "count": request_counts[index],
                            "exact": True,
                        },
                        "tool_steps": task_number + repetition,
                        "repeated_reads": int(task_id in {"T04", "T05", "T06"}),
                        "elapsed_time_ms": 1000 + index,
                    },
                    "evidence": {
                        "run_record": f"public/rows/{row_id}/run-record.json",
                        "evidence_view": f"public/rows/{row_id}/evidence-view.json",
                        "codex_audit": f"public/rows/{row_id}/codex-audit.json",
                        "public_checksums": f"public/rows/{row_id}/checksums.json",
                        "private_checksums": f"private/rows/{row_id}/checksums.json",
                        "verifier_result": (
                            f"public/rows/{row_id}/verifier/result.json"
                        ),
                        "public_originals": [
                            f"public/rows/{row_id}/original/.pico/report.json"
                        ],
                        "private_originals": [
                            f"private/rows/{row_id}/original/.pico/session.json"
                        ],
                    },
                }
            )
    cohort = _scope(rows)
    by_task = {
        task_id: {
            "repository": REPOSITORIES[task_id],
            **_scope([row for row in rows if row["task_id"] == task_id]),
        }
        for task_id in REPOSITORIES
    }
    by_repository = {
        repo_id: _scope([row for row in rows if row["repo_id"] == repo_id])
        for repo_id in sorted(set(REPOSITORIES.values()))
    }
    return {
        "cohort": {
            "id": "baseline-v1",
            "source": {
                "commit": "a" * 40,
                "tree": "b" * 40,
                "workspace_root": "/frozen/source",
            },
            "run_config": {
                "path": "public/run-config.json",
                "sha256": "c" * 64,
            },
            "profile": {
                "provider": "openai-compatible",
                "profile_id": "test",
                "model": "test-model",
            },
            "taskset": {"path": "benchmarks/v3/local-repos/taskset.json"},
        },
        "coding": {
            **cohort,
            "by_repository": by_repository,
            "by_task": by_task,
            "rows": rows,
        },
        "measurement_quality": {
            "planned_rows": 27,
            "valid_rows": 27,
            "invalid_rows": [],
            "exact_provider_request_rows": 27,
            "credential_scan_passed_rows": 27,
            "sdk_retry_total": 0,
            "pico_retry_total": 0,
            "protocol_error_rows": [],
        },
        "modules": _modules(),
    }


def _modules() -> dict[str, Any]:
    return {
        "cohort_id": "module-baseline-v1",
        "source_sha": "d" * 40,
        "scope": {"kind": "deterministic"},
        "modules": {
            "harness_regression": {
                "metrics": {
                    "passed": 12,
                    "total_tasks": 12,
                    "verifier_pass_rate": 1.0,
                },
                "artifact_path": "public/modules/harness.json",
            },
            "context_ablation": {
                "sample_counts": {
                    "configs": 12,
                    "repetitions_per_config": 5,
                },
                "metrics": {
                    "avg_prompt_compression_ratio": 0.1,
                    "current_request_preserved_rate": 1.0,
                },
                "formulas": {
                    "avg_prompt_compression_ratio": "1 - after / before"
                },
                "artifact_path": "public/modules/context.json",
            },
            "working_memory_ablation": {
                "metrics": {
                    "memory_on": {"repeated_reads": 0, "correct_rate": 1.0},
                    "memory_off": {"repeated_reads": 60},
                },
                "formulas": {"repeated_reads": "sum(repeated reads)"},
                "artifact_path": "public/modules/memory.json",
            },
            "recovery_ablation": {
                "metrics": {
                    "resume_enabled": {
                        "resume_success_rate": 0.9,
                        "workspace_drift_detection_rate": 1.0,
                        "resume_false_accept_rate": 0.0,
                    }
                },
                "formulas": {"resume_success_rate": "success / attempts"},
                "artifact_path": "public/modules/recovery.json",
            },
        },
        "evidence": {
            "report": "reports/module-baseline-report.json",
            "checksums": "checksums.json",
            "files": {},
        },
    }


def _report() -> dict[str, Any]:
    formal = _formal_results()
    return {
        "schema_version": reportlib.REPORT_SCHEMA,
        "artifact_type": "pico-evaluation-v2-baseline-report",
        "formal_results_sha256": hashlib.sha256(
            canonical_json(formal)
        ).hexdigest(),
        "formal_results": formal,
        "improvement_opportunities": [
            {
                "id": item_id,
                "title": item_id,
                "observation": "Observed in the frozen baseline.",
                "next_step": "Use a separate future cohort.",
                "limitation": "No causal conclusion.",
            }
            for item_id in (
                "t02-boundary-correctness",
                "t09-execution-cost",
                "miniqueue-repeated-reads",
            )
        ],
        "resume_claims": [
            {
                "claim": "26/27 valid coding rows passed.",
                "cohort": "baseline-v1",
                "sample": "27 rows",
                "formula": "passed / valid",
                "evidence": ["public/rows/<row-id>/codex-audit.json"],
                "limitation": "Fixed taskset.",
            }
        ],
        "boundary_observations": [
            {
                "id": "prompt-normalization-scope",
                "title": "Prompt 规范化与测试边界",
                "observation": "Runtime 直接注入路径存在条件式契约缺口。",
                "product_boundary": "标准入口会先规范化。",
                "runtime_boundary": "独立 Runtime API 可视为 bug。",
                "metric_impact": "Pilot 不进入正式分母。",
                "evidence": ["pilot-v3/report", "pilot-v4/report"],
                "limitation": "两个 Pilot 不是严格 A/B。",
            }
        ],
        "limitations": ["Synthetic report fixture."],
    }


def _layout(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "baseline-v1" / ("a" * 40)
    public = root / "public"
    public.mkdir(parents=True)
    run_config = public / "run-config.json"
    run_config.write_text("{}\n", encoding="utf-8")
    module_root = tmp_path / "module-baseline-v1" / ("d" * 40)
    (module_root / "public").mkdir(parents=True)
    (module_root / "reports").mkdir()
    published = tmp_path / "docs" / "evaluation-report-v2.md"
    return root, run_config, module_root, published


def test_report_acceptance_values_and_zero_denominator() -> None:
    formal = _formal_results()
    coding = formal["coding"]

    assert coding["counts"]["final_classified"] == 27
    assert coding["counts"]["valid_passed"] == 26
    assert coding["counts"]["valid_failed"] == 1
    assert coding["counts"]["invalid"] == 0
    assert coding["metrics"]["provider_requests"]["total"] == 284
    assert coding["metrics"]["failure_category_counts"] == {"model_behavior": 1}
    assert coding["by_task"]["T02"]["metrics"]["stable_task_status"] == {
        "T02": "mixed-valid"
    }
    assert all(
        scope["metrics"]["stable_task_status"][task_id] == "stable-pass"
        for task_id, scope in coding["by_task"].items()
        if task_id != "T02"
    )
    assert summarize_coding_rows([])["metrics"]["verified_run_success"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }


def test_boundary_observation_does_not_change_formal_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    formal = _formal_results()
    monkeypatch.setattr(reportlib, "verified_baseline_config", lambda _path: {})
    monkeypatch.setattr(reportlib, "cohort_root", lambda _path: tmp_path)
    monkeypatch.setattr(reportlib, "verify_coding_rows", lambda *_args: None)
    monkeypatch.setattr(reportlib, "_verify_row_evidence", lambda *_args: None)
    monkeypatch.setattr(reportlib, "verify_module_baseline", lambda _root: None)
    monkeypatch.setattr(reportlib, "_formal_results", lambda *_args: formal)
    monkeypatch.setattr(
        reportlib,
        "_boundary_observations",
        lambda _root: _report()["boundary_observations"],
    )

    result = reportlib.build_evaluation_report(tmp_path / "config.json", tmp_path)

    assert result["formal_results"] == formal
    assert result["formal_results_sha256"] == hashlib.sha256(
        canonical_json(formal)
    ).hexdigest()
    assert result["formal_results"]["coding"]["counts"]["planned"] == 27
    assert "pilot" not in json.dumps(result["formal_results"]).lower()
    assert [item["id"] for item in result["improvement_opportunities"]] == [
        "t02-boundary-correctness",
        "t09-execution-cost",
        "miniqueue-repeated-reads",
    ]


def test_sensitive_candidate_causes_zero_report_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, config, module_root, published = _layout(tmp_path)
    monkeypatch.setattr(reportlib, "build_evaluation_report", lambda *_args: _report())

    with pytest.raises(ValueError, match="sensitive value"):
        reportlib.write_evaluation_report(
            config,
            module_root,
            published,
            sensitive_values=("Prompt 规范化",),
        )

    assert not (root / reportlib.REPORT_JSON).exists()
    assert not (root / reportlib.REPORT_MARKDOWN).exists()
    assert not published.exists()


def test_report_json_markdown_and_repository_mirror_are_rebuilt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, config, module_root, published = _layout(tmp_path)
    monkeypatch.setattr(reportlib, "build_evaluation_report", lambda *_args: _report())

    result = reportlib.write_evaluation_report(
        config,
        module_root,
        published,
        sensitive_values=(),
    )

    assert result["g2_deterministic"] == "passed"
    assert result["public_export_scan"]["passed"] is True
    assert set(result["report_files"]) == {
        "artifact-json",
        "artifact-markdown",
        "published-markdown",
    }
    assert (root / reportlib.REPORT_MARKDOWN).read_bytes() == published.read_bytes()
    assert reportlib.verify_evaluation_report(
        config,
        module_root,
        published,
    )["rows"] == {
        "planned": 27,
        "final_classified": 27,
        "valid_passed": 26,
        "valid_failed": 1,
        "invalid": 0,
    }


@pytest.mark.parametrize("target", ["json", "markdown", "published"])
def test_report_verifier_rejects_content_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str,
) -> None:
    root, config, module_root, published = _layout(tmp_path)
    monkeypatch.setattr(reportlib, "build_evaluation_report", lambda *_args: _report())
    reportlib.write_evaluation_report(
        config,
        module_root,
        published,
        sensitive_values=(),
    )
    path = {
        "json": root / reportlib.REPORT_JSON,
        "markdown": root / reportlib.REPORT_MARKDOWN,
        "published": published,
    }[target]
    path.write_bytes(path.read_bytes() + b"\nDRIFT")

    with pytest.raises(ValueError):
        reportlib.verify_evaluation_report(config, module_root, published)


def test_verify_cli_is_read_only_and_does_not_resolve_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, config, module_root, published = _layout(tmp_path)
    monkeypatch.setattr(reportlib, "build_evaluation_report", lambda *_args: _report())
    reportlib.write_evaluation_report(
        config,
        module_root,
        published,
        sensitive_values=(),
    )
    before = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert verify_cli.main(
        [
            "--run-config",
            str(config),
            "--module-root",
            str(module_root),
            "--publish-doc",
            str(published),
        ]
    ) == 0

    assert json.loads(capsys.readouterr().out)["g2_deterministic"] == "passed"
    assert {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before
    assert not hasattr(verify_cli, "resolve_provider_config")


@pytest.mark.parametrize(
    "value",
    ["/absolute/path", "../escape", "nested/../escape", r"windows\escape"],
)
def test_report_rejects_dangerous_evidence_paths(value: str) -> None:
    with pytest.raises(ValueError, match="safe|unsafe"):
        reportlib._safe_relative_path(value)


def test_build_propagates_missing_or_tampered_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(reportlib, "verified_baseline_config", lambda _path: {})
    monkeypatch.setattr(reportlib, "cohort_root", lambda _path: tmp_path)
    monkeypatch.setattr(
        reportlib,
        "verify_coding_rows",
        lambda *_args: (_ for _ in ()).throw(ValueError("audit or checksum missing")),
    )

    with pytest.raises(ValueError, match="audit or checksum missing"):
        reportlib.build_evaluation_report(tmp_path / "config.json", tmp_path)
