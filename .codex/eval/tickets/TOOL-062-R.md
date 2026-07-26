# TOOL-062-R — Selected Profile Native Restart Conformance

**Plan type:** `run_shard` — 由当前 `integrator` 启动本地 Process，不创建模型 Thread
**Wave:** `W8`
**Run snapshot SHA:** 由 `integrator` 在 Process dispatch 中填写；必须等于冻结的 `run_snapshot_sha`，且 checkout clean。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Dependency Ticket: `TOOL-050-S-R1`
- Dependency Ticket: `TOOL-061-T`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

使用 selected profile 运行两个最小跨进程 native continuation 场景：assistant tool batch 已落盘未执行；tool result 已落盘未发下一请求。额外验证 risky executing crash 只走安全拒绝/uncertain，不调用模型伪造结果。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-resume-conformance/<RUN_SHA>/selected-profile/**`
- `.codex/eval/handoffs/TOOL-062-R.json`

## Forbidden write paths

- `所有源码、frozen contract、本地配置写入`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- restart rows
- continuation hash evidence
- process logs

## Acceptance checklist

- [ ] 使用 `native_eval_ready` 选定的 profile 和固定 SDK/profile hash
- [ ] 跨进程后 call/result ID 连续
- [ ] reasoning/thinking continuation 无丢失
- [ ] 无副作用自动重放
- [ ] SDK retry=0

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

```bash
uv run python scripts/run_native_resume_contract.py --live-selected-profile --output <ARTIFACT_ROOT>/native-resume-conformance/<RUN_SHA>/selected-profile
```

`integrator` 在启动前把精确命令及全部 SHA/Freeze bindings 写入 Process manifest。Process 只返回 exit code、Row/HTTP attempt 数量、失败分类、Artifact/log 路径和 SHA-256。

## Notes

- 无额外说明。

## Completion rule

全部 Processes 完成后，由 `integrator` 生成一份 `.codex/eval/handoffs/TOOL-062-R.json`。有效任务/provider 失败作为 `evaluation_failure` 保留；证据绑定、runner 或 Artifact 无效才是 `measurement_defect`。Process 不提交 Git-tracked files，不更新 CURRENT/FREEZE，也不为每个 Process 创建单独 handoff。
