# TEST-059-A-R1 — Anthropic Stateless Transcript Remediation Red Tests

**Thread type:** `implementer`
**Wave:** `W6R3`
**Remediation finding:** `AUDIT-059-A-P1-001`

## Start conditions

- `AUDIT-059-A`

## Goal

只提交测试，稳定复现 Anthropic Messages continuation 只保留最近一轮 assistant/tool result、导致更早 read/edit evidence 丢失的问题。记录未修复 remediation candidate 的精确 red baseline 后停止。

## Allowed write paths

- `tests/test_anthropic_stateless_transcript.py`
- `.codex/eval/handoffs/TEST-059-A-R1.json`

## Forbidden write paths

- `pico/**`
- frozen Oracle、cases、human-smoke fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 第二次 follow-up 包含原始 Runtime prompt、第一轮 call/result 与第二轮 call/result
- [ ] 三轮 `read_file → patch_file → read_file` 后的请求仍包含全部有序证据
- [ ] 每个 `tool_use_id` 恰好对应一个 result，原 provider call ID 保持不变
- [ ] 测试严格度与 `tests/test_native_stateless_transcript.py` 的 Responses 三轮断言对称
- [ ] 测试不依赖 live provider、provider cache 或 server-side storage
- [ ] 记录未修复 candidate 的精确 expected failures

## Stop rule

提交 red tests 与 per-ticket handoff 后停止；不得修改 Anthropic Adapter。
