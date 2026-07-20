# EVAL-050-R — Local Task Pilot Review 与正式参数冻结

**Thread type:** `reviewer`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-050-P`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

审查 task/verifier/runner/profile 的有效性，冻结正式 run 的预算、Pico attempts、temperature 和 failure taxonomy；不得按 pilot 结果删题。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-pilot/review.md`
- `.codex/eval/proposals/EVAL-050-R.freeze.json`
- `.codex/eval/handoffs/EVAL-050-R.json`

## Forbidden write paths

- `产品源码、taskset、raw rows`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- pilot review
- formal run config freeze

## Acceptance checklist

- [ ] 无 hidden verifier 泄漏
- [ ] 无文本 fallback 或 protocol mismatch
- [ ] 基础设施失败与任务失败区分
- [ ] 不基于表现修改 task prompt/oracle
- [ ] 正式 shard 参数完全冻结

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
