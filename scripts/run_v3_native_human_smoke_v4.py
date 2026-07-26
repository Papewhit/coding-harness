#!/usr/bin/env python3
"""Grounded v4 native human-smoke harness with durable public trajectory."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from pico import Pico, SessionStore, WorkspaceContext
from pico.config import resolve_provider_config
from pico.evaluation.native_provider_live import bind_native_safety_evidence
from pico.evaluation.native_provider_profiles import (
    assert_provider_profile_matches,
    load_public_provider_profile,
    provider_session_identity,
)
from pico.providers import build_native_model_client
from pico.providers.contracts import ModelResponse
from pico.testing import native_final_response, native_tool_call_response


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks/v3/native-provider/human-smoke-v4.json"
ProviderFactory = Callable[[Mapping[str, Any]], Any]
TRAJECTORY_DIRECTORY = "public-trajectory"
TRAJECTORY_INVENTORY = "trajectory-inventory.json"
ARTIFACT_INVENTORY = "inventory.json"
_PUBLIC_FILE_SUFFIXES = frozenset({".json", ".jsonl", ".txt"})
_PRIVATE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "base_url",
        "config_path",
        "continuation",
        "endpoint",
        "locator",
        "opaque_continuation",
        "private_continuation",
        "provider_config",
        "reasoning",
        "secret",
        "thinking",
    }
)
_RAW_URL = re.compile(r"https?://", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~+/=-]{12,}|sk-[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)


class FakeProvider:
    """Native scripted provider with no transport or HTTP capability."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.http_attempts = 0
        self._pico_profile_identity = {
            "profile_id": "scripted-native:human-smoke-v4",
            "profile": "scripted",
            "model": "fake-v4",
            "wire_dialect": "scripted-native",
            "base_url_fingerprint": "sha256:fake",
            "capabilities": {"native_tools": True},
            "adapter_mode": "fake",
            "sdk_package": "none",
            "sdk_version": "0",
            "sdk_max_retries": 0,
            "provider_attempts": 1,
        }

    def request(self, request: Any) -> ModelResponse:
        if not self.responses:
            raise RuntimeError("fake provider ran out of v4 responses")
        return self.responses.pop(0)


class AuditedLiveProvider:
    """Thin transport wrapper that records real provider operations only."""

    def __init__(self, inner: Any, identity: Mapping[str, Any]) -> None:
        self.inner = inner
        self.http_attempts = 0
        self._pico_profile_identity = dict(identity)

    def request(self, request: Any) -> ModelResponse:
        self.http_attempts += 1
        return self.inner.request(request)

    def close(self) -> None:
        self.inner.close()


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "pico-native-human-smoke-v4":
        raise ValueError("unsupported v4 human-smoke manifest")
    modes = manifest.get("execution_modes", {})
    if modes.get("fake_provider", {}).get("expected_http_attempts") != 0:
        raise ValueError("fake provider must be no-HTTP")
    live = modes.get("authorized_live", {})
    if live.get("requires_explicit_authorization") is not True:
        raise ValueError("live mode must require explicit authorization")
    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("v4 human-smoke manifest requires scenarios")
    for scenario in scenarios:
        expected = scenario.get("expected_postcondition", {})
        if not isinstance(expected.get("files"), dict):
            raise ValueError("scenario expected files must be manifest-driven")
        if not isinstance(expected.get("semantic_order"), list):
            raise ValueError("scenario semantic order must be manifest-driven")
    return manifest


def _fake_factory(scenario: Mapping[str, Any]) -> FakeProvider:
    responses: list[ModelResponse] = []
    for index, step in enumerate(scenario["fake_responses"], 1):
        if "final" in step:
            responses.append(native_final_response(step["final"]))
        else:
            tool = step["tool"]
            responses.append(
                native_tool_call_response(
                    f"fake-v4-{index}", tool["name"], tool["arguments"]
                )
            )
    return FakeProvider(responses)


def authorized_live_provider_factory(
    *, provider: str, config_path: str, frozen_profile: Mapping[str, Any]
) -> ProviderFactory:
    """Bind exact config/profile before constructing a live transport or any I/O."""
    config = resolve_provider_config(provider, start=ROOT, config_path=config_path)
    assert_provider_profile_matches(config, frozen_profile)
    if not config.api_key or not config.base_url:
        raise ValueError("authorized-live requires provider credentials and base URL")

    def build(_scenario: Mapping[str, Any]) -> AuditedLiveProvider:
        inner = build_native_model_client(
            wire_dialect=config.wire_dialect,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            profile_id=frozen_profile["profile_id"],
            max_retries=0,
        )
        return AuditedLiveProvider(inner, provider_session_identity(config))

    build._pico_private_values = (  # type: ignore[attr-defined]
        config.api_key,
        config.base_url,
        config_path,
    )
    return build


def _write_fixture(workspace: Path, scenario: Mapping[str, Any]) -> None:
    for relative, content in scenario["fixture"]["files"].items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _snapshot(
    workspace: Path, fixture_files: Mapping[str, str]
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for relative in fixture_files:
        path = workspace / relative
        data = path.read_bytes() if path.exists() else b""
        files[relative] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "text": data.decode("utf-8") if path.exists() else None,
        }
    return files


def _events(agent: Pico) -> list[dict[str, Any]]:
    return _load_jsonl(agent.session_event_bus.path)


def _observed_calls(
    agent: Pico, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Join provider calls to journal results, Runtime results, and safety evidence."""
    exchanges = agent.session.get("model_exchange", {}).get("events", [])
    model_calls = [
        call
        for exchange in exchanges
        if exchange.get("event") == "assistant_tool_batch"
        for call in exchange.get("tool_calls", [])
    ]
    journal_results = [
        exchange for exchange in exchanges if exchange.get("event") == "tool_result"
    ]
    finished = [event for event in events if event.get("event") == "tool_finished"]
    safety = [
        event for event in events if event.get("event") == "native_safety_stage"
    ]
    model_ids = _unique_call_ids(model_calls, "model call", key="call_id")
    journal_ids = _unique_call_ids(journal_results, "journal result", key="call_id")
    runtime_ids = _unique_call_ids(finished, "Runtime result", key="call_id")
    if set(model_ids) != set(journal_ids) or set(model_ids) != set(runtime_ids):
        raise ValueError("model/result/Runtime call_id mapping is not one-to-one")
    safety_ids = {
        event.get("call_id")
        for event in safety
        if isinstance(event.get("call_id"), str) and event.get("call_id")
    }
    if safety_ids != set(model_ids):
        raise ValueError("model/safety call_id mapping is not one-to-one")
    result_by_id = {event["call_id"]: event for event in journal_results}
    runtime_by_id = {event["call_id"]: event for event in finished}
    observed = []
    for call in model_calls:
        call_id = call["call_id"]
        result = result_by_id[call_id]
        runtime = runtime_by_id[call_id]
        matching_safety = [
            entry for entry in safety if entry.get("call_id") == call_id
        ]
        if result.get("name") != call.get("name"):
            raise ValueError("journal result call_id/tool name mismatch")
        if runtime.get("tool_name") != call.get("name"):
            raise ValueError("Runtime result call_id/tool name mismatch")
        if any(entry.get("tool_name") != call.get("name") for entry in matching_safety):
            raise ValueError("safety call_id/tool name mismatch")
        observed.append(
            {
                "call_id": call_id,
                "name": call.get("name"),
                "arguments": call.get("arguments"),
                "model_result": result,
                "runtime": runtime,
                "safety": matching_safety,
            }
        )
    return observed


def _unique_call_ids(
    records: Iterable[Mapping[str, Any]], label: str, *, key: str
) -> list[str]:
    ids = [record.get(key) for record in records]
    if any(not isinstance(call_id, str) or not call_id for call_id in ids):
        raise ValueError(f"{label} missing call_id")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} call_id values are not unique")
    return ids


def verify_scenario(
    scenario: Mapping[str, Any],
    workspace: Path,
    agent: Pico,
    events: list[dict[str, Any]],
    before: Mapping[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected = scenario["expected_postcondition"]
    observed = _observed_calls(agent, events)
    names = [item["name"] for item in observed]

    def check(name: str, passed: bool, detail: Any = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    for relative, rule in expected["files"].items():
        path = workspace / relative
        content = path.read_text(encoding="utf-8") if path.is_file() else None
        check(f"exists:{relative}", content is not None)
        for needle in rule.get("contains", []):
            check(f"contains:{relative}", content is not None and needle in content)
        if "equals" in rule:
            check(f"equals:{relative}", content == rule["equals"])
    required = expected["semantic_order"]
    cursor = 0
    for name in names:
        if cursor < len(required) and name == required[cursor]:
            cursor += 1
    check(
        "semantic_partial_order",
        cursor == len(required),
        {"required": required, "observed": names},
    )
    check(
        "exchange_call_ids_present",
        all(item["call_id"] for item in observed),
        observed,
    )
    check(
        "runtime_results_bound",
        all(item["runtime"].get("tool_name") == item["name"] for item in observed),
        observed,
    )
    check(
        "journal_results_bound",
        all(item["model_result"].get("name") == item["name"] for item in observed),
        observed,
    )
    check(
        "safety_evidence_bound",
        all(item["safety"] for item in observed),
        observed,
    )
    if scenario["verifier"]["kind"] == "runtime_denial_then_safe_continuation":
        denied = next((item for item in observed if item["name"] == "run_shell"), None)
        safe = next((item for item in observed if item["name"] == "read_file"), None)
        denial = (
            []
            if denied is None
            else [
                event
                for event in denied["safety"]
                if event.get("stage") == "permission"
            ]
        )
        check(
            "runtime_denial_on_observed_call_id",
            any(
                event.get("outcome") == "rejected"
                and event.get("reason") == "approval_denied"
                for event in denial
            ),
            denial,
        )
        check(
            "denied_command_no_side_effect",
            denied is not None
            and denied["runtime"].get("workspace_changed") is False,
            denied,
        )
        check(
            "safe_continuation_after_denial",
            denied is not None
            and safe is not None
            and observed.index(safe) > observed.index(denied)
            and any(
                event.get("stage") == "execute"
                and event.get("outcome") == "completed"
                for event in safe["safety"]
            ),
            observed,
        )
    after = _snapshot(workspace, scenario["fixture"]["files"])
    diffs = {
        path: "".join(
            difflib.unified_diff(
                (before[path]["text"] or "").splitlines(keepends=True),
                (after[path]["text"] or "").splitlines(keepends=True),
                fromfile=f"before/{path}",
                tofile=f"after/{path}",
            )
        )
        for path in after
    }
    return {
        "status": "PASS" if all(item["passed"] for item in checks) else "FAIL",
        "checks": checks,
        "observed_calls": observed,
        "workspace_before": before,
        "workspace_after": after,
        "diff": diffs,
    }


def copy_public_trajectory(
    workspace: Path,
    target: Path,
    observed_calls: list[dict[str, Any]],
    *,
    private_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Copy only public session events and run evidence before workspace cleanup."""
    trajectory = target / TRAJECTORY_DIRECTORY
    if trajectory.exists():
        raise ValueError("public trajectory destination already exists")
    values = tuple(value for value in private_values if value)
    source_sessions = workspace / ".pico" / "sessions"
    source_runs = workspace / ".pico" / "runs"
    event_paths = sorted(source_sessions.glob("*.events.jsonl"))
    if not event_paths:
        raise ValueError("public session event evidence is missing")
    _validate_source_runs(source_runs)
    source_files = event_paths + sorted(
        path for path in source_runs.rglob("*") if path.is_file()
    )
    for source in source_files:
        _parse_public_file(source, values)
    session_target = trajectory / ".pico" / "sessions"
    runs_target = trajectory / ".pico" / "runs"
    session_target.mkdir(parents=True)
    for source in event_paths:
        if source.is_symlink() or not source.is_file():
            raise ValueError("public session evidence must be regular files")
        shutil.copy2(source, session_target / source.name)
    shutil.copytree(source_runs, runs_target)
    inventory_path = target / TRAJECTORY_INVENTORY
    inventory = _write_inventory(trajectory, inventory_path)
    validation = validate_public_trajectory(
        trajectory,
        inventory_path,
        observed_calls,
        private_values=values,
    )
    return {
        "root": TRAJECTORY_DIRECTORY,
        "inventory": TRAJECTORY_INVENTORY,
        "inventory_sha256": _sha256(inventory_path),
        "file_count": inventory["file_count"],
        "call_count": validation["call_count"],
        "validated_after_workspace_cleanup": False,
    }


def validate_public_trajectory(
    trajectory: Path,
    inventory_path: Path,
    observed_calls: list[dict[str, Any]],
    *,
    private_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Reparse, rescan, hash-check, and bind durable public evidence."""
    _validate_inventory(trajectory, inventory_path)
    values = tuple(value for value in private_values if value)
    files = _public_files(trajectory)
    parsed = {
        path.relative_to(trajectory).as_posix(): _parse_public_file(path, values)
        for path in files
    }
    session_records = [
        record
        for relative, records in parsed.items()
        if relative.startswith(".pico/sessions/")
        for record in records
    ]
    run_records = [
        record
        for relative, records in parsed.items()
        if relative.startswith(".pico/runs/") and relative.endswith("trace.jsonl")
        for record in records
    ]
    model_calls = [
        call
        for record in session_records
        if record.get("event") == "model_exchange"
        and isinstance(record.get("exchange"), dict)
        and record["exchange"].get("event") == "assistant_tool_batch"
        for call in record["exchange"].get("tool_calls", [])
    ]
    journal_results = [
        record["exchange"]
        for record in session_records
        if record.get("event") == "model_exchange"
        and isinstance(record.get("exchange"), dict)
        and record["exchange"].get("event") == "tool_result"
    ]
    runtime_results = [
        record for record in session_records if record.get("event") == "tool_finished"
    ]
    safety = [
        record
        for record in session_records
        if record.get("event") == "native_safety_stage"
    ]
    run_results = [
        record for record in run_records if record.get("event") == "tool_executed"
    ]
    expected_ids = _unique_call_ids(observed_calls, "result model call", key="call_id")
    categories = {
        "durable model call": _unique_call_ids(
            model_calls, "durable model call", key="call_id"
        ),
        "durable journal result": _unique_call_ids(
            journal_results, "durable journal result", key="call_id"
        ),
        "durable Runtime result": _unique_call_ids(
            runtime_results, "durable Runtime result", key="call_id"
        ),
        "durable run result": _unique_call_ids(
            run_results, "durable run result", key="call_id"
        ),
    }
    expected_set = set(expected_ids)
    for label, call_ids in categories.items():
        if set(call_ids) != expected_set:
            raise ValueError(f"{label} call_id mapping is not one-to-one")
    safety_ids = {
        record.get("call_id")
        for record in safety
        if isinstance(record.get("call_id"), str) and record.get("call_id")
    }
    if safety_ids != expected_set:
        raise ValueError("durable safety call_id mapping is not one-to-one")
    expected_names = {call["call_id"]: call["name"] for call in observed_calls}
    named_categories = (
        (model_calls, "name"),
        (journal_results, "name"),
        (runtime_results, "tool_name"),
        (run_results, "name"),
        (safety, "tool_name"),
    )
    for records, name_key in named_categories:
        for record in records:
            call_id = record.get("call_id")
            if call_id in expected_names and record.get(name_key) != expected_names[call_id]:
                raise ValueError("durable call_id/tool name mismatch")
    return {"call_count": len(expected_ids), "file_count": len(files)}


def _validate_source_runs(source_runs: Path) -> None:
    if not source_runs.is_dir() or source_runs.is_symlink():
        raise ValueError("public run evidence is missing")
    run_dirs = sorted(path for path in source_runs.iterdir() if path.is_dir())
    if not run_dirs:
        raise ValueError("public run evidence is missing")
    for run_dir in run_dirs:
        if run_dir.is_symlink():
            raise ValueError("public run evidence cannot contain symlinks")
        for name in ("task_state.json", "trace.jsonl", "report.json"):
            if not (run_dir / name).is_file():
                raise ValueError(f"public run evidence is missing {name}")
    if any(path.is_symlink() for path in source_runs.rglob("*")):
        raise ValueError("public run evidence cannot contain symlinks")


def _parse_public_file(path: Path, private_values: tuple[str, ...]) -> list[Any]:
    if path.suffix not in _PUBLIC_FILE_SUFFIXES:
        raise ValueError(f"unsupported public Artifact file: {path.name}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"public Artifact is not UTF-8: {path.name}") from exc
    _scan_public_value(text, private_values, context=path.as_posix())
    if path.suffix == ".txt":
        return []
    if path.suffix == ".json":
        try:
            values = [json.loads(text)]
        except json.JSONDecodeError as exc:
            raise ValueError(f"public Artifact JSON parse failed: {path.name}") from exc
    else:
        values = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"public Artifact JSONL parse failed: {path.name}:{number}"
                ) from exc
    for value in values:
        _scan_public_value(value, private_values, context=path.as_posix())
    return values


def _scan_public_value(
    value: Any, private_values: tuple[str, ...], *, context: str
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in _PRIVATE_KEYS:
                raise ValueError(f"private field {key!r} in public Artifact {context}")
            _scan_public_value(item, private_values, context=context)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _scan_public_value(item, private_values, context=context)
        return
    if not isinstance(value, str):
        return
    if _RAW_URL.search(value):
        raise ValueError(f"raw endpoint in public Artifact {context}")
    if _CREDENTIAL.search(value):
        raise ValueError(f"credential-like secret in public Artifact {context}")
    if any(secret in value for secret in private_values):
        raise ValueError(f"private locator or secret in public Artifact {context}")


def _write_inventory(root: Path, inventory_path: Path) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in _public_files(root)
    }
    inventory = {
        "schema_version": "pico-native-human-smoke-v4-inventory",
        "hash_algorithm": "sha256",
        "hash_basis": "file bytes",
        "root": root.name,
        "file_count": len(files),
        "files": files,
    }
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return inventory


def _validate_inventory(root: Path, inventory_path: Path) -> None:
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("public trajectory inventory is missing or invalid") from exc
    expected = {
        path.relative_to(root).as_posix(): {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in _public_files(root)
    }
    if inventory.get("files") != expected or inventory.get("file_count") != len(
        expected
    ):
        raise ValueError("public trajectory inventory hash mismatch")


def _public_files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("public Artifact root is missing or unsafe")
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("public Artifact cannot contain symlinks")
    return paths


def write_artifact_inventory(
    output_dir: Path, *, private_values: Iterable[str] = ()
) -> dict[str, Any]:
    inventory_path = output_dir / ARTIFACT_INVENTORY
    if inventory_path.exists():
        inventory_path.unlink()
    values = tuple(value for value in private_values if value)
    for path in _public_files(output_dir):
        _parse_public_file(path, values)
    inventory = _write_inventory(output_dir, inventory_path)
    validate_artifact_inventory(output_dir, inventory_path)
    return inventory


def validate_artifact_inventory(output_dir: Path, inventory_path: Path) -> None:
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Artifact inventory is missing or invalid") from exc
    expected = {
        path.relative_to(output_dir).as_posix(): {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in _public_files(output_dir)
        if path != inventory_path
    }
    if inventory.get("files") != expected or inventory.get("file_count") != len(
        expected
    ):
        raise ValueError("Artifact inventory hash mismatch")


def run_manifest(
    manifest_path: Path,
    output_dir: Path,
    *,
    provider_factory: ProviderFactory | None = None,
    execution_mode: str = "fake_provider",
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if execution_mode == "fake_provider" and (
        provider_factory is not None or profile is not None
    ):
        raise ValueError("fake_provider rejects provider_factory and profile")
    if execution_mode == "authorized_live" and (
        provider_factory is None or profile is None
    ):
        raise ValueError(
            "authorized-live requires an injected bound provider factory "
            "and sanitized frozen profile"
        )
    if execution_mode not in {"fake_provider", "authorized_live"}:
        raise ValueError("unsupported execution mode")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    factory = provider_factory or _fake_factory
    private_values = tuple(
        value
        for value in getattr(factory, "_pico_private_values", ())
        if isinstance(value, str) and value
    )
    records = []
    for scenario in manifest["scenarios"]:
        target = output_dir / scenario["id"]
        target.mkdir(parents=True)
        workspace: Path
        with tempfile.TemporaryDirectory(
            prefix=f"{scenario['id']}-", dir=target
        ) as temporary:
            workspace = Path(temporary)
            _write_fixture(workspace, scenario)
            before = _snapshot(workspace, scenario["fixture"]["files"])
            provider = factory(scenario)
            agent = Pico(
                model_client=provider,
                workspace=WorkspaceContext.build(workspace),
                session_store=SessionStore(workspace / ".pico/sessions"),
                approval_policy=scenario["approval_policy"],
                max_steps=16,
                auto_dream=False,
            )
            bind_native_safety_evidence(
                agent, case_id=scenario["id"], repetition=1
            )
            exit_code, stdout, stderr = 0, "", ""
            try:
                stdout = agent.ask(scenario["prompt"])
            except Exception as exc:
                exit_code, stderr = 1, f"{type(exc).__name__}: {exc}"
            events = _events(agent)
            verification = verify_scenario(
                scenario, workspace, agent, events, before
            )
            attempts = int(getattr(provider, "http_attempts", 0))
            if execution_mode == "fake_provider" and attempts != 0:
                raise ValueError("fake_provider observed nonzero http_attempts")
            record = {
                "scenario_id": scenario["id"],
                "pico_exit": exit_code,
                "verifier_exit": 0 if verification["status"] == "PASS" else 1,
                "stdout": stdout,
                "stderr": stderr,
                "http_attempts": attempts,
                "runtime_source": {
                    "commit": _git_head(),
                    "manifest_sha256": _sha256(manifest_path),
                    "profile": dict(
                        profile or provider._pico_profile_identity
                    ),
                },
                "verification": verification,
            }
            record["trajectory"] = copy_public_trajectory(
                workspace,
                target,
                verification["observed_calls"],
                private_values=private_values,
            )
            _scan_public_value(
                record,
                private_values,
                context=f"{scenario['id']}/result.json",
            )
            _write_record_files(target, record)
            close = getattr(provider, "close", None)
            if callable(close):
                close()
        if workspace.exists():
            raise RuntimeError("temporary workspace cleanup failed")
        validate_public_trajectory(
            target / TRAJECTORY_DIRECTORY,
            target / TRAJECTORY_INVENTORY,
            record["verification"]["observed_calls"],
            private_values=private_values,
        )
        record["trajectory"]["validated_after_workspace_cleanup"] = True
        _scan_public_value(
            record,
            private_values,
            context=f"{scenario['id']}/result.json",
        )
        _write_record_files(target, record)
        records.append(record)
    summary_profile = dict(profile or records[0]["runtime_source"]["profile"])
    if not summary_profile:
        raise ValueError("summary profile identity must be non-empty")
    summary = {
        "schema_version": "pico-native-human-smoke-v4-artifact",
        "execution_mode": execution_mode,
        "manifest_sha256": _sha256(manifest_path),
        "profile": summary_profile,
        "http_attempts": sum(record["http_attempts"] for record in records),
        "scenarios": records,
        "status": (
            "PASS"
            if all(
                record["pico_exit"] == 0 and record["verifier_exit"] == 0
                for record in records
            )
            else "FAIL"
        ),
    }
    _scan_public_value(summary, private_values, context="summary.json")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    inventory = write_artifact_inventory(
        output_dir, private_values=private_values
    )
    summary["inventory_sha256"] = _sha256(output_dir / ARTIFACT_INVENTORY)
    summary["inventory_file_count"] = inventory["file_count"]
    return summary


def _write_record_files(target: Path, record: Mapping[str, Any]) -> None:
    (target / "result.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for name, content in {
        "pico.stdout.txt": str(record["stdout"]),
        "pico.stderr.txt": str(record["stderr"]),
        "pico.exit.txt": f"{record['pico_exit']}\n",
        "verifier.exit.txt": f"{record['verifier_exit']}\n",
    }.items():
        (target / name).write_text(content, encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record must be an object at {path}:{number}")
        records.append(value)
    return records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake-provider", action="store_true")
    mode.add_argument("--authorized-live", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--provider")
    parser.add_argument("--config")
    parser.add_argument("--frozen-profile", type=Path)
    args = parser.parse_args(argv)
    if args.fake_provider and (
        args.provider or args.config or args.frozen_profile is not None
    ):
        parser.error(
            "--fake-provider rejects live-only provider, config, "
            "and frozen-profile options"
        )
    if args.authorized_live:
        if not args.provider or not args.config or args.frozen_profile is None:
            parser.error(
                "--authorized-live requires --provider, --config, "
                "and --frozen-profile"
            )
        profile = load_public_provider_profile(args.frozen_profile)
        summary = run_manifest(
            args.manifest.resolve(),
            args.output_dir.resolve(),
            provider_factory=authorized_live_provider_factory(
                provider=args.provider,
                config_path=args.config,
                frozen_profile=profile,
            ),
            execution_mode="authorized_live",
            profile=profile,
        )
    else:
        summary = run_manifest(
            args.manifest.resolve(), args.output_dir.resolve()
        )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "http_attempts": summary["http_attempts"],
            }
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
