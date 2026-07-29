from __future__ import annotations

import json

import pytest

from scripts.run_v3_native_human_smoke import DEFAULT_MANIFEST, load_manifest, main, run_manifest


def test_manifest_is_the_single_source_for_prompt_fixture_and_verifier() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    scenarios = {scenario["id"]: scenario for scenario in manifest["scenarios"]}

    assert "`coda sync`" in scenarios["HSMOKE-V2-A"]["expected_postcondition"]["files"]["docs/quickstart.md"]["contains"][0]
    assert "test" not in json.dumps(scenarios["HSMOKE-V2-B"]["fixture"], ensure_ascii=False).lower()
    assert "den" not in scenarios["HSMOKE-V2-B"]["prompt"].lower()


def test_fake_provider_harness_persists_complete_pass_artifacts(tmp_path) -> None:
    summary = run_manifest(DEFAULT_MANIFEST, tmp_path)

    assert summary["status"] == "PASS"
    assert summary["provider_http_attempts"] == 0
    assert summary["execution_mode"] == "fake_provider"
    for scenario in summary["scenarios"]:
        assert scenario["coda_exit"] == 0
        assert scenario["verifier_exit"] == 0
        assert scenario["provider_http_attempts"] == 0
        assert scenario["verification"]["status"] == "PASS"
        assert (tmp_path / scenario["scenario_id"] / "coda.stdout.txt").is_file()
        assert (tmp_path / scenario["scenario_id"] / "coda.stderr.txt").is_file()
        assert (tmp_path / scenario["scenario_id"] / "coda.exit.txt").is_file()
        assert (tmp_path / scenario["scenario_id"] / "verifier.exit.txt").is_file()


def test_verifier_accumulates_failures_instead_of_failing_fast(tmp_path) -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    manifest["scenarios"][0]["expected_postcondition"]["files"]["docs/quickstart.md"]["contains"].append("missing literal")
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(manifest), encoding="utf-8")

    summary = run_manifest(altered, tmp_path / "artifacts")

    checks = summary["scenarios"][0]["verification"]["checks"]
    assert summary["status"] == "FAIL"
    assert len(checks) > 3
    assert any(check["name"].startswith("file_contains") and not check["passed"] for check in checks)
    assert any(check["name"] == "tool_sequence" for check in checks)


def test_denial_requires_runtime_evidence_and_safe_continuation(tmp_path) -> None:
    summary = run_manifest(DEFAULT_MANIFEST, tmp_path)
    scenario = next(item for item in summary["scenarios"] if item["scenario_id"] == "HSMOKE-V2-B")
    checks = {item["name"]: item["passed"] for item in scenario["verification"]["checks"]}

    assert checks["runtime_approval_requested"]
    assert checks["runtime_approval_denied"]
    assert checks["denied_command_has_no_side_effect"]
    assert checks["continued_with_safe_runtime_call"]


def test_cli_is_fail_closed_without_a_mode(tmp_path) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--output-dir", str(tmp_path)])

    assert error.value.code == 2


def test_authorized_live_is_gated_before_provider_construction(tmp_path) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--authorized-live", "--output-dir", str(tmp_path)])

    assert error.value.code == 2
