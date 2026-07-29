# EVAL-021-R — Auto-dream Native Live Run Shard

**Plan type:** `run_shard` — 由当前 `integrator` 启动本地 Process，不创建模型 Thread
**Wave:** `W7`
**Run snapshot SHA:** 由 `integrator` 在 Process dispatch 中填写；必须等于冻结的 `run_snapshot_sha`，且 checkout clean。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Dependency Ticket: `TOOL-050-S-R1`
- Dependency Ticket: `EVAL-020`
- Dependency Ticket: `EVAL-021-A`
- Dependency Ticket: `EVAL-021-B`
- Dependency Ticket: `EVAL-022`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

按 D01-D04 与 D05-D08 分成两个 shard，各 case 重复 3 次；只使用 selected native profile，生命周期 deterministic rows 由聚合阶段读取。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-1-auto-dream/<RUN_SHA>/<SHARD_ID>/**`
- `.codex/eval/handoffs/EVAL-021-R.json`

## Forbidden write paths

- `所有源码与 frozen fixtures`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- shard manifest/rows/logs

## Acceptance checklist

- [ ] source/evaluator/cases/provider/native gate hash 完整
- [ ] SDK retry=0 且 HTTP attempts 可见
- [ ] 失败 row 不删除
- [ ] 源码 clean
- [ ] 不接受 text envelope fallback

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

`integrator` 必须在 Process manifest 中填写精确命令和所有 hash bindings。Process 只返回 exit code、Row/HTTP attempt 数量、失败分类、Artifact/log 路径和 SHA-256；不得创建模型 Thread 来运行或解释命令。

## Notes

- 无额外说明。

## Completion rule

全部 Processes 完成后，由 `integrator` 生成一份 `.codex/eval/handoffs/EVAL-021-R.json`。有效任务/provider 失败作为 `evaluation_failure` 保留；证据绑定、runner 或 Artifact 无效才是 `measurement_defect`。Process 不提交 Git-tracked files，不更新 CURRENT/FREEZE，也不为每个 Process 创建单独 handoff。
