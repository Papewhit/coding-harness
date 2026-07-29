# EVAL-059-O — Native Provider Oracle v2 与历史证据审定

**Thread type:** `fixture_builder`
**Wave:** `W6R3`

## Start conditions

- `TOOL-050-S-R1`
- W6R2 wave handoff 与原始 conformance/human-smoke evidence 可读

## Goal

版本化 Oracle v2，不覆盖 W6R2 输入或结果。冻结责任归属、证据分母、case predicate 与 selection metric：

- 安全链是 Runtime snapshot 级不变量；
- Runtime 前拒绝不进入执行安全链分母；
- `execute=completed` 遵循 Runtime“工具实现已返回”的语义，结果成功与否读取结构化 metadata；
- profile metrics 只评价 provider/adapter 可控制的 wire、call/result、batch、continuation 与 retry；
- 不再依赖模型随机产生 invalid args 或 multi-call 来证明 Runtime 行为，此类覆盖迁入 deterministic fixtures。

使用 Oracle v2 对 W6R2 A/O rows 与两次 human smoke 生成只读、版本化 adjudication。历史 artifact 只能被引用和哈希绑定，不能原地修改或用于直接晋级 profile。

## Allowed write paths

- `benchmarks/v3/native-provider/cases-v2.json`
- `pico/evaluation/native_provider.py`
- `pico/evaluation/native_provider_live.py`
- `tests/test_native_provider_evaluator.py`
- `tests/test_native_provider_live.py`
- `<ARTIFACT_ROOT>/native-provider-oracle-v2/**`
- `.codex/eval/proposals/EVAL-059-O.freeze.json`
- `.codex/eval/proposals/EVAL-059-O.status.json`
- `.codex/eval/handoffs/EVAL-059-O.json`

## Forbidden write paths

- W6/W6R/W6R2 cases、rows、selection、handoff 与 artifacts
- Provider adapters、Runtime/Core
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] Oracle v2 schema、case predicates、metric ownership 与 hash basis 明确
- [ ] `pre_runtime_rejection` 不进入安全链执行分母
- [ ] nonzero shell exit 的 `execute=completed + tool_status=error` 被正确接受
- [ ] 真正 Runtime chain violation 阻断 snapshot，而非归因 profile
- [ ] stochastic invalid-args/multi-call 不再作为 live profile hard eligibility 的隐含前提
- [ ] W6R2 原始 evidence hashes 保持不变
- [ ] 历史 adjudication 明确区分事实重释与正式重新晋级

## Stop rule

提交 Oracle、tests、proposals 与 handoff 后停止。不得修改产品 Adapter，不得发 provider HTTP。
