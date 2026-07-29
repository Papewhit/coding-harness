"""Offline subprocess entry for the Evaluation v2 production bridge test."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV  # noqa: E402
from pico.providers import NativeProviderModelClient  # noqa: E402
from pico.providers.openai_responses import OpenAIResponsesAdapter  # noqa: E402
from pico.providers.provider_transport import (  # noqa: E402
    HttpAttempt,
    ProviderTransportResponse,
)
from scripts.run_pico_live_task_client import (  # noqa: E402
    EVIDENCE_ENV,
    PROMPT_ENV,
    run_live_task,
)


class DeterministicOfflineTransport:
    """Prove normalized input reaches the production adapter without network."""

    last_http_attempts: tuple[HttpAttempt, ...] = ()

    def create(self, request: object) -> ProviderTransportResponse:
        if not isinstance(request, dict):
            raise AssertionError("offline transport requires a wire request")
        raw_prompt = os.environ[PROMPT_ENV]
        normalized = raw_prompt.strip()
        wire_input = request.get("input")
        if raw_prompt == normalized:
            raise AssertionError("bridge fixture must exercise outer whitespace")
        if not isinstance(wire_input, str) or not wire_input.endswith(
            f"Current user request:\n{normalized}"
        ):
            raise AssertionError("live bridge did not normalize prompt like user entrypoints")
        self.last_http_attempts = (
            HttpAttempt(
                number=1,
                method="POST",
                url="https://offline.invalid/v1/responses",
                status_code=200,
                request_id="offline-bridge-request",
            ),
        )
        payload = {
            "id": "offline-bridge-response",
            "status": "completed",
            "model": "offline-bridge-model",
            "output": [
                {
                    "type": "message",
                    "id": "offline-bridge-message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Normalized prompt reached transport.",
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return ProviderTransportResponse(
            payload=payload,
            raw_bytes=raw,
            status_code=200,
            request_id="offline-bridge-request",
            http_attempts=self.last_http_attempts,
            sdk_retry_count=0,
        )

    def close(self) -> None:
        return None


def main() -> int:
    profile_id = "sha256:" + "1" * 64
    transport = DeterministicOfflineTransport()
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
