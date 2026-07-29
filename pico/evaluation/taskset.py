"""Load and verify local-repository tasksets without exposing hidden inputs."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from pico.evaluation.live_tasks import TaskSpec


IGNORED_TREE_PARTS = frozenset({".git", ".pytest_cache", ".ruff_cache", "__pycache__"})


def select_tasks(
    tasks: Sequence[TaskSpec],
    *,
    task_ids: Sequence[str] = (),
    repo_ids: Sequence[str] = (),
    run_kinds: Sequence[str] = (),
    shards: Sequence[str] = (),
) -> list[TaskSpec]:
    """Apply independently composable task/repo/run-kind/shard filters."""

    task_filter = set(task_ids)
    repo_filter = set(repo_ids)
    kind_filter = set(run_kinds)
    shard_filter = set(shards)
    return [
        task
        for task in tasks
        if (not task_filter or task.task_id in task_filter)
        and (not repo_filter or task.repo_id in repo_filter)
        and (not kind_filter or bool(kind_filter.intersection(task.run_kinds)))
        and (not shard_filter or task.shard in shard_filter)
    ]


def load_task_specs(path: Path) -> list[TaskSpec]:
    """Load either a standalone manifest or the frozen repository taskset."""

    from pico.evaluation.live_tasks import TaskSpec

    path = path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping) and "repositories" in payload:
        return _load_repository_taskset(payload, path.parent)
    rows = payload if isinstance(payload, list) else payload.get("tasks", [])
    if not isinstance(rows, list):
        raise ValueError("task manifest must be a list or contain a tasks list")
    tasks = [TaskSpec.from_mapping(row, base_dir=path.parent) for row in rows]
    _reject_duplicate_task_ids(tasks)
    return tasks


def verify_taskset_lock(
    *,
    source_root: Path,
    taskset_path: Path,
    lock_path: Path,
) -> dict[str, Any]:
    """Recompute every frozen task and repository identity."""

    source_root = source_root.resolve()
    taskset_path = (source_root / taskset_path).resolve()
    lock_path = (source_root / lock_path).resolve()
    taskset = _load_object(taskset_path)
    lock = _load_object(lock_path)
    expected = lock.get("taskset", {})
    actual_taskset_hash = sha256_file(taskset_path, normalize_lf=True)
    if expected.get("path") != taskset_path.name:
        raise ValueError("taskset lock points to an unexpected taskset path")
    if expected.get("sha256") != actual_taskset_hash:
        raise ValueError("taskset content does not match taskset.lock.json")
    if taskset.get("taskset_id") != lock.get("taskset_id"):
        raise ValueError("taskset_id does not match taskset.lock.json")

    base = taskset_path.parent
    observed_ids: set[str] = set()
    for repository in _required_list(taskset, "repositories"):
        repo_id = _required_string(repository, "id")
        repo_lock = _required_object(lock.get("repositories", {}), repo_id)
        repo_path = _resolve_below(base, _required_string(repository, "base_snapshot"))
        files = _tree_files(repo_path)
        if len(files) != int(repo_lock.get("file_count", -1)):
            raise ValueError(f"repository file count drift: {repo_id}")
        if _repository_tree_hash(repo_path, files) != repo_lock.get("tree_sha256"):
            raise ValueError(f"repository tree drift: {repo_id}")
        for task in _required_list(repository, "tasks"):
            task_id = _required_string(task, "id")
            if task_id in observed_ids:
                raise ValueError(f"duplicate task ID: {task_id}")
            observed_ids.add(task_id)
            task_lock = _required_object(lock.get("tasks", {}), task_id)
            for field, lock_field in (
                ("task_doc", "task_doc_sha256"),
                ("hidden_verifier", "hidden_verifier_sha256"),
                ("reference_patch", "reference_patch_sha256"),
            ):
                path = _resolve_below(base, _required_string(task, field))
                if sha256_file(path, normalize_lf=True) != task_lock.get(lock_field):
                    raise ValueError(f"frozen task input drift: {task_id} {field}")
    if observed_ids != set(lock.get("tasks", {})):
        raise ValueError("taskset and lock contain different task IDs")
    return {
        "taskset_id": str(taskset["taskset_id"]),
        "taskset_sha256": actual_taskset_hash,
        "lock_sha256": sha256_file(lock_path, normalize_lf=True),
        "task_count": len(observed_ids),
    }


def sha256_file(path: Path, *, normalize_lf: bool = False) -> str:
    value = path.read_bytes()
    if normalize_lf:
        value = value.replace(b"\r\n", b"\n")
    return hashlib.sha256(value).hexdigest()


def _load_repository_taskset(payload: Mapping[str, Any], base_dir: Path) -> list[TaskSpec]:
    from pico.evaluation.live_tasks import FORMAL_RUN_KIND, TaskSpec

    repositories = payload.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("repository taskset must contain a repositories list")
    execution_policy = payload.get("execution_policy", {})
    if not isinstance(execution_policy, Mapping):
        raise ValueError("taskset execution_policy must be an object")
    network_access = execution_policy.get("network_access", False)
    if type(network_access) is not bool:
        raise ValueError("taskset network_access must be a boolean")

    tasks: list[TaskSpec] = []
    for repository in repositories:
        if not isinstance(repository, Mapping):
            raise ValueError("taskset repository entries must be objects")
        repo_id = str(repository.get("id", "")).strip()
        base_snapshot = str(repository.get("base_snapshot", "")).strip()
        rows = repository.get("tasks")
        if not repo_id or not base_snapshot or not isinstance(rows, list):
            raise ValueError("taskset repository requires id, base_snapshot, and tasks")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("taskset task entries must be objects")
            task_doc = _resolve_below(base_dir, str(row["task_doc"]))
            tasks.append(
                TaskSpec(
                    task_id=str(row["id"]),
                    repo_id=repo_id,
                    prompt=task_doc.read_text(encoding="utf-8"),
                    source_dir=_resolve_below(base_dir, base_snapshot),
                    verifier=_resolve_below(base_dir, str(row["hidden_verifier"])),
                    run_kinds=("synthetic", "probe", FORMAL_RUN_KIND),
                    shard=repo_id,
                    reference_paths=(
                        _resolve_below(base_dir, str(row["reference_patch"])),
                    ),
                    expected_files_changed=tuple(
                        str(item) for item in row.get("expected_files_changed", [])
                    ),
                    network_access=network_access,
                )
            )
    _reject_duplicate_task_ids(tasks)
    return tasks


def _tree_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in IGNORED_TREE_PARTS for part in path.relative_to(root).parts)
        and path.suffix != ".pyc"
    ]


def _repository_tree_hash(root: Path, files: list[Path]) -> str:
    records = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        records.append(
            f"{relative}\0{sha256_file(path, normalize_lf=True)}\n"
        )
    return hashlib.sha256("".join(records).encode("utf-8")).hexdigest()


def _resolve_below(base: Path, raw: str) -> Path:
    path = (base / raw).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"taskset path escapes its root: {raw}") from exc
    if not path.exists():
        raise ValueError(f"taskset path does not exist: {raw}")
    return path


def _reject_duplicate_task_ids(tasks: Sequence[TaskSpec]) -> None:
    counts = Counter(task.task_id for task in tasks)
    duplicates = sorted(task_id for task_id, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate task IDs: {', '.join(duplicates)}")


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


def _required_list(value: Mapping[str, Any], key: str) -> list[Any]:
    item = value.get(key)
    if not isinstance(item, list):
        raise ValueError(f"{key} must be a list")
    return item


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item


__all__ = ["load_task_specs", "select_tasks", "sha256_file", "verify_taskset_lock"]
