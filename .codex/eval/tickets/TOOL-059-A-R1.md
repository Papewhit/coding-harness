# TOOL-059-A-R1 — Anthropic 完整无状态 Transcript 修复

**Thread type:** `implementer`
**Wave:** `W6R3`
**Remediation finding:** `AUDIT-059-A-P1-001`

## Start conditions

- `TEST-059-A-R1`

## Goal

修复 Anthropic Messages Adapter，使无 server-side state 的每次请求按 Anthropic message ordering 保存并重放原始 Runtime prompt、全部 assistant blocks 与匹配 tool results。不可恢复的旧 continuation 必须明确 fail closed。

## Allowed write paths

- `pico/providers/anthropic_messages.py`
- `.codex/eval/handoffs/TOOL-059-A-R1.json`

## Forbidden write paths

- OpenAI Responses Adapter、Core/Runtime
- `TEST-059-A-R1` tests、Oracle、cases、human-smoke fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] `TEST-059-A-R1` 从 red 变 green
- [ ] 多轮 user/assistant message ordering 合法且完整
- [ ] prompt、call 或 result 不重复、不丢失
- [ ] continuation 只保存 JSON-safe Pico contract，不保存 SDK 对象
- [ ] 不启用 provider storage 或 SDK-managed tool execution
- [ ] 不完整旧 continuation 在 transport 前 fail closed

## Stop rule

提交单一产品修复与 per-ticket handoff 后停止；不得修改测试或其他 dialect。
