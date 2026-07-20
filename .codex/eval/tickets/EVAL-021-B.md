# EVAL-021-B — Auto-dream 语义 Fixtures D05–D08

**Thread type:** `fixture_builder`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；必须等于本波 `wave_base_sha` 或 run ticket 的 `run_snapshot_sha`。

## Start conditions

- `EVAL-020`

读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

建设 multi-topic/index、相对日期、瞬时/代码可推导过滤、secret 过滤与幂等四个 fixture fragment。

## Allowed write paths

- `benchmarks/v3/auto-dream/fixtures/D05/**`
- `benchmarks/v3/auto-dream/fixtures/D06/**`
- `benchmarks/v3/auto-dream/fixtures/D07/**`
- `benchmarks/v3/auto-dream/fixtures/D08/**`
- `benchmarks/v3/auto-dream/fragments/D05-D08.json`
- `.codex/eval/handoffs/EVAL-021-B.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py`
- `pico/evaluation/dream_eval.py`
- `benchmarks/v3/auto-dream/cases.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- D05-D08 inputs/expectations
- fragment manifest
- self-check evidence

## Acceptance checklist

- [ ] 使用合成 secret-shaped 字符串
- [ ] 相对日期有明确基准时间
- [ ] 幂等输入固定
- [ ] 不写共享 cases.json

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 STATUS/FREEZE（Integrator ticket 除外）或开始下游工作。
