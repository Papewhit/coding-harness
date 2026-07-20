# TOOL-042-G — Deterministic Native Eval-ready Gate

**Thread type:** `integrator`  
**Wave:** `W5`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-041-M`
- `TOOL-049-I`
- `EVAL-031-G`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

运行全套 deterministic native、Context、架构与安全 Gate，冻结可供 live conformance 使用的 run snapshot。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-deterministic-gate/**`
- `.codex/eval/proposals/TOOL-042-G.freeze.json`
- `.codex/eval/handoffs/TOOL-042-G.json`

## Forbidden write paths

- `产品源码`
- `frozen evaluator/fixtures`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- gate report
- run_snapshot_sha
- native_deterministic_gate hash

## Acceptance checklist

- [ ] call ID/result 与 batch completeness tests 100%
- [ ] Runtime/online evaluator text envelope seen=0
- [ ] unknown block loss=0
- [ ] safety chain bypass=0
- [ ] SDK Tool/Agent Runner 不存在
- [ ] architecture/safety/permission/policy 全通过

## Commands

```bash
uv run ruff check .
```

```bash
uv run pytest tests/test_architecture_boundaries.py tests/test_safety_invariants.py tests/test_tool_policy_acceptance.py tests/test_permissions_acceptance.py -q
```

```bash
uv run pytest tests/test_provider_contracts.py tests/test_openai_responses_tools.py tests/test_anthropic_messages_tools.py tests/test_native_tool_loop.py tests/test_native_session_exchange.py tests/test_native_request_context.py tests/test_native_runtime_integration.py tests/test_native_provider_evaluator.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
