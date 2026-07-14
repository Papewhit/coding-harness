from datetime import date

from pico.features.memory import (
    LayeredMemory,
    append_to_daily_log,
    build_dream_prompt,
    build_memory_system_section,
    daily_log_path,
    ensure_memory_dir,
    extract_memory_tags,
    list_sessions_since,
    load_memory_index_text,
    release_lock,
    try_acquire_lock,
)


PUBLIC_MEMORY_SYMBOLS = {
    "DREAM_MIN_NEW_TOKENS",
    "DREAM_SESSION_CAP",
    "DURABLE_MEMORY_INTENT_PATTERN",
    "DURABLE_MEMORY_INTENT_ZH_PATTERN",
    "DURABLE_MEMORY_LINE_PATTERNS",
    "DURABLE_MEMORY_LIST_PREFIX_PATTERN",
    "DURABLE_TOPIC_DEFAULTS",
    "ENTRYPOINT_NAME",
    "EPISODIC_NOTE_LIMIT",
    "FILE_SUMMARY_LIMIT",
    "HOLDER_STALE_S",
    "LOCK_FILE_NAME",
    "MAX_ENTRYPOINT_LINES",
    "MAX_MEMORY_INDEX_CHARS",
    "SECRET_SHAPED_TEXT_PATTERN",
    "WORKING_FILE_LIMIT",
    "DurableMemoryStore",
    "LayeredMemory",
    "append_note",
    "append_to_daily_log",
    "build_dream_prompt",
    "build_memory_system_section",
    "canonicalize_path",
    "daily_log_path",
    "default_memory_maintenance_audit",
    "default_memory_state",
    "ensure_memory_dir",
    "evaluate_auto_dream_gate",
    "extract_durable_promotions",
    "extract_memory_tags",
    "file_freshness",
    "invalidate_file_summary",
    "invalidate_stale_file_summaries",
    "is_effectively_empty",
    "list_sessions_since",
    "load_memory_index_text",
    "maintain_memory_after_turn",
    "normalize_memory_state",
    "promote_durable_memory",
    "read_last_consolidated_at",
    "record_consolidation",
    "reject_durable_reason",
    "release_lock",
    "remember_file",
    "render_memory_text",
    "resolve_workspace_path",
    "retrieval_candidates",
    "retrieval_view",
    "run_dream",
    "set_file_summary",
    "set_task_summary",
    "should_auto_dream",
    "summarize_read_result",
    "try_acquire_lock",
}


def test_memory_module_preserves_public_surface():
    from pico.features import memory

    assert PUBLIC_MEMORY_SYMBOLS <= set(vars(memory))


def test_memory_implementation_is_split_by_responsibility():
    from pico.features import memory, memory_durable, memory_working

    assert memory.DurableMemoryStore is memory_durable.DurableMemoryStore
    assert memory.build_dream_prompt is memory_durable.build_dream_prompt
    assert memory.LayeredMemory is memory_working.LayeredMemory
    assert memory.normalize_memory_state is memory_working.normalize_memory_state


def test_working_memory_tracks_summary_and_recent_files():
    memory = LayeredMemory()

    memory.set_task_summary("Investigate flaky tests")
    memory.remember_file("README.md")
    memory.remember_file("src/app.py")
    memory.remember_file("README.md")

    snapshot = memory.to_dict()

    assert snapshot["working"]["task_summary"] == "Investigate flaky tests"
    assert snapshot["working"]["recent_files"] == ["src/app.py", "README.md"]
    assert snapshot["task"] == "Investigate flaky tests"
    assert snapshot["files"] == ["src/app.py", "README.md"]


def test_episodic_notes_append_and_retrieve_deterministically():
    memory = LayeredMemory()

    memory.append_note("Exact tag note", tags=("recall",), created_at="2026-04-07T10:00:00+00:00")
    memory.append_note("Keyword overlap note about memory", created_at="2026-04-07T10:01:00+00:00")
    memory.append_note("Newest unrelated note", created_at="2026-04-07T10:02:00+00:00")
    memory.append_note("Older unrelated note", created_at="2026-04-07T09:59:00+00:00")

    snapshot = memory.to_dict()
    assert [note["text"] for note in snapshot["episodic_notes"]] == [
        "Exact tag note",
        "Keyword overlap note about memory",
        "Newest unrelated note",
        "Older unrelated note",
    ]
    assert snapshot["notes"] == [
        "Exact tag note",
        "Keyword overlap note about memory",
        "Newest unrelated note",
        "Older unrelated note",
    ]

    lines = [line for line in memory.retrieval_view("recall memory", limit=4).splitlines() if line.startswith("- ")]
    assert lines == [
        "- Exact tag note",
        "- Keyword overlap note about memory",
    ]


def test_file_summaries_use_canonical_paths_and_freshness(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\n", encoding="utf-8")
    memory = LayeredMemory(workspace_root=tmp_path)

    memory.set_file_summary("./sample.txt", "sample.txt: alpha")
    memory.remember_file("./sample.txt")
    snapshot = memory.to_dict()["file_summaries"]["sample.txt"]

    assert snapshot["summary"] == "sample.txt: alpha"
    assert snapshot["freshness"]

    assert "sample.txt: alpha" in memory.render_memory_text()
    file_path.write_text("beta\n", encoding="utf-8")
    assert "sample.txt: alpha" not in memory.render_memory_text()

    memory.invalidate_file_summary("sample.txt")

    assert "sample.txt" not in memory.to_dict()["file_summaries"]


def test_process_notes_keep_kind_and_latest_duplicate_wins():
    memory = LayeredMemory()

    memory.append_note(
        "Shell partial success on README.md; inspect diff before retry",
        tags=("process", "partial_success"),
        created_at="2026-04-07T10:00:00+00:00",
        kind="process",
    )
    memory.append_note(
        "Shell partial success on README.md; inspect diff before retry",
        tags=("process", "partial_success"),
        created_at="2026-04-07T10:01:00+00:00",
        kind="process",
    )

    notes = memory.to_dict()["episodic_notes"]

    assert len(notes) == 1
    assert notes[0]["kind"] == "process"
    assert notes[0]["created_at"] == "2026-04-07T10:01:00+00:00"


def test_durable_memory_index_and_topic_notes_are_loaded_and_retrieved(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"
    topics_dir = memory_root / "topics"
    topics_dir.mkdir(parents=True)
    (memory_root / "MEMORY.md").write_text(
        "# Durable Memory Index\n\n"
        "- [project-conventions](topics/project-conventions.md): Project Conventions\n"
        "  - summary: Stable repository conventions.\n"
        "  - tags: convention\n",
        encoding="utf-8",
    )
    (topics_dir / "project-conventions.md").write_text(
        "# Project Conventions\n\n"
        "- topic: project-conventions\n"
        "- summary: Stable repository conventions.\n"
        "- tags: convention\n"
        "- updated_at: 2026-04-12T08:14:49+00:00\n\n"
        "## Notes\n"
        "- Use constrained tools instead of guessing.\n"
        "- Preserve local agent state under .pico/.\n",
        encoding="utf-8",
    )

    memory = LayeredMemory(workspace_root=tmp_path)

    snapshot = memory.to_dict()
    assert snapshot["durable_topics"] == ["project-conventions"]

    lines = [line for line in memory.retrieval_view("constrained tools", limit=4).splitlines() if line.startswith("- ")]
    assert any("Use constrained tools instead of guessing." in line for line in lines)


def test_kairos_daily_log_index_policy_and_memory_tag_helpers(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"

    ensure_memory_dir(memory_root)
    append_to_daily_log(memory_root, "Prefer repo-local memory assets.", today=date(2026, 5, 12))
    (memory_root / "MEMORY.md").write_text(
        "# Durable Memory Index\n\n- [User Preferences](user-preferences.md): Collaboration preferences\n",
        encoding="utf-8",
    )

    log_path = daily_log_path(memory_root, today=date(2026, 5, 12))
    assert log_path == memory_root / "logs" / "2026" / "05" / "2026-05-12.md"
    assert "Prefer repo-local memory assets." in log_path.read_text(encoding="utf-8")
    assert "User Preferences" in load_memory_index_text(memory_root)

    policy = build_memory_system_section(memory_root)
    assert "# Auto Memory" in policy
    assert "/remember <text>" in policy
    assert "Current Memory Index" in policy
    assert "User Preferences" in policy

    assert extract_memory_tags("x <memory>alpha</memory> y <memory> beta </memory>") == ["alpha", "beta"]


def test_kairos_memory_system_section_defines_file_contract_and_forget_policy(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"

    policy = build_memory_system_section(memory_root)

    assert "There are four discrete types of memory" in policy
    for memory_type in ("### user", "### feedback", "### project", "### reference"):
        assert memory_type in policy
    assert "If the user explicitly asks you to remember something, save it immediately" in policy
    assert "If they ask you to forget something, find and remove the relevant entry" in policy
    assert "name: {{memory name}}" in policy
    assert "description: {{one-line description" in policy
    assert "type: {{user | feedback | project | reference}}" in policy
    assert "MEMORY.md is an index, not a memory" in policy
    assert "Keep it under 200 lines" in policy
    assert "You MUST access memory when the user explicitly asks you to recall or remember" in policy
    assert "Code patterns, architecture, file paths" in policy


def test_dream_prompt_targets_repo_local_memory_assets(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"

    prompt = build_dream_prompt(memory_root, transcript_dir=str(tmp_path / ".pico" / "sessions"), session_ids=["s1", "s2"])

    assert "Dream: Memory Consolidation" in prompt
    assert str(memory_root) in prompt
    assert "MEMORY.md" in prompt
    assert "logs/YYYY/MM/YYYY-MM-DD.md" in prompt
    assert "s1" in prompt and "s2" in prompt


def test_dream_prompt_uses_four_phase_filesystem_maintenance_flow(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"
    transcript_dir = tmp_path / ".pico" / "sessions"

    prompt = build_dream_prompt(memory_root, transcript_dir=str(transcript_dir), session_ids=["s1"])

    assert "Phase 1" in prompt and "Orient" in prompt
    assert "Phase 2" in prompt and "Gather recent signal" in prompt
    assert "Phase 3" in prompt and "Consolidate" in prompt
    assert "Phase 4" in prompt and "Prune and index" in prompt
    assert "grep -rn" in prompt
    assert "--include=\"*.jsonl\"" in prompt
    assert "Use the memory file format and type conventions" in prompt
    assert "Converting relative dates" in prompt
    assert f"under {200} lines" in prompt
    assert "under ~25KB" in prompt
    assert "Never write memory content directly into it" in prompt
    assert "Remove pointers to memories that are now stale, wrong, or superseded" in prompt


def test_consolidation_lock_can_be_reacquired_after_release(tmp_path):
    memory_root = tmp_path / ".pico" / "memory"

    assert try_acquire_lock(memory_root) is True
    release_lock(memory_root)

    assert try_acquire_lock(memory_root) is True


def test_session_scan_deduplicates_session_files_and_event_logs(tmp_path):
    sessions_dir = tmp_path / ".pico" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "s1.json").write_text("{}", encoding="utf-8")
    (sessions_dir / "s1.events.jsonl").write_text("", encoding="utf-8")

    assert list_sessions_since(0, sessions_dir=sessions_dir) == ["s1"]
