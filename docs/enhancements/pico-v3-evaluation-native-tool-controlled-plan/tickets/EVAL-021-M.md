# EVAL-021-M — Auto-dream 结果聚合与 Freeze

**Thread type:** `integrator`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-021-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

合并两个 native live shard 与生命周期证据，输出事实保留/更新/过滤/幂等指标、协议失败明细和产品缺陷。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-1-auto-dream/summary.json`
- `<ARTIFACT_ROOT>/phase-1-auto-dream/summary.md`
- `.codex/eval/proposals/EVAL-021-M.freeze.json`
- `.codex/eval/handoffs/EVAL-021-M.json`

## Forbidden write paths

- `Dream 产品源码`
- `frozen fixtures/oracle`
- `raw rows`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- summary/evidence index/freeze entry

## Acceptance checklist

- [ ] 24 个语义 run 均有 row 或明确 exclusion
- [ ] 4 个生命周期 case 均入 artifact
- [ ] native protocol failures 与 Dream semantic failures 分开
- [ ] 不外推 Coding Task 成功率

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
