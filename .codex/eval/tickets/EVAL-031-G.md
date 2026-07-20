# EVAL-031-G — Structured Context Deterministic Integration Gate

**Thread type:** `integrator`  
**Wave:** `W5`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-031-I`
- `EVAL-031-A`
- `EVAL-031-B`
- `TOOL-041-M`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

组装 15 cases，在最终 native structured request path 上运行 evaluator，冻结 contract/case hash，并单独列出 Runtime 缺陷。

## Allowed write paths

- `benchmarks/v3/context-assets/cases.json`
- `<ARTIFACT_ROOT>/phase-2-context-assets/**`
- `.codex/eval/proposals/EVAL-031-G.freeze.json`
- `.codex/eval/handoffs/EVAL-031-G.json`

## Forbidden write paths

- `frozen fragment 内容`
- `产品 Runtime`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- cases.json
- structured summary
- freeze entry
- defect list

## Acceptance checklist

- [ ] 八类资产正常预算均有证据
- [ ] 15 cases 全部判定
- [ ] current request 100% 保留
- [ ] tools 不重复渲染进 system prompt
- [ ] 未完成 native turn 完整
- [ ] 产品修复不与 Gate 混提交

## Commands

```bash
uv run pytest tests/test_context_asset_evaluator.py tests/test_context_manager.py tests/test_context_governance_acceptance.py tests/test_native_request_context.py -q
```

```bash
uv run python scripts/run_context_asset_evaluation.py --output <ARTIFACT_ROOT>/phase-2-context-assets
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
