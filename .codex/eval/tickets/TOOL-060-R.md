# TOOL-060-R — Native Tool-call Resume 状态机与 Checkpoint Schema

**Plan type:** `implementer` — 使用 `implementer` Thread
**Wave:** `W7`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `TOOL-042-G-R2`
- Dependency Ticket: `TOOL-031-S`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

扩展 session/checkpoint，表达 native batch 的 pending/executing/completed/rejected/uncertain_after_crash，锁定 provider/model/dialect/schema，并定义 crash replay policy。保留 W0 记录的既有 runtime_checkpoints 修改。

## Allowed write paths

- `pico/core/runtime_checkpoints.py`
- `pico/core/task_state.py`
- `pico/core/session_lifecycle.py`
- `pico/core/model_exchange.py`
- `pico/core/tool_call_batch.py`
- `tests/test_native_tool_resume.py`
- `.codex/eval/handoffs/TOOL-060-R.json`

## Forbidden write paths

- `frozen evaluator/fixtures`
- `provider adapters`
- `tests/test_architecture_boundaries.py`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- checkpoint schema bump
- resume policy
- migration/rejection tests

## Acceptance checklist

- [ ] 旧 session 不伪造 call ID
- [ ] provider/model/dialect mismatch 安全拒绝
- [ ] completed result 不重复执行
- [ ] pending read-only 可继续
- [ ] executing 副作用 call 标记 uncertain 且不自动重放
- [ ] compact 不破坏未完成 native turn
- [ ] 原 dirty diff 语义被保留并在 handoff 说明

## Commands

```bash
uv run pytest tests/test_native_tool_resume.py tests/test_pico.py -k "resume or checkpoint" -q
```

## Notes

- 无额外说明。

## Completion rule

运行本 Ticket 的 targeted tests 与 scoped lint。先把 `.codex/eval/**` 之外的 Git-tracked 变更形成一个语义 commit，再按 `templates/HANDOFF.md` 写 handoff；handoff 和其他控制文件不得进入该 commit。返回 `integrator` 验收。若 dispatch sequence 还有后续 Ticket，只有在 `integrator` 已复制并验证本 handoff、清理未提交控制文件，并给出下一 Ticket 的精确 base/dependency commits 后才继续；不得自行开始未 dispatch 的工作。
