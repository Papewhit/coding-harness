# TOOL-042-G-R2 — Deterministic Native Eval-ready Gate Recovery R2

**Thread type:** `integrator`

**Wave:** `W5R2`

**Base SHA:** 由 Integrator 填写；应用全部已验收 W5R2 dependency commits 后冻结 `run_snapshot_sha`。

## Goal

在 canonical Ubuntu WSL2 fresh clone 中重新运行完整 deterministic Gate。Gate ticket 不修改源码、tests、fixtures 或 bindings。

## Canonical environment

- Ubuntu WSL2，用户 `papewhit`
- repository：`~/dev/pico-w5r2-gate-<short-sha>`，不得在 `/mnt/f` checkout 运行
- Python 3.12、committed `uv.lock`、用户级 `uv`
- 禁止 `sudo`；需要系统级依赖时立即停止
- 禁止 live provider、正式效果评测与 Resume evaluation

## Deliverables

- environment manifest 与 dependency verification
- architecture 24-module audit matrix
- protected、deterministic、full-suite、fixture/profile、Context 与 static-audit logs/JUnit
- Gate report、artifact manifest、run snapshot
- freeze/status proposals 与 handoff

## Acceptance checklist

- [ ] source checkout 精确等于 `run_snapshot_sha`
- [ ] Ruff、protected suite、deterministic suite 与 full repository suite 全部 exit 0
- [ ] 只保留既有 live-provider opt-in skips
- [ ] architecture tripwire 一次审计全部 24 个 modules，无超限
- [ ] 无 locked-provider-profile fixture failure 或其 worker/TUI 间接症状
- [ ] retry-after-read、真正重复 mutation、safety chain 与 fixture negative control 保持通过
- [ ] Context v2 binding 可从 fresh-clone Git blob 重建
- [ ] text envelope、SDK Tool/Agent Runner、unknown-block loss 与 call-ID mismatch 均为零
- [ ] 未使用 monkey patch、skip/xfail、失败重分类或 sudo

## Commands

```bash
uv sync --locked --extra providers --python 3.12
uv run ruff check .
uv run pytest tests/test_architecture_boundaries.py tests/test_safety_invariants.py tests/test_tool_policy_acceptance.py tests/test_permissions_acceptance.py -q
uv run pytest tests/test_provider_contracts.py tests/test_openai_responses_tools.py tests/test_anthropic_messages_tools.py tests/test_native_tool_loop.py tests/test_native_session_exchange.py tests/test_native_request_context.py tests/test_native_runtime_integration.py tests/test_native_provider_evaluator.py tests/test_native_tool_repetition.py tests/test_context_freeze_integrity.py -q
uv run pytest tests -q
```

## Stop rule

完成 artifact、proposals 与 handoff 后停止；不得直接写正式 STATUS/FREEZE 或启动 W6。
