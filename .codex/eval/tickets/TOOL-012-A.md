# TOOL-012-A — Anthropic SDK Probe Plugin

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-012-I`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现 Anthropic Messages SDK viability plugin，验证 custom base_url、tool_use/tool_result、tool_use_id、thinking/redacted-thinking roundtrip、raw response 与 max_retries=0。

## Allowed write paths

- `pico/evaluation/sdk_probe_anthropic.py`
- `tests/test_sdk_probe_anthropic.py`
- `.codex/eval/handoffs/TOOL-012-A.json`

## Forbidden write paths

- `pyproject.toml`
- `uv.lock`
- `pico/providers/**`
- `SDK Tool Runner`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- Anthropic probe plugin
- request/response fake tests
- required uv --with invocation

## Acceptance checklist

- [ ] tool_result 紧随 assistant tool_use turn
- [ ] 每个 tool_use_id 恰有一个 result
- [ ] thinking block 内容不进入公开 artifact
- [ ] SDK retry 可显式禁用
- [ ] 不改变产品依赖

## Commands

```bash
uv run --with anthropic pytest tests/test_sdk_probe_anthropic.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
