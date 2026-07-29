"""持久记忆的文件存储、索引、合并策略与维护提示。"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict

from ..core.workspace import now


class DurableTopicDefaults(TypedDict):
    title: str
    summary: str
    tags: list[str]


class DurableTopic(TypedDict):
    topic: str
    title: str
    summary: str
    tags: list[str]


class DurableNote(TypedDict):
    text: str
    tags: list[str]
    source: str
    created_at: str
    kind: str


class AutoDreamGate(TypedDict):
    should_run: bool
    skip_reason: str
    session_count: int
    session_ids: list[str]

MAX_MEMORY_INDEX_CHARS = 10000


MAX_ENTRYPOINT_LINES = 200


ENTRYPOINT_NAME = "MEMORY.md"


LOCK_FILE_NAME = ".consolidate-lock"


HOLDER_STALE_S = 3600


DREAM_SESSION_CAP = 30


DREAM_MIN_NEW_TOKENS = 4096


DURABLE_MEMORY_INTENT_PATTERN = re.compile(r"(?i)\b(capture|remember|save|store|persist|note)\b")


DURABLE_MEMORY_INTENT_ZH_PATTERN = re.compile(r"(记住|保存|记录|沉淀|长期记忆|持久记忆)")


DURABLE_MEMORY_LIST_PREFIX_PATTERN = re.compile(r"^(?:[-*]|\d+[.)])\s+")


DURABLE_MEMORY_LINE_PATTERNS = (
    ("project-conventions", re.compile(r"(?i)^Project convention:\s*(.+)$")),
    ("key-decisions", re.compile(r"(?i)^Decision:\s*(.+)$")),
    ("dependency-facts", re.compile(r"(?i)^Dependency:\s*(.+)$")),
    ("user-preferences", re.compile(r"(?i)^Preference:\s*(.+)$")),
    ("project-conventions", re.compile(r"^项目约定：\s*(.+)$")),
    ("key-decisions", re.compile(r"^决策：\s*(.+)$")),
    ("dependency-facts", re.compile(r"^依赖：\s*(.+)$")),
    ("user-preferences", re.compile(r"^偏好：\s*(.+)$")),
)


SECRET_SHAPED_TEXT_PATTERN = re.compile(r"(?i)(\b(api[_ -]?key|token|secret|password)\b|sk-[A-Za-z0-9_-]{6,})")


DURABLE_TOPIC_DEFAULTS: dict[str, DurableTopicDefaults] = {
    "project-conventions": {
        "title": "Project Conventions",
        "summary": "Stable repository conventions.",
        "tags": ["convention"],
    },
    "key-decisions": {
        "title": "Key Decisions",
        "summary": "Long-lived decisions and rationale anchors.",
        "tags": ["decision"],
    },
    "dependency-facts": {
        "title": "Dependency Facts",
        "summary": "Stable dependency and environment facts.",
        "tags": ["dependency"],
    },
    "user-preferences": {
        "title": "User Preferences",
        "summary": "Stable user preferences.",
        "tags": ["preference"],
    },
}


def ensure_memory_dir(memory_dir: str | Path) -> Path:
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "logs").mkdir(parents=True, exist_ok=True)
    (memory_dir / "topics").mkdir(parents=True, exist_ok=True)
    index_path = memory_dir / ENTRYPOINT_NAME
    if not index_path.exists():
        index_path.write_text(
            "# Durable Memory Index\n\n"
            "_Empty. `/remember` writes a daily log entry; `/dream` consolidates "
            "logs into topic files and adds entries here._\n",
            encoding="utf-8",
        )
    return memory_dir


def daily_log_path(memory_dir: str | Path, today: date | None = None) -> Path:
    today = today or date.today()
    memory_dir = ensure_memory_dir(memory_dir)
    path = memory_dir / "logs" / str(today.year) / f"{today.month:02d}" / f"{today.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_to_daily_log(memory_dir: str | Path, entry: str, today: date | None = None) -> Path | None:
    entry = str(entry).strip()
    if not entry:
        return None
    path = daily_log_path(memory_dir, today=today)
    timestamp = datetime.now().strftime("%H:%M")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"- [{timestamp}] {entry}\n")
    return path


def load_memory_index_text(memory_dir: str | Path) -> str:
    path = Path(memory_dir) / ENTRYPOINT_NAME
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_MEMORY_INDEX_CHARS]
    except OSError:
        return ""
    # 占位模板里没有实际 topic 条目（行首 "- [name]"），视作空索引，
    # 让 /memory 显示"No durable memories yet"提示而不是占位文本。
    if not any(line.lstrip().startswith("- [") for line in text.splitlines()):
        return ""
    return text


def extract_memory_tags(text: str) -> list[str]:
    return [match.strip() for match in re.findall(r"<memory>(.*?)</memory>", str(text), re.DOTALL) if match.strip()]


def _lock_path(memory_dir: str | Path) -> Path:
    return Path(memory_dir) / LOCK_FILE_NAME


def read_last_consolidated_at(memory_dir: str | Path) -> float:
    try:
        return _lock_path(memory_dir).stat().st_mtime
    except OSError:
        return 0.0


def try_acquire_lock(memory_dir: str | Path) -> bool:
    ensure_memory_dir(memory_dir)
    lock_path = _lock_path(memory_dir)
    current_pid = os.getpid()
    try:
        stat = lock_path.stat()
        age = datetime.now().timestamp() - stat.st_mtime
        holder_pid = int(lock_path.read_text(encoding="utf-8").strip())
        if age < HOLDER_STALE_S:
            try:
                os.kill(holder_pid, 0)
                return False
            except OSError:
                pass
    except (OSError, ValueError):
        pass
    lock_path.write_text(str(current_pid), encoding="utf-8")
    return True


def release_lock(memory_dir: str | Path) -> None:
    lock_path = _lock_path(memory_dir)
    try:
        timestamp = datetime.now().timestamp()
        lock_path.write_text("released", encoding="utf-8")
        os.utime(lock_path, (timestamp, timestamp))
    except OSError:
        pass


def record_consolidation(memory_dir: str | Path) -> None:
    ensure_memory_dir(memory_dir)
    lock_path = _lock_path(memory_dir)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    timestamp = datetime.now().timestamp()
    os.utime(lock_path, (timestamp, timestamp))


def list_sessions_since(since_ts: float, sessions_dir: str | Path | None = None, current_session_id: str = "") -> list[str]:
    scan_dir = Path(sessions_dir) if sessions_dir is not None else None
    if scan_dir is None or not scan_dir.exists():
        return []
    result = set()
    for path in scan_dir.iterdir():
        if path.suffix not in {".json", ".jsonl"}:
            continue
        session_id = path.stem.removesuffix(".events")
        if current_session_id and current_session_id == session_id:
            continue
        if path.stat().st_mtime > since_ts:
            result.add(session_id)
    return sorted(result)


def should_auto_dream(memory_dir: str | Path, min_hours: float, min_sessions: int, current_session_id: str, sessions_dir: str | Path | None = None) -> bool:
    return evaluate_auto_dream_gate(memory_dir, min_hours, min_sessions, current_session_id, sessions_dir=sessions_dir)["should_run"]


def evaluate_auto_dream_gate(
    memory_dir: str | Path,
    min_hours: float,
    min_sessions: int,
    current_session_id: str,
    sessions_dir: str | Path | None = None,
) -> AutoDreamGate:
    last = read_last_consolidated_at(memory_dir)
    current = datetime.now().timestamp()
    hours_since = (current - last) / 3600 if last > 0 else float("inf")
    session_ids = list_sessions_since(last, sessions_dir=sessions_dir, current_session_id=current_session_id)
    result: AutoDreamGate = {
        "should_run": False,
        "skip_reason": "",
        "session_count": len(session_ids),
        "session_ids": session_ids,
    }
    if hours_since < float(min_hours):
        result["skip_reason"] = "interval_gate"
        return result
    if len(session_ids) < int(min_sessions):
        result["skip_reason"] = "session_gate"
        return result
    result["should_run"] = True
    return result


def build_memory_system_section(memory_dir: str | Path) -> str:
    index = load_memory_index_text(memory_dir)
    if index:
        index_section = f"## Current Memory Index ({ENTRYPOINT_NAME})\n{index}\n"
    else:
        index_section = "No durable memories consolidated yet.\n"
    section = f"""# Auto Memory

You have a persistent, file-based memory system at `{Path(memory_dir)}/`.
This directory already exists. Write to it directly with memory-safe file tools; do not create a second memory store.

## Critical memory contract
- `/remember <text>` appends a note to the daily log.
- `/memory` prints the durable memory index.
- `/dream` consolidates daily logs into memory files and updates `{ENTRYPOINT_NAME}`.
- Structured memory files must use frontmatter: `name`, `description`, and `type`.
- Allowed `type` values are `user`, `feedback`, `project`, and `reference`.
- MEMORY.md is an index, not a memory. Keep it under {MAX_ENTRYPOINT_LINES} lines.
- If the user asks you to forget something, find and remove the relevant entry.

{index_section}
Build this memory system over time so future sessions can understand who the user is, how they prefer to collaborate, what behavior to avoid or repeat, and the context behind long-running work.

If the user explicitly asks you to remember something, save it immediately using whichever type fits best. If they ask you to forget something, find and remove the relevant entry instead of adding a contradiction.

## Types of memory

There are four discrete types of memory:

### user
Information about the user's role, goals, responsibilities, knowledge, and collaboration preferences.
**When to save:** When you learn stable details about the user's role, goals, responsibilities, preferences, or knowledge.

### feedback
Guidance or correction the user has given you that should change future behavior.
**When to save:** Any time the user corrects your approach in a way applicable to future conversations.
**Body structure:** Lead with the rule, then a **Why:** line and a **How to apply:** line.

### project
Information about ongoing work, goals, initiatives, bugs, incidents, or decisions not directly derivable from code or git history.
**When to save:** When you learn who is doing what, why, or by when. Always convert relative dates to absolute dates.
**Body structure:** Lead with the fact or decision, then **Why:** and **How to apply:** lines.

### reference
Pointers to where information lives in external systems and why it matters.
**When to save:** When you learn about a resource, external system, document, issue tracker, dataset, or link that future sessions should know how to find.

## What NOT to save
- Code patterns, architecture, file paths, or APIs that are derivable from reading the project
- Git history or recent changes; git is authoritative
- Debugging solutions where the fix is already in code or commit history
- Secrets, credentials, tokens, private keys, or secret-shaped values
- Raw command output, stack traces, or long logs
- Ephemeral task details, current blockers, next steps, or transient conversation context

## How to save memories

**Option A — <memory> tags (quick notes):**
Wrap text in `<memory>...</memory>` tags in your final answer. These are automatically extracted and appended to the daily log.

**Option B - Write files directly (structured memories):**
Write a `.md` file under `{Path(memory_dir)}/` with this frontmatter:

```markdown
---
name: {{{{memory name}}}}
description: {{{{one-line description — used to decide relevance later}}}}
type: {{{{user | feedback | project | reference}}}}
---

{{{{memory content}}}}
```

Then add a pointer to that file in `{Path(memory_dir)}/{ENTRYPOINT_NAME}`. MEMORY.md is an index, not a memory; it should contain only links with brief descriptions. Keep it under {MAX_ENTRYPOINT_LINES} lines.

## When to access memories
- When specific known memories seem relevant to the task at hand
- When the user seems to be referring to work from a prior conversation
- You MUST access memory when the user explicitly asks you to recall or remember

## Slash commands
- `/remember <text>` appends a note to the daily log.
- `/memory` prints the durable memory index.
- `/dream` consolidates daily logs into memory files and updates `{ENTRYPOINT_NAME}`.
"""
    return section


def build_dream_prompt(memory_dir: str | Path, transcript_dir: str = "", session_ids: list[str] | None = None) -> str:
    session_ids = list(session_ids or [])
    total = len(session_ids)
    truncated = False
    if total > DREAM_SESSION_CAP:
        session_ids = session_ids[-DREAM_SESSION_CAP:]
        truncated = True
    extra_parts = [
        "Tool constraints for this run: shell execution is not required. Writes must stay inside the memory directory. Read/search/list tools may be used to inspect existing memories and transcripts."
    ]
    if session_ids:
        header = (
            f"Sessions since last consolidation (showing the most recent {len(session_ids)} of {total}; "
            "consolidate these and the next dream will pick up the rest):"
            if truncated
            else "Sessions since last consolidation:"
        )
        extra_parts.append(header + "\n" + "\n".join(f"- {session_id}" for session_id in session_ids))
    extra_section = "\n\n## Additional context\n\n" + "\n\n".join(extra_parts)
    transcript_line = ""
    if transcript_dir:
        transcript_line = (
            f"\nSession transcripts: `{transcript_dir}` (large JSONL files — search narrowly, do not read whole files).\n"
        )

    return f"""# Dream: Memory Consolidation

You are performing a dream: a reflective pass over Coda's memory files. Synthesize recent signal into durable, well-organized memory files so future sessions can orient quickly.

Memory directory: `{Path(memory_dir)}`
This directory already exists. Write to it directly; do not create a second memory store.
{transcript_line}
Daily logs live under `logs/YYYY/MM/YYYY-MM-DD.md`.
The memory index is `{ENTRYPOINT_NAME}`.

## Phase 1 - Orient

- List files in `{Path(memory_dir)}/` to see what already exists.
- Read `{ENTRYPOINT_NAME}` if it exists to understand the current index.
- Skim existing topic files so you improve them instead of creating duplicates.
- If `logs/` or session transcript files exist, review recent entries first.

## Phase 2 - Gather recent signal

Look for new information worth persisting. Sources in rough priority order:

1. Daily logs (`logs/YYYY/MM/YYYY-MM-DD.md`) - these are the append-only memory intake stream.
2. Existing memories that drifted - facts that contradict what you now know.
3. Transcript search - if you need specific context, use narrow grep-style terms:
   `grep -rn "<narrow term>" {transcript_dir}/ --include="*.jsonl" | tail -50`

Do not exhaustively read transcripts. Look only for things you already suspect matter.

## Phase 3 - Consolidate

For each thing worth remembering, write or update a memory file using the memory file format and type conventions from the Auto Memory section. Use the memory file format and type conventions as the source of truth for what to save, how to structure it, and what NOT to save.

Focus on:
- Merging new signal into existing topic files rather than creating near-duplicates.
- Converting relative dates ("yesterday", "last week") to absolute dates so they remain interpretable after time passes.
- Deleting contradicted facts; if current evidence disproves an old memory, fix it at the source.
- Keeping secrets, raw command output, stack traces, and transient task state out of memory files.

## Phase 4 - Prune and index

Update `{ENTRYPOINT_NAME}` so it stays under {MAX_ENTRYPOINT_LINES} lines and under ~25KB. It is an index, not a dump; each entry should be one line under ~150 characters, like `- [Title](file.md) — one-line hook`. Never write memory content directly into it.

- Remove pointers to memories that are now stale, wrong, or superseded.
- Demote verbose index entries into topic files.
- Add pointers to newly important memories.
- Resolve contradictions by fixing the wrong memory file, not by adding a second contradictory entry.

Return a brief summary of what you consolidated, updated, or pruned. If nothing changed, say so.{extra_section}"""


def reject_durable_reason(note_text: str, redacted_value: str = "<redacted>") -> str:
    text = str(note_text or "").strip()
    lowered = text.lower()
    if not text:
        return "empty"
    if redacted_value in text or SECRET_SHAPED_TEXT_PATTERN.search(text):
        return "secret_shaped"
    checkpoint_like_prefixes = (
        "current goal",
        "current blocker",
        "next step",
        "current phase",
        "key files",
        "freshness",
        "当前目标",
        "当前卡点",
        "下一步",
        "当前阶段",
        "关键文件",
        "已完成",
        "已排除",
    )
    if any(lowered.startswith(prefix) for prefix in checkpoint_like_prefixes):
        return "transient_task_state"
    if re.search(r"(?i)\b(stdout|stderr|traceback|exit_code)\b", text) or len(text) > 220:
        return "noisy_output"
    return ""


def extract_durable_promotions(user_message: str, final_answer: str, redacted_value: str = "<redacted>") -> tuple[list[tuple[str, str]], list[str]]:
    user_text = str(user_message or "")
    if not (DURABLE_MEMORY_INTENT_PATTERN.search(user_text) or DURABLE_MEMORY_INTENT_ZH_PATTERN.search(user_text)):
        return [], []
    promotions = []
    rejections = []
    for line in str(final_answer or "").splitlines():
        text = DURABLE_MEMORY_LIST_PREFIX_PATTERN.sub("", line.strip(), count=1)
        if not text or redacted_value in text:
            continue
        for topic, pattern in DURABLE_MEMORY_LINE_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            note_text = match.group(1).strip()
            if note_text:
                reason = reject_durable_reason(note_text, redacted_value=redacted_value)
                if reason:
                    rejections.append(f"{topic}:{reason}")
                    break
                promotions.append((topic, note_text))
            break
    return promotions, rejections


class DurableMemoryStore:
    def __init__(self, root: str | Path):
        self.root: Path = Path(root)
        self.index_path: Path = self.root / "MEMORY.md"
        self.topics_dir: Path = self.root / "topics"

    def topic_slugs(self) -> list[str]:
        return [topic["topic"] for topic in self.load_index()]

    def load_index(self) -> list[DurableTopic]:
        if not self.index_path.exists():
            return []
        lines = self.index_path.read_text(encoding="utf-8").splitlines()
        topics: list[DurableTopic] = []
        current: DurableTopic | None = None
        for raw in lines:
            line = raw.strip()
            match = re.match(r"- \[([^\]]+)\]\([^)]+\):\s*(.+)", line)
            if match:
                current = {
                    "topic": match.group(1).strip(),
                    "title": match.group(2).strip(),
                    "summary": "",
                    "tags": [],
                }
                topics.append(current)
                continue
            if current is None:
                continue
            summary_match = re.match(r"- summary:\s*(.+)", line)
            if summary_match:
                current["summary"] = summary_match.group(1).strip()
                continue
            tags_match = re.match(r"- tags:\s*(.+)", line)
            if tags_match:
                current["tags"] = [tag.strip() for tag in tags_match.group(1).split(",") if tag.strip()]
        return topics

    def load_topic_notes(self, topic: str) -> list[DurableNote]:
        path = self.topics_dir / f"{topic}.md"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        notes: list[DurableNote] = []
        capture = False
        updated_at = ""
        tags = []
        for raw in lines:
            line = raw.strip()
            if line.startswith("- tags:"):
                tags = [tag.strip() for tag in line.split(":", 1)[1].split(",") if tag.strip()]
            elif line.startswith("- updated_at:"):
                updated_at = line.split(":", 1)[1].strip()
            elif line == "## Notes":
                capture = True
            elif capture and line.startswith("- "):
                notes.append(
                    {
                        "text": line[2:].strip(),
                        "tags": tags,
                        "source": topic,
                        "created_at": updated_at or now(),
                        "kind": "durable",
                    }
                )
        return notes

    @staticmethod
    def _subject_key(text: str) -> str | None:
        text = str(text).strip()
        patterns = (
            r"^(.+?)\s+is\s+.+$",
            r"^(.+?)\s+are\s+.+$",
            r"^(.+?)\s+uses?\s+.+$",
            r"^(.+?)\s+should\s+.+$",
            r"^(.+?)是.+$",
            r"^(.+?)使用.+$",
        )
        for pattern in patterns:
            match = re.match(pattern, text, re.I)
            if match:
                subject = " ".join(_tokenize(match.group(1)))
                return subject or None
        return None

    def retrieval_candidates(self, query: str, limit: int = 3) -> list[DurableNote]:
        query_tokens = _tokenize(query)
        ranked: list[tuple[tuple[int, int, float], DurableNote]] = []
        for topic in self.load_index():
            notes = self.load_topic_notes(topic["topic"])
            for note in notes:
                note_tags = {tag.lower() for tag in note.get("tags", [])}
                note_tokens = _tokenize(note.get("text", "")) | _tokenize(topic.get("title", "")) | note_tags
                exact_tag_match = int(bool(query_tokens & note_tags))
                keyword_overlap = len(query_tokens & note_tokens)
                if exact_tag_match == 0 and keyword_overlap == 0:
                    continue
                recency = _parse_timestamp(note.get("created_at"))
                ranked.append(((exact_tag_match, keyword_overlap, recency), note))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [note for _, note in ranked[:limit]]

    def _write_index(self, topics: list[DurableTopic]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        lines = ["# Durable Memory Index", ""]
        for topic in topics:
            lines.append(f"- [{topic['topic']}](topics/{topic['topic']}.md): {topic['title']}")
            lines.append(f"  - summary: {topic['summary']}")
            lines.append(f"  - tags: {', '.join(topic['tags'])}")
        self.index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_topic(self, topic: str, notes: list[str]) -> None:
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        meta = DURABLE_TOPIC_DEFAULTS[topic]
        lines = [
            f"# {meta['title']}",
            "",
            f"- topic: {topic}",
            f"- summary: {meta['summary']}",
            f"- tags: {', '.join(meta['tags'])}",
            f"- updated_at: {now()}",
            "",
            "## Notes",
        ]
        for note in notes:
            lines.append(f"- {note}")
        (self.topics_dir / f"{topic}.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def promote(self, promotions: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
        if not promotions:
            return [], []
        topics: dict[str, DurableTopic] = {topic["topic"]: topic for topic in self.load_index()}
        topic_notes: dict[str, list[str]] = {
            slug: [note["text"] for note in self.load_topic_notes(slug)] for slug in topics
        }
        results: list[str] = []
        superseded: list[str] = []
        for topic, note_text in promotions:
            meta = DURABLE_TOPIC_DEFAULTS[topic]
            topics.setdefault(
                topic,
                {
                    "topic": topic,
                    "title": meta["title"],
                    "summary": meta["summary"],
                    "tags": list(meta["tags"]),
                },
            )
            existing = topic_notes.setdefault(topic, [])
            if note_text in existing:
                continue
            new_subject = self._subject_key(note_text)
            replaced = False
            if new_subject:
                for index, old_text in enumerate(list(existing)):
                    if self._subject_key(old_text) == new_subject:
                        superseded.append(f"{topic}: {old_text} -> {note_text}")
                        existing[index] = note_text
                        replaced = True
                        break
            if not replaced:
                existing.append(note_text)
            results.append(f"{topic}: {note_text}")
        self._write_index([topics[slug] for slug in sorted(topics)])
        for topic, notes in topic_notes.items():
            self._write_topic(topic, notes)
        return results, superseded


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", str(text))}


def _parse_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return 0.0
