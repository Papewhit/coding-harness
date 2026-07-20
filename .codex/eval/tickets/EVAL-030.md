# EVAL-030 — Structured Context Asset Contract

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-011`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

把八类 v3 prompt assets 的合同改写为 `system_text/messages/tools/continuation` 结构，定义 producer、activation、lifetime、priority、floor、drop、metadata、duplication 与 evidence；不再假设单一 prompt 字符串。

## Allowed write paths

- `benchmarks/v3/context-assets/assets.json`
- `docs/metrics/pico-v3-context-asset-contract.md`
- `.codex/eval/handoffs/EVAL-030.json`

## Forbidden write paths

- `pico/core/context_manager.py`
- `pico/core/runtime.py`
- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- structured assets.json
- contract doc
- observed-vs-guaranteed matrix

## Acceptance checklist

- [ ] 覆盖 Skills/Todo/Plan/Checkpoint/Worker/Durable/Compact/Pointer
- [ ] current request 标记 never-drop
- [ ] 工具定义单独属于 tools，不再复制进 system text
- [ ] 未完成 native turn 标记 non-compactable
- [ ] 无实现保证的策略标记 observed

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 该 ticket 定义目标与观察合同，不修 Context Runtime。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
