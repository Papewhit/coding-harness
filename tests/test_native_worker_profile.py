"""Lock worker parent/child provider profiles before native requests."""

from __future__ import annotations

import json

import pytest

from coda import Coda, SessionStore, WorkspaceContext
from coda.config import ProviderCapabilities, ProviderConfig
from coda.core.worker_runtime import build_child_runtime
from coda.providers import native_provider_profile
from tests.native_fixtures import final, scripted_client, scripted_provider_identity


def _parent(tmp_path, child_client):
    return Coda(
        model_client=scripted_client([]),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".coda" / "sessions"),
        approval_policy="auto",
        model_client_factory=lambda: child_client,
    )


class ProductionLikeClient:
    def __init__(self, identity=None):
        self._client = scripted_client([final("Child done.")])
        self.model = "child-model"
        self.wire_dialect = "openai-responses"
        self.provider = "openai"
        self.base_url = "https://provider.example/v1"
        self.sdk_max_retries = 0
        self.provider_attempts = 1
        if identity is not None:
            self._coda_profile_identity = identity

    def request(self, request):
        return self._client.request(request)


@pytest.mark.parametrize(
    ("subagent_type", "write_scope", "expected_tool_profile"),
    (("Explore", (), "readonly"), ("worker", ("notes",), "worker")),
)
def test_child_profile_matches_client_identity_and_final_tool_schema(
    tmp_path, subagent_type, write_scope, expected_tool_profile
):
    child_client = scripted_client([final("Child done.")])
    child_identity = {
        **scripted_provider_identity(),
        "profile_id": "scripted-native:child-profile",
        "profile": "scripted-child",
        "model": "scripted-child-model",
        "wire_dialect": "scripted-child-native",
    }
    child_client._coda_profile_identity = child_identity
    parent = _parent(tmp_path, child_client)

    child = build_child_runtime(parent, subagent_type, write_scope)
    profile = child.session["provider_profile"]

    assert parent.session["provider_profile"]["tool_schema"] == parent.tool_signature()
    assert child.model_client is child_client
    assert child.active_tool_profile.name == expected_tool_profile
    assert profile == {**child_identity, "tool_schema": child.tool_signature()}
    assert profile["tool_schema"] != parent.session["provider_profile"]["tool_schema"]
    assert json.loads(json.dumps(child.session))["provider_profile"] == profile
    assert child.ask("prove the child profile is locked") == "Child done."


def test_child_runtime_rejects_parent_without_locked_profile(tmp_path):
    child_client = scripted_client([final("must not run")])
    parent = _parent(tmp_path, child_client)
    parent.session.pop("provider_profile")
    parent.session_path = parent.session_store.save(parent.session)

    with pytest.raises(ValueError, match="worker parent requires a locked provider_profile"):
        build_child_runtime(parent, "Explore", ())


def test_child_profile_verifies_production_client_before_inheriting_identity(tmp_path):
    config = ProviderConfig(
        name="child-provider",
        wire_dialect="openai-responses",
        api_key="unused",
        base_url="https://provider.example/v1",
        model="child-model",
        capabilities=ProviderCapabilities(),
    )
    identity = {
        **config.public_identity(),
        **native_provider_profile(config.wire_dialect),
    }
    parent_client = ProductionLikeClient(identity)
    child_client = ProductionLikeClient()
    parent = Coda(
        model_client=parent_client,
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".coda" / "sessions"),
        approval_policy="auto",
        model_client_factory=lambda: child_client,
    )

    child = build_child_runtime(parent, "worker", ("notes",))

    assert child.model_client is child_client
    assert child.session["provider_profile"] == {
        **identity,
        "tool_schema": child.tool_signature(),
    }
    assert child.ask("prove inherited production identity") == "Child done."
