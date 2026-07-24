# TOOL-059-O-R1 — Responses Call/Result Closure 修复

**Thread type:** `implementer`
**Wave:** `W6R3`
**Remediation finding:** `AUDIT-059-A-P1-002`

## Start conditions

- `TEST-059-O-R1`

## Goal

在 OpenAI Responses transport 前验证当前 unresolved function calls 与本次 tool results 精确一一对应，并按原 call order 生成 outputs；不得破坏 W6R3 已修复的完整累计 transcript。

## Allowed write paths

- `pico/providers/openai_responses.py`
- `.codex/eval/handoffs/TOOL-059-O-R1.json`

## Forbidden write paths

- Anthropic Adapter、Core/Runtime
- `TEST-059-O-R1` tests、Oracle、cases、human-smoke fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] `TEST-059-O-R1` 从 red 变 green
- [ ] missing、extra、unknown 与 duplicate result 均在 transport 前 fail closed
- [ ] 合法重排 results 规范化为 provider call order
- [ ] 原始 prompt 与所有历史 call/result 仍完整且只出现一次
- [ ] `store=false`、无 `previous_response_id`、无 SDK-managed execution 保持不变

## Stop rule

提交单一产品修复与 per-ticket handoff 后停止；不得修改测试或其他 dialect。
