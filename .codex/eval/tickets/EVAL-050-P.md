# EVAL-050-P — Local Task Native Pilot Run Shard

**Thread type:** `run_shard`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `EVAL-040-M`
- `EVAL-041`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按三个 repo 分 shard，各任务使用 selected native profile 跑 1 次 pilot；用于稳定预算/失败分类，不进入正式分母。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-pilot/<RUN_SHA>/<REPO_SHARD>/**`
- `.codex/eval/handoffs/<REPO_SHARD>.json`

## Forbidden write paths

- `所有源码、taskset、verifier`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- 3 pilot shard outputs

## Acceptance checklist

- [ ] 同一 run snapshot/profile/native gate/decoding/budget
- [ ] pilot 不进入正式分母
- [ ] 所有 failure 保留
- [ ] call/result 与 HTTP attempts 可审计
- [ ] 源码 clean

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
