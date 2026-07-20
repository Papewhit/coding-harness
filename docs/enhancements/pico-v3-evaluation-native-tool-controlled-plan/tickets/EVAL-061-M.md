# EVAL-061-M — Native Resume Paired 聚合

**Thread type:** `integrator`  
**Wave:** `W9`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-061-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

聚合 Resume vs Cold 的最终完成、额外工具步骤、重复 read/search/test、冲突写入和 protocol errors；no-checkpoint 等 contract cases 不进入可恢复分母。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-5-resume/summary.json`
- `<ARTIFACT_ROOT>/phase-5-resume/summary.md`
- `.codex/eval/proposals/EVAL-061-M.freeze.json`
- `.codex/eval/handoffs/EVAL-061-M.json`

## Forbidden write paths

- `产品源码、raw rows、frozen predicates`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- paired summary
- evidence index
- resume freeze

## Acceptance checklist

- [ ] pair 数与 exclusions 明确
- [ ] 最终成功和重复工作同时报告
- [ ] protocol/restart failure 独立分类
- [ ] 不复用旧 90% recovery 口径

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
