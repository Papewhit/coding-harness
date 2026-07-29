# ARCH-046-T — Core Module Growth Tripwire Recalibration

**Thread type:** `implementer`

**Wave:** `W5R2`

**Base SHA:** 由 Integrator 填写；必须等于 W5R2 `wave_base_sha`。

## Goal

把 Core 行数检查明确为异常增长 tripwire，一次性审计全部 tracked files，并让失败输出同时列出所有超限项。不得修改产品源码。

## Required thresholds

基于 W5R canonical 实际行数，将以下门限更新为：

- `runtime.py`: 1000（用户指定）
- `task_state.py`: 160
- `todo_ledger.py`: 130
- `worker_manager.py`: 280
- `context_manager.py`: 510
- `compact.py`: 190
- `engine.py`: 500
- `model_errors.py`: 140
- `tool_policy.py`: 100
- `tool_executor.py`: 220
- `features/skills.py`: 240
- `tools/todos.py`: 90

其余 tracked thresholds 不降低。保留全部 24 个 tracked modules。

## Deliverables

- 更新后的 architecture test 与 rationale 文档
- 包含 24 个模块 `actual / old / new / margin` 的审计 artifact
- 一次聚合报告全部超限项的断言逻辑
- handoff

## Acceptance checklist

- [ ] `runtime.py` 门限精确为 1000
- [ ] 上述其余门限精确更新，未降低其他门限
- [ ] 单次运行可同时报告所有超限项，不再 first-failure masking
- [ ] canonical 产品源码 blob 均未改变
- [ ] 文档说明该检查是 coarse growth tripwire，不是严格规模预算
- [ ] architecture suite exit 0

## Commands

```bash
uv run pytest tests/test_architecture_boundaries.py -q
uv run ruff check tests/test_architecture_boundaries.py
git diff --check
```

## Stop rule

完成 commit、artifact 与 handoff 后停止；不得顺手重构源码或修改正式 STATUS/FREEZE。
