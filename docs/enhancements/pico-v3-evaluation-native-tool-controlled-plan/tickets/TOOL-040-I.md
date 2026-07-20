# TOOL-040-I — Native Adapter/Core Runtime Wiring

**Thread type:** `implementer`  
**Wave:** `W5`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-020-O`
- `TOOL-020-A`
- `TOOL-021-P`
- `TOOL-030-E`
- `TOOL-031-S`
- `TOOL-032-C`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

把 adapters、structured request、Engine batch loop 和 Session exchange 接入实际 Runtime/CLI。生产路径只允许 native tools；旧 client 可暂留为不可达迁移代码，随后由 TOOL-041-M 删除。

## Allowed write paths

- `pico/providers/clients.py`
- `pico/providers/base.py`
- `pico/providers/__init__.py`
- `pico/core/runtime.py`
- `pico/core/engine.py`
- `pico/core/engine_helpers.py`
- `pico/core/session_lifecycle.py`
- `pico/cli.py`
- `tests/test_native_runtime_integration.py`
- `.codex/eval/handoffs/TOOL-040-I.json`

## Forbidden write paths

- `pico/core/runtime_checkpoints.py`
- `frozen evaluator/fixtures`
- `tests/test_architecture_boundaries.py`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- active native runtime path
- adapter factory wiring
- integration tests

## Acceptance checklist

- [ ] 模型请求含非空 tools（有可用工具时）
- [ ] tool result 使用 provider-native structure
- [ ] 无 native capability 的 profile 启动失败
- [ ] 安全链与 tool profiles 保持
- [ ] SDK retry 配置可见
- [ ] 不引入文本 fallback

## Commands

```bash
uv run pytest tests/test_native_runtime_integration.py tests/test_safety_invariants.py tests/test_permissions_acceptance.py tests/test_tool_policy_acceptance.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
