# EVAL-050-P — Local Task Native Pilot Run Shard

**Plan type:** `run_shard` — 由当前 `integrator` 启动本地 Process，不创建模型 Thread
**Wave:** `W7`
**Run snapshot SHA:** 由 `integrator` 在 Process dispatch 中填写；必须等于冻结的 `run_snapshot_sha`，且 checkout clean。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Dependency Ticket: `TOOL-050-S-R1`
- Dependency Ticket: `EVAL-040-M`
- Dependency Ticket: `EVAL-041`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

按三个 repo 分 shard，各任务使用 selected native profile 跑 1 次 pilot；用于稳定预算/失败分类，不进入正式分母。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-pilot/<RUN_SHA>/<REPO_SHARD>/**`
- `.codex/eval/handoffs/EVAL-050-P.json`

## Forbidden write paths

- `所有源码、taskset、verifier`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- 3 pilot shard outputs

## Acceptance checklist

- [ ] 同一 run snapshot/profile/native gate/decoding/budget
- [ ] pilot 不进入正式分母
- [ ] 所有 failure 保留
- [ ] call/result 与 HTTP attempts 可审计
- [ ] 源码 clean

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

`integrator` 必须在 Process manifest 中填写精确命令和所有 hash bindings。Process 只返回 exit code、Row/HTTP attempt 数量、失败分类、Artifact/log 路径和 SHA-256；不得创建模型 Thread 来运行或解释命令。

## Notes

- 无额外说明。

## Completion rule

全部 Processes 完成后，由 `integrator` 生成一份 `.codex/eval/handoffs/EVAL-050-P.json`。有效任务/provider 失败作为 `evaluation_failure` 保留；证据绑定、runner 或 Artifact 无效才是 `measurement_defect`。Process 不提交 Git-tracked files，不更新 CURRENT/FREEZE，也不为每个 Process 创建单独 handoff。
