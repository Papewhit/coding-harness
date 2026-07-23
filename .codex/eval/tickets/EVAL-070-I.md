# EVAL-070-I — Structured Context Grouped Ablation Hook 与 Runner

**Thread type:** `implementer`  
**Wave:** `W8`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-031-G`
- `EVAL-040-M`
- `EVAL-041`
- `TOOL-050-S-R1`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

复用 live task runner 实现 Full structured request vs 单个 grouped asset set off；feature hook 作用于 system/messages/tools 资产，不重新启用文本 prompt。

## Allowed write paths

- `pico/evaluation/context_ablation.py`
- `scripts/run_context_task_ablation.py`
- `tests/test_context_ablation_evaluator.py`
- `.codex/eval/handoffs/EVAL-070-I.json`

## Forbidden write paths

- `pico/core/context_manager.py`
- `pico/core/runtime.py`
- `provider adapters`
- `frozen taskset`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- ablation evaluator/script/tests

## Acceptance checklist

- [ ] Full/off 只有目标 asset group 差异
- [ ] 不破坏 native turn adjacency/continuation
- [ ] 复用 selected native profile
- [ ] 不做八字段全排列
- [ ] 支持 paired shard

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
