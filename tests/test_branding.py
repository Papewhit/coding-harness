from __future__ import annotations

from importlib import metadata, util
import os
from pathlib import Path, PurePosixPath
import subprocess
import xml.etree.ElementTree as ET

from coda import config as configlib


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCUMENTS = frozenset(
    {
        "docs/configuration.md",
        "docs/memory.md",
        "docs/sandbox.md",
        "docs/skills.md",
        "docs/metrics/coda-v3-context-asset-contract.md",
    }
)
NON_TEXT_SUFFIXES = frozenset(
    {
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".mp3",
        ".mp4",
        ".pdf",
        ".png",
        ".pyc",
        ".webp",
        ".zip",
    }
)


def _tracked_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"]
    ).decode("utf-8")
    return [value for value in output.split("\0") if value]


def _is_active(relative: str) -> bool:
    path = PurePosixPath(relative)
    if path.parts[:2] == (".codex", "eval") or path.parts[:1] == ("release",):
        return False
    if path.parts[:1] == ("docs",):
        return relative in CURRENT_DOCUMENTS
    return True


def test_active_tracked_paths_and_text_have_no_previous_brand() -> None:
    legacy = ("pi" + "co").casefold()
    path_findings: list[str] = []
    text_findings: list[str] = []

    for relative in _tracked_paths():
        if not _is_active(relative):
            continue
        if legacy in relative.casefold():
            path_findings.append(relative)
        path = ROOT / Path(relative)
        if not path.is_file() or path.suffix.casefold() in NON_TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if legacy in text.casefold():
            text_findings.append(relative)

    assert path_findings == []
    assert text_findings == []


def test_distribution_and_console_scripts_expose_only_coda() -> None:
    legacy = "pi" + "co"
    assert util.find_spec(legacy) is None

    distribution = metadata.distribution("coda")
    scripts = {
        entry.name: entry.value
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    assert scripts == {
        "coda": "coda.cli:main",
        "coda-tui": "coda.tui.main:main",
    }


def test_logo_uses_valid_bright_teal_brand_palette() -> None:
    logo = ROOT / "assets" / "coda-logo.svg"

    ET.parse(logo)
    source = logo.read_text(encoding="utf-8").lower()

    assert "#ffffff" in source
    assert "#e9f6f2" in source
    assert "#9fcfc5" in source
    assert "#62b8aa" in source
    assert "#237a70" in source
    assert "#164f49" in source
    assert "#0f1117" not in source


def test_previous_brand_config_and_environment_are_not_discovered(
    tmp_path: Path, monkeypatch
) -> None:
    legacy = "pi" + "co"
    (tmp_path / f".{legacy}.toml").write_text(
        'provider = "deepseek"\n',
        encoding="utf-8",
    )
    previous_provider_env = f"{legacy.upper()}_PROVIDER"
    monkeypatch.setattr(
        configlib,
        "DEFAULT_CONFIG_PATH",
        tmp_path / "missing-global-config.toml",
    )

    with monkeypatch.context() as scoped:
        for name in tuple(os.environ):
            if name.startswith(("CODA_", "OPENAI_", "ANTHROPIC_", "DEEPSEEK_")):
                scoped.delenv(name, raising=False)
        scoped.setenv(previous_provider_env, "deepseek")

        assert configlib.find_project_config(tmp_path) is None
        resolved = configlib.resolve_provider_config(start=tmp_path)

    assert resolved.name == configlib.DEFAULT_PROVIDER
