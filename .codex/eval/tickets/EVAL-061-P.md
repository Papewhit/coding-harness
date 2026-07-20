# EVAL-061-P — Resume Pilot 与 Native 中断谓词冻结

**Thread type:** `reviewer`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-050-R`
- `EVAL-060`
- `TOOL-062-G`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

从 9 tasks 选择 3 个轨迹稳定且 native-resume-eligible 的任务，运行 uninterrupted pilot，冻结 K1/K2 事件谓词。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-5-resume-pilot/**`
- `.codex/eval/proposals/EVAL-061-P.freeze.json`
- `.codex/eval/handoffs/EVAL-061-P.json`

## Forbidden write paths

- `taskset、runner source、产品 Runtime`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- selected task IDs
- pilot traces
- resume predicate freeze

## Acceptance checklist

- [ ] 覆盖 bugfix/patch-validation/small feature 或 CLI
- [ ] K1 在首次 mutation 前且 native batch/checkpoint 落盘
- [ ] K2 在首次有效 mutation/result 后且 checkpoint 落盘
- [ ] 不使用时间点 kill
- [ ] predicate 引用 Gate N2 hash

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
