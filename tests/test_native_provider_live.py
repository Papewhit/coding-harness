from __future__ import annotations

import json
from pathlib import Path

import pytest

from pico import Pico
from pico.config import ProviderConfig
from pico.evaluation.native_provider import (
    evaluate_native_provider_case,
    load_case_set,
    run_native_provider_conformance,
)
from pico.evaluation.native_provider_live import (
    NativeProviderLiveRunner,
    run_native_provider_live_case,
)
from pico.evaluation.native_provider_profiles import (
    ProviderProfileMismatchError,
    build_public_provider_profile,
)
from pico.providers.anthropic_messages import AnthropicMessagesAdapter
from pico.providers.contracts import (
    ModelResponse,
    ProviderContinuation,
    StopReason,
    ToolCall,
)
from pico.providers.provider_transport import (
    HttpAttempt,
    ProviderTransportResponse,
)
from pico.providers.openai_responses import OpenAIResponsesAdapter
from pico.testing import ScriptedNativeModelClient


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "benchmarks" / "v3" / "native-provider" / "cases.json"
SECRET = "sk-native-live-secret-sentinel"
RAW_URL = "https://secret-native.example.test/private/v1"


class FakeNativeTransport:
    """No-I/O wire transport consumed by a production native adapter."""

    def __init__(self, config: ProviderConfig, responses: list[ModelResponse]) -> None:
        self.payloads = [_wire_payload(config, response) for response in responses]
        self.last_http_attempts: tuple[HttpAttempt, ...] = ()
        self.requests: list[dict] = []

    def create(self, request: dict) -> ProviderTransportResponse:
        self.requests.append(dict(request))
        if not self.payloads:
            raise RuntimeError("fake transport ran out of payloads")
        payload = self.payloads.pop(0)
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.last_http_attempts = (
            HttpAttempt(
                number=1,
                method="POST",
                url=RAW_URL,
                status_code=200,
                request_id="request-fixture",
            ),
        )
        return ProviderTransportResponse(
            payload=payload,
            raw_bytes=raw,
            status_code=200,
            request_id="request-fixture",
            http_attempts=self.last_http_attempts,
            sdk_retry_count=0,
        )


class FakeAdapterClient:
    def __init__(self, config: ProviderConfig, responses: list[ModelResponse]) -> None:
        self.model = config.model
        self.base_url = config.base_url
        self._transport = FakeNativeTransport(config, responses)
        if config.wire_dialect == "anthropic-messages":
            self._adapter = AnthropicMessagesAdapter(
                self._transport,
                model=config.model,
                profile_id=config.public_identity()["profile_id"],
            )
        elif config.wire_dialect == "openai-responses":
            self._adapter = OpenAIResponsesAdapter(
                transport=self._transport,
                model=config.model,
                profile_id=config.public_identity()["profile_id"],
            )
        else:  # pragma: no cover - constrained by the local test config
            raise AssertionError(config.wire_dialect)

    def request(self, request):
        return self._adapter.request(request)


class AdverseScriptedClient(ScriptedNativeModelClient):
    def __init__(self, config: ProviderConfig, responses: list[ModelResponse]) -> None:
        super().__init__(responses)
        self.model = config.model
        self.base_url = config.base_url


def _config(
    tmp_path: Path,
    wire_dialect: str = "anthropic-messages",
) -> Path:
    path = tmp_path / f"{wire_dialect}.toml"
    path.write_text(
        "\n".join(
            [
                "[providers.fixture]",
                f'wire_dialect = "{wire_dialect}"',
                'model = "fixture-model"',
                f'base_url = "{RAW_URL}"',
                f'api_key = "{SECRET}"',
                "",
                "[providers.fixture.capabilities]",
                "native_tools = true",
                "strict_tool_schema = false",
                "parallel_tool_calls = false",
                "reasoning = false",
                "thinking = true",
                "opaque_continuation = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _clear_provider_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PICO_PROVIDER",
        "PICO_API_KEY",
        "PICO_BASE_URL",
        "PICO_MODEL",
        "PICO_WIRE_DIALECT",
        "PICO_PROTOCOL",
    ):
        monkeypatch.delenv(name, raising=False)


def _metadata(**extra: object) -> dict:
    return {
        "http_attempts": [
            {
                "number": 1,
                "method": "POST",
                "status_code": 200,
                "request_id": "request-fixture",
                "error_type": None,
            }
        ],
        "sdk_retry_count": 0,
        **extra,
    }


def _response(
    *,
    text: str = "",
    calls: tuple[ToolCall, ...] = (),
    continuation: ProviderContinuation | None = None,
    metadata: dict | None = None,
) -> ModelResponse:
    return ModelResponse(
        text=text,
        tool_calls=calls,
        stop_reason=StopReason.TOOL_CALLS if calls else StopReason.END_TURN,
        continuation=continuation,
        metadata=_metadata() if metadata is None else metadata,
    )


def _anthropic_payload(
    config: ProviderConfig, response: ModelResponse
) -> dict:
    content = []
    if response.text:
        content.append({"type": "text", "text": response.text})
    content.extend(
        {
            "type": "tool_use",
            "id": call.call_id,
            "name": call.name,
            "input": dict(call.arguments),
        }
        for call in response.tool_calls
    )
    blocks = response.metadata.get("content_blocks", {})
    if isinstance(blocks, dict) and "future_block" in blocks.get("unknown_types", []):
        content.append(
            {
                "type": "future_block",
                "opaque_fixture": "retained-without-interpretation",
            }
        )
    return {
        "id": "message-fixture",
        "type": "message",
        "role": "assistant",
        "model": config.model,
        "content": content,
        "stop_reason": "tool_use" if response.tool_calls else "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _openai_payload(
    config: ProviderConfig, response: ModelResponse
) -> dict:
    output = []
    if response.text:
        output.append(
            {
                "type": "message",
                "id": "message-fixture",
                "role": "assistant",
                "content": [{"type": "output_text", "text": response.text}],
            }
        )
    output.extend(
        {
            "type": "function_call",
            "id": f"function-{call.call_id}",
            "call_id": call.call_id,
            "name": call.name,
            "arguments": json.dumps(call.arguments, ensure_ascii=False),
        }
        for call in response.tool_calls
    )
    blocks = response.metadata.get("content_blocks", {})
    if isinstance(blocks, dict) and "future_block" in blocks.get("unknown_types", []):
        output.append(
            {
                "type": "future_block",
                "opaque_fixture": "retained-without-interpretation",
            }
        )
    return {
        "id": "response-fixture",
        "status": "completed",
        "model": config.model,
        "output": output,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _wire_payload(config: ProviderConfig, response: ModelResponse) -> dict:
    if config.wire_dialect == "anthropic-messages":
        return _anthropic_payload(config, response)
    if config.wire_dialect == "openai-responses":
        return _openai_payload(config, response)
    raise AssertionError(config.wire_dialect)


def _call(call_id: str, name: str, arguments: dict) -> ToolCall:
    return ToolCall(call_id=call_id, name=name, arguments=arguments)


def _responses(config: ProviderConfig, case: dict) -> list[ModelResponse]:
    scenario = case["scenario"]
    profile_id = config.public_identity()["profile_id"]
    final = _response(text="done")
    if scenario == "final":
        return [final]
    if scenario == "single_call":
        return [
            _response(calls=(_call("read-1", "read_file", {"path": "README.md"}),)),
            final,
        ]
    if scenario == "unicode":
        return [
            _response(
                calls=(
                    _call(
                        "write-unicode",
                        "write_file",
                        {"path": "unicode.txt", "content": "雪山 🚀 café"},
                    ),
                )
            ),
            _response(
                calls=(
                    _call("read-unicode", "read_file", {"path": "unicode.txt"}),
                )
            ),
            final,
        ]
    if scenario == "invalid_args_repair":
        return [
            _response(calls=(_call("bad-read", "read_file", {}),)),
            _response(
                calls=(
                    _call("fixed-read", "read_file", {"path": "README.md"}),
                )
            ),
            final,
        ]
    if scenario == "permission_denial":
        return [
            _response(
                calls=(
                    _call(
                        "denied-shell",
                        "run_shell",
                        {"command": "echo forbidden", "timeout": 20},
                    ),
                )
            ),
            final,
        ]
    if scenario == "multi_round_patch_verify":
        return [
            _response(calls=(_call("read-a", "read_file", {"path": "a.py"}),)),
            _response(
                calls=(
                    _call(
                        "patch-a",
                        "patch_file",
                        {
                            "path": "a.py",
                            "old_text": "VALUE = 1",
                            "new_text": "VALUE = 3",
                        },
                    ),
                )
            ),
            _response(calls=(_call("verify-a", "read_file", {"path": "a.py"}),)),
            final,
        ]
    if scenario == "unexpected_multi_call":
        return [
            _response(
                calls=(
                    _call("read-a-batch", "read_file", {"path": "a.py"}),
                    _call("read-b-batch", "read_file", {"path": "b.py"}),
                )
            ),
            final,
        ]
    continuation = ProviderContinuation(
        profile_id,
        {
            "version": "fixture-continuation-v1",
            "opaque": {"do_not_interpret": "future-block"},
        },
    )
    return [
        _response(
            calls=(
                _call("opaque-read", "read_file", {"path": "README.md"}),
            ),
            continuation=continuation,
            metadata=_metadata(
                content_blocks={
                    "count": 2,
                    "types": ["tool_use", "future_block"],
                    "unknown_types": ["future_block"],
                    "private_count": 0,
                }
            ),
        ),
        _response(text="done", continuation=continuation),
    ]


def _factory(config: ProviderConfig, case: dict) -> FakeAdapterClient:
    return FakeAdapterClient(config, _responses(config, case))


def _profile(config_path: Path) -> dict:
    from pico.config import resolve_provider_config

    return build_public_provider_profile(
        resolve_provider_config("fixture", config_path=str(config_path))
    )


def test_both_dialects_cover_identical_eight_case_repetition_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    case_set = load_case_set(CASE_PATH)
    artifacts = {}
    for dialect in ("openai-responses", "anthropic-messages"):
        dialect_root = tmp_path / dialect
        dialect_root.mkdir()
        config_path = _config(dialect_root, dialect)
        profile = _profile(config_path)
        runner = NativeProviderLiveRunner(
            provider="fixture",
            config_path=str(config_path),
            client_factory=_factory,
            workspace_parent=dialect_root,
        )
        artifact = run_native_provider_conformance(
            case_set=case_set,
            profile=profile,
            runner=runner,
            repetitions=2,
        )
        artifacts[dialect] = artifact

        assert artifact["summary"]["passed"] == 16, [
            {
                "row_id": row["row_id"],
                "case_errors": row["case_errors"],
                "protocol_errors": row["native_protocol"]["protocol_errors"],
                "received": row["continuation_received"],
                "sent": row["continuation_sent"],
            }
            for row in artifact["rows"]
            if row["status"] != "passed"
        ]
        assert artifact["summary"]["failed"] == 0
        assert artifact["summary"]["infrastructure_failure"] == 0
        assert artifact["summary"]["call_id_result_match"]["value"] == 1.0
        assert artifact["summary"]["batch_completeness"]["value"] == 1.0
        assert artifact["summary"]["text_envelope_seen_count"] == 0
        assert artifact["summary"]["implicit_sdk_retry_seen"] is False
        assert all(
            result["tool_status"] in {"ok", "rejected"}
            and "tool_error_code" in result
            and result["execution_scope"]
            in {"runtime_execution", "pre_runtime_rejection"}
            for row in artifact["rows"]
            for result in row["result_evidence"]
        )
        assert SECRET not in json.dumps(artifact)
        assert RAW_URL not in json.dumps(artifact)

        opaque = runner(case_set["cases"][-1], profile)
        assert opaque["audit"]["unknown_blocks"] == [
            {
                "response_index": 0,
                "dialect": dialect,
                "type": "future_block",
            }
        ]
        assert opaque["audit"]["unknown_block_loss_count"] == 0
        assert opaque["audit"]["safety_chain_bypass_count"] == 0
        evidence = opaque["audit"]["safety_chain_evidence"]
        assert [(item["stage"], item["outcome"]) for item in evidence] == [
            ("validate", "passed"),
            ("repetition", "passed"),
            ("permission", "passed"),
            ("policy", "passed"),
            ("execute", "completed"),
        ]
        assert {
            (item["case_id"], item["repetition"], item["call_id"])
            for item in evidence
        } == {("NP08-opaque-block-roundtrip", 3, "opaque-read")}
        assert opaque["pico_retry_count"] == 0

    parity_fields = (
        "row_id",
        "case_id",
        "repetition",
        "status",
        "case_errors",
        "text_envelope_seen",
        "implicit_sdk_retry_seen",
    )
    assert [
        {field: row[field] for field in parity_fields}
        for row in artifacts["openai-responses"]["rows"]
    ] == [
        {field: row[field] for field in parity_fields}
        for row in artifacts["anthropic-messages"]["rows"]
    ]
    protocol_parity_fields = (
        "native_tool_call_observed",
        "call_id_result_match",
        "batch_completeness",
        "duplicate_call_after_result",
        "protocol_errors",
        "http_attempts",
        "sdk_retry_count",
        "pico_retry_count",
    )
    assert [
        {
            field: row["native_protocol"][field]
            for field in protocol_parity_fields
        }
        for row in artifacts["openai-responses"]["rows"]
    ] == [
        {
            field: row["native_protocol"][field]
            for field in protocol_parity_fields
        }
        for row in artifacts["anthropic-messages"]["rows"]
    ]


def test_profile_mismatch_stops_before_client_or_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path = _config(tmp_path)
    profile = {**_profile(config_path), "model": "wrong-model"}
    called = False

    def forbidden_factory(config: ProviderConfig, case: dict) -> FakeAdapterClient:
        nonlocal called
        called = True
        return _factory(config, case)

    with pytest.raises(ProviderProfileMismatchError, match="model"):
        run_native_provider_live_case(
            case=load_case_set(CASE_PATH)["cases"][0],
            expected_profile=profile,
            provider="fixture",
            config_path=str(config_path),
            client_factory=forbidden_factory,
            workspace_parent=tmp_path,
        )

    assert called is False


def test_secret_sentinel_and_raw_url_never_enter_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path = _config(tmp_path)
    observation = run_native_provider_live_case(
        case=load_case_set(CASE_PATH)["cases"][1],
        expected_profile=_profile(config_path),
        provider="fixture",
        config_path=str(config_path),
        client_factory=_factory,
        workspace_parent=tmp_path,
    )

    rendered = json.dumps(observation, ensure_ascii=False)
    assert SECRET not in rendered
    assert RAW_URL not in rendered
    assert observation["audit"]["model_response_count"] == 2


def test_safety_chain_bypass_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path = _config(tmp_path)

    def bypass(_self: Pico, _name: str, _args: dict) -> str:
        return "bypassed"

    monkeypatch.setattr(Pico, "run_tool", bypass)
    observation = run_native_provider_live_case(
        case=load_case_set(CASE_PATH)["cases"][1],
        expected_profile=_profile(config_path),
        provider="fixture",
        config_path=str(config_path),
        client_factory=_factory,
        workspace_parent=tmp_path,
    )

    assert observation["audit"]["safety_chain_bypass_count"] == 1
    assert observation["audit"]["safety_chain"][0]["bypass"] is True


def test_text_envelope_and_implicit_retry_remain_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_overrides(monkeypatch)
    config_path = _config(tmp_path)
    case = load_case_set(CASE_PATH)["cases"][0]

    def adverse_factory(
        config: ProviderConfig, _case: dict
    ) -> AdverseScriptedClient:
        return AdverseScriptedClient(
            config,
            [
                _response(
                    text="<tool>legacy</tool>",
                    metadata=_metadata(sdk_retry_count=1),
                )
            ],
        )

    observation = run_native_provider_live_case(
        case=case,
        expected_profile=_profile(config_path),
        provider="fixture",
        config_path=str(config_path),
        client_factory=adverse_factory,
        workspace_parent=tmp_path,
    )
    row = evaluate_native_provider_case(case, observation)

    assert row["text_envelope_seen"] is True
    assert row["implicit_sdk_retry_seen"] is True
    assert row["status"] == "failed"
    assert {item["code"] for item in row["native_protocol"]["protocol_errors"]} >= {
        "text_protocol_envelope",
        "implicit_sdk_retry",
    }
