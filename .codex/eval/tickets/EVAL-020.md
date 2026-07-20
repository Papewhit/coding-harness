# EVAL-020 — Auto-dream Fixture Schema、Atomic Oracle 与 Runner Core

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；必须等于本波 `wave_base_sha` 或 run ticket 的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现 atomic fact、must_keep/replace/drop、topic/index/frontmatter、semantic snapshot 和 shard merge API；不修 Dream 产品逻辑。

## Allowed write paths

- `pico/evaluation/dream_eval.py`
- `scripts/run_dream_evaluation.py`
- `tests/test_dream_evaluator.py`
- `benchmarks/v3/auto-dream/schema.json`
- `.codex/eval/handoffs/EVAL-020.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py`
- `pico/features/memory.py`
- `tests/test_memory.py`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- dream evaluator core
- fixture schema
- oracle tests
- runner with case filtering

## Acceptance checklist

- [ ] 不使用另一个在线模型作为唯一评分器
- [ ] secret/scope/dangling-link 硬 gate
- [ ] 幂等比较忽略允许变化时间字段
- [ ] 支持 case shard 独立运行

## Commands

```bash
uv run pytest tests/test_dream_evaluator.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 STATUS/FREEZE（Integrator ticket 除外）或开始下游工作。
