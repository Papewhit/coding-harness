# EVAL-070-M — Context Ablation 聚合

**Thread type:** `integrator`  
**Wave:** `W9`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-070-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

逐 case 展示 Full/off 的 success、steps、重复工作、provider/tool retries 和 protocol errors，不用单一均值掩盖方向相反结果。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-6-context-ablation/summary.json`
- `<ARTIFACT_ROOT>/phase-6-context-ablation/summary.md`
- `.codex/eval/handoffs/EVAL-070-M.json`

## Forbidden write paths

- `源码、raw rows、selection`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- summary/evidence index

## Acceptance checklist

- [ ] 无稳定提升时明确写未观察到任务收益
- [ ] 不把 prompt chars 当 token/cost
- [ ] 不把 native protocol 失败归因于 Context 功能

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
