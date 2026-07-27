#!/usr/bin/env python3
"""Run one Evaluation v2 task through the production Pico Runtime."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from pico.config import resolve_provider_config
from pico.core.runtime import Pico
from pico.core.session_store import SessionStore
from pico.core.workspace import WorkspaceContext
from pico.evaluation.evaluation_v2_config import (
    CONFIG_LOCATOR_ENV,
    canonical_json,
    verify_run_config,
)
from pico.evaluation.live_client import (
    AuditedNativeClient,
    build_client_result,
    required_network_sandbox,
)
from pico.evaluation.live_tasks import ClientResult, FailureCategory, HttpAttempt
from pico.evaluation.native_provider_profiles import (
    assert_provider_profile_matches,
    provider_session_identity,
)
from pico.providers import build_native_model_client


PROMPT_ENV = "PICO_LIVE_TASK_PROMPT"
EVIDENCE_ENV = "PICO_LIVE_EVIDENCE_PATH"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    (
        workspace,
        evidence_path,
        prompt,
        run_config,
        provider_config,
        locator,
    ) = _validated_live_inputs(args.run_config)
    expected_profile = run_config["profile"]["public_profile"]
    inner = build_native_model_client(
        wire_dialect=provider_config.wire_dialect,
        model=provider_config.model,
        base_url=provider_config.base_url,
        api_key=provider_config.api_key,
        profile_id=provider_config.public_identity()["profile_id"],
        timeout=float(run_config["runtime"]["provider_timeout_seconds"]),
        max_retries=0,
    )
    sensitive_values = tuple(value for value in (locator, provider_config.api_key) if value)

    def persist_attempts(attempts: tuple[HttpAttempt, ...]) -> None:
        _merge_client_result(
            evidence_path,
            {
                "profile": expected_profile,
                "native_gate_hash": run_config["profile"]["native_gate_hash"],
                "http_attempts": [attempt.as_dict() for attempt in attempts],
                "http_attempts_exact": True,
                "sdk_retry_count": 0,
                "pico_retry_count": 0,
                "failure_category": FailureCategory.NONE.value,
            },
            sensitive_values,
        )

    client = AuditedNativeClient(inner, persist_attempts=persist_attempts)
    client._pico_profile_identity = provider_session_identity(provider_config)
    agent = None
    try:
        agent = _build_agent(
            workspace=workspace,
            client=client,
            run_config=run_config,
        )
        final_answer = agent.ask(prompt)
        result = build_client_result(
            agent=agent,
            client=client,
            profile=expected_profile,
            native_gate_hash=str(run_config["profile"]["native_gate_hash"]),
            final_answer=final_answer,
        )
        _merge_client_result(
            evidence_path,
            _client_result_dict(result),
            sensitive_values,
        )
        return 0 if result.failure_category is FailureCategory.NONE else 1
    except Exception as exc:
        result = (
            build_client_result(
                agent=agent,
                client=client,
                profile=expected_profile,
                native_gate_hash=str(run_config["profile"]["native_gate_hash"]),
                final_answer="",
            )
            if agent is not None
            else ClientResult(
                profile=expected_profile,
                native_gate_hash=str(run_config["profile"]["native_gate_hash"]),
                http_attempts=tuple(client.http_attempts),
                error=type(exc).__name__,
                failure_category=(
                    FailureCategory.PROVIDER
                    if client.http_attempts
                    else FailureCategory.INFRASTRUCTURE
                ),
            )
        )
        payload = _client_result_dict(result)
        payload["error"] = type(exc).__name__
        _merge_client_result(evidence_path, payload, sensitive_values)
        print("live task client failed; inspect run-record.json", file=sys.stderr)
        return 1
    finally:
        client.close()


def _validated_live_inputs(
    run_config_path: Path,
) -> tuple[Path, Path, str, dict[str, Any], Any, str]:
    workspace = Path.cwd().resolve()
    evidence_path = _required_path_env(EVIDENCE_ENV)
    prompt = os.environ.get(PROMPT_ENV, "")
    if not prompt:
        raise SystemExit(f"{PROMPT_ENV} is required")
    run_config = _load_object(run_config_path)
    source_root = Path(run_config["source"]["workspace_root"])
    verify_run_config(run_config_path, source_root=source_root)
    locator = os.environ.get(CONFIG_LOCATOR_ENV, "")
    if not locator or not Path(locator).is_file():
        raise SystemExit(f"{CONFIG_LOCATOR_ENV} must identify an existing file")
    expected_profile = run_config["profile"]["public_profile"]
    provider_config = resolve_provider_config(
        str(expected_profile["provider"]),
        start=workspace,
        config_path=locator,
    )
    assert_provider_profile_matches(provider_config, expected_profile)
    return workspace, evidence_path, prompt, run_config, provider_config, locator


def _build_agent(
    *,
    workspace: Path,
    client: AuditedNativeClient,
    run_config: Mapping[str, Any],
) -> Pico:
    runtime = run_config["runtime"]
    sandbox = required_network_sandbox(
        extra_readonly_paths=(
            sys.prefix,
            str(Path(sys.base_prefix).parent),
        )
    )
    probe = sandbox.run("true", cwd=workspace, env={}, timeout=10)
    if probe.returncode:
        raise RuntimeError("network-isolated bubblewrap preflight failed")
    agent = Pico(
        model_client=client,
        workspace=WorkspaceContext.build(workspace),
        session_store=SessionStore(workspace / ".pico" / "sessions"),
        approval_policy=str(runtime["approval_policy"]),
        max_steps=int(runtime["max_tool_steps"]),
        max_new_tokens=int(runtime["max_output_tokens"]),
        auto_dream=bool(runtime["auto_dream"]),
        write_scope=str(workspace),
        allowed_tools=tuple(runtime["allowed_tools"]),
        secret_env_names=(CONFIG_LOCATOR_ENV,),
    )
    agent.sandbox_runner = sandbox
    return agent


def _client_result_dict(result: ClientResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["failure_category"] = result.failure_category.value
    payload["http_attempts"] = [attempt.as_dict() for attempt in result.http_attempts]
    return payload


def _merge_client_result(
    path: Path,
    client_result: Mapping[str, Any],
    sensitive_values: tuple[str, ...],
) -> None:
    envelope = _load_object(path) if path.is_file() else {}
    envelope["client_result"] = _redact_known(dict(client_result), sensitive_values)
    temporary = path.with_name(path.name + ".client.tmp")
    temporary.write_bytes(canonical_json(envelope))
    temporary.replace(path)


def _redact_known(value: Any, sensitive_values: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        for sensitive in sensitive_values:
            if sensitive:
                value = value.replace(sensitive, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {str(key): _redact_known(item, sensitive_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_known(item, sensitive_values) for item in value]
    return value


def _required_path_env(name: str) -> Path:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required")
    return Path(value).resolve()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
