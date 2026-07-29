# EVAL-060 — Native 事件驱动的外部进程中断 Runner

**Plan type:** `implementer` — 使用 `implementer` Thread
**Wave:** `W7`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `TOOL-060-R`
- Dependency Ticket: `EVAL-040-M`
- Dependency Ticket: `EVAL-041`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

基于 native exchange/checkpoint 事件实现父进程监控、落盘确认、进程组终止、同一 snapshot 的 Resume/Cold 克隆、配对预算与重复探索计数。

## Allowed write paths

- `pico/evaluation/interruption_eval.py`
- `scripts/run_interruption_evaluation.py`
- `scripts/_run_live_task_child.py`
- `tests/test_interruption_evaluator.py`
- `.codex/eval/handoffs/EVAL-060.json`

## Forbidden write paths

- `pico/core/runtime_checkpoints.py`
- `provider adapters`
- `frozen taskset`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- interruption evaluator/scripts/tests

## Acceptance checklist

- [ ] 不使用线程模拟 kill
- [ ] 按明确 session_id/profile/dialect resume
- [ ] kill 前证明 assistant batch/checkpoint 完整落盘
- [ ] cold 保留 workspace 但删除 session/checkpoint/private continuation
- [ ] 重复 read/search/test 规范化
- [ ] no-checkpoint/schema/workspace 与主要分母分离

## Commands

```bash
uv run pytest tests/test_interruption_evaluator.py tests/test_native_tool_resume.py -q
```

## Notes

- 无额外说明。

## Completion rule

运行本 Ticket 的 targeted tests 与 scoped lint。先把 `.codex/eval/**` 之外的 Git-tracked 变更形成一个语义 commit，再按 `templates/HANDOFF.md` 写 handoff；handoff 和其他控制文件不得进入该 commit。返回 `integrator` 验收。若 dispatch sequence 还有后续 Ticket，只有在 `integrator` 已复制并验证本 handoff、清理未提交控制文件，并给出下一 Ticket 的精确 base/dependency commits 后才继续；不得自行开始未 dispatch 的工作。
