# EVAL-050-M — Local Task Final 聚合与 Baseline Freeze

**Thread type:** `integrator`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-050-F`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

汇总 27 rows，同时报告 run-level success 与每题至少 2/3 成功的 stable task success；保留 native protocol 和 infrastructure 失败分类。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-final/summary.json`
- `<ARTIFACT_ROOT>/phase-4-local-tasks-final/summary.md`
- `.codex/eval/proposals/EVAL-050-M.freeze.json`
- `.codex/eval/handoffs/EVAL-050-M.json`

## Forbidden write paths

- `产品源码、raw rows、taskset`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- summary/evidence index/baseline freeze

## Acceptance checklist

- [ ] 27 rows 全部可追踪
- [ ] run/stable task 两种口径并列
- [ ] 协议失败不伪装成任务失败
- [ ] 不外推大型仓库/复杂重构能力

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
