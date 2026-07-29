#!/usr/bin/env python3
"""Run the versioned native human-smoke v2 harness.

The default is fail-closed.  Fixture tests use ``--fake-provider``.  A future
human smoke must explicitly supply ``--authorized-live`` plus a frozen public
profile and provider config; both modes use the same manifest and artifact
format.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from collections.abc import Callable
from typing import Any, Mapping

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
DEFAULT_MANIFEST = ROOT / "benchmarks" / "v3" / "native-provider" / "human-smoke-v2.json"


class FakeNativeProvider:
    """Deterministic provider with no transport implementation or HTTP path."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[Any] = []
        self.http_attempts = 0
        self._pico_profile_identity = {
            "profile_id": "scripted-native:human-smoke-v2",
            "profile": "scripted-native",
            "model": "fake-human-smoke-v2",
            "wire_dialect": "scripted-native",
            "base_url_fingerprint": "sha256:fake-no-http",
            "capabilities": {"native_tools": True},
            "adapter_mode": "fake",
            "sdk_package": "none",
            "sdk_version": "0",
            "sdk_max_retries": 0,
            "provider_attempts": 1,
        }

    def request(self, request: Any) -> ModelResponse:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("fake provider ran out of manifest responses")
        return self._responses.pop(0)


class AuditedLiveProvider:
    """Count one explicit provider operation per Runtime request."""

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
    if manifest.get("schema_version") != "pico-native-human-smoke-v2":
        raise ValueError("unsupported human-smoke manifest schema")
    modes = manifest.get("execution_modes")
    if not isinstance(modes, Mapping):
        raise ValueError("manifest must declare execution modes")
    if modes.get("fake_provider", {}).get("expected_provider_http_attempts") != 0:
        raise ValueError("fake-provider manifest mode must prohibit provider HTTP")
    if modes.get("authorized_live", {}).get("requires_explicit_authorization") is not True:
        raise ValueError("authorized-live mode must require explicit authorization")
    if not isinstance(manifest.get("scenarios"), list) or not manifest["scenarios"]:
        raise ValueError("manifest must contain scenarios")
    return manifest


def _responses(scenario: Mapping[str, Any]) -> list[ModelResponse]:
    parsed: list[ModelResponse] = []
    for item in scenario["fake_responses"]:
        if "final" in item:
            parsed.append(native_final_response(str(item["final"])))
            continue
        call = item["tool_call"]
        parsed.append(native_tool_call_response(call["call_id"], call["name"], call["arguments"]))
    return parsed


def _write_fixture(workspace: Path, scenario: Mapping[str, Any]) -> None:
    for relative, content in scenario["fixture"]["files"].items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _events(agent: Pico) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in agent.session_event_bus.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_scenario(scenario: Mapping[str, Any], workspace: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Accumulate every manifest-derived assertion; never fail fast."""

    expected = scenario["expected_postcondition"]
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    for relative, rule in expected["files"].items():
        path = workspace / relative
        text = path.read_text(encoding="utf-8") if path.is_file() else None
        check(f"file_exists:{relative}", text is not None)
        if "contains" in rule:
            for needle in rule["contains"]:
                check(f"file_contains:{relative}:{needle}", text is not None and needle in text)
        if "equals" in rule:
            check(f"file_equals:{relative}", text == rule["equals"])

    tool_finished = [event for event in events if event.get("event") == "tool_finished"]
    observed_names = [event.get("tool_name") for event in tool_finished]
    check("tool_sequence", observed_names == expected["tool_sequence"], observed_names)
    safety = [event for event in events if event.get("event") == "native_safety_stage"]
    call_ids = {event.get("call_id") for event in safety}
    for call_id in expected["required_call_ids"]:
        check(f"runtime_call_id:{call_id}", call_id in call_ids)

    if scenario["verifier"]["kind"] == "runtime_approval_denial_then_safe_continuation":
        denied_id = expected["denied_call_id"]
        denial = [event for event in safety if event.get("call_id") == denied_id and event.get("stage") == "permission"]
        check("runtime_approval_requested", bool(denial), denial)
        check("runtime_approval_denied", any(event.get("outcome") == "rejected" and event.get("reason") == "approval_denied" for event in denial), denial)
        denied_finish = [event for event in tool_finished if event.get("tool_name") == "run_shell"]
        check("denied_command_has_no_side_effect", bool(denied_finish) and all(event.get("workspace_changed") is False for event in denied_finish), denied_finish)
        safe_id = expected["safe_continuation_call_id"]
        safe_events = [event for event in safety if event.get("call_id") == safe_id]
        check("continued_with_safe_runtime_call", any(event.get("stage") == "execute" and event.get("outcome") == "completed" for event in safe_events), safe_events)

    return {"status": "PASS" if all(item["passed"] for item in checks) else "FAIL", "checks": checks}


ProviderFactory = Callable[[Mapping[str, Any]], Any]


def _fake_provider_factory(scenario: Mapping[str, Any]) -> FakeNativeProvider:
    return FakeNativeProvider(_responses(scenario))


def authorized_live_provider_factory(
    *, provider: str, config_path: str | None, frozen_profile: Mapping[str, Any]
) -> ProviderFactory:
    """Bind a future authorized run to an exact frozen public profile before I/O."""

    config = resolve_provider_config(provider, start=ROOT, config_path=config_path)
    assert_provider_profile_matches(config, frozen_profile)
    if not config.api_key or not config.base_url:
        raise ValueError("authorized live smoke requires a configured provider key and base URL")

    def build(_scenario: Mapping[str, Any]) -> AuditedLiveProvider:
        client = build_native_model_client(
            wire_dialect=config.wire_dialect,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            profile_id=frozen_profile["profile_id"],
            max_retries=0,
        )
        return AuditedLiveProvider(client, provider_session_identity(config))

    return build


def run_manifest(
    manifest_path: Path,
    output_dir: Path,
    *,
    provider_factory: ProviderFactory | None = None,
    execution_mode: str = "fake_provider",
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if execution_mode not in manifest["execution_modes"]:
        raise ValueError(f"unsupported execution mode: {execution_mode}")
    provider_factory = provider_factory or _fake_provider_factory
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios: list[dict[str, Any]] = []
    for scenario in manifest["scenarios"]:
        scenario_dir = output_dir / scenario["id"]
        scenario_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{scenario['id']}-", dir=scenario_dir) as temporary:
            workspace = Path(temporary)
            _write_fixture(workspace, scenario)
            provider = provider_factory(scenario)
            agent = Pico(
                model_client=provider,
                workspace=WorkspaceContext.build(workspace),
                session_store=SessionStore(workspace / ".pico" / "sessions"),
                approval_policy=scenario["approval_policy"],
                max_steps=max(12, len(scenario["fake_responses"]) + 1),
                auto_dream=False,
            )
            bind_native_safety_evidence(agent, case_id=scenario["id"], repetition=1)
            pico_exit = 0
            stdout = ""
            stderr = ""
            try:
                stdout = agent.ask(scenario["prompt"])
            except Exception as exc:  # verifier must retain the Runtime failure.
                pico_exit = 1
                stderr = f"{type(exc).__name__}: {exc}"
            events = _events(agent)
            verification = verify_scenario(scenario, workspace, events)
            verifier_exit = 0 if verification["status"] == "PASS" else 1
            result = {
                "scenario_id": scenario["id"], "pico_exit": pico_exit,
                "verifier_exit": verifier_exit, "stdout": stdout, "stderr": stderr,
                "provider_http_attempts": provider.http_attempts,
                "verification": verification, "events": events,
            }
            (scenario_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (scenario_dir / "pico.stdout.txt").write_text(stdout, encoding="utf-8")
            (scenario_dir / "pico.stderr.txt").write_text(stderr, encoding="utf-8")
            (scenario_dir / "pico.exit.txt").write_text(f"{pico_exit}\n", encoding="utf-8")
            (scenario_dir / "verifier.exit.txt").write_text(f"{verifier_exit}\n", encoding="utf-8")
            scenarios.append(result)
            close = getattr(provider, "close", None)
            if callable(close):
                close()
    summary = {
        "schema_version": "pico-native-human-smoke-v2-artifact",
        "manifest": str(manifest_path), "execution_mode": execution_mode,
        "provider_http_attempts": sum(item["provider_http_attempts"] for item in scenarios),
        "scenarios": scenarios, "status": "PASS" if all(item["verification"]["status"] == "PASS" and item["pico_exit"] == 0 for item in scenarios) else "FAIL",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake-provider", action="store_true", help="run the no-HTTP deterministic fixture")
    mode.add_argument("--authorized-live", action="store_true", help="run only after explicit user authorization")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", help="configured provider name required for --authorized-live")
    parser.add_argument("--config", help="provider config path required for --authorized-live")
    parser.add_argument("--frozen-profile", type=Path, help="frozen public profile JSON required for --authorized-live")
    args = parser.parse_args(argv)
    if args.fake_provider:
        summary = run_manifest(args.manifest.resolve(), args.output_dir.resolve())
    else:
        if not args.provider or not args.config or args.frozen_profile is None:
            parser.error("--authorized-live requires --provider, --config, and --frozen-profile")
        profile = load_public_provider_profile(args.frozen_profile)
        factory = authorized_live_provider_factory(
            provider=args.provider, config_path=args.config, frozen_profile=profile
        )
        summary = run_manifest(
            args.manifest.resolve(), args.output_dir.resolve(),
            provider_factory=factory, execution_mode="authorized_live",
        )
    print(json.dumps({"status": summary["status"], "provider_http_attempts": summary["provider_http_attempts"]}))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
