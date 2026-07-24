from __future__ import annotations

import json

import pytest

from scripts.run_v3_native_human_smoke_v3 import DEFAULT_MANIFEST, load_manifest, main, run_manifest


def test_v3_manifest_has_semantic_order_and_non_leaking_denial_fixture() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    b = manifest["scenarios"][1]
    assert b["expected_postcondition"]["semantic_order"] == ["run_shell", "read_file"]
    assert "test" not in json.dumps(b["fixture"]).lower()
    assert "den" not in b["prompt"].lower()


def test_fake_run_binds_exchange_call_ids_to_runtime_events_and_file_provenance(tmp_path) -> None:
    summary = run_manifest(DEFAULT_MANIFEST, tmp_path)
    assert summary["status"] == "PASS"
    assert summary["http_attempts"] == 0
    for scenario in summary["scenarios"]:
        evidence = scenario["verification"]
        assert evidence["workspace_before"] and evidence["workspace_after"] and evidence["diff"]
        assert all(call["call_id"] and call["runtime"] for call in evidence["observed_calls"])
    b = summary["scenarios"][1]["verification"]
    assert {check["name"] for check in b["checks"]} >= {"runtime_denial_on_observed_call_id", "safe_continuation_after_denial"}


def test_v3_live_api_and_cli_fail_closed(tmp_path) -> None:
    with pytest.raises(ValueError, match="authorized-live"):
        run_manifest(DEFAULT_MANIFEST, tmp_path, execution_mode="authorized_live")
    with pytest.raises(SystemExit) as error:
        main(["--authorized-live", "--output-dir", str(tmp_path)])
    assert error.value.code == 2
