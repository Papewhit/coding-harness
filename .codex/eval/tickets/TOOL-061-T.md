# TOOL-061-T — Native Resume Crash Contract Harness

**Plan type:** `implementer` — 使用 `implementer` Thread
**Wave:** `W7`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `TOOL-060-R`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

建设 deterministic crash/restart harness，覆盖 assistant batch 落盘后、tool result 落盘后、multi-call 中途和 risky executing crash；输出可供 `native_resume_ready` Gate 使用的 contract Artifact。

## Allowed write paths

- `pico/evaluation/native_resume_contract.py`
- `scripts/run_native_resume_contract.py`
- `tests/test_native_resume_contract.py`
- `.codex/eval/handoffs/TOOL-061-T.json`

## Forbidden write paths

- `产品 Runtime`
- `正式 Resume taskset`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- contract runner
- crash fixtures
- deterministic rows

## Acceptance checklist

- [ ] 真实子进程终止而非线程模拟
- [ ] 每个中断点证明 event/checkpoint fsync/完整落盘
- [ ] completed/pending/uncertain 判定正确
- [ ] 副作用工具无自动 replay
- [ ] private continuation hash 前后一致

## Commands

```bash
uv run pytest tests/test_native_resume_contract.py -q
```

```bash
uv run python scripts/run_native_resume_contract.py --output <ARTIFACT_ROOT>/native-resume-contract
```

## Notes

- 无额外说明。

## Completion rule

运行本 Ticket 的 targeted tests 与 scoped lint。先把 `.codex/eval/**` 之外的 Git-tracked 变更形成一个语义 commit，再按 `templates/HANDOFF.md` 写 handoff；handoff 和其他控制文件不得进入该 commit。返回 `integrator` 验收。若 dispatch sequence 还有后续 Ticket，只有在 `integrator` 已复制并验证本 handoff、清理未提交控制文件，并给出下一 Ticket 的精确 base/dependency commits 后才继续；不得自行开始未 dispatch 的工作。
