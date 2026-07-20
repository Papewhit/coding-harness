# TOOL-032-C — Structured ModelRequest Context 与 Prompt 协议拆除

**Thread type:** `implementer`  
**Wave:** `W4`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-011`
- `EVAL-030`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

把单一 prompt 拆为 system_text、messages、tools 和 continuation-aware request context；删除 prefix 中工具 XML/JSON 语法与文本 schema，保留行为、安全和 workspace 约束。

## Allowed write paths

- `pico/core/request_context.py`
- `pico/core/context_manager.py`
- `pico/core/runtime.py`
- `pico/core/compact.py`
- `pico/core/context_usage.py`
- `pico/core/tool_profiles.py`
- `tests/test_native_request_context.py`
- `.codex/eval/handoffs/TOOL-032-C.json`

## Forbidden write paths

- `pico/core/engine.py`
- `pico/core/runtime_checkpoints.py`
- `provider adapter 文件`
- `tests/test_architecture_boundaries.py`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- structured request builder
- asset metadata split
- architecture-safe refactor

## Acceptance checklist

- [ ] current request never-drop
- [ ] 八类 v3 assets 可归因到 system/messages/tools
- [ ] tool schema token/char 与 system prompt 分开统计
- [ ] 未完成 native turn 不被 compact 破坏
- [ ] runtime.py 回到架构预算内且不放宽测试
- [ ] 不含 <tool>/<final> 指令

## Commands

```bash
uv run pytest tests/test_native_request_context.py tests/test_context_manager.py tests/test_context_governance_acceptance.py tests/test_architecture_boundaries.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
