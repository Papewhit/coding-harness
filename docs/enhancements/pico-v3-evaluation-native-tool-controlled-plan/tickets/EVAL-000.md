# EVAL-000 — Preflight、Native 基线与可复现 Bootstrap Snapshot

**Thread type:** `integrator`  
**Wave:** `W0`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- 无；由 W0 Integrator 直接启动。

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

记录仓库/分支/commit、本地配置位置、候选 profile 名称、当前 dirty paths、既有 `runtime_checkpoints.py` diff hash、architecture baseline、所有 `<tool>/<final>` 引用和当前 ModelClient/provider 合同。创建保留现有修改的 bootstrap snapshot。

## Allowed write paths

- `.codex/eval/proposals/EVAL-000.status.json`
- `.codex/eval/state/preflight.json`
- `.codex/eval/state/native-baseline.json`
- `.codex/eval/handoffs/EVAL-000.json`

## Forbidden write paths

- `除 bootstrap snapshot 外的产品/Evaluation 实现`
- `本地密钥内容`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- bootstrap commit
- preflight.json
- native-baseline.json
- handoff
- STATUS proposal（由 W0 Wave Integrator 落盘）

## Acceptance checklist

- [ ] 保留既有 runtime_checkpoints diff 且 hash 可核验
- [ ] 记录 architecture boundary 当前失败而不放宽测试
- [ ] 枚举 active parser/provider/test fixture 引用
- [ ] 只记录配置路径/profile 名称，不记录 key
- [ ] 后续 worktree 均可从 bootstrap_sha 创建

## Commands

```bash
uv run pytest tests/test_architecture_boundaries.py -q || true
```

```bash
grep -RInE "<tool>|<final>" pico tests scripts benchmarks > /tmp/pico-native-text-protocol-baseline.txt || true
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
