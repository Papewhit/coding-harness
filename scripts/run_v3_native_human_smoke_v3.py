#!/usr/bin/env python3
"""Versioned v3 native human-smoke harness; default operation is fail-closed."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping
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
DEFAULT_MANIFEST = ROOT / "benchmarks/v3/native-provider/human-smoke-v3.json"
ProviderFactory = Callable[[Mapping[str, Any]], Any]


class FakeProvider:
    """Native scripted provider with no transport or HTTP capability."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.http_attempts = 0
        self._pico_profile_identity = {"profile_id": "scripted-native:human-smoke-v3", "profile": "scripted", "model": "fake-v3", "wire_dialect": "scripted-native", "base_url_fingerprint": "sha256:fake", "capabilities": {"native_tools": True}, "adapter_mode": "fake", "sdk_package": "none", "sdk_version": "0", "sdk_max_retries": 0, "provider_attempts": 1}

    def request(self, request: Any) -> ModelResponse:
        if not self.responses:
            raise RuntimeError("fake provider ran out of v3 responses")
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
    if manifest.get("schema_version") != "pico-native-human-smoke-v3":
        raise ValueError("unsupported v3 human-smoke manifest")
    modes = manifest.get("execution_modes", {})
    if modes.get("fake_provider", {}).get("expected_http_attempts") != 0:
        raise ValueError("fake provider must be no-HTTP")
    if modes.get("authorized_live", {}).get("requires_explicit_authorization") is not True:
        raise ValueError("live mode must require explicit authorization")
    return manifest


def _fake_factory(scenario: Mapping[str, Any]) -> FakeProvider:
    responses: list[ModelResponse] = []
    for index, step in enumerate(scenario["fake_responses"], 1):
        if "final" in step:
            responses.append(native_final_response(step["final"]))
        else:
            tool = step["tool"]
            responses.append(native_tool_call_response(f"fake-v3-{index}", tool["name"], tool["arguments"]))
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
            wire_dialect=config.wire_dialect, model=config.model,
            base_url=config.base_url, api_key=config.api_key,
            profile_id=frozen_profile["profile_id"], max_retries=0,
        )
        return AuditedLiveProvider(inner, provider_session_identity(config))

    return build


def _write_fixture(workspace: Path, scenario: Mapping[str, Any]) -> None:
    for relative, content in scenario["fixture"]["files"].items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _snapshot(workspace: Path, fixture_files: Mapping[str, str]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for relative in fixture_files:
        path = workspace / relative
        data = path.read_bytes() if path.exists() else b""
        files[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "text": data.decode("utf-8") if path.exists() else None}
    return files


def _events(agent: Pico) -> list[dict[str, Any]]:
    return [json.loads(line) for line in agent.session_event_bus.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _observed_calls(agent: Pico, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join call IDs from actual model exchanges with Runtime completion events."""
    exchanges = agent.session.get("model_exchange", {}).get("events", [])
    model_calls = [call for exchange in exchanges if exchange.get("event") == "assistant_tool_batch" for call in exchange.get("tool_calls", [])]
    finished = [event for event in events if event.get("event") == "tool_finished"]
    safety = [event for event in events if event.get("event") == "native_safety_stage"]
    runtime_by_id = {event.get("call_id"): event for event in finished}
    model_ids = [call.get("call_id") for call in model_calls]
    runtime_ids = [event.get("call_id") for event in finished]
    if any(not isinstance(call_id, str) or not call_id for call_id in runtime_ids):
        raise ValueError("tool_finished missing call_id")
    if len(set(runtime_ids)) != len(runtime_ids) or set(runtime_ids) != set(model_ids):
        raise ValueError("tool_finished call_id mapping is not one-to-one")
    observed = []
    for call in model_calls:
        call_id = call.get("call_id")
        matching_safety = [entry for entry in safety if entry.get("call_id") == call_id]
        runtime = runtime_by_id[call_id]
        if runtime.get("tool_name") != call.get("name"):
            raise ValueError("tool_finished call_id/tool name mismatch")
        observed.append({"call_id": call_id, "name": call.get("name"), "arguments": call.get("arguments"), "runtime": runtime, "safety": matching_safety})
    return observed


def verify_scenario(scenario: Mapping[str, Any], workspace: Path, agent: Pico, events: list[dict[str, Any]], before: Mapping[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected = scenario["expected_postcondition"]
    observed = _observed_calls(agent, events)
    names = [item["name"] for item in observed]

    def check(name: str, passed: bool, detail: Any = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    for relative, rule in expected["files"].items():
        content = (workspace / relative).read_text(encoding="utf-8") if (workspace / relative).is_file() else None
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
    check("semantic_partial_order", cursor == len(required), {"required": required, "observed": names})
    check("exchange_call_ids_present", all(isinstance(item["call_id"], str) and item["call_id"] for item in observed), observed)
    check("runtime_events_bound", all(item["runtime"] is not None and item["runtime"].get("tool_name") == item["name"] for item in observed), observed)
    if scenario["verifier"]["kind"] == "runtime_denial_then_safe_continuation":
        denied = next((item for item in observed if item["name"] == "run_shell"), None)
        safe = next((item for item in observed if item["name"] == "read_file"), None)
        denial = [] if denied is None else [event for event in denied["safety"] if event.get("stage") == "permission"]
        check("runtime_denial_on_observed_call_id", any(event.get("outcome") == "rejected" and event.get("reason") == "approval_denied" for event in denial), denial)
        check("denied_command_no_side_effect", denied is not None and denied["runtime"].get("workspace_changed") is False, denied)
        check("safe_continuation_after_denial", safe is not None and observed.index(safe) > observed.index(denied) and any(event.get("stage") == "execute" and event.get("outcome") == "completed" for event in safe["safety"]), observed)
    after = _snapshot(workspace, scenario["fixture"]["files"])
    diffs = {path: "".join(difflib.unified_diff((before[path]["text"] or "").splitlines(keepends=True), (after[path]["text"] or "").splitlines(keepends=True), fromfile=f"before/{path}", tofile=f"after/{path}")) for path in after}
    return {"status": "PASS" if all(item["passed"] for item in checks) else "FAIL", "checks": checks, "observed_calls": observed, "workspace_before": before, "workspace_after": after, "diff": diffs}


def run_manifest(manifest_path: Path, output_dir: Path, *, provider_factory: ProviderFactory | None = None, execution_mode: str = "fake_provider", profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if execution_mode == "fake_provider" and (provider_factory is not None or profile is not None):
        raise ValueError("fake_provider rejects provider_factory and profile")
    if execution_mode == "authorized_live" and (provider_factory is None or profile is None):
        raise ValueError("authorized-live requires an injected bound provider factory and sanitized frozen profile")
    if execution_mode != "fake_provider" and execution_mode != "authorized_live":
        raise ValueError("unsupported execution mode")
    factory = provider_factory or _fake_factory
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for scenario in manifest["scenarios"]:
        target = output_dir / scenario["id"]
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{scenario['id']}-", dir=target) as temporary:
            workspace = Path(temporary)
            _write_fixture(workspace, scenario)
            before = _snapshot(workspace, scenario["fixture"]["files"])
            provider = factory(scenario)
            agent = Pico(model_client=provider, workspace=WorkspaceContext.build(workspace), session_store=SessionStore(workspace / ".pico/sessions"), approval_policy=scenario["approval_policy"], max_steps=16, auto_dream=False)
            bind_native_safety_evidence(agent, case_id=scenario["id"], repetition=1)
            exit_code, stdout, stderr = 0, "", ""
            try:
                stdout = agent.ask(scenario["prompt"])
            except Exception as exc:  # preserve all verifier evidence on Runtime failure.
                exit_code, stderr = 1, f"{type(exc).__name__}: {exc}"
            events = _events(agent)
            verification = verify_scenario(scenario, workspace, agent, events, before)
            attempts = int(getattr(provider, "http_attempts", 0))
            if execution_mode == "fake_provider" and attempts != 0:
                raise ValueError("fake_provider observed nonzero http_attempts")
            record = {"scenario_id": scenario["id"], "pico_exit": exit_code, "verifier_exit": 0 if verification["status"] == "PASS" else 1, "stdout": stdout, "stderr": stderr, "http_attempts": attempts, "runtime_source": {"commit": _git_head(), "manifest_sha256": _sha256(manifest_path), "profile": dict(profile or provider._pico_profile_identity)}, "verification": verification}
            (target / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for name, content in {"pico.stdout.txt": stdout, "pico.stderr.txt": stderr, "pico.exit.txt": f"{exit_code}\n", "verifier.exit.txt": f"{record['verifier_exit']}\n"}.items():
                (target / name).write_text(content, encoding="utf-8")
            records.append(record)
            close = getattr(provider, "close", None)
            if callable(close):
                close()
    summary_profile = dict(profile or records[0]["runtime_source"]["profile"])
    if not summary_profile:
        raise ValueError("summary profile identity must be non-empty")
    summary = {"schema_version": "pico-native-human-smoke-v3-artifact", "execution_mode": execution_mode, "manifest_sha256": _sha256(manifest_path), "profile": summary_profile, "http_attempts": sum(record["http_attempts"] for record in records), "scenarios": records, "status": "PASS" if all(record["pico_exit"] == 0 and record["verifier_exit"] == 0 for record in records) else "FAIL"}
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    import subprocess
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT}", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


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
    if args.fake_provider and (args.provider or args.config or args.frozen_profile is not None):
        parser.error("--fake-provider rejects live-only provider, config, and frozen-profile options")
    if args.authorized_live:
        if not args.provider or not args.config or args.frozen_profile is None:
            parser.error("--authorized-live requires --provider, --config, and --frozen-profile")
        profile = load_public_provider_profile(args.frozen_profile)
        summary = run_manifest(
            args.manifest.resolve(), args.output_dir.resolve(),
            provider_factory=authorized_live_provider_factory(
                provider=args.provider, config_path=args.config, frozen_profile=profile
            ), execution_mode="authorized_live", profile=profile,
        )
    else:
        summary = run_manifest(args.manifest.resolve(), args.output_dir.resolve())
    print(json.dumps({"status": summary["status"], "http_attempts": summary["http_attempts"]}))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
