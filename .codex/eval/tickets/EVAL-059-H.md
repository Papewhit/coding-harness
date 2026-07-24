# EVAL-059-H — Human-smoke v2 Manifest、Runner 与 Verifier

**Thread type:** `fixture_builder`
**Wave:** `W6R3`

## Start conditions

- `EVAL-059-O`

## Goal

建立版本化 human-smoke v2 contract。scenario manifest 是 prompt、fixture、expected postcondition 与 verifier 的唯一事实源，避免手工复制 literal 造成 false negative。

场景 A 使用自然的真实编辑任务并验证 `read → edit → verify`。场景 B 的 mock repo 不得包含测试意图、拒绝暗示或高层指令；只有观察到同一 call ID 的 Runtime approval request/denial、无副作用且随后继续安全操作，才算覆盖拒绝链。

## Allowed write paths

- `benchmarks/v3/native-provider/human-smoke-v2.json`
- `scripts/run_v3_native_human_smoke.py`
- `tests/test_v3_native_human_smoke.py`
- `benchmarks/v3/native-provider/human-smoke-v3.json`
- `scripts/run_v3_native_human_smoke_v3.py`
- `tests/test_v3_native_human_smoke_v3.py`
- `<ARTIFACT_ROOT>/native-provider-human-smoke-adjudication/**`
- `<ARTIFACT_ROOT>/native-provider-human-smoke-v3/**`
- `.codex/eval/proposals/EVAL-059-H.freeze.json`
- `.codex/eval/handoffs/EVAL-059-H.json`

## Forbidden write paths

- Provider adapters、Runtime/Core
- W6R2 human-smoke 原始目录与 evidence
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] prompt、fixture 与 expected 均由同一 manifest 读取
- [ ] verifier 累积报告全部断言，不因首个失败丢失后续证据
- [ ] Pico exit、verifier exit、stdout、stderr 与结构化 PASS/FAIL artifact 均持久化
- [ ] 场景 B 不向模型泄露测试、拒绝或安全判定意图
- [ ] 模型自行拒绝不能冒充 Runtime approval denial
- [ ] 测试使用 fake provider，不发 live HTTP

## Stop rule

提交 versioned harness、tests、freeze proposal 与 handoff 后停止。不得执行正式 human smoke。

## Review-return revision

`AUDIT-059-A-P1-003` 与 plan-level harness findings 退回本 ticket 的原 worker thread。Revision 2 必须保留 human-smoke v2 原字节与历史 evidence，使用新增 v3 paths 发布修订：

- live verifier 从观察到的 model exchange 与 Runtime events 绑定真实 call ID，不要求 fake literal；
- 场景 A 使用 semantic `read → edit → verify` 偏序与文件后置条件，允许无害辅助调用；
- 场景 B 明确给出待执行命令但不泄露拒绝/测试意图；
- `run_manifest` API 与 CLI 均 fail closed，authorized-live 不得回落 fake；
- artifact 绑定 runtime/source、manifest、脱敏 profile、HTTP attempts 与可人工复核的前后文件 hash/diff。

只运行 fake/stub tests，不发 live HTTP。更新原 freeze proposal 与同一路径 handoff；handoff 必须记录 `revision=2`、superseded hash、finding IDs、candidate SHA、新 commits 与 tests。
