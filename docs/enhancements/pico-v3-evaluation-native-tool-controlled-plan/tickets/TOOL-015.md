# TOOL-015 — Scripted Native Model Client 与结构化 Fixtures

**Thread type:** `implementer`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

扩展 `pico.testing`，提供结构化 final/tool call/multi-call/protocol-error/opaque continuation fixtures，供 Engine、Session、Context 和 Resume 的 deterministic tests 使用。迁移期可保留旧 helper，但标记 deprecated。

## Allowed write paths

- `pico/testing.py`
- `tests/test_native_model_fixtures.py`
- `.codex/eval/handoffs/TOOL-015.json`

## Forbidden write paths

- `pico/core/**`
- `pico/providers/clients.py`
- `在线 provider 配置`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- ScriptedNativeModelClient
- fixture constructors
- deterministic call log

## Acceptance checklist

- [ ] 返回 ModelResponse 而非标签文本
- [ ] 可断言下一次 ModelRequest 中的 tool results/continuation
- [ ] 支持多个 call 与错误 stop reason
- [ ] 不调用网络
- [ ] 旧 helper 不再被新测试引用

## Commands

```bash
uv run pytest tests/test_native_model_fixtures.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
