# EVAL-059-H-R1 — Human-smoke v3 Contract 与 Harness 修复

**Thread type:** `fixture_builder`
**Wave:** `W6R3`
**Remediation findings:** `AUDIT-059-A-P1-003` 及 plan-level harness audit

## Start conditions

- `AUDIT-059-A`

## Goal

发布 human-smoke v3 manifest、runner、verifier 与 fake-provider tests。保留 v2 原字节，不覆盖历史 evidence。V3 必须以语义后置条件和 Runtime evidence 判定 live run，不把 fake call ID 或唯一工具轨迹强加给真实模型。

## Allowed write paths

- `benchmarks/v3/native-provider/human-smoke-v3.json`
- `scripts/run_v3_native_human_smoke_v3.py`
- `tests/test_v3_native_human_smoke_v3.py`
- `<ARTIFACT_ROOT>/native-provider-human-smoke-v3/**`
- `.codex/eval/proposals/EVAL-059-H-R1.freeze.json`
- `.codex/eval/handoffs/EVAL-059-H-R1.json`

## Forbidden write paths

- human-smoke v2 manifest、runner、tests 与历史 artifacts
- Provider adapters、Runtime/Core、Oracle v2
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] fake mode 保持 deterministic；live mode 从观察到的 model exchange 与 Runtime safety events 绑定真实 call ID
- [ ] 场景 A 验证 `read → edit → verify` 语义偏序和文件后置条件，允许无害辅助调用
- [ ] 场景 B 明确给出待执行命令但不泄露拒绝/测试意图；模型自行拒绝不能冒充 Runtime denial
- [ ] denied command、无副作用与后续安全操作绑定到观察到的同一组真实 call IDs
- [ ] `run_manifest` API 与 CLI 均 fail closed：authorized-live 不得回落 fake，fake mode 不得注入 live provider
- [ ] artifact 记录 runtime/source SHA、manifest SHA、脱敏 profile identity/hash、Pico/verifier exit、HTTP attempts、结构化 checks 及可人工复核的前后文件 hash/diff
- [ ] 临时 workspace 删除前持久化上述 evidence；公开 artifact 不含凭据
- [ ] tests 只使用 fake/stub provider，不发 live HTTP

## Stop rule

提交 versioned v3 harness、fake evidence、freeze proposal与 per-ticket handoff 后停止；不得执行正式 human smoke。
