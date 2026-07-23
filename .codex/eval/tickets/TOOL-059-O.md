# TOOL-059-O — OpenAI Responses 完整无状态 Transcript 修复

**Thread type:** `implementer`
**Wave:** `W6R3`

## Start conditions

- `EVAL-059-O`
- `TEST-059-C`

## Goal

修复 OpenAI Responses Adapter：在 `store=false` 且不使用 `previous_response_id` 时，由客户端按顺序维护完整 JSON-safe transcript，包括原始 Runtime prompt、所有必要 response output items 与 tool outputs。

## Allowed write paths

- `pico/providers/openai_responses.py`
- `.codex/eval/handoffs/TOOL-059-O.json`

## Forbidden write paths

- Core/Runtime、Anthropic Adapter
- Oracle v2、frozen cases 与 TEST-059-C tests
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] TEST-059-C 从 red 变 green
- [ ] prompt、call、result 的顺序与累计语义正确
- [ ] 不重复 prompt、call 或 result
- [ ] continuation 仅保存 Pico JSON-safe contract，不保存 SDK 对象
- [ ] 不启用 provider storage、`previous_response_id` 或 SDK-managed tool execution
- [ ] 旧 continuation version 明确兼容或 fail closed，不静默误读

## Stop rule

提交单一产品修复与 handoff 后停止；不得修改 Oracle、fixture 或 Anthropic Adapter。
