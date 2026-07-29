# EVAL-070-S — Context Ablation Case Selection

**Thread type:** `reviewer`  
**Wave:** `W9`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-050-M`
- `EVAL-061-M`
- `EVAL-070-I`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

选择 4–6 个确实依赖 resume/working-control/durable/skills assets 的 case，并记录结构化依赖理由。

## Allowed write paths

- `benchmarks/v3/context-ablation/selection.json`
- `.codex/eval/proposals/EVAL-070-S.freeze.json`
- `.codex/eval/handoffs/EVAL-070-S.json`

## Forbidden write paths

- `frozen taskset、Runtime、结果 rows`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- selection.json
- freeze hash

## Acceptance checklist

- [ ] 每 case 有依赖理由
- [ ] 不加入无关任务扩大样本
- [ ] Worker notification 不用于收益对比
- [ ] 最多 6 cases
- [ ] selection 绑定 Context contract 与 native profile hash

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
