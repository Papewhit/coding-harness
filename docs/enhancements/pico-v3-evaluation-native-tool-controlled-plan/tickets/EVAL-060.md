# EVAL-060 — Native 事件驱动的外部进程中断 Runner

**Thread type:** `implementer`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-060-R`
- `EVAL-040-M`
- `EVAL-041`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

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

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

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

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
