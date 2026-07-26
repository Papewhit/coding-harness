from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.run_v3_native_human_smoke_v4 import (
    DEFAULT_MANIFEST,
    FakeProvider,
    PublicArtifactScanError,
    TRAJECTORY_DIRECTORY,
    TRAJECTORY_INVENTORY,
    _fake_factory,
    _scan_public_value,
    _write_inventory,
    copy_public_trajectory,
    load_manifest,
    main,
    run_manifest,
    validate_artifact_inventory,
    validate_public_trajectory,
)


@pytest.fixture
def live_public_shape() -> dict:
    return {
        "event": "model_exchange",
        "exchange": {
            "event": "assistant_tool_batch",
            "metadata": {
                "output_item_counts": {
                    "reasoning": 1,
                    "function_call": 2,
                    "future-item": 0,
                }
            },
        },
        "prompt_metadata": {
            "provider_profile": {
                "capabilities": {
                    "native_tools": True,
                    "reasoning": True,
                    "thinking": False,
                    "opaque_continuation": True,
                }
            }
        },
        "reasoning": {
            "hash": "sha256:" + "a" * 64,
            "type": "openai-reasoning",
            "count": 1,
        },
        "thinking": {
            "hash": "c" * 64,
            "type": "anthropic-thinking",
            "count": 2,
        },
    }


@pytest.fixture(scope="module")
def fake_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("human-smoke-v4-pass")
    summary = run_manifest(DEFAULT_MANIFEST, output)
    assert summary["status"] == "PASS"
    assert summary["http_attempts"] == 0
    return output


def test_v4_manifest_grounds_scenario_a_and_is_the_only_semantic_source() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    scenario = manifest["scenarios"][0]
    expected = scenario["expected_postcondition"]

    assert scenario["id"] == "HSMOKE-V4-A"
    assert "`pico setup`" in scenario["prompt"]
    assert "`pico sync`" in scenario["prompt"]
    assert "dependencies are ready" in scenario["prompt"]
    assert expected["semantic_order"] == ["read_file", "patch_file", "read_file"]
    assert expected["files"]["docs/quickstart.md"]["contains"] == [
        "Run `pico sync` before opening the workspace so dependencies are ready."
    ]
    runner = (
        Path(__file__).parents[1] / "scripts/run_v3_native_human_smoke_v4.py"
    ).read_text(encoding="utf-8")
    assert "pico sync" not in runner
    assert "dependencies are ready" not in runner


def test_fake_pass_survives_workspace_cleanup_with_public_hashes(
    fake_artifact: Path,
) -> None:
    summary = json.loads(
        (fake_artifact / "summary.json").read_text(encoding="utf-8")
    )

    assert summary["status"] == "PASS"
    assert summary["http_attempts"] == 0
    for record in summary["scenarios"]:
        scenario_dir = fake_artifact / record["scenario_id"]
        trajectory = scenario_dir / TRAJECTORY_DIRECTORY
        session_dir = trajectory / ".pico" / "sessions"
        assert record["trajectory"]["validated_after_workspace_cleanup"] is True
        assert list(session_dir.glob("*.events.jsonl"))
        assert not list(session_dir.glob("*.json"))
        validation = validate_public_trajectory(
            trajectory,
            scenario_dir / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
        )
        assert validation["call_count"] == len(
            record["verification"]["observed_calls"]
        )
    validate_artifact_inventory(
        fake_artifact, fake_artifact / "inventory.json"
    )


def test_semantic_failure_is_preserved_without_http(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    manifest["scenarios"][0]["expected_postcondition"]["files"][
        "docs/quickstart.md"
    ]["contains"] = ["manifest-driven unreachable postcondition"]
    manifest_path = tmp_path / "semantic-fail.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    summary = run_manifest(manifest_path, tmp_path / "artifact")

    assert summary["status"] == "FAIL"
    assert summary["http_attempts"] == 0
    assert summary["scenarios"][0]["verifier_exit"] == 1


def test_copy_fails_closed_when_public_evidence_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="session event evidence is missing"):
        copy_public_trajectory(workspace, tmp_path / "target", [])


def test_public_scanner_accepts_live_profile_and_sanitized_reasoning_thinking_shapes(
    live_public_shape: dict,
) -> None:
    _scan_public_value(
        live_public_shape,
        (),
        context="live-session.events.jsonl",
    )


@pytest.mark.parametrize(
    ("value", "value_type", "shape"),
    [
        (True, "bool", "scalar"),
        (-1, "int", "scalar"),
        ("1", "str", "scalar"),
        ({"payload": "PRIVATE-COUNT-SENTINEL"}, "mapping", "mapping"),
    ],
)
def test_output_item_counts_reject_invalid_reasoning_counts_with_safe_evidence(
    value: object,
    value_type: str,
    shape: str,
) -> None:
    event = {
        "event": "model_exchange",
        "exchange": {
            "metadata": {"output_item_counts": {"reasoning": value}}
        },
    }

    with pytest.raises(PublicArtifactScanError) as error:
        _scan_public_value(event, (), context="live-session.events.jsonl")

    evidence = error.value.public_evidence()
    assert evidence == {
        "reason": "invalid_output_item_count",
        "path": "$.exchange.metadata.output_item_counts.reasoning",
        "value_type": value_type,
        "shape": shape,
    }
    assert "PRIVATE-COUNT-SENTINEL" not in str(error.value)
    assert "PRIVATE-COUNT-SENTINEL" not in json.dumps(evidence)


@pytest.mark.parametrize(
    "field", ["reasoning", "thinking", "opaque_continuation"]
)
def test_public_capability_fields_require_exact_booleans(field: str) -> None:
    invalid = {
        "capabilities": {
            field: {
                "hash": "sha256:" + "d" * 64,
                "type": "public-shape",
                "count": 1,
            }
        }
    }

    with pytest.raises(ValueError, match="must be boolean"):
        _scan_public_value(invalid, (), context="live-profile")


def test_durable_call_id_mismatch_is_rejected(
    fake_artifact: Path, tmp_path: Path
) -> None:
    scenario_dir, record = _copy_scenario(fake_artifact, tmp_path)
    trajectory = scenario_dir / TRAJECTORY_DIRECTORY
    event_path = next((trajectory / ".pico" / "sessions").glob("*.events.jsonl"))
    records = _read_jsonl(event_path)
    finished = next(record for record in records if record["event"] == "tool_finished")
    finished["call_id"] = "mismatched-call-id"
    _write_jsonl(event_path, records)
    _write_inventory(trajectory, scenario_dir / TRAJECTORY_INVENTORY)

    with pytest.raises(ValueError, match="call_id mapping is not one-to-one"):
        validate_public_trajectory(
            trajectory,
            scenario_dir / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
        )


@pytest.mark.parametrize(
    ("field", "value", "private_values", "message"),
    [
        (
            "private_continuation",
            {"payload": "must-not-persist"},
            (),
            "private field",
        ),
        ("note", "https://private.example.invalid", (), "raw endpoint"),
        ("note", "sk-private-credential-12345", (), "credential-like secret"),
        (
            "note",
            "C:/private/provider-config.json",
            ("C:/private/provider-config.json",),
            "private locator or secret",
        ),
        ("reasoning", "private chain of thought", (), "private 'reasoning' payload"),
        (
            "reasoning",
            {
                "hash": "sha256:" + "b" * 64,
                "type": "openai-reasoning",
                "count": 1,
                "content": "private chain of thought",
            },
            (),
            "private 'reasoning' payload",
        ),
        (
            "opaque_continuation",
            {
                "hash": "sha256:" + "e" * 64,
                "type": "ProviderContinuation",
                "count": 1,
            },
            (),
            "private 'opaque_continuation' payload",
        ),
    ],
)
def test_private_material_in_public_trajectory_is_rejected(
    fake_artifact: Path,
    tmp_path: Path,
    field: str,
    value: object,
    private_values: tuple[str, ...],
    message: str,
) -> None:
    scenario_dir, record = _copy_scenario(fake_artifact, tmp_path)
    trajectory = scenario_dir / TRAJECTORY_DIRECTORY
    report_path = next((trajectory / ".pico" / "runs").glob("*/report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report[field] = value
    report_path.write_text(json.dumps(report), encoding="utf-8")
    _write_inventory(trajectory, scenario_dir / TRAJECTORY_INVENTORY)

    with pytest.raises(ValueError, match=message):
        validate_public_trajectory(
            trajectory,
            scenario_dir / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
            private_values=private_values,
        )


def test_measurement_failure_persists_exact_stub_attempt_accounting(
    tmp_path: Path,
) -> None:
    private_reasoning = "PRIVATE-REASONING-SENTINEL"

    class CountingStub:
        def __init__(self, scenario: dict) -> None:
            self.inner = _fake_factory(scenario)
            self.http_attempts = 0
            self._pico_profile_identity = {
                **self.inner._pico_profile_identity,
                "capabilities": {
                    "native_tools": True,
                    "reasoning": private_reasoning,
                },
            }

        def request(self, request):
            self.http_attempts += 1
            return self.inner.request(request)

    output = tmp_path / "accounting"
    with pytest.raises(ValueError, match="must be boolean"):
        run_manifest(
            DEFAULT_MANIFEST,
            output,
            provider_factory=lambda scenario: CountingStub(scenario),
            execution_mode="authorized_live",
            profile={"profile_id": "stub-live-public"},
        )

    result_path = output / "HSMOKE-V4-A" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["artifact_status"] == "INVALID"
    assert result["failure_classification"] == "measurement_defect"
    assert result["failure_stage"] == "public_result_validation"
    assert result["http_attempts"] == 4
    assert result["http_accounting"] == {
        "exact": True,
        "provider_http_attempts": 4,
        "persisted_before_trajectory_validation": True,
    }
    assert result["scanner_failure"] == {
        "reason": "invalid_capability_type",
        "path": (
            "$.verification.checks.3.detail.0.model_result.profile."
            "capabilities.reasoning"
        ),
        "value_type": "str",
        "shape": "scalar",
    }
    assert not (output / "summary.json").exists()
    rendered = "".join(
        path.read_text(encoding="utf-8")
        for path in output.rglob("*")
        if path.is_file()
    )
    assert private_reasoning not in rendered


def test_public_artifact_parse_failure_is_rejected(
    fake_artifact: Path, tmp_path: Path
) -> None:
    scenario_dir, record = _copy_scenario(fake_artifact, tmp_path)
    trajectory = scenario_dir / TRAJECTORY_DIRECTORY
    report_path = next((trajectory / ".pico" / "runs").glob("*/report.json"))
    report_path.write_text("{not-json", encoding="utf-8")
    _write_inventory(trajectory, scenario_dir / TRAJECTORY_INVENTORY)

    with pytest.raises(ValueError, match="JSON parse failed"):
        validate_public_trajectory(
            trajectory,
            scenario_dir / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
        )


def test_trajectory_inventory_detects_post_cleanup_mutation(
    fake_artifact: Path, tmp_path: Path
) -> None:
    scenario_dir, record = _copy_scenario(fake_artifact, tmp_path)
    trajectory = scenario_dir / TRAJECTORY_DIRECTORY
    report_path = next((trajectory / ".pico" / "runs").glob("*/report.json"))
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="inventory hash mismatch"):
        validate_public_trajectory(
            trajectory,
            scenario_dir / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
        )


def test_live_paths_and_fake_transport_contamination_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="authorized-live"):
        run_manifest(
            DEFAULT_MANIFEST,
            tmp_path / "live",
            execution_mode="authorized_live",
        )
    with pytest.raises(SystemExit) as error:
        main(["--authorized-live", "--output-dir", str(tmp_path / "cli")])
    assert error.value.code == 2

    def contaminated_factory(_scenario):
        provider = FakeProvider([])
        provider.http_attempts = 1
        return provider

    monkeypatch.setattr(
        "scripts.run_v3_native_human_smoke_v4._fake_factory",
        contaminated_factory,
    )
    with pytest.raises(ValueError, match="nonzero http_attempts"):
        run_manifest(DEFAULT_MANIFEST, tmp_path / "contaminated")


def _copy_scenario(artifact: Path, target: Path) -> tuple[Path, dict]:
    source = artifact / "HSMOKE-V4-A"
    destination = target / "HSMOKE-V4-A"
    shutil.copytree(source, destination)
    record = json.loads((destination / "result.json").read_text(encoding="utf-8"))
    return destination, record


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
