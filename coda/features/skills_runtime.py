"""Execution helpers for Coda skills."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from ..core.runtime import Coda
from ..core.tool_profiles import ToolSetProfile
from .skills import Skill


def invoke_skill(agent: Coda, name: str, arguments: str = "") -> str:
    skill = agent.skills.get(str(name).lstrip("/"))
    if not skill:
        raise KeyError(name)
    prompt = _skill_prompt(skill, arguments)
    agent.session_event_bus.emit("skill_invoked", _event_payload(skill, arguments, prompt))
    if skill.disable_model_invocation:
        agent.session_event_bus.emit("skill_completed", _event_payload(skill, arguments, prompt, status="prompt_only"))
        return skill.render(arguments)
    # 使用上下文管理器临时覆盖模型和工具配置，以确保技能在执行时使用正确的环境设置
    with _model_override(agent, skill.model), _skill_tool_profile(agent, skill):
        # 根据技能的 context metadata 决定是否在子会话中运行技能
        answer = _run_fork(agent, skill, prompt) if skill.context == "fork" else agent.ask(prompt)
    agent.session_event_bus.emit("skill_completed", _event_payload(skill, arguments, prompt, status="completed", answer=answer))
    return answer


def _run_fork(agent: Coda, skill: Skill, prompt: str) -> str:
    parent_profile = agent.session.get("provider_profile")
    if not isinstance(parent_profile, Mapping):
        raise ValueError("fork skill parent requires a locked provider_profile")
    child = type(agent)(
        model_client=agent.model_client,
        workspace=agent.workspace,
        session_store=agent.session_store,
        approval_policy=agent.approval_policy,
        max_steps=agent.max_steps,
        max_new_tokens=agent.max_new_tokens,
        depth=agent.depth,
        max_depth=agent.max_depth,
        read_only=agent.read_only,
        shell_env_allowlist=agent.shell_env_allowlist,
        secret_env_names=agent.secret_env_names,
        feature_flags=agent.feature_flags,
    )
    child.session["provider_profile"] = {
        **{key: value for key, value in parent_profile.items() if key != "tool_schema"},
        "tool_schema": child.tool_signature(),
    }
    child.session_path = child.session_store.save(child.session)
    with _model_override(child, skill.model), _skill_tool_profile(child, skill):
        answer = child.ask(prompt)
    agent.session_event_bus.emit("skill_fork_completed", {"skill": skill.name, "child_session_id": child.session["id"]})
    return answer


def _skill_prompt(skill: Skill, arguments: str) -> str:
    return (
        f"Skill: {skill.name}\nSource: {skill.source}\nContext: {skill.context}\n"
        f"Arguments: {arguments}\n\n{skill.render(arguments)}"
    )


def _event_payload(skill: Skill, arguments: str, prompt: str, status: str = "", answer: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "skill": skill.name,
        "source": skill.source,
        "context": skill.context,
        "arguments": str(arguments),
        "allowed_tools": list(skill.allowed_tools),
        "prompt_chars": len(prompt),
        "model_override": skill.model,
    }
    if status:
        payload["status"] = status
    if answer:
        payload["answer_chars"] = len(str(answer))
    return payload


@contextmanager
def _skill_tool_profile(agent: Coda, skill: Skill) -> Generator[None, None, None]:
    if not skill.allowed_tools:
        yield
        return
    previous = agent.active_tool_profile.name
    profile_name = f"skill:{skill.name}"
    allowed = frozenset(name for name in skill.allowed_tools if name in agent.tools)
    agent.tool_profiles[profile_name] = ToolSetProfile(profile_name, allowed)
    agent.set_tool_profile(profile_name)
    try:
        yield
    finally:
        agent.set_tool_profile(previous)
        agent.tool_profiles.pop(profile_name, None)


@contextmanager
def _model_override(agent: Coda, model: str | None) -> Generator[None, None, None]:
    if not model:
        yield
        return
    sentinel = object()
    previous = getattr(agent.model_client, "model", sentinel)
    setattr(agent.model_client, "model", model)
    try:
        yield
    finally:
        # Restore the previous model if it was set, otherwise remove the attribute
        if previous is sentinel:
            delattr(agent.model_client, "model")
        else:
            setattr(agent.model_client, "model", previous)
