# TOOL-042-G-R1 — Deterministic Native Eval-ready Gate Recovery R1

**Thread type:** `integrator`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；应用全部已验收 W5R dependency commits 后冻结 `run_snapshot_sha`。

## Start conditions

- `TOOL-043-R`
- `TOOL-044-F`
- `ARCH-045-B`
- `CHORE-045-L`
- `EVAL-032-F`
- `TOOL-049-I`
- W5 blocked `TOOL-042-G` handoff 与 artifacts

## Goal

在 Ubuntu WSL2 的 fresh ext4 clone 中重新运行 W5 deterministic Gate。所有 required commands 必须真实 exit 0，并冻结新的 live-conformance `run_snapshot_sha`。

## Canonical environment

- WSL distribution：Ubuntu
- user：`papewhit`
- repository：`~/dev/pico-w5r-gate-<short-sha>`
- Python：3.12
- dependency source：committed `uv.lock`
- package manager：用户级 `uv`
- 禁止 `sudo`；如需要系统级安装，立即停止并请求用户处理
- 不得直接在 `/mnt/f` checkout 上运行 canonical Gate

## Allowed write paths

- `<ARTIFACT_ROOT>/native-deterministic-gate-w5r/**`
- `.codex/eval/proposals/TOOL-042-G-R1.freeze.json`
- `.codex/eval/proposals/TOOL-042-G-R1.status.json`
- `.codex/eval/handoffs/TOOL-042-G-R1.json`

## Forbidden write paths

- 产品源码、tests、fixtures、bindings
- skip、xfail、失败重分类或 monkey patch
- `sudo`、系统级包安装
- live provider 或正式效果评测

## Deliverables

- environment manifest
- protected/full deterministic/Context/Ruff command logs 与 JUnit
- fixture negative-control evidence verification
- fresh-clone Context binding reconstruction
- Gate report、run snapshot、freeze/status proposal 与 handoff

## Acceptance checklist

- [ ] source checkout 精确等于冻结的 `run_snapshot_sha`
- [ ] repository Ruff、protected suite 与 deterministic suites 全部 exit 0
- [ ] retry-after-read protected test 通过，真正重复 mutation 仍被拒绝
- [ ] protected tests 无全局 patch，fixture negative control 已验证
- [ ] Runtime/online evaluator text envelope seen=0
- [ ] call ID/result、batch completeness、unknown block loss 与 safety-chain checks 全通过
- [ ] Context v2 binding 可从 fresh clone Git blob 重建且 artifact 输入一致
- [ ] SDK Tool/Agent Runner 不存在
- [ ] 未使用 skip、xfail、known-failure 重分类或 sudo

## Commands

```bash
uv sync --locked --extra providers --python 3.12
```

```bash
uv run ruff check .
```

```bash
uv run pytest tests/test_architecture_boundaries.py tests/test_safety_invariants.py tests/test_tool_policy_acceptance.py tests/test_permissions_acceptance.py -q
```

```bash
uv run pytest tests/test_provider_contracts.py tests/test_openai_responses_tools.py tests/test_anthropic_messages_tools.py tests/test_native_tool_loop.py tests/test_native_session_exchange.py tests/test_native_request_context.py tests/test_native_runtime_integration.py tests/test_native_provider_evaluator.py tests/test_native_tool_repetition.py tests/test_context_freeze_integrity.py -q
```

```bash
uv run pytest tests -q
```

## Stop rule

完成 artifact、proposal 与 handoff 后停止；不得直接写正式 STATUS/FREEZE 或启动 W6。
