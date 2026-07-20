# EVAL-022 — Auto-dream 生命周期确定性证据

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；必须等于本波 `wave_base_sha` 或 run ticket 的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

把 interval/session-count gate、active/stale lock、失败隔离和 write scope 纳入统一 artifact，不调用在线模型。

## Allowed write paths

- `pico/evaluation/dream_lifecycle_eval.py`
- `tests/test_dream_lifecycle_evaluator.py`
- `benchmarks/v3/auto-dream/lifecycle.json`
- `.codex/eval/handoffs/EVAL-022.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py`
- `pico/features/memory.py`
- `tests/test_memory.py`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- lifecycle evaluator/tests/cases
- unified artifact rows

## Acceptance checklist

- [ ] 复用现有行为和证据
- [ ] Dream 失败不覆盖主任务结果
- [ ] write scope 越界为硬失败
- [ ] 不改变 Dream 异步/权限语义

## Commands

```bash
uv run pytest tests/test_dream_lifecycle_evaluator.py tests/test_memory.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 STATUS/FREEZE（Integrator ticket 除外）或开始下游工作。
