# EVAL-061-R — Native Resume Paired Live Run Shard

**Thread type:** `run_shard`  
**Wave:** `W9`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `TOOL-062-G`
- `EVAL-061-P`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按 3 个 selected tasks 分 shard，每个 K1/K2 snapshot 分别运行 Resume 与 Cold Restart，保持剩余预算和 selected profile 完全一致。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-5-resume/<RUN_SHA>/<TASK_SHARD>/**`
- `.codex/eval/handoffs/<TASK_SHARD>.json`

## Forbidden write paths

- `所有源码、frozen predicates/taskset`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- paired continuation rows
- snapshot manifests
- process logs

## Acceptance checklist

- [ ] 每个 pair 共享相同 snapshot hash
- [ ] Resume 保留 private continuation，Cold 删除
- [ ] SDK/profile/native gate hash 一致
- [ ] completed/uncertain call 不被错误重放
- [ ] 所有 failures 保留

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
