from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from coda.evaluation import evaluation_v2_config as configlib
from coda.evaluation.taskset import sha256_file


ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "benchmarks" / "v3" / "native-provider" / "selection.json"
PROFILE_FIELDS = frozenset(
    {
        "name",
        "profile_id",
        "model",
        "base_url_fingerprint",
        "wire_dialect",
        "adapter_mode",
        "sdk",
        "capabilities",
        "stream",
        "parallel_tool_execution",
        "sdk_max_retries",
        "coda_provider_attempts",
    }
)
FORBIDDEN_PROFILE_FIELDS = frozenset(
    {
        "api_key",
        "base_url",
        "credential",
        "secret",
        "token",
        "ticket",
        "wave",
        "handoff",
        "artifact_path",
        "evaluation_rows",
        "gate_conclusion",
        "evaluated_for_current_source",
    }
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def test_selection_is_the_only_current_canonical_profile_manifest() -> None:
    payload = json.loads(SELECTION.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "coda-native-provider-selection-v1"
    assert payload["selection_status"] == "selected"
    assert set(payload) == {
        "schema_version",
        "selection_status",
        "selected_profile",
        "provenance",
    }
    assert set(payload["selected_profile"]) == PROFILE_FIELDS
    assert set(payload["selected_profile"]).isdisjoint(FORBIDDEN_PROFILE_FIELDS)
    assert not (SELECTION.parent / "selection-w6r2.json").exists()
    assert "evaluated_for_current_source" not in SELECTION.read_text(encoding="utf-8")


def test_selection_provenance_resolves_to_the_recorded_git_blob() -> None:
    provenance = json.loads(SELECTION.read_text(encoding="utf-8"))["provenance"]

    assert provenance == {
        "source_ref": "eval-v2/p5-integrated",
        "source_path_at_ref": "benchmarks/v3/native-provider/selection-w6r2.json",
        "source_git_blob_oid": "6649c651c09e7e65936dadea0efee901e6f12d61",
    }
    assert (
        _git(
            "rev-parse",
            f"{provenance['source_ref']}:{provenance['source_path_at_ref']}",
        )
        == provenance["source_git_blob_oid"]
    )


def test_run_config_binds_the_clean_selection_without_a_gate_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        configlib,
        "_git_identity",
        lambda _root, require_clean=True: ("a" * 40, "b" * 40),
    )
    payload = configlib.build_run_config(
        source_root=ROOT,
        artifact_root=tmp_path,
        cohort_id="pilot-v3",
    )

    assert payload["profile"]["selection_path"] == (
        "benchmarks/v3/native-provider/selection.json"
    )
    assert payload["profile"]["selection_sha256"] == sha256_file(
        SELECTION, normalize_lf=True
    )
    assert payload["profile"]["native_gate_hash"] == ""
