# EVAL-070-I — Structured Context Grouped Ablation Hook 与 Runner

**Plan type:** `implementer` — 使用 `implementer` Thread
**Wave:** `W8`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `EVAL-031-G`
- Dependency Ticket: `EVAL-040-M`
- Dependency Ticket: `EVAL-041`
- Dependency Ticket: `TOOL-050-S-R1`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

复用 live task runner 实现 Full structured request vs 单个 grouped asset set off；feature hook 作用于 system/messages/tools 资产，不重新启用文本 prompt。

## Allowed write paths

- `pico/evaluation/context_ablation.py`
- `scripts/run_context_task_ablation.py`
- `tests/test_context_ablation_evaluator.py`
- `.codex/eval/handoffs/EVAL-070-I.json`

## Forbidden write paths

- `pico/core/context_manager.py`
- `pico/core/runtime.py`
- `provider adapters`
- `frozen taskset`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- ablation evaluator/script/tests

## Acceptance checklist

- [ ] Full/off 只有目标 asset group 差异
- [ ] 不破坏 native turn adjacency/continuation
- [ ] 复用 selected native profile
- [ ] 不做八字段全排列
- [ ] 支持 paired shard

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Completion rule

运行本 Ticket 的 targeted tests 与 scoped lint。先把 `.codex/eval/**` 之外的 Git-tracked 变更形成一个语义 commit，再按 `templates/HANDOFF.md` 写 handoff；handoff 和其他控制文件不得进入该 commit。返回 `integrator` 验收。若 dispatch sequence 还有后续 Ticket，只有在 `integrator` 已复制并验证本 handoff、清理未提交控制文件，并给出下一 Ticket 的精确 base/dependency commits 后才继续；不得自行开始未 dispatch 的工作。
