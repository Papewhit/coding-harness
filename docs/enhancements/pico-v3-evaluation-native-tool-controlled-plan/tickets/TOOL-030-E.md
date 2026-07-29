# TOOL-030-E — Engine Native Tool Batch Loop

**Thread type:** `implementer`  
**Wave:** `W4`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-011`
- `TOOL-015`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

让 Engine 消费 ModelResponse，处理 final、interim text 和 tool batch；每个 call 经现有工具安全链后形成匹配 ToolCallResult。实现 received/persisted/executing/completed/rejected/uncertain 状态接口，但本 ticket 不做 checkpoint persistence。

## Allowed write paths

- `pico/core/engine.py`
- `pico/core/engine_helpers.py`
- `pico/core/tool_call_batch.py`
- `pico/core/model_errors.py`
- `pico/core/runtime_events.py`
- `tests/test_native_tool_loop.py`
- `.codex/eval/handoffs/TOOL-030-E.json`

## Forbidden write paths

- `pico/core/runtime.py`
- `pico/core/runtime_checkpoints.py`
- `provider adapter 文件`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- native engine loop
- batch state model
- error result bridge
- deterministic tests

## Acceptance checklist

- [ ] 模型响应在首个工具执行前触发 persist hook
- [ ] 未知工具/参数/权限/策略拒绝均形成匹配 error result
- [ ] batch 下一次模型请求前结果完整
- [ ] 工具仍只经 run_tool/既有安全链
- [ ] step-limit summary 使用 tool_choice=none
- [ ] 不调用 model_output parser

## Commands

```bash
uv run pytest tests/test_native_tool_loop.py tests/test_tool_validation.py tests/test_permissions_acceptance.py tests/test_tool_policy_acceptance.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
