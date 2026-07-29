# TOOL-020-O — OpenAI Responses Native Adapter

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

实现单一 `openai-responses` dialect：编译 instructions/input/tools/tool_choice，解析全部 output items，保留 reasoning/unknown continuation，并用 call_id 生成 function_call_output。第一版非流式、请求关闭 parallel tools。

## Allowed write paths

- `pico/providers/openai_responses.py`
- `tests/test_openai_responses_tools.py`
- `.codex/eval/handoffs/TOOL-020-O.json`

## Forbidden write paths

- `pico/core/**`
- `pico/providers/anthropic_messages.py`
- `SDK Tool/Agent Runner`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- adapter
- request/response golden tests
- protocol error taxonomy

## Acceptance checklist

- [ ] 不猜测 /chat/completions fallback
- [ ] text + tool call 时保留 interim text 但继续工具循环
- [ ] 缺 call_id/非法 arguments fail closed
- [ ] reasoning/unknown items roundtrip
- [ ] 所有 metadata 脱敏且 SDK 对象不外泄

## Commands

```bash
uv run pytest tests/test_openai_responses_tools.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
