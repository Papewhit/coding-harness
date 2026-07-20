# TOOL-013-S — SDK Transport Decision Freeze

**Thread type:** `integrator`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-012-QO-R`
- `TOOL-012-QA-R`
- `TOOL-012-DA-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

独立汇总 SDK Spike，按 dialect 冻结 `typed_sdk | sdk_raw_response | raw_http`、SDK 版本、依赖策略和已知兼容限制。此 ticket 不选择最终 Evaluation 模型。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-sdk-spike/decision.json`
- `<ARTIFACT_ROOT>/native-sdk-spike/decision.md`
- `.codex/eval/proposals/TOOL-013-S.freeze.json`
- `.codex/eval/handoffs/TOOL-013-S.json`

## Forbidden write paths

- `产品源码`
- `probe raw rows`
- `本地配置`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- sdk_transport_decision
- decision rationale
- freeze hash

## Acceptance checklist

- [ ] 官方 SDK typed mode 可用时优先
- [ ] typed mode 丢失未知 block 时选择 raw-response
- [ ] 只有 SDK 无法表达必需 wire 字段时才允许 narrow raw HTTP
- [ ] 明确禁止 Tool/Agent Runner
- [ ] 每个 dialect 可有不同 transport decision

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 若某个 profile 未配置，保留 exclusion；只要同 dialect 仍有足够证据即可做技术决策。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
