# TOOL-050-S — Native Provider Profile Selection（Gate N1）

**Thread type:** `integrator`  
**Wave:** `W6`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-QO-R`
- `TOOL-050-QA-R`
- `TOOL-050-DA-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

聚合 configured profiles，先应用协议硬 Gate，再按 micro-task completion、protocol/retry errors 和稳定性选择唯一 Evaluation profile。冻结完整 profile identity，而不是只冻结模型名。

## Allowed write paths

- `benchmarks/v3/native-provider/selection.json`
- `<ARTIFACT_ROOT>/native-provider-conformance/summary.json`
- `<ARTIFACT_ROOT>/native-provider-conformance/summary.md`
- `.codex/eval/proposals/TOOL-050-S.freeze.json`
- `.codex/eval/proposals/TOOL-050-S.status.json`
- `.codex/eval/handoffs/TOOL-050-S.json`

## Forbidden write paths

- `产品源码`
- `raw rows`
- `conformance cases`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- selection.json
- summary
- native_eval_ready gate state

## Acceptance checklist

- [ ] tool-required cases 的 native call observed=100%
- [ ] call_id_result_match=100%
- [ ] batch result completeness=100%
- [ ] duplicate_call_after_result=0
- [ ] unknown_block_loss=0
- [ ] safety_chain_bypass=0
- [ ] text_envelope_seen=0
- [ ] 至少一个 profile eligible；否则只阻塞正式在线 lane

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- selection 必须包含 model、profile、base URL fingerprint、wire dialect、adapter mode、SDK package/version、capabilities、retry/stream/parallel settings 和 conformance hash。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
