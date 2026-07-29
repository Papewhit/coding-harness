# TOOL-010 — Provider-neutral Native Model/Tool Contract

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

新增 SDK 无关、JSON-safe 的 ModelRequest/ModelResponse、ToolDefinition、ToolCall、ToolCallResult、ProviderContinuation、ToolChoice 与 stop reason 合同。保留临时 legacy client 适配边界，但不切换 active Runtime。

## Allowed write paths

- `pico/providers/contracts.py`
- `pico/providers/base.py`
- `tests/test_provider_contracts.py`
- `docs/architecture/native-tool-contract.md`
- `.codex/eval/handoffs/TOOL-010.json`

## Forbidden write paths

- `pico/core/**`
- `pico/tools/**`
- `pyproject.toml`
- `uv.lock`
- `任何 SDK import`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- provider-neutral contracts
- contract invariants tests
- profile identity and continuation schema doc

## Acceptance checklist

- [ ] call_id 为非空稳定标识
- [ ] continuation 可 JSON 序列化并可 hash，但 Core 不解析 opaque blocks
- [ ] ModelResponse 同时表达 text、tool_calls、stop_reason
- [ ] 不出现 SDK 类型或 <tool>/<final> 协议
- [ ] 临时兼容层不改变当前 Runtime 行为

## Commands

```bash
uv run pytest tests/test_provider_contracts.py -q
```

```bash
uv run ruff check pico/providers/contracts.py pico/providers/base.py tests/test_provider_contracts.py
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
