# EVAL-021-R — Auto-dream Native Live Run Shard

**Thread type:** `run_shard`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `EVAL-020`
- `EVAL-021-A`
- `EVAL-021-B`
- `EVAL-022`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按 D01-D04 与 D05-D08 分成两个 shard，各 case 重复 3 次；只使用 selected native profile，生命周期 deterministic rows 由聚合阶段读取。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-1-auto-dream/<RUN_SHA>/<SHARD_ID>/**`
- `.codex/eval/handoffs/<SHARD_ID>.json`

## Forbidden write paths

- `所有源码与 frozen fixtures`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- shard manifest/rows/logs

## Acceptance checklist

- [ ] source/evaluator/cases/provider/native gate hash 完整
- [ ] SDK retry=0 且 HTTP attempts 可见
- [ ] 失败 row 不删除
- [ ] 源码 clean
- [ ] 不接受 text envelope fallback

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
