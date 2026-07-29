# EVAL-031-A — Context Cases C01–C08 单资产正常预算

**Thread type:** `fixture_builder`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-030`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

为八类资产各建设唯一 sentinel 的正常预算 fixture，expectation 明确目标落在 system_text、messages、tools 或 artifact pointer metadata。

## Allowed write paths

- `benchmarks/v3/context-assets/fixtures/C01/**`
- `benchmarks/v3/context-assets/fixtures/C02/**`
- `benchmarks/v3/context-assets/fixtures/C03/**`
- `benchmarks/v3/context-assets/fixtures/C04/**`
- `benchmarks/v3/context-assets/fixtures/C05/**`
- `benchmarks/v3/context-assets/fixtures/C06/**`
- `benchmarks/v3/context-assets/fixtures/C07/**`
- `benchmarks/v3/context-assets/fixtures/C08/**`
- `benchmarks/v3/context-assets/fragments/C01-C08.json`
- `.codex/eval/handoffs/EVAL-031-A.json`

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

- C01-C08 fixtures/expectations/fragment

## Acceptance checklist

- [ ] 每 case 只激活一个目标 asset
- [ ] sentinel 不与系统常见文本碰撞
- [ ] 明确 expected structure/metadata
- [ ] 工具 schema 不使用文本 prompt 断言
- [ ] 不写共享 cases.json

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
