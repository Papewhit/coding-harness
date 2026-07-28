from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import pico.config as pico_config
from pico.evaluation import evaluation_v2_config as configlib
from pico.evaluation import live_client
from pico.evaluation.evaluation_v2_config import (
    canonical_json,
    validate_live_start,
    verify_run_config,
)
from scripts import run_local_coding_tasks as cli
from tests.evaluation_v2_helpers import (
    ROOT,
    SOURCE_COMMIT,
    SOURCE_TREE,
    write_config,
)


class _Provider:
    name = "dashscope-o"
    model = "qwen3.6-plus"
    api_key = "test-api-key"

    def public_identity(self) -> dict[str, str]:
        return {
            "profile_id": (
                "sha256:"
                "41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70"
            )
        }


def _rewrite(
    config_path: Path,
    mutate: object,
    *,
    canonical: bool = True,
) -> dict[str, object]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    mutate(payload)
    encoded = (
        canonical_json(payload)
        if canonical
        else (json.dumps(payload, indent=4, ensure_ascii=False) + "\n").encode()
    )
    config_path.write_bytes(encoded)
    config_path.with_name("run-config.sha256").write_text(
        hashlib.sha256(encoded).hexdigest() + "\n",
        encoding="ascii",
    )
    return payload


def _ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, list[int]]:
    config_path, cohort_root = write_config(
        tmp_path,
        monkeypatch,
        cohort_id="pilot-v3",
    )
    _rewrite(
        config_path,
        lambda payload: payload["artifacts"].update(
            {"cohort_wsl": str(cohort_root.resolve())}
        ),
    )
    locator = tmp_path / "provider.json"
    locator.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv(configlib.CONFIG_LOCATOR_ENV, str(locator))
    monkeypatch.setattr(
        pico_config,
        "resolve_provider_config",
        lambda *_args, **_kwargs: _Provider(),
    )
    probes: list[int] = []
    monkeypatch.setattr(
        live_client,
        "probe_required_network_sandbox",
        lambda: probes.append(1),
    )
    return config_path, cohort_root, probes


def _validate(
    config_path: Path,
    cohort_root: Path,
    *,
    row: tuple[str, int, str] = ("T01", 1, "pilot-v3-T01-r1"),
) -> configlib.LiveStartValidation:
    return validate_live_start(
        config_path,
        source_root=ROOT,
        cohort_id="pilot-v3",
        requested_rows=[row],
        artifact_root=cohort_root,
    )


def test_live_start_validates_one_allowed_row_and_probes_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, probes = _ready(tmp_path, monkeypatch)

    result = _validate(config_path, cohort_root)

    assert result.row_ids == ("pilot-v3-T01-r1",)
    assert result.sensitive_values[-1] == "test-api-key"
    assert probes == [1]


def test_live_start_allows_an_allowed_subset_without_stage_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)

    result = _validate(
        config_path,
        cohort_root,
        row=("T04", 1, "pilot-v3-T04-r1"),
    )

    assert result.row_ids == ("pilot-v3-T04-r1",)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.pop("runtime"), "top-level fields"),
        (
            lambda payload: payload["source"].update({"commit": "f" * 40}),
            "HEAD/tree",
        ),
        (
            lambda payload: payload["artifacts"].update(
                {"cohort_wsl": "/outside/artifact"}
            ),
            "Artifact",
        ),
    ],
)
def test_live_start_rejects_schema_source_and_artifact_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    message: str,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)
    _rewrite(config_path, mutation)

    with pytest.raises(ValueError, match=message):
        _validate(config_path, cohort_root)


def test_live_start_rejects_dirty_tracked_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)
    monkeypatch.setattr(
        configlib,
        "_git_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("tracked files must be clean")
        ),
    )

    with pytest.raises(ValueError, match="tracked files"):
        _validate(config_path, cohort_root)


def test_live_start_rejects_outside_or_existing_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="outside run config"):
        _validate(
            config_path,
            cohort_root,
            row=("T02", 1, "pilot-v3-T02-r1"),
        )

    existing = cohort_root / "public" / "rows" / "pilot-v3-T01-r1"
    existing.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        _validate(config_path, cohort_root)


def test_live_start_rejects_locator_profile_and_sandbox_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)
    monkeypatch.delenv(configlib.CONFIG_LOCATOR_ENV)
    with pytest.raises(ValueError, match="regular file"):
        _validate(config_path, cohort_root)

    locator = tmp_path / "provider.json"
    monkeypatch.setenv(configlib.CONFIG_LOCATOR_ENV, str(locator))
    monkeypatch.setattr(_Provider, "model", "other-model")
    with pytest.raises(ValueError, match="provider/profile/model"):
        _validate(config_path, cohort_root)

    monkeypatch.setattr(_Provider, "model", "qwen3.6-plus")
    monkeypatch.setattr(
        live_client,
        "probe_required_network_sandbox",
        lambda: (_ for _ in ()).throw(RuntimeError("probe failed")),
    )
    with pytest.raises(RuntimeError, match="probe failed"):
        _validate(config_path, cohort_root)


def test_live_start_ignores_non_blocking_environment_and_serialization_differences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)

    def mutate(payload: dict[str, object]) -> None:
        payload["source"]["workspace_root"] = "/different/clone"
        payload["environment"]["os"] = "ubuntu 99.99"
        payload["environment"]["python"] = "3.12.99"
        payload["environment"]["openai_sdk"] = "9.9.9"
        payload["client"]["command"][0] = "/venv/bin/python3"
        payload["launch_commands"]["p3_g0"]["display"] = "different display"

    _rewrite(config_path, mutate, canonical=False)

    result = _validate(config_path, cohort_root)

    assert result.row_ids == ("pilot-v3-T01-r1",)
    with pytest.raises(ValueError, match="canonical"):
        verify_run_config(config_path)


def test_live_start_does_not_rebuild_config_or_construct_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, cohort_root, _ = _ready(tmp_path, monkeypatch)
    monkeypatch.setattr(
        configlib,
        "build_run_config",
        lambda **_kwargs: pytest.fail("live validation must not rebuild config"),
    )

    _validate(config_path, cohort_root)


@pytest.mark.parametrize(
    "selection",
    [
        ("--cohort-id", "pilot-v3"),
        ("--stage", "P3-G0"),
        ("--task", "T01"),
        ("--repo", "pico"),
        ("--repetitions", "1"),
    ],
)
def test_verify_only_rejects_live_selection_and_has_no_live_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: tuple[str, str],
) -> None:
    config_path, _, _ = _ready(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "validate_live_start",
        lambda *_args, **_kwargs: pytest.fail(
            "--verify-only must not validate live start"
        ),
    )
    monkeypatch.setattr(
        configlib,
        "build_run_config",
        lambda **_kwargs: pytest.fail("--verify-only must not generate a config"),
    )
    monkeypatch.setattr(
        pico_config,
        "resolve_provider_config",
        lambda *_args, **_kwargs: pytest.fail(
            "--verify-only must not resolve a provider"
        ),
    )
    monkeypatch.setattr(
        live_client,
        "probe_required_network_sandbox",
        lambda: pytest.fail("--verify-only must not probe the sandbox"),
    )

    assert cli.main(["--run-config", str(config_path), "--verify-only"]) == 0
    with pytest.raises(SystemExit, match="live selection"):
        cli.main(
            [
                "--run-config",
                str(config_path),
                "--verify-only",
                *selection,
            ]
        )


def test_generator_clean_check_ignores_untracked_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *args: str) -> str:
        calls.append(args)
        return (
            SOURCE_COMMIT
            if args == ("rev-parse", "HEAD")
            else SOURCE_TREE
            if args == ("rev-parse", "HEAD^{tree}")
            else ""
        )

    monkeypatch.setattr(configlib, "_git", fake_git)

    assert configlib._git_identity(ROOT) == (SOURCE_COMMIT, SOURCE_TREE)
    assert (
        "status",
        "--porcelain",
        "--untracked-files=no",
    ) in calls


def test_generator_records_environment_and_absent_locator_without_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        configlib,
        "_git_identity",
        lambda _root, require_clean=True: (SOURCE_COMMIT, SOURCE_TREE),
    )
    monkeypatch.setattr(
        configlib,
        "_runtime_environment",
        lambda: {
            "execution_environment": "different",
            "os": "ubuntu 99.99",
            "python": "3.99.1",
            "implementation": "CPython",
            "openai_sdk": "9.9.9",
        },
    )
    monkeypatch.delenv(configlib.CONFIG_LOCATOR_ENV, raising=False)

    payload = configlib.build_run_config(
        source_root=ROOT,
        artifact_root=tmp_path,
        cohort_id="pilot-v3",
    )

    assert payload["environment"]["python"] == "3.99.1"
    assert payload["environment"]["openai_sdk"] == "9.9.9"
    assert payload["private_config"]["env_defined"] is False
    assert payload["private_config"]["target_exists"] is False
    assert payload["private_config"]["target_is_file"] is False
