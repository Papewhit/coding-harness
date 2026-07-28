"""Offline subprocess entry for the Evaluation v2 production bridge test."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV  # noqa: E402
from pico.providers import NativeProviderModelClient  # noqa: E402
from pico.providers.openai_responses import OpenAIResponsesAdapter  # noqa: E402
from scripts.run_pico_live_task_client import (  # noqa: E402
    EVIDENCE_ENV,
    PROMPT_ENV,
    run_live_task,
)


class UnreachableOfflineTransport:
    """Deterministic no-network transport that the injected Runtime error precedes."""

    last_http_attempts: tuple[object, ...] = ()

    def create(self, request: object) -> object:
        del request
        raise AssertionError("offline transport must not be reached")

    def close(self) -> None:
        return None


def main() -> int:
    profile_id = "sha256:" + "1" * 64
    transport = UnreachableOfflineTransport()
    inner = NativeProviderModelClient.__new__(NativeProviderModelClient)
    inner.model = "offline-bridge-model"
    inner.base_url = "https://offline.invalid/v1"
    inner.wire_dialect = "openai-responses"
    inner.protocol = "openai-responses"
    inner.provider = "openai"
    inner.sdk_max_retries = 0
    inner.provider_attempts = 1
    inner.supports_prompt_cache = False
    inner._transport = transport
    inner._adapter = OpenAIResponsesAdapter(
        transport=transport,
        model="offline-bridge-model",
        profile_id=profile_id,
    )
    profile = {
        "provider": "offline-bridge",
        "profile_id": profile_id,
        "model": "offline-bridge-model",
        "wire_dialect": "openai-responses",
    }
    run_config = {
        "profile": {
            "public_profile": profile,
            "native_gate_hash": "2" * 64,
        },
        "runtime": {
            "approval_policy": "auto",
            "max_tool_steps": 50,
            "max_output_tokens": 4096,
            "auto_dream": False,
            "allowed_tools": ["read_file"],
        },
    }
    return run_live_task(
        workspace=Path.cwd().resolve(),
        evidence_path=Path(os.environ[EVIDENCE_ENV]).resolve(),
        prompt=os.environ[PROMPT_ENV],
        run_config=run_config,
        inner=inner,
        session_identity={
            "profile_id": profile_id,
            "profile": "offline-bridge",
            "model": "offline-bridge-model",
            "wire_dialect": "openai-responses",
            "base_url_fingerprint": "sha256:" + "3" * 64,
            "capabilities": {
                "native_tools": True,
                "strict_tool_schema": False,
                "parallel_tool_calls": False,
                "reasoning": False,
                "thinking": False,
                "opaque_continuation": False,
            },
        },
        sensitive_values=(os.environ.get(CONFIG_LOCATOR_ENV, ""),),
    )


if __name__ == "__main__":
    raise SystemExit(main())
