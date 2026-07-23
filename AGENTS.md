# Repository Guidance

## Common Commands

```bash
uv sync                                      # Install project and development dependencies

uv run pico                                  # Start the interactive Textual TUI
uv run pico --repl                           # Start the plain terminal REPL
uv run pico "one-shot prompt"                # Run one non-interactive agent task

uv run ruff check .                          # Lint the repository
uv run pytest tests -q                       # Run the full pytest suite
uv run pytest tests/test_pico.py -k test_name -q  # Run matching tests from one file

uv run python scripts/run_v3_human_scenario_gate.py  # Run the prioritized human-scenario gate
uv run python scripts/run_v3_human_scenario_gate.py --suite full  # Run all human scenarios
```

The full human-scenario suite is a release-level gate rather than a routine
inner-loop check. Live provider smoke tests are opt-in and require both a
configured provider key and `PICO_LIVE_SMOKE=1`:

```bash
PICO_LIVE_SMOKE=1 uv run pytest tests/test_release_smoke.py -q  # Test a configured live provider
```

## Agent Constraints

- Treat the current source and tests as the source of truth.
- Preserve the architecture budgets and safety invariants enforced by
  `tests/test_architecture_boundaries.py`, `tests/test_safety_invariants.py`,
  and the tool-policy tests. Do not weaken those tests merely to make a change
  pass; split responsibilities or update the design deliberately instead.
- Put generated documentation under `docs/`, prefer an existing
  matching subdirectory, and use descriptive kebab-case filenames. Do not
  modify `.gitignore` merely to track generated documentation.

## Architecture and Design Materials

- **In-project**: `release/v3` AI-generated learning material, for quick overview and key pattern insights.
- **Online**: `pico` at 飞书云文档, mirrors v2 and remains valid learning material for core module design. Access through Lark CLI.

## Troubleshooting

On Windows in Codex sandboxed mode, consult `docs/annoying-uv-codex.md` if
`uv` cannot write to its cache.

## Pico v3 Evaluation and Native Tool Calling

- The current plan-level thread only summarizes user decisions and Wave results; use a fresh non-ticket Integrator thread for every Wave.
- Work from `.codex/eval/PLAN.json` and one ticket per ticket thread.
- The current Wave Integrator is the only writer of the canonical `.codex/eval/state/STATUS.json` and `FREEZE.json`; tickets emit `status_proposal` / `freeze_proposal` files instead.
- Formal Runtime and online Evaluation must not add or retain executable `<tool>/<final>` fallbacks.
- Provider SDKs stay at the Adapter/transport boundary. Do not use SDK Tool Runners, Agents Runners, or SDK-managed execution of Pico tools.
- Core, Session, and Checkpoint persist only Pico contracts and JSON-safe opaque continuation, never SDK objects.
- Match every native tool call/result one-to-one using the provider call ID and preserve the existing safety chain.
- Use Ubuntu WSL2/Python 3.12 fresh clones as the canonical testing and evaluation environment. Windows is a best-effort development compatibility lane during this evaluation plan; Windows failures or unavailable native capabilities do not block evaluation and are tracked separately.
- Do not run formal online effectiveness evaluation before recovered Gate N1 `TOOL-050-S-R1` and the user-authorized human smoke, or formal Resume evaluation before `TOOL-062-G`.
- Every write ticket uses its own worktree/branch from an immutable base SHA. Run shards do not change source and write only their exclusive artifact directory.
- Freeze fixture/oracle/metric inputs before product fixes; never change frozen questions to improve results.
- Continue downstream work only through Git SHA, STATUS/FREEZE hashes, handoffs, and artifacts, not through a preceding long conversation.
