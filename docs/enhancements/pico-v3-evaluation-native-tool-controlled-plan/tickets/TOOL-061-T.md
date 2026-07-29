# TOOL-061-T — Native Resume Crash Contract Harness

**Thread type:** `implementer`  
**Wave:** `W7`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-060-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

建设 deterministic crash/restart harness，覆盖 assistant batch 落盘后、tool result 落盘后、multi-call 中途和 risky executing crash；输出可供 Gate N2 使用的 contract artifact。

## Allowed write paths

- `pico/evaluation/native_resume_contract.py`
- `scripts/run_native_resume_contract.py`
- `tests/test_native_resume_contract.py`
- `.codex/eval/handoffs/TOOL-061-T.json`

## Forbidden write paths

- `产品 Runtime`
- `正式 Resume taskset`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

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

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
