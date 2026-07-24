# TEST-059-O-R1 — Responses Call/Result Closure Remediation Red Tests

**Thread type:** `implementer`
**Wave:** `W6R3`
**Remediation finding:** `AUDIT-059-A-P1-002`

## Start conditions

- `AUDIT-059-A`

## Goal

只提交测试，冻结 OpenAI Responses transcript 对当前未闭合 function-call batch 的一一对应要求。

## Allowed write paths

- `tests/test_openai_responses_call_result_closure.py`
- `.codex/eval/handoffs/TEST-059-O-R1.json`

## Forbidden write paths

- `pico/**`
- frozen Oracle、cases、human-smoke fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 两个 unresolved calls 只有一个 result 时在 transport 前拒绝
- [ ] extra、unknown 或 duplicate result ID 在 transport 前拒绝
- [ ] 重排的合法 results 按原 call order 规范化，而不是机械误拒绝
- [ ] 历史已闭合 calls 不被误算为当前 batch
- [ ] legacy v1 continuation 继续 fail closed
- [ ] 记录未修复 candidate 的精确 expected failures

## Stop rule

提交 red tests 与 per-ticket handoff 后停止；不得修改 Responses Adapter。
