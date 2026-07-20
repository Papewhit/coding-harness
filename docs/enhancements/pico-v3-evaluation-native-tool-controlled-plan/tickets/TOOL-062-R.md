# TOOL-062-R — Selected Profile Native Restart Conformance

**Thread type:** `run_shard`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `TOOL-061-T`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

使用 selected profile 运行两个最小跨进程 native continuation 场景：assistant tool batch 已落盘未执行；tool result 已落盘未发下一请求。额外验证 risky executing crash 只走安全拒绝/uncertain，不调用模型伪造结果。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-resume-conformance/<RUN_SHA>/selected-profile/**`
- `.codex/eval/handoffs/TOOL-062-R.json`

## Forbidden write paths

- `所有源码`
- `frozen contract`
- `本地配置写入`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- restart rows
- continuation hash evidence
- process logs

## Acceptance checklist

- [ ] 使用 Gate N1 profile 和固定 SDK/profile hash
- [ ] 跨进程后 call/result ID 连续
- [ ] reasoning/thinking continuation 无丢失
- [ ] 无副作用自动重放
- [ ] SDK retry=0

## Commands

```bash
uv run python scripts/run_native_resume_contract.py --live-selected-profile --output <ARTIFACT_ROOT>/native-resume-conformance/<RUN_SHA>/selected-profile
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
