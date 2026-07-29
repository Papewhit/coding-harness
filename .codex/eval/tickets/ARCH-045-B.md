# ARCH-045-B — Worker Manager Architecture Budget Decision

**Thread type:** `implementer`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；必须等于 W5R `wave_base_sha`。

## Start conditions

- 用户明确授权把 `pico/core/worker_manager.py` 的预算从 220 调整为 250

## Goal

记录并实施 architecture budget 决策。当前 232 行来自既有类型标注、docstring 与注释完善；模块职责仍内聚，拆分没有收益。本 ticket 不重构产品源码。

## Allowed write paths

- `tests/test_architecture_boundaries.py`
- `docs/architecture/core-module-budgets.md`
- `.codex/eval/handoffs/ARCH-045-B.json`

## Forbidden write paths

- `pico/core/worker_manager.py`
- 其他模块预算
- 其他架构断言或测试行为

## Deliverables

- `worker_manager.py` budget 250
- architecture budget rationale
- handoff

## Acceptance checklist

- [ ] 只调整 `worker_manager.py` 的预算值 220 → 250
- [ ] canonical `worker_manager.py` blob 未变化
- [ ] 文档记录用户决策、当前 232 行和保留的约束余量
- [ ] architecture suite 不再因该模块失败

## Commands

```bash
uv run pytest tests/test_architecture_boundaries.py -q
```

```bash
git diff --check
```

## Stop rule

完成 commit 与 handoff 后停止；不得顺手修改源码、其他预算或正式状态。
