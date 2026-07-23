from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico.config import resolve_provider_config
from pico.evaluation.native_provider_profiles import (
    PROFILE_SCHEMA_VERSION,
    ProviderProfileMismatchError,
    assert_provider_profile_matches,
    build_public_provider_profile,
    canonical_profile_json,
    load_public_provider_profile,
)
from scripts.build_native_provider_profile import main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "profile.example.json"
SCHEMA_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "profile.schema.json"
SECRET = "sk-native-profile-secret-sentinel"
RAW_URL = "https://secret-host.example.test/private/v1"


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
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
    return path


def _clear_provider_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PICO_PROVIDER",
        "PICO_API_KEY",
        "PICO_BASE_URL",
        "PICO_MODEL",
        "PICO_WIRE_DIALECT",
        "PICO_PROTOCOL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_builder_writes_canonical_sanitized_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path = _config(tmp_path)
    output = tmp_path / "public" / "profile.json"

    assert (
        main(
            [
                "--provider",
                "fixture",
                "--manifest-out",
                str(output),
                "--config",
                str(config_path),
            ]
        )
        == 0
    )

    text = output.read_text(encoding="utf-8")
    profile = load_public_provider_profile(output)
    assert text == canonical_profile_json(profile)
    assert profile["schema_version"] == PROFILE_SCHEMA_VERSION
    assert profile["provider"] == "fixture"
    assert profile["sdk"] == {"package": "anthropic", "version": "0.117.0"}
    assert profile["retry"] == {
        "pico_provider_attempts": 1,
        "sdk_max_retries": 0,
    }
    assert profile["stream"] is False
    assert profile["parallel_tool_calls"] is False
    assert SECRET not in text
    assert RAW_URL not in text


def test_profile_is_rebuilt_from_config_and_compared_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    config = resolve_provider_config(
        "fixture",
        config_path=str(_config(tmp_path)),
    )
    expected = build_public_provider_profile(config)

    assert assert_provider_profile_matches(config, expected) == expected

    mismatched = {**expected, "model": "other-model"}
    with pytest.raises(ProviderProfileMismatchError, match="model"):
        assert_provider_profile_matches(config, mismatched)

    invalid = {**expected, "profile_id": "sha256:not-a-digest"}
    with pytest.raises(ValueError, match="profile_id"):
        assert_provider_profile_matches(config, invalid)


def test_versioned_schema_and_example_cover_the_public_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = load_public_provider_profile(EXAMPLE_PATH)

    assert schema["properties"]["schema_version"]["const"] == PROFILE_SCHEMA_VERSION
    assert set(schema["required"]) == set(example)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["retry"]["const"] == {
        "sdk_max_retries": 0,
        "pico_provider_attempts": 1,
    }
    assert "api_key" not in json.dumps(schema)
    assert "base_url\"" not in json.dumps(schema)
