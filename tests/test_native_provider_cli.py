from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from pico.config import resolve_provider_config
from pico.evaluation.native_provider_profiles import (
    build_public_provider_profile,
    canonical_profile_json,
)
from scripts.run_native_provider_conformance import (
    CONFIG_LOCATOR_ENV,
    CONFIG_LOCATOR_SCHEMA_VERSION,
    build_parser,
    main,
)

from .test_native_provider_evaluator import _passing_observation


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "cases.json"
SECRET = "sk-native-cli-secret-sentinel"
RAW_URL = "https://native-cli-secret.example.test/private/v1"


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    config_root = tmp_path / "secret-config-root"
    config_root.mkdir()
    config_path = config_root / "provider.toml"
    config_path.write_text(
        "\n".join(
            [
                "[providers.fixture]",
                'wire_dialect = "anthropic-messages"',
                'model = "fixture-model"',
                f'base_url = "{RAW_URL}"',
                f'api_key = "{SECRET}"',
                "",
                "[providers.fixture.capabilities]",
                "native_tools = true",
                "strict_tool_schema = false",
                "parallel_tool_calls = false",
                "reasoning = false",
                "thinking = true",
                "opaque_continuation = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    profile = build_public_provider_profile(
        resolve_provider_config("fixture", config_path=str(config_path))
    )
    run_root = tmp_path / "run-snapshot"
    run_root.mkdir()
    profile_path = run_root / "expected-profile.json"
    profile_path.write_text(canonical_profile_json(profile), encoding="utf-8")
    return config_path, profile_path, run_root


def _clear_provider_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PICO_PROVIDER",
        "PICO_API_KEY",
        "PICO_BASE_URL",
        "PICO_MODEL",
        "PICO_WIRE_DIALECT",
        "PICO_PROTOCOL",
        CONFIG_LOCATOR_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def _argv(profile_path: Path, artifact_dir: Path) -> list[str]:
    return [
        "--case-set",
        str(CASE_PATH),
        "--provider",
        "fixture",
        "--expected-profile",
        str(profile_path),
        "--repetitions",
        "2",
        "--artifact-dir",
        str(artifact_dir),
    ]


def test_help_exposes_only_frozen_contract(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(["--help"])

    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    for option in (
        "--case-set",
        "--provider",
        "--expected-profile",
        "--repetitions",
        "--artifact-dir",
        "--case",
    ):
        assert option in help_text
    for forbidden in ("--profile", "--output", "--runner-plugin", "--config"):
        assert forbidden not in help_text


@pytest.mark.parametrize(
    "arguments",
    [
        ["--profile", "legacy.json"],
        ["--output", "legacy.json"],
        ["--runner-plugin", "module:callable"],
        ["--config", "private.toml"],
    ],
)
def test_parser_rejects_legacy_and_unfrozen_options(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(arguments)

    assert raised.value.code == 2


def test_cli_resolves_profile_from_independent_worktree_without_config_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path, profile_path, run_root = _workspace(tmp_path)
    artifact_dir = tmp_path / "artifacts" / "shard"
    invocation_root = tmp_path / "invocation-cwd"
    invocation_root.mkdir()
    monkeypatch.chdir(invocation_root)
    monkeypatch.setenv(CONFIG_LOCATOR_ENV, str(config_path))
    calls: list[tuple[str, str]] = []

    def fake_live_call(self, case, expected_profile):
        calls.append((self.provider, case["id"]))
        return _passing_observation(case)

    monkeypatch.setattr(
        "pico.evaluation.native_provider_live.NativeProviderLiveRunner.__call__",
        fake_live_call,
    )

    assert main(_argv(profile_path, artifact_dir)) == 0

    rows = [
        json.loads(line)
        for line in (artifact_dir / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in artifact_dir.iterdir()
    )
    assert calls[:3] == [
        ("fixture", "NP01-final"),
        ("fixture", "NP01-final"),
        ("fixture", "NP02-single-call"),
    ]
    assert len(rows) == 16
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bindings"]["config_locator"]["schema_version"] == (
        CONFIG_LOCATOR_SCHEMA_VERSION
    )
    assert manifest["bindings"]["config_locator"]["environment_variable"] == (
        CONFIG_LOCATOR_ENV
    )
    assert manifest["bindings"]["public_profile_id"].startswith("sha256:")
    assert len(manifest["bindings"]["public_profile_sha256"]) == 64
    assert set(manifest["bindings"]["config_locator"]) == {
        "schema_version",
        "environment_variable",
    }
    assert ROOT != config_path.parent
    assert run_root != config_path.parent
    assert invocation_root != config_path.parent
    assert config_path.name not in serialized
    assert str(config_path) not in serialized
    assert hashlib.sha256(config_path.read_bytes()).hexdigest() not in serialized
    assert "config_file_sha256" not in serialized
    assert SECRET not in serialized
    assert RAW_URL not in serialized
    assert "native-cli-secret.example.test" not in serialized


def test_profile_mismatch_writes_zero_row_not_computable_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path, profile_path, run_root = _workspace(tmp_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["model"] = "wrong-model"
    profile_path.write_text(canonical_profile_json(profile), encoding="utf-8")
    artifact_dir = tmp_path / "mismatch"
    monkeypatch.chdir(run_root)
    monkeypatch.setenv(CONFIG_LOCATOR_ENV, str(config_path))

    assert main(_argv(profile_path, artifact_dir)) == 2

    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
    assert (artifact_dir / "rows.jsonl").read_bytes() == b""
    assert manifest["run_status"] == "preflight_failure"
    assert manifest["row_count"] == 0
    assert summary["computability"] == "not_computable"


def test_missing_audited_config_locator_fails_before_case_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    _, profile_path, run_root = _workspace(tmp_path)
    artifact_dir = tmp_path / "missing-locator"
    monkeypatch.chdir(run_root)
    called = False

    def unexpected_call(_self, _case, _profile):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        "pico.evaluation.native_provider_live.NativeProviderLiveRunner.__call__",
        unexpected_call,
    )

    assert main(_argv(profile_path, artifact_dir)) == 2
    assert called is False
    assert (artifact_dir / "rows.jsonl").read_bytes() == b""
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bindings"]["config_locator"] == {
        "schema_version": CONFIG_LOCATOR_SCHEMA_VERSION,
        "environment_variable": CONFIG_LOCATOR_ENV,
    }


def test_invalid_public_profile_never_hashes_secret_bearing_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path, profile_path, run_root = _workspace(tmp_path)
    unsafe = profile_path.read_text(encoding="utf-8").rstrip()
    unsafe = unsafe[:-1] + f',\"api_key\":\"{SECRET}\"}}\n'
    profile_path.write_text(unsafe, encoding="utf-8")
    unsafe_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    artifact_dir = tmp_path / "invalid-profile"
    monkeypatch.chdir(run_root)
    monkeypatch.setenv(CONFIG_LOCATOR_ENV, str(config_path))

    assert main(_argv(profile_path, artifact_dir)) == 2

    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in artifact_dir.iterdir()
    )
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bindings"]["public_profile_sha256"] == ""
    assert manifest["bindings"]["public_profile_id"] == ""
    assert unsafe_hash not in serialized
    assert SECRET not in serialized


def test_existing_artifact_directory_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path, profile_path, run_root = _workspace(tmp_path)
    artifact_dir = tmp_path / "existing"
    artifact_dir.mkdir()
    marker = artifact_dir / "owned.txt"
    marker.write_text("retain", encoding="utf-8")
    monkeypatch.chdir(run_root)
    monkeypatch.setenv(CONFIG_LOCATOR_ENV, str(config_path))
    monkeypatch.setattr(
        "pico.evaluation.native_provider_live.NativeProviderLiveRunner.__call__",
        lambda _self, case, _profile: _passing_observation(case),
    )

    assert main(_argv(profile_path, artifact_dir)) == 2
    assert marker.read_text(encoding="utf-8") == "retain"
    assert list(artifact_dir.iterdir()) == [marker]
