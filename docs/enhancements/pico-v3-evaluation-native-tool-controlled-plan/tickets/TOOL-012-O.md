# TOOL-012-O — OpenAI SDK Probe Plugin

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-012-I`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现 OpenAI Responses SDK 的 viability plugin，验证 custom base_url、tools/tool_choice、call_id、function_call_output、raw response、reasoning item roundtrip 和 max_retries=0。

## Allowed write paths

- `pico/evaluation/sdk_probe_openai.py`
- `tests/test_sdk_probe_openai.py`
- `.codex/eval/handoffs/TOOL-012-O.json`

## Forbidden write paths

- `pyproject.toml`
- `uv.lock`
- `pico/providers/**`
- `SDK Tool/Agent Runner`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- OpenAI probe plugin
- request/response fake tests
- required uv --with invocation

## Acceptance checklist

- [ ] 不自动执行工具
- [ ] typed parse 与 raw-response 模式均可记录
- [ ] reasoning/unknown item 不丢失
- [ ] SDK retry 可显式禁用
- [ ] 不改变产品依赖

## Commands

```bash
uv run --with openai pytest tests/test_sdk_probe_openai.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
