# EVAL-040-M — 组装并冻结 3 Repo / 9 Task Taskset

**Thread type:** `integrator`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；必须等于本波 `wave_base_sha` 或 run ticket 的 `run_snapshot_sha`。

## Start conditions

- `EVAL-040-A`
- `EVAL-040-B`
- `EVAL-040-C`

读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

组合三个 fragment，执行防作弊/无网络/路径隔离自检，并冻结 pico-local-python-v1 hash。

## Allowed write paths

- `benchmarks/v3/local-repos/taskset.json`
- `benchmarks/v3/local-repos/taskset.lock.json`
- `.codex/eval/proposals/EVAL-040-M.freeze.json`
- `.codex/eval/handoffs/EVAL-040-M.json`

## Forbidden write paths

- `各 repo frozen 内容，除非退回对应 builder ticket`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- taskset.json
- taskset lock/hash
- self-check report

## Acceptance checklist

- [ ] 9 tasks 齐全
- [ ] baseline/reference/inverted checks 完整
- [ ] 无用户主目录依赖
- [ ] taskset version/hash 写入 freeze

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 STATUS/FREEZE 或开始下游工作；所需状态变化只写 proposal。
