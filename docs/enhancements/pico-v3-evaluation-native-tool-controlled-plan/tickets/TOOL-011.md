# TOOL-011 — Tool Schema 单一事实源与 Strict Normalization

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

让 RegisteredTool 直接持有 Pydantic 参数模型，并从同一模型生成本地校验、provider-neutral JSON Schema、人类可读签名与稳定 tool signature。保留迁移期兼容属性，避免提前破坏 Runtime。

## Allowed write paths

- `pico/tools/definitions.py`
- `pico/tools/base.py`
- `pico/tools/registry.py`
- `pico/tools/schemas.py`
- `tests/test_tool_schema_export.py`
- `.codex/eval/handoffs/TOOL-011.json`

## Forbidden write paths

- `pico/core/**`
- `pico/providers/**`
- `pyproject.toml`
- `uv.lock`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- tool definition API
- strict schema normalization
- golden tests and signature tests

## Acceptance checklist

- [ ] 所有注册工具只有一个参数 schema 事实源
- [ ] 额外字段策略明确且本地校验仍是最终权威
- [ ] required/default/nullable 转换有 golden tests
- [ ] object 的 additionalProperties 策略稳定
- [ ] 不削弱 workspace-aware validation

## Commands

```bash
uv run pytest tests/test_tool_schema_export.py tests/test_tool_validation.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
