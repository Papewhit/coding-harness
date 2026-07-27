import hashlib
import json

import pytest

from scripts import run_evaluation_v2_modules as modules_runner


SOURCE_SHA = "a" * 40


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _install_fake_evaluators(monkeypatch, calls):
    def run_harness(*, benchmark_path, artifact_path, workspace_root):
        calls.append(("harness", benchmark_path, workspace_root))
        return _write_json(
            artifact_path,
            {
                "summary": {
                    "total_tasks": 12,
                    "passed": 11,
                    "failed": 1,
                    "pass_rate": 11 / 12,
                    "within_budget": 12,
                    "within_budget_rate": 1.0,
                    "verifier_passes": 11,
                    "verifier_pass_rate": 11 / 12,
                    "failure_category_counts": {"verifier_failed": 1},
                },
                "failure_category_counts": {"verifier_failed": 1},
            },
        )

    def run_context(*, artifact_path, repetitions):
        calls.append(("context", repetitions))
        return _write_json(
            artifact_path,
            {
                "schema_version": 2,
                "artifact_type": "context-ablation-v2",
                "config_count": 12,
                "repetitions": repetitions,
                "run_count": 12 * repetitions,
                "configs": [],
                "summary": {
                    "avg_full_prompt_chars": 100.0,
                    "avg_raw_prompt_chars": 200.0,
                    "avg_prompt_compression_ratio": 0.5,
                    "max_prompt_compression_ratio": 0.75,
                    "current_request_preserved_rate": 1.0,
                },
            },
        )

    def run_memory(*, artifact_path, repetitions):
        calls.append(("memory", repetitions))
        variants = {
            variant: {
                "repeated_reads": index,
                "avg_tool_steps": 1.0 + index,
                "correct_rate": 1.0,
                "memory_hit_rate": 1.0,
            }
            for index, variant in enumerate(
                ("memory_on", "memory_off", "memory_irrelevant")
            )
        }
        return _write_json(
            artifact_path,
            {
                "schema_version": 2,
                "artifact_type": "memory-ablation-v2",
                "task_count": 12,
                "repetitions": repetitions,
                "variant_count": 3,
                "runs_per_variant": 12 * repetitions,
                "run_count": 36 * repetitions,
                "category_counts": {},
                "variants": variants,
                "rows": {},
            },
        )

    def run_recovery(*, artifact_path, repetitions):
        calls.append(("recovery", repetitions))
        summary = {
            "resume_success_rate": 1.0,
            "stale_reanchor_rate": 1.0,
            "workspace_drift_detection_rate": 1.0,
            "resume_false_accept_rate": 0.0,
        }
        return _write_json(
            artifact_path,
            {
                "schema_version": 2,
                "artifact_type": "recovery-ablation-v2",
                "task_count": 10,
                "repetitions": repetitions,
                "variant_count": 2,
                "runs_per_variant": 10 * repetitions,
                "run_count": 20 * repetitions,
                "variants": {
                    "resume_enabled": {"summary": summary, "rows": []},
                    "resume_disabled": {"summary": summary, "rows": []},
                },
            },
        )

    monkeypatch.setattr(modules_runner, "run_harness_regression_v2", run_harness)
    monkeypatch.setattr(modules_runner, "run_context_ablation_v2", run_context)
    monkeypatch.setattr(modules_runner, "run_memory_ablation_v2", run_memory)
    monkeypatch.setattr(modules_runner, "run_recovery_ablation_v2", run_recovery)


def _run_fake_baseline(tmp_path, monkeypatch):
    calls = []
    _install_fake_evaluators(monkeypatch, calls)
    output_root = tmp_path / SOURCE_SHA
    result = modules_runner.run_module_baseline(output_root, SOURCE_SHA)
    return output_root, result, calls


def test_module_runner_writes_fixed_outputs_and_rebuildable_report(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PICO_NATIVE_PROVIDER_CONFIG", "do-not-persist-this-locator")
    output_root, result, calls = _run_fake_baseline(tmp_path, monkeypatch)

    assert [call[0] for call in calls] == [
        "harness",
        "context",
        "memory",
        "recovery",
    ]
    assert calls[1:] == [("context", 5), ("memory", 5), ("recovery", 3)]
    assert result == {
        "cohort_id": "module-baseline-v1",
        "source_sha": SOURCE_SHA,
        "verified_json_files": 5,
        "markdown_rebuilt": True,
    }

    checksums = json.loads(
        (output_root / modules_runner.CHECKSUMS_PATH).read_text(encoding="utf-8")
    )
    expected_paths = {
        path.as_posix() for path in modules_runner.CHECKSUMMED_PATHS
    }
    assert set(checksums["files"]) == expected_paths
    assert modules_runner.CHECKSUMS_PATH.as_posix() not in checksums["files"]
    for relative_path, record in checksums["files"].items():
        data = (output_root / relative_path).read_bytes()
        assert record == {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }

    report = json.loads(
        (output_root / modules_runner.REPORT_JSON_PATH).read_text(encoding="utf-8")
    )
    assert report["scope"]["provider_http_requests"] == 0
    assert report["scope"]["is_end_to_end_coding_result"] is False
    assert report["modules"]["context_ablation"]["sample_counts"]["runs"] == 60
    assert (
        report["modules"]["working_memory_ablation"]["sample_counts"]["runs"] == 180
    )
    assert report["modules"]["recovery_ablation"]["sample_counts"]["runs"] == 60
    assert report["modules"]["harness_regression"]["exclusions"]["count"] == 0
    markdown = (output_root / modules_runner.REPORT_MARKDOWN_PATH).read_text(
        encoding="utf-8"
    )
    assert modules_runner.render_benchmark_core_report(report) == markdown
    assert "不属于真实端到端编码任务结果" in markdown

    persisted_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_root.rglob("*")
        if path.is_file()
    )
    assert "do-not-persist-this-locator" not in persisted_text


def test_module_runner_rejects_nonempty_output_before_evaluators(
    tmp_path, monkeypatch
):
    calls = []
    _install_fake_evaluators(monkeypatch, calls)
    output_root = tmp_path / SOURCE_SHA
    output_root.mkdir()
    (output_root / "existing.txt").write_text("immutable\n", encoding="utf-8")

    with pytest.raises(ValueError, match="absent or empty"):
        modules_runner.run_module_baseline(output_root, SOURCE_SHA)

    assert calls == []
    assert (output_root / "existing.txt").read_text(encoding="utf-8") == "immutable\n"


def test_module_verifier_detects_json_and_markdown_tampering(tmp_path, monkeypatch):
    output_root, _, _ = _run_fake_baseline(tmp_path, monkeypatch)
    harness_path = output_root / modules_runner.MODULE_PATHS["harness"]
    original_harness = harness_path.read_bytes()
    harness_path.write_bytes(original_harness + b"\n")

    with pytest.raises(ValueError, match="checksum mismatch"):
        modules_runner.verify_module_baseline(output_root, SOURCE_SHA)

    harness_path.write_bytes(original_harness)
    markdown_path = output_root / modules_runner.REPORT_MARKDOWN_PATH
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8") + "tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot be rebuilt"):
        modules_runner.verify_module_baseline(output_root, SOURCE_SHA)


def test_module_runner_requires_source_sha_directory(tmp_path):
    with pytest.raises(ValueError, match="must end with"):
        modules_runner.run_module_baseline(tmp_path / "wrong", SOURCE_SHA)


def test_verify_only_cli_flag_is_available():
    args = modules_runner.build_parser().parse_args(
        ["--output-root", SOURCE_SHA, "--verify-only"]
    )
    assert args.verify_only is True


def test_clean_checkout_guard_rejects_repository_changes(monkeypatch):
    monkeypatch.setattr(
        modules_runner,
        "_run_git",
        lambda *args: " M pico/evaluation/metrics.py",
    )
    with pytest.raises(RuntimeError, match="clean checkout"):
        modules_runner.require_clean_checkout()
