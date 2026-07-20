# TOOL-020-A — Anthropic Messages Native Adapter

**Thread type:** `implementer`  
**Wave:** `W3`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-011`
- `TOOL-013-S`
- `TOOL-019-D`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现单一 `anthropic-messages` dialect：编译 system/messages/tools/tool_choice，解析完整 content blocks，以匹配 tool_use_id 的 user tool_result 回传，并原样保存 thinking/redacted-thinking continuation。

## Allowed write paths

- `pico/providers/anthropic_messages.py`
- `tests/test_anthropic_messages_tools.py`
- `.codex/eval/handoffs/TOOL-020-A.json`

## Forbidden write paths

- `pico/core/**`
- `pico/providers/openai_responses.py`
- `SDK Tool Runner`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- adapter
- request/response golden tests
- stop reason handling

## Acceptance checklist

- [ ] tool_result 在任何普通 user text 前
- [ ] batch 中每个 tool_use 都有 result
- [ ] thinking 内容不进入公开 trace
- [ ] max_tokens/unknown stop reason fail closed
- [ ] SDK 对象不外泄

## Commands

```bash
uv run pytest tests/test_anthropic_messages_tools.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
