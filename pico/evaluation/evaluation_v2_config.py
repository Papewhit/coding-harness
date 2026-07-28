"""Frozen run configuration and taskset verification for Evaluation v2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

from pico.evaluation.taskset import (
    sha256_file,
    verify_taskset_lock as verify_frozen_taskset,
)
from pico.evaluation.evaluation_v2_schedule import (
    PILOT_COHORTS,
    allowed_rows,
    launch_commands,
)


RUN_CONFIG_SCHEMA = "pico-evaluation-v2-run-config-v1"
TASKSET_PATH = Path("benchmarks/v3/local-repos/taskset.json")
TASKSET_LOCK_PATH = Path("benchmarks/v3/local-repos/taskset.lock.json")
PROFILE_SELECTION_PATH = Path("benchmarks/v3/native-provider/selection-w6r2.json")
CLIENT_PATH = Path("scripts/run_pico_live_task_client.py")
CONFIG_LOCATOR_ENV = "PICO_NATIVE_PROVIDER_CONFIG"
WINDOWS_ARTIFACT_ROOT = r"F:\dev\llm\pico-eval-artifacts\evaluation-v2"
WSL_ARTIFACT_ROOT = "/mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2"
SUPPORTED_COHORTS = frozenset({*PILOT_COHORTS, "baseline-v1"})
RUN_CONFIG_KEYS = frozenset(
    "allowed_rows artifacts client cohort_id environment launch_commands "
    "private_config profile retry runtime schema_version source taskset".split()
)


@dataclass(frozen=True)
class LiveStartValidation:
    """Facts produced by the single pre-row live-start validator."""

    payload: Mapping[str, Any]
    sha256: str
    row_ids: tuple[str, ...]
    sensitive_values: tuple[str, ...]


def canonical_json(value: Any) -> bytes:
    """Return stable, readable UTF-8 JSON bytes."""

    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verify_taskset_lock(source_root: Path) -> dict[str, Any]:
    """Recompute every frozen task and repository identity."""

    return verify_frozen_taskset(
        source_root=source_root,
        taskset_path=TASKSET_PATH,
        lock_path=TASKSET_LOCK_PATH,
    )


def build_run_config(
    *,
    source_root: Path,
    artifact_root: Path,
    cohort_id: str,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build one credential-free, source-bound run configuration."""

    if cohort_id not in SUPPORTED_COHORTS:
        raise ValueError(f"unsupported Evaluation v2 cohort: {cohort_id}")
    source_root = source_root.resolve()
    artifact_root = artifact_root.resolve()
    source_commit, source_tree = _git_identity(source_root)
    taskset = verify_taskset_lock(source_root)
    selection = _load_object(source_root / PROFILE_SELECTION_PATH)
    selected = _required_object(selection, "selected_profile")
    profile = _public_profile(selected)
    _validate_selected_profile(profile)
    runtime_environment = dict(environment or _runtime_environment())
    locator = _locator_check()
    cohort_wsl = f"{WSL_ARTIFACT_ROOT}/{cohort_id}/{source_commit}"
    run_config_wsl = f"{cohort_wsl}/public/run-config.json"
    client_path = source_root / CLIENT_PATH
    if not client_path.is_file():
        raise ValueError(f"live task client does not exist: {client_path}")
    inner_client_command = [
        _environment_python(),
        str(client_path),
        "--run-config",
        str(artifact_root / cohort_id / source_commit / "public" / "run-config.json"),
    ]
    commands = launch_commands(
        source_root=str(source_root),
        run_config=run_config_wsl,
        cohort_id=cohort_id,
    )
    return _run_config_payload(
        source_root=source_root,
        source_commit=source_commit,
        source_tree=source_tree,
        cohort_id=cohort_id,
        taskset=taskset,
        selection=selection,
        profile=profile,
        runtime_environment=runtime_environment,
        locator=locator,
        cohort_wsl=cohort_wsl,
        client_path=client_path,
        inner_client_command=inner_client_command,
        commands=commands,
    )


def _run_config_payload(
    *,
    source_root: Path,
    source_commit: str,
    source_tree: str,
    cohort_id: str,
    taskset: Mapping[str, Any],
    selection: Mapping[str, Any],
    profile: Mapping[str, Any],
    runtime_environment: Mapping[str, str],
    locator: Mapping[str, bool],
    cohort_wsl: str,
    client_path: Path,
    inner_client_command: list[str],
    commands: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RUN_CONFIG_SCHEMA,
        "cohort_id": cohort_id,
        "source": {
            "commit": source_commit,
            "tree": source_tree,
            "workspace_root": str(source_root),
        },
        "taskset": {
            "path": TASKSET_PATH.as_posix(),
            "sha256": taskset["taskset_sha256"],
            "lock_path": TASKSET_LOCK_PATH.as_posix(),
            "lock_sha256": taskset["lock_sha256"],
            "taskset_id": taskset["taskset_id"],
            "task_count": taskset["task_count"],
        },
        "profile": {
            "public_profile": profile,
            "selection_path": PROFILE_SELECTION_PATH.as_posix(),
            "selection_sha256": sha256_file(
                source_root / PROFILE_SELECTION_PATH, normalize_lf=True
            ),
            "native_gate_hash": str(
                selection.get("frozen_inputs", {}).get(
                    "native_deterministic_gate_sha256", ""
                )
            ),
        },
        "runtime": _runtime_policy(),
        "retry": {
            "sdk_max_retries": 0,
            "pico_provider_attempts": 1,
            "semantic_reruns": 0,
        },
        "environment": runtime_environment,
        "private_config": {
            "locator_env": CONFIG_LOCATOR_ENV,
            "locator_type": "path",
            **locator,
            "value_persisted": False,
        },
        "artifacts": {
            "windows_root": WINDOWS_ARTIFACT_ROOT,
            "wsl_root": WSL_ARTIFACT_ROOT,
            "cohort_windows": (
                WINDOWS_ARTIFACT_ROOT + f"\\{cohort_id}\\{source_commit}"
            ),
            "cohort_wsl": cohort_wsl,
        },
        "client": {
            "path": CLIENT_PATH.as_posix(),
            "sha256": sha256_file(client_path, normalize_lf=True),
            "command": inner_client_command,
        },
        "allowed_rows": allowed_rows(cohort_id),
        "launch_commands": commands,
    }


def _runtime_policy() -> dict[str, Any]:
    not_applicable = {
        "status": "not_applicable",
        "reason": "Pico native ModelRequest exposes no sampling parameter",
    }
    return {
        "sampling_parameters": {
            "sampling": dict(not_applicable),
            "temperature": dict(not_applicable),
        },
        "max_output_tokens": 4096,
        "max_tool_steps": 50,
        "provider_timeout_seconds": 300,
        "row_timeout_seconds": 600,
        "stream": False,
        "parallel_tool_execution": False,
        "approval_policy": "auto",
        "auto_dream": False,
        "allowed_tools": [
            "list_files",
            "read_file",
            "search",
            "run_shell",
            "write_file",
            "patch_file",
            "todo_add",
            "todo_update",
            "todo_list",
        ],
        "shell_network_access": False,
        "shell_sandbox": {"mode": "required", "backend": "bubblewrap"},
    }


def _environment_python() -> str:
    """Use one stable venv interpreter spelling across direct and uv-run entry."""

    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidate = Path(sys.prefix) / relative
    return str(candidate) if candidate.is_file() else sys.executable


def write_run_config(
    *,
    source_root: Path,
    artifact_root: Path,
    cohort_id: str,
    environment: Mapping[str, str] | None = None,
) -> tuple[Path, str]:
    """Create one run config without overwriting any existing cohort content."""

    if artifact_root.resolve() != Path(WSL_ARTIFACT_ROOT).resolve():
        raise ValueError(
            f"Evaluation v2 configs must use the frozen artifact root: {WSL_ARTIFACT_ROOT}"
        )
    payload = build_run_config(
        source_root=source_root,
        artifact_root=artifact_root,
        cohort_id=cohort_id,
        environment=environment,
    )
    source_commit = str(payload["source"]["commit"])
    cohort_root = artifact_root.resolve() / cohort_id / source_commit
    if cohort_root.exists() and any(cohort_root.iterdir()):
        raise FileExistsError(f"cohort directory is not empty: {cohort_root}")
    public = cohort_root / "public"
    public.mkdir(parents=True, exist_ok=True)
    config_path = public / "run-config.json"
    encoded = canonical_json(payload)
    _write_bytes_atomic(config_path, encoded)
    digest = sha256_bytes(encoded)
    _write_bytes_atomic(public / "run-config.sha256", f"{digest}\n".encode("ascii"))
    return config_path, digest


def verify_run_config(path: Path) -> dict[str, Any]:
    """Verify only canonical JSON, the existing schema, and the sibling hash."""

    payload, digest = _read_run_config(path, require_canonical=True)
    return {
        "cohort_id": payload["cohort_id"],
        "sha256": digest,
        "source": payload["source"],
    }


def validate_live_start(
    run_config: Path,
    *,
    source_root: Path,
    cohort_id: str,
    requested_rows: Sequence[tuple[str, int, str]],
    artifact_root: Path,
) -> LiveStartValidation:
    """Apply the closed live-start blocker set once before any row exists."""

    path = run_config.resolve()
    payload, digest = _read_run_config(path, require_canonical=False)
    source_root = source_root.resolve()
    artifact_root = artifact_root.resolve()

    source_commit, source_tree = _git_identity(source_root)
    expected_source = _required_object(payload, "source")
    if (
        source_commit != expected_source.get("commit")
        or source_tree != expected_source.get("tree")
    ):
        raise ValueError("live source HEAD/tree does not match run config")
    if payload.get("cohort_id") != cohort_id:
        raise ValueError("requested cohort is outside run config")

    artifacts = _required_object(payload, "artifacts")
    declared_artifact = Path(str(artifacts.get("cohort_wsl", ""))).resolve()
    if (
        artifact_root != declared_artifact
        or path != artifact_root / "public" / "run-config.json"
    ):
        raise ValueError("Artifact output directory is outside run config")

    allowed = {
        (str(row["task_id"]), int(row["repetition"]), str(row["row_id"]))
        for row in payload.get("allowed_rows", [])
        if isinstance(row, Mapping)
    }
    row_ids = []
    for task_id, repetition, row_id in requested_rows:
        identity = (str(task_id), int(repetition), str(row_id))
        if identity not in allowed:
            raise ValueError("requested row is outside run config")
        private_row = artifact_root / "private" / "rows" / row_id
        public_row = artifact_root / "public" / "rows" / row_id
        if private_row.exists() or public_row.exists():
            raise ValueError(f"target row already exists: {row_id}")
        row_ids.append(row_id)

    locator = os.environ.get(CONFIG_LOCATOR_ENV, "")
    locator_path = Path(locator) if locator else None
    if not locator_path or not locator_path.is_file():
        raise ValueError(
            f"{CONFIG_LOCATOR_ENV} must identify an existing regular file"
        )
    expected_profile = _required_object(
        _required_object(payload, "profile"),
        "public_profile",
    )
    from pico.config import resolve_provider_config

    provider = resolve_provider_config(
        str(expected_profile["provider"]),
        start=source_root,
        config_path=locator,
    )
    actual_identity = provider.public_identity()
    actual_profile = {
        "provider": provider.name,
        "profile_id": actual_identity.get("profile_id"),
        "model": provider.model,
    }
    frozen_profile = {
        key: expected_profile.get(key)
        for key in ("provider", "profile_id", "model")
    }
    if actual_profile != frozen_profile:
        raise ValueError("resolved provider/profile/model does not match run config")

    from pico.evaluation.live_client import probe_required_network_sandbox

    probe_required_network_sandbox()
    return LiveStartValidation(
        payload=payload,
        sha256=digest,
        row_ids=tuple(row_ids),
        sensitive_values=tuple(
            value for value in (locator, provider.api_key) if value
        ),
    )


def _read_run_config(
    path: Path,
    *,
    require_canonical: bool,
) -> tuple[dict[str, Any], str]:
    path = path.resolve()
    payload = _load_object(path)
    if payload.get("schema_version") != RUN_CONFIG_SCHEMA:
        raise ValueError("unsupported run config schema")
    if canonical_json(payload) != path.read_bytes():
        if require_canonical:
            raise ValueError("run config is not canonical JSON")
    digest = sha256_file(path)
    hash_path = path.with_name("run-config.sha256")
    if hash_path.read_text(encoding="ascii").strip() != digest:
        raise ValueError("run config SHA-256 does not match")
    _validate_run_config_payload(payload)
    return payload, digest


def _validate_run_config_payload(payload: Mapping[str, Any]) -> None:
    if set(payload) != RUN_CONFIG_KEYS:
        raise ValueError("run config top-level fields drift")
    cohort_id = str(payload.get("cohort_id", ""))
    if cohort_id not in SUPPORTED_COHORTS:
        raise ValueError("run config has unsupported cohort")
    profile = _required_object(_required_object(payload, "profile"), "public_profile")
    _validate_selected_profile(profile)
    runtime = _required_object(payload, "runtime")
    expected = {
        "max_output_tokens": 4096,
        "max_tool_steps": 50,
        "provider_timeout_seconds": 300,
        "row_timeout_seconds": 600,
        "stream": False,
        "parallel_tool_execution": False,
        "approval_policy": "auto",
        "auto_dream": False,
        "shell_network_access": False,
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise ValueError(f"run config runtime drift: {key}")
    expected_sampling = {
        "sampling": {
            "status": "not_applicable",
            "reason": "Pico native ModelRequest exposes no sampling parameter",
        },
        "temperature": {
            "status": "not_applicable",
            "reason": "Pico native ModelRequest exposes no sampling parameter",
        },
    }
    if runtime.get("sampling_parameters") != expected_sampling:
        raise ValueError("run config sampling policy drift")
    if runtime.get("allowed_tools") != [
        "list_files",
        "read_file",
        "search",
        "run_shell",
        "write_file",
        "patch_file",
        "todo_add",
        "todo_update",
        "todo_list",
    ]:
        raise ValueError("run config tool allowlist drift")
    if runtime.get("shell_sandbox") != {
        "mode": "required",
        "backend": "bubblewrap",
    }:
        raise ValueError("run config shell sandbox drift")
    if payload.get("retry") != {
        "sdk_max_retries": 0,
        "pico_provider_attempts": 1,
        "semantic_reruns": 0,
    }:
        raise ValueError("run config retry policy drift")
    if payload.get("allowed_rows") != allowed_rows(cohort_id):
        raise ValueError("run config allowed row identities drift")
    private = _required_object(payload, "private_config")
    if private.get("locator_env") != CONFIG_LOCATOR_ENV or private.get(
        "value_persisted"
    ) is not False:
        raise ValueError("run config private locator policy drift")


def _public_profile(selected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "pico-native-provider-profile-v1",
        "provider": selected.get("name"),
        "profile_id": selected.get("profile_id"),
        "model": selected.get("model"),
        "base_url_fingerprint": selected.get("base_url_fingerprint"),
        "wire_dialect": selected.get("wire_dialect"),
        "adapter_mode": selected.get("adapter_mode"),
        "sdk": dict(selected.get("sdk", {})),
        "capabilities": dict(selected.get("capabilities", {})),
        "retry": {
            "sdk_max_retries": selected.get("sdk_max_retries"),
            "pico_provider_attempts": selected.get("pico_provider_attempts"),
        },
        "stream": selected.get("stream"),
        "parallel_tool_calls": selected.get("parallel_tool_execution"),
    }


def _validate_selected_profile(profile: Mapping[str, Any]) -> None:
    from pico.evaluation.native_provider_profiles import validate_public_provider_profile

    validate_public_provider_profile(profile)
    if profile.get("provider") != "dashscope-o":
        raise ValueError("Evaluation v2 requires dashscope-o")
    if (
        profile.get("profile_id")
        != "sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70"
    ):
        raise ValueError("Evaluation v2 profile ID drift")
    if profile.get("model") != "qwen3.6-plus":
        raise ValueError("Evaluation v2 model drift")
    if profile.get("sdk") != {"package": "openai", "version": "2.46.0"}:
        raise ValueError("Evaluation v2 SDK drift")


def _runtime_environment() -> dict[str, str]:
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    try:
        sdk_version = metadata.version("openai")
    except metadata.PackageNotFoundError:
        sdk_version = "unavailable"
    return {
        "execution_environment": "Ubuntu WSL2",
        "os": f"{release.get('ID', '')} {release.get('VERSION_ID', '')}".strip(),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "openai_sdk": sdk_version,
    }


def _locator_check() -> dict[str, bool]:
    value = os.environ.get(CONFIG_LOCATOR_ENV, "")
    path = Path(value) if value else None
    return {
        "env_defined": bool(value),
        "target_exists": bool(path and path.exists()),
        "target_is_file": bool(path and path.is_file()),
    }


def _git_identity(source_root: Path, *, require_clean: bool = True) -> tuple[str, str]:
    if require_clean:
        status = _git(
            source_root,
            "status",
            "--porcelain",
            "--untracked-files=no",
        )
        if status:
            raise ValueError("run config source tracked files must be clean")
    commit = _git(source_root, "rev-parse", "HEAD")
    tree = _git(source_root, "rev-parse", "HEAD^{tree}")
    if len(commit) != 40 or len(tree) != 40:
        raise ValueError("run config source requires full Git identities")
    return commit, tree


def _git(source_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=source_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _required_object(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"{key} must be an object")
    return item


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


__all__ = [
    "CONFIG_LOCATOR_ENV",
    "LiveStartValidation",
    "RUN_CONFIG_SCHEMA",
    "SUPPORTED_COHORTS",
    "TASKSET_LOCK_PATH",
    "TASKSET_PATH",
    "build_run_config",
    "canonical_json",
    "sha256_file",
    "validate_live_start",
    "verify_run_config",
    "verify_taskset_lock",
    "write_run_config",
]
