# EVAL-041 — Local Live Task Runner、Native Evidence 与 Hidden Verifier 隔离

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`
- `TOOL-010`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现 fresh workspace、manifest diff、workspace 外 verifier、RunEvidence、sanitized trace 与 failure taxonomy；runner 必须记录 native profile/gate/call-result/HTTP attempt 信息，先用 synthetic client 测试。

## Allowed write paths

- `pico/evaluation/live_tasks.py`
- `scripts/run_local_coding_tasks.py`
- `tests/test_live_task_evaluator.py`
- `tests/fixtures/live_task_runner/**`
- `.codex/eval/handoffs/EVAL-041.json`

## Forbidden write paths

- `benchmarks/v3/local-repos/taskset.json`
- `产品 Runtime`
- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- live task runner
- synthetic isolation fixture
- native manifest fields

## Acceptance checklist

- [ ] Agent workspace 无 hidden verifier/reference
- [ ] 每 run 独立复制
- [ ] provider/protocol/infrastructure 单独分类
- [ ] 支持 task/repo/run-kind/shard filters
- [ ] 正式 run 缺 recovered Gate N1 `TOOL-050-S-R1` selection hash 时拒绝
- [ ] 不依赖最终 taskset 才能测试

## Commands

```bash
uv run pytest tests/test_live_task_evaluator.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
