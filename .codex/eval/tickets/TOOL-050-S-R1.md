# TOOL-050-S-R1 — Recovered Native Provider Profile Selection（Gate N1）

**Thread type:** `integrator`
**Wave:** `W6R2`
**Base SHA:** 由 Integrator 填写；只聚合三个 R2 shard。

## Start conditions

- `TOOL-050-QO-R2`
- `TOOL-050-QA-R2`
- `TOOL-050-DA-R2`

## Goal

只使用 W6R2 repaired harness 的新 artifacts 执行 Gate N1，选择唯一正式 Evaluation profile；保留 W6/W6R blocked 状态与证据，不覆盖或复用其 rows。

## Allowed write paths

- `benchmarks/v3/native-provider/selection-w6r2.json`
- `<ARTIFACT_ROOT>/native-provider-conformance/<RUN_SHA>/selection/**`
- `.codex/eval/proposals/TOOL-050-S-R1.freeze.json`
- `.codex/eval/proposals/TOOL-050-S-R1.status.json`
- `.codex/eval/handoffs/TOOL-050-S-R1.json`

## Forbidden write paths

- W6 `selection.json`、W6/W6R artifacts
- 产品源码、raw rows、conformance cases、public profile manifests
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 验证三个 shard 的 run snapshot、cases、evaluator、runner、CLI、profile、SDK-decision 与 artifact hashes
- [ ] preflight failure 与 0-observation profile 的协议指标保持 `not_computable`
- [ ] tool-required native call observed=100%
- [ ] call ID/result match=100%，batch completeness=100%
- [ ] duplicate-after-result、unknown-block-loss、safety-chain-bypass、text-envelope 均为 0
- [ ] SDK hidden retry 为 0，所有 scheduled rows 完整
- [ ] 只在完整 hard Gate 通过后比较 completion、protocol/retry errors 与 repetition stability
- [ ] selection 冻结完整 public identity、profile manifest hash 与 conformance bundle hash
- [ ] 若至少一个 profile eligible，提出 `native_eval_ready=accepted`，并给出 human smoke 的 profile 与 canonical commit
- [ ] 若无 eligible profile，只提出 blocked 状态，不以 prior SDK probe 或 W6 rows 替代

## Stop rule

完成 selection、summary、proposals 与 handoff 后停止。不得启动 W7；等待用户完成并明确确认 human smoke。
