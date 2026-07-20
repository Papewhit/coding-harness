# TOOL-041-M — Legacy Text Protocol 删除与 Fixture 机械迁移

**Thread type:** `implementer`  
**Wave:** `W5`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-040-I`
- `TOOL-015`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

删除 active Runtime 的 parser/retry notice/协议 prompt，迁移所有 `<tool>/<final>` 测试与脚本 fixture 为结构化 Native helpers。只做协议机械迁移，不改变测试保护语义。

## Allowed write paths

- `pico/core/model_output.py`
- `pico/core/runtime.py`
- `pico/core/engine_helpers.py`
- `pico/evaluation/evaluator.py`
- `pico/evaluation/metrics.py`
- `pico/tools/agents.py`
- `pico/tools/ask_user.py`
- `pico/tools/plan.py`
- `pico/tools/registry.py`
- `pico/tools/todos.py`
- `scripts/run_business_scenario_dogfood.py`
- `scripts/run_real_session_acceptance.py`
- `scripts/run_v3_human_scenario_gate.py`
- `tests/**`
- `.codex/eval/handoffs/TOOL-041-M.json`

## Forbidden write paths

- `pico/core/runtime_checkpoints.py`
- `native contracts/adapters`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py 的断言语义削弱`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- parser deletion or unreachable tombstone with removal proof
- migrated tests/scripts
- static grep report

## Acceptance checklist

- [ ] Engine 不 import model_output.parse
- [ ] Runtime/prompt/online evaluator 无文本协议指令
- [ ] 所有原测试意图保持
- [ ] human scenario scripts 使用 native profile
- [ ] 不通过删除/弱化安全断言换取通过

## Commands

```bash
grep -RInE "<tool>|<final>" pico tests scripts benchmarks || true
```

```bash
uv run pytest tests -q
```

```bash
uv run ruff check .
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
