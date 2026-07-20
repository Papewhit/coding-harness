# TOOL-031-S — Session Exchange Events 与 Private Continuation Persistence

**Thread type:** `implementer`  
**Wave:** `W4`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-015`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

新增 assistant_tool_batch/tool_result/model_final 等统一 exchange events，保存规范化字段与 JSON-safe private continuation；公开 trace/report 只记录摘要/hash。此阶段覆盖同进程续传，不实现 crash replay policy。

## Allowed write paths

- `pico/core/model_exchange.py`
- `pico/core/turn_history.py`
- `pico/core/session_events.py`
- `pico/core/session_lifecycle.py`
- `pico/core/run_store.py`
- `pico/core/runtime_consumers.py`
- `tests/test_native_session_exchange.py`
- `.codex/eval/handoffs/TOOL-031-S.json`

## Forbidden write paths

- `pico/core/runtime.py`
- `pico/core/runtime_checkpoints.py`
- `provider adapter 文件`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- event schema
- private/public persistence split
- session profile lock tests

## Acceptance checklist

- [ ] assistant tool batch 先于工具执行落盘
- [ ] call_id/name/arguments/status 可审计
- [ ] opaque 内容不进入公开 trace/report
- [ ] provider/model/dialect mismatch 可检测
- [ ] 不保存 SDK 对象或 pickle

## Commands

```bash
uv run pytest tests/test_native_session_exchange.py tests/test_run_store.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
