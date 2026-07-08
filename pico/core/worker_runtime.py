"""Child runtime construction for worker tasks."""

from __future__ import annotations

from typing import Any

from .workspace import WorkspaceContext


def build_child_runtime(parent: Any, subagent_type: str, write_scope: tuple[str, ...]) -> Any:
    from .runtime import Pico

    child = Pico(
        model_client=new_model_client(parent),
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
    child.refresh_prefix(force=True)
    return child


def new_model_client(parent: Any) -> Any:
    factory = getattr(parent, "model_client_factory", None)
    if factory is not None:
        return factory()
    return parent.model_client
