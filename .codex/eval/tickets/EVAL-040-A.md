# EVAL-040-A — Mini Repo tinyconfig：T01, T02, T03

**Thread type:** `fixture_builder`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；必须等于本波 `wave_base_sha` 或 run ticket 的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

建设离线小型 Python repo `tinyconfig` 及 3 个任务：boolean env、nested keys、稳定且不泄漏 secret 的 validation errors。

## Allowed write paths

- `benchmarks/v3/local-repos/repos/tinyconfig/**`
- `benchmarks/v3/local-repos/hidden_verifiers/tinyconfig/**`
- `benchmarks/v3/local-repos/reference_patches/tinyconfig/**`
- `benchmarks/v3/local-repos/task_docs/tinyconfig/**`
- `benchmarks/v3/local-repos/fragments/tinyconfig.json`
- `.codex/eval/handoffs/EVAL-040-A.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_safety_invariants.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_permissions_acceptance.py`
- `benchmarks/v3/local-repos/taskset.json`
- `pico/evaluation/live_tasks.py`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- tinyconfig base snapshot
- 3 hidden verifiers
- 3 reference patches
- fragment manifest

## Acceptance checklist

- [ ] 200–1500 LOC 范围
- [ ] 单任务通常改 1–3 文件
- [ ] 目标测试 <5 秒且不联网
- [ ] 原 snapshot 对目标 hidden case 失败
- [ ] reference patch 全过
- [ ] verifier/reference 不进入 Agent workspace
- [ ] 不写共享 taskset.json

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 STATUS/FREEZE（Integrator ticket 除外）或开始下游工作。
