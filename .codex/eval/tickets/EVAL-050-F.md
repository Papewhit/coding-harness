# EVAL-050-F — Local Task Native Final Run Shard

**Thread type:** `run_shard`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S-R1`
- `EVAL-050-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按 repo 分 3 个 shard，9 tasks × 3 repetitions，共 27 rows；使用冻结 selected profile 和正式参数。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-final/<RUN_SHA>/<REPO_SHARD>/**`
- `.codex/eval/handoffs/<REPO_SHARD>.json`

## Forbidden write paths

- `所有源码、taskset、verifier`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- final rows/manifests/logs

## Acceptance checklist

- [ ] 所有核心 hash 一致
- [ ] SDK retry=0/Pico attempts 符合 freeze
- [ ] 失败 rows 不删除
- [ ] Verified Success 由 hidden verifier/路径边界判定
- [ ] protocol/infrastructure failure 单独分类

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
