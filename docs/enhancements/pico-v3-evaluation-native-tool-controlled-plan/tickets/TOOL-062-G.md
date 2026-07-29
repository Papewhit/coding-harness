# TOOL-062-G — Native Resume-ready Gate（Gate N2）

**Thread type:** `integrator`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-061-T`
- `TOOL-062-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

合并 deterministic crash contract 与 selected-profile restart evidence，冻结 native Resume contract/gate；只在所有安全硬约束满足时允许正式 Resume Evaluation。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-resume-conformance/summary.json`
- `<ARTIFACT_ROOT>/native-resume-conformance/summary.md`
- `.codex/eval/proposals/TOOL-062-G.freeze.json`
- `.codex/eval/proposals/TOOL-062-G.status.json`
- `.codex/eval/handoffs/TOOL-062-G.json`

## Forbidden write paths

- `产品源码`
- `raw rows`
- `frozen contract`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- native_resume_gate
- summary
- STATUS gate transition

## Acceptance checklist

- [ ] pending/completed/uncertain 状态恢复正确
- [ ] provider continuation roundtrip=100%
- [ ] completed call replay=0
- [ ] uncertain risky call replay=0
- [ ] profile/dialect mismatch 安全拒绝
- [ ] 至少两个 live restart cases 通过

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 不把 no-checkpoint 计入可恢复成功率分母。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
