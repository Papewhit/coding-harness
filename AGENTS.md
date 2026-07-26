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

- From W6R4 onward, use `.codex/eval/CONTROL.md`, `CURRENT.md`, and the current Wave file as the execution entry point. Treat `PLAN.json` as a machine registry and load only the exact current entries when needed. `state/STATUS.json` is historical through W6R3 and is not the live status source.
- A Ticket is a commit, acceptance, and handoff unit, not a Thread lifetime. One `implementer` Thread may complete multiple explicitly ordered Tickets.
- Each Wave uses a fresh, user-visible top-level `integrator` Thread. The persistent `program_supervisor` is a separate top-level Thread. They communicate through Codex cross-thread messages and must not form an Agent parent-child relationship. See `.codex/eval/CONTROL.md` for the decision boundary.
- The current `integrator` is the only writer of `.codex/eval/CURRENT.md` and `FREEZE.json`. Do not create commits for dispatch, acceptance, waiting, or routine state updates.
- Review findings must be classified as `implementation_defect`, `measurement_defect`, `evaluation_failure`, or `change_request`. A valid evaluation failure is a result, not an automatic product-repair request.
- Formal Runtime and online Evaluation must not add or retain executable `<tool>/<final>` fallbacks.
- Provider SDKs stay at the Adapter/transport boundary. Do not use SDK Tool Runners, Agents Runners, or SDK-managed execution of Pico tools.
- Core, Session, and Checkpoint persist only Pico contracts and JSON-safe opaque continuation, never SDK objects.
- Match every native tool call/result one-to-one using the provider call ID and preserve the existing safety chain.
- Use Ubuntu WSL2/Python 3.12 fresh clones as the canonical testing and evaluation environment. Windows is best-effort compatibility only.
- Do not run formal online effectiveness evaluation before `native_eval_ready=accepted`, or formal Resume evaluation before `native_resume_ready=accepted`.
- Each concurrent `implementer` sequence uses its own worktree/branch from an immutable Candidate. Run Processes do not change source and write only their exclusive Artifact directories.
- Freeze fixture/oracle/metric inputs before product fixes; never change frozen questions to improve results.
- Continue work through exact Git SHAs, CURRENT, Freeze hashes, handoffs, and Artifacts, not through a preceding long conversation.
