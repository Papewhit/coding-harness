# EVAL-070-R — Native Context Ablation Live Run Shard

**Plan type:** `run_shard` — 由当前 `integrator` 启动本地 Process，不创建模型 Thread
**Wave:** `W9`
**Run snapshot SHA:** 由 `integrator` 在 Process dispatch 中填写；必须等于冻结的 `run_snapshot_sha`，且 checkout clean。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Required Gate: `native_resume_ready=accepted`
- Dependency Ticket: `TOOL-050-S-R1`
- Dependency Ticket: `EVAL-070-S`
- 可选分支：只有 `EVAL-070-S` 的分支决定选择 Context Ablation 后，本 Ticket 才启动。
- 适用条件：若 `native_resume_ready=rejected`，不得启动本 Ticket；reason=`required_gate_rejected`。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

按 asset group 划分 2–4 shards，每个 Full/off arm 至少 3 次，使用同一 selected native profile 和 run snapshot。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-6-context-ablation/<RUN_SHA>/<GROUP_SHARD>/**`
- `.codex/eval/handoffs/EVAL-070-R.json`

## Forbidden write paths

- `所有源码、frozen taskset/selection`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- group shard outputs

## Acceptance checklist

- [ ] Full/off core hashes 一致
- [ ] 逐 case 结果保留
- [ ] 无稳定提升时不调题
- [ ] 输入 token 只在 provider usage 可比时报告
- [ ] protocol errors 单独报告

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

`integrator` 必须在 Process manifest 中填写精确命令和所有 hash bindings。Process 只返回 exit code、Row/HTTP attempt 数量、失败分类、Artifact/log 路径和 SHA-256；不得创建模型 Thread 来运行或解释命令。

## Notes

- 无额外说明。

## Completion rule

全部 Processes 完成后，由 `integrator` 生成一份 `.codex/eval/handoffs/EVAL-070-R.json`。有效任务/provider 失败作为 `evaluation_failure` 保留；证据绑定、runner 或 Artifact 无效才是 `measurement_defect`。Process 不提交 Git-tracked files，不更新 CURRENT/FREEZE，也不为每个 Process 创建单独 handoff。
