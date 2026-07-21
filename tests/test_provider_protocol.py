from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch

import pytest

from pico import cli
from pico.config import resolve_provider_config


def _load_provider_base_module():
    module_path = Path(__file__).resolve().parents[1] / "pico" / "providers" / "base.py"
    spec = importlib.util.spec_from_file_location(
        "_pico_provider_base_for_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_model_client_protocol_is_complete_model_contract() -> None:
    provider_base = _load_provider_base_module()

    assert (
        get_type_hints(provider_base.complete_model)["model_client"]
        is provider_base.ModelClient
    )


def _write_profile(path: Path, body: str) -> Path:
    config = path / ".pico.toml"
    config.write_text(body, encoding="utf-8")
    return config


def test_profile_records_wire_dialect_and_independent_capabilities(
    tmp_path: Path,
) -> None:
    _write_profile(
        tmp_path,
        """
provider = "local"

[providers.local]
wire_dialect = "openai-responses"
api_key = "super-secret"
base_url = "https://example.test/v1"
model = "coding-model"

[providers.local.capabilities]
native_tools = true
strict_tool_schema = true
parallel_tool_calls = false
reasoning = true
thinking = false
opaque_continuation = true
""".strip(),
    )

    config = resolve_provider_config(start=tmp_path)

    assert config.wire_dialect == "openai-responses"
    assert config.protocol == "openai"
    assert config.capabilities.to_dict() == {
        "native_tools": True,
        "strict_tool_schema": True,
        "parallel_tool_calls": False,
        "reasoning": True,
        "thinking": False,
        "opaque_continuation": True,
    }


def test_coding_profile_without_native_tools_fails_before_startup(
    tmp_path: Path,
) -> None:
    _write_profile(
        tmp_path,
        """
provider = "local"
[providers.local]
wire_dialect = "anthropic-messages"
[providers.local.capabilities]
native_tools = false
""".strip(),
    )

    with pytest.raises(ValueError, match=r"native_tools must be true"):
        resolve_provider_config(start=tmp_path)


def test_profile_does_not_infer_dialect_from_name_or_endpoint(tmp_path: Path) -> None:
    _write_profile(
        tmp_path,
        """
provider = "looks-like-openai"
[providers.looks-like-openai]
base_url = "https://api.openai.com/v1"
model = "model"
""".strip(),
    )

    with pytest.raises(ValueError, match=r"must declare a supported wire_dialect"):
        resolve_provider_config(start=tmp_path)


def test_known_legacy_protocol_has_explicit_mapping_and_conflicts_fail(
    tmp_path: Path,
) -> None:
    config_path = _write_profile(
        tmp_path,
        """
provider = "local"
[providers.local]
protocol = "anthropic"
""".strip(),
    )
    assert resolve_provider_config(start=tmp_path).wire_dialect == "anthropic-messages"

    config_path.write_text(
        """
provider = "local"
[providers.local]
protocol = "anthropic"
wire_dialect = "openai-responses"
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicting"):
        resolve_provider_config(start=tmp_path)


def test_public_identity_excludes_secret_and_raw_url(tmp_path: Path) -> None:
    secret = "sk-identity-secret"
    raw_url = "https://user:password@example.test/v1?token=secret"
    config = resolve_provider_config(
        "openai", start=tmp_path, api_key=secret, base_url=raw_url
    )

    rendered = json.dumps(config.public_identity(tool_schema="sha256:schema"))

    assert secret not in rendered
    assert raw_url not in rendered
    assert "password" not in rendered
    assert (
        config.public_identity(tool_schema="sha256:schema")["tool_schema"]
        == "sha256:schema"
    )
    rotated = resolve_provider_config(
        "openai",
        start=tmp_path,
        api_key="new-key",
        base_url="https://other:credentials@example.test/v1?token=rotated",
    )
    assert (
        rotated.public_identity()["base_url_fingerprint"]
        == config.public_identity()["base_url_fingerprint"]
    )
    assert (
        rotated.public_identity()["profile_id"]
        == rotated.public_identity(tool_schema="another-schema")["profile_id"]
    )


def test_cli_inspect_prints_credential_free_profile_without_building_agent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_profile(
        tmp_path,
        """
provider = "local"
[providers.local]
wire_dialect = "anthropic-messages"
api_key = "do-not-print"
base_url = "https://user:password@example.test/anthropic"
model = "model"
""".strip(),
    )

    with patch("pico.cli.build_agent", side_effect=AssertionError("must not build")):
        assert cli.main(["--cwd", str(tmp_path), "--inspect-provider"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["profile"] == "local"
    assert payload["wire_dialect"] == "anthropic-messages"
    assert "do-not-print" not in output
    assert "password" not in output


def test_build_agent_locks_profile_and_tool_schema_in_session(tmp_path: Path) -> None:
    args = cli.build_arg_parser().parse_args(
        ["--cwd", str(tmp_path), "--provider", "openai"]
    )
    with patch("pico.cli.OpenAICompatibleModelClient"):
        agent = cli.build_agent(args)

    locked = agent.session["provider_profile"]
    assert locked["profile"] == "openai"
    assert locked["model"] == "gpt-5.4"
    assert locked["wire_dialect"] == "openai-responses"
    assert locked["tool_schema"] == agent.tool_signature()
    assert "api_key" not in locked
    assert "base_url" not in locked

    changed_model = resolve_provider_config(
        "openai", start=tmp_path, model="different-model"
    )
    with pytest.raises(ValueError, match="locked to a different"):
        cli._lock_provider_session(agent, changed_model, resumed=True)

    del agent.session["provider_profile"]
    with pytest.raises(ValueError, match="predates provider profile locking"):
        cli._lock_provider_session(
            agent,
            resolve_provider_config("openai", start=tmp_path),
            resumed=True,
        )
