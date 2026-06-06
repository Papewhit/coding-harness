# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # Install dev dependencies (pytest, ruff)
uv run ruff check .              # Lint
uv run pytest                    # Run all tests
uv run pytest tests/test_pico.py -k test_name   # Run a single test
uv run pico                      # Start interactive TUI
uv run pico "one-shot prompt"    # Run a single task
uv run pico --repl               # Start REPL (non-TUI) mode
uv run python scripts/readable_session.py --all -o docs/sessions/  # Convert session JSONs to readable Markdown
```

Runtime dependencies: `textual>=0.86.0`, `tomli>=2.0.0` (Python < 3.11). Dev dependencies: `pytest`, `ruff`.

## Architecture

**pico** is a local terminal coding agent. It reads/writes files in a workspace, calls a model provider, and persists session state under `.pico/`.

### Startup flow

`cli.py:main()` → `build_arg_parser()` parses args → `_build_model_client()` selects provider backend → builds `WorkspaceContext` and `SessionStore` → either one-shot `agent.ask(prompt)` or interactive REPL/TUI loop.

### Core runtime

`Pico` (in `core/runtime.py`) is the central runtime object — it owns session state, workspace context, memory, checkpoints, tool profiles, worker manager, and persistence handles. Nearly everything hangs off it.

`Engine` (in `core/engine.py`) owns the turn control loop. `Engine.ask()` calls `run_turn()` which yields events — each turn: builds prompt via `ContextManager`, calls model via `complete_model()`, parses the response as `<tool>`, `<final>`, or error. If tool: validates, checks approval policy, executes, records result, creates checkpoint, loops. If final: records answer, promotes durable memory, writes report, returns.

### Model backends (`providers/`)

Two clients, both exposing a `complete(prompt, max_new_tokens, **kwargs)` method:
- **`OpenAICompatibleModelClient`** — POSTs to `/v1/responses`, supports `prompt_cache_key` for `openai.com` / `right.codes` hosts, handles both JSON and SSE responses
- **`AnthropicCompatibleModelClient`** — POSTs to `/v1/messages`, no cache support

`providers/base.py` provides `complete_model()` which wraps either `complete_result()` (returns `ModelResult` directly) or `complete()` (returns raw text), normalizing the interface.

### Configuration (`config/`)

Provider profiles merge with priority: **CLI args > env vars > project `.pico.toml` > global `~/.config/pico/config.toml` > code defaults**. A profile has: `protocol` (openai/anthropic), `api_key`, `base_url`, `model`. The `protocol` field determines the HTTP request format; the profile name is just a label.

### Tools (`tools/`)

13 tools registered explicitly in `build_tool_registry()`: `list_files`, `read_file`, `search`, `run_shell`, `write_file`, `patch_file`, `todo_add`, `todo_update`, `todo_list`, `agent`, `send_message`, `task_stop`, `enter_plan_mode`, `exit_plan_mode`, `ask_user`. Tool execution flows through `Pico.run_tool()` which enforces: existence check → argument validation → repeated-call detection → approval gate (if risky) → execution → workspace diff → memory update.

Tools accept both JSON (`<tool>{"name":"...","args":{}}</tool>`) and XML-style (`<tool name="..."><content>...</content></tool>`) formats. `patch_file` requires `old_text` to match exactly once — the semantics are intentionally strict.

### Prompt assembly (`core/context_manager.py`)

`ContextManager.build()` assembles prompt sections in order: prefix, memory, skills, relevant_memory, history, current_request. When total exceeds budget (default 60K chars), sections are reduced in priority order: `relevant_memory → skills → history → memory → prefix`. The current user request is never trimmed.

### Memory (`features/memory.py`)

`LayeredMemory` wraps a small working memory (task summary, recent files, file summaries, episodic notes) plus a `DurableMemoryStore` that persists to `.pico/memory/` as markdown topic files. Episodic notes auto-populate from `read_file` results and process events. Durable memory triggers on explicit user intent (keywords: capture, remember, save, persist in English or Chinese).

### Workers / subagents (`core/worker_manager.py`, `core/worker_runtime.py`)

The `agent` tool spawns child `Pico` instances via `WorkerManager`. Subagent types: `Explore` (read-only, any mode), `worker` (read/write, blocked in plan mode). Workers run in threads; notification results are drained into the parent's history. Max depth is constrained to prevent recursion.

### Plan mode (`core/plan_mode.py`)

Entered via `enter_plan_mode` tool or `/plan` slash command. Applies a restricted tool profile (read + plan tools only), writes the plan to a file under `.pico/`, user approves via `exit_plan_mode` to switch back to full tool access.

### Persistence

- **`SessionStore`** — saves/loads `session.json` under `.pico/sessions/` (full agent state for resume)
- **`RunStore`** — writes per-run artifacts under `.pico/runs/<run_id>/`: `task_state.json`, `trace.jsonl`, `report.json`
- **Checkpoints** — written on each tool execution and at run completion. On resume, validated for schema version, file freshness, and runtime identity match.

### TUI (`tui/`)

Built with Textual. `tui/main.py` entry point. Connects to the same `Pico` runtime — the TUI is a view layer, not a separate agent.

### Evaluation (`evaluation/`)

`BenchmarkEvaluator` runs fixed-regression tasks from `benchmarks/coding_tasks.json` using `ScriptedModelClient` with predetermined outputs. Each task specifies a fixture repo (under `tests/fixtures/`), allowed tools, step budget, and a shell verifier command.

## Key patterns

- **Path safety**: All file tools resolve through `Pico.path()` which rejects paths escaping the workspace root (handles `../` and symlink traversal).
- **Secrets handling**: Sensitive env vars (matching `API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`) are detected and redacted from trace/report output. `run_shell` uses a filtered allowlist env, not full parent env.
- **Feature flags**: `memory`, `relevant_memory`, `context_reduction`, `prompt_cache` are toggled via `DEFAULT_FEATURE_FLAGS` dict in `runtime.py` and influence prompt building and memory behavior.
- **No dynamic tool discovery**: Tools are explicitly registered; the model sees a bounded, auditable action set.
- **Atomic file writes**: `SessionStore.save()` writes to a temp file then `os.replace()` for atomicity. `write_file` creates parent directories automatically.
