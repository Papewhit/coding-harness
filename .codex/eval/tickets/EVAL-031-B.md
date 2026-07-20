# EVAL-031-B — Context Cases C09–C15 组合与预算压力

**Thread type:** `fixture_builder`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-030`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

建设 all-assets、memory/history/system pressure、tool schema budget 和 extreme current-request survival 场景；未完成 native assistant/tool-result 邻接必须保持。

## Allowed write paths

- `benchmarks/v3/context-assets/fixtures/C09/**`
- `benchmarks/v3/context-assets/fixtures/C10/**`
- `benchmarks/v3/context-assets/fixtures/C11/**`
- `benchmarks/v3/context-assets/fixtures/C12/**`
- `benchmarks/v3/context-assets/fixtures/C13/**`
- `benchmarks/v3/context-assets/fixtures/C14/**`
- `benchmarks/v3/context-assets/fixtures/C15/**`
- `benchmarks/v3/context-assets/fragments/C09-C15.json`
- `.codex/eval/handoffs/EVAL-031-B.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py`
- `benchmarks/v3/context-assets/cases.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- C09-C15 fixtures/expectations/fragment

## Acceptance checklist

- [ ] 预算值可复现
- [ ] 必须保留/允许降级/必须移出定义清楚
- [ ] 覆盖 pointer integrity 与 tools budget
- [ ] 未完成 native turn 不得被 compact
- [ ] 不写共享 cases.json

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
