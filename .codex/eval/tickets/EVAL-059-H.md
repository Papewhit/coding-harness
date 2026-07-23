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
- `<ARTIFACT_ROOT>/native-provider-human-smoke-adjudication/**`
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
