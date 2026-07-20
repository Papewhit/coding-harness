# TOOL-060-R — Native Tool-call Resume 状态机与 Checkpoint Schema

**Thread type:** `implementer`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-042-G`
- `TOOL-031-S`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

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

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

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

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
