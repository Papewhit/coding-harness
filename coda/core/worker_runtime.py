"""Child runtime construction for worker tasks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from ..providers.base import ModelClient
from .workspace import WorkspaceContext
if TYPE_CHECKING:
    from .runtime import Coda


def build_child_runtime(parent: Coda, subagent_type: str, write_scope: tuple[str, ...]) -> Coda:
    from .runtime import Coda

    parent_profile = parent.session.get("provider_profile")
    if not isinstance(parent_profile, Mapping):
        raise ValueError("worker parent requires a locked provider_profile")
    model_client = new_model_client(parent)
    child = Coda(
        model_client=model_client,
        workspace=WorkspaceContext.build(parent.root, repo_root_override=parent.root),
        session_store=parent.session_store,
        run_store=parent.run_store,
        approval_policy="never" if subagent_type == "Explore" else "auto",
        max_steps=parent.max_steps,
        max_new_tokens=parent.max_new_tokens,
        depth=parent.depth + 1,
        max_depth=parent.max_depth,
        read_only=subagent_type == "Explore"
        or (subagent_type == "worker" and not write_scope),
        secret_env_names=parent.secret_env_names,
        shell_env_allowlist=parent.shell_env_allowlist,
        feature_flags=parent.feature_flags,
        write_scope=write_scope,
        model_client_factory=getattr(parent, "model_client_factory", None),
        sandbox_config=getattr(parent, "sandbox_config", None),
        ask_user_callback=getattr(parent, "ask_user_callback", None),
    )
    child.set_tool_profile("readonly" if subagent_type == "Explore" else "worker")
    child.session["provider_profile"] = _child_provider_profile(
        parent_profile, model_client, child.tool_signature()
    )
    child.session_path = child.session_store.save(child.session)
    child.refresh_prefix(force=True)
    return child


def new_model_client(parent: Coda) -> ModelClient:
    factory = getattr(parent, "model_client_factory", None)
    if factory is not None:
        return factory()
    return parent.model_client


def _child_provider_profile(
    parent_profile: Mapping[str, object],
    model_client: ModelClient,
    tool_schema: str,
) -> dict[str, object]:
    client_identity = getattr(model_client, "_coda_profile_identity", None)
    identity = client_identity if isinstance(client_identity, Mapping) else parent_profile
    profile = {key: value for key, value in identity.items() if key != "tool_schema"}
    _validate_client_identity(profile, model_client)
    profile["tool_schema"] = tool_schema
    return profile


def _validate_client_identity(
    profile: Mapping[str, object], model_client: ModelClient
) -> None:
    for profile_key, client_attribute in (
        ("model", "model"),
        ("wire_dialect", "wire_dialect"),
        ("sdk_package", "provider"),
        ("sdk_max_retries", "sdk_max_retries"),
        ("provider_attempts", "provider_attempts"),
    ):
        actual = getattr(model_client, client_attribute, None)
        if actual is not None and profile.get(profile_key) != actual:
            raise ValueError(
                f"worker child {profile_key} does not match its model client"
            )
    base_url = getattr(model_client, "base_url", None)
    if base_url is not None and profile.get("base_url_fingerprint") != _fingerprint(
        str(base_url)
    ):
        raise ValueError("worker child base_url does not match its model client")


def _fingerprint(base_url: str) -> str:
    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    endpoint = urlunsplit(
        (parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", "")
    )
    return "sha256:" + hashlib.sha256(endpoint.encode("utf-8")).hexdigest()
