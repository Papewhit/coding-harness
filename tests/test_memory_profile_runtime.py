import json

from tests.native_fixtures import final
from tests.test_coda import build_agent


def test_explicit_memory_promotion_audits_markdown_emphasized_secret_label(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            final(
                "- **Dependency:** API key is sk-live-secret-abc.\n"
                "- **Project convention:** Use pytest for tests."
            ),
        ],
    )

    agent.ask("请记住这些稳定事实到 durable memory。")

    report = json.loads(
        agent.run_store.report_path(agent.current_task_state).read_text(
            encoding="utf-8"
        )
    )
    conventions_path = (
        tmp_path / ".coda" / "memory" / "topics" / "project-conventions.md"
    )

    assert report["durable_rejections"] == ["dependency-facts:secret_shaped"]
    assert report["durable_promotions"] == [
        "project-conventions: Use pytest for tests."
    ]
    assert "Use pytest for tests." in conventions_path.read_text(encoding="utf-8")


def test_dream_child_inherits_locked_provider_profile(tmp_path):
    agent = build_agent(tmp_path, [final("Nothing to consolidate.")])
    del agent.model_client._coda_profile_identity

    assert agent.run_dream() == "Nothing to consolidate."

    child_sessions = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in agent.session_store.root.glob("*.json")
        if path.stem != agent.session["id"]
    ]
    assert len(child_sessions) == 1
    assert child_sessions[0]["provider_profile"]["tool_schema"] != (
        agent.session["provider_profile"]["tool_schema"]
    )
