# EVAL-070-R — Native Context Ablation Live Run Shard

**Thread type:** `run_shard`  
**Wave:** `W9`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `EVAL-070-S`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按 asset group 划分 2–4 shards，每个 Full/off arm 至少 3 次，使用同一 selected native profile 和 run snapshot。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-6-context-ablation/<RUN_SHA>/<GROUP_SHARD>/**`
- `.codex/eval/handoffs/<GROUP_SHARD>.json`

## Forbidden write paths

- `所有源码、frozen taskset/selection`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- group shard outputs

## Acceptance checklist

- [ ] Full/off core hashes 一致
- [ ] 逐 case 结果保留
- [ ] 无稳定提升时不调题
- [ ] 输入 token 只在 provider usage 可比时报告
- [ ] protocol errors 单独报告

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
