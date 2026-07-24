# TOOL-059-G — W6R3 Deterministic Recovery Gate

**Thread type:** `integrator`
**Wave:** `W6R3`

## Start conditions

- `AUDIT-059-A` 的最新 handoff revision 已 accepted
- W6R3 所有实现与 fixture tickets 已验收

## Goal

在 Ubuntu WSL2/Python 3.12 fresh clone 对完成 remediation 且复审通过的 W6R3 source 执行 deterministic Gate。通过后提出新的 immutable recovery snapshot 与 W6R4 ready set。若 Gate 发现可由既有约定唯一决定的实现偏差，输出 `needs_remediation` proposal 供 Wave Integrator 继续同 Wave 修复；只有符合 `CONTROL.md` 真正 blocked 条件时才提出 blocked。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-deterministic-gate/W6R3-TOOL-059-G-01/**`
- `.codex/eval/proposals/TOOL-059-G.freeze.json`
- `.codex/eval/proposals/TOOL-059-G.status.json`
- `.codex/eval/handoffs/TOOL-059-G.json`

## Forbidden write paths

- 所有产品源码、tests、Oracle、fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] fresh clone 与 Python/uv identity 可审计，无 sudo
- [ ] Oracle v2、双 dialect 完整 stateless transcript、call/result closure、human-smoke v3 与 repetition targeted tests 通过
- [ ] protected、deterministic、full suite、Ruff、compileall 与 PLAN 校验通过
- [ ] Windows 仅 best-effort，不影响 Gate
- [ ] provider HTTP attempts=0
- [ ] 新 snapshot 绑定 source/tree、Oracle v2、tests、SDK lock 与 artifact hashes
- [ ] W7 继续 blocked，直到 W6R4 重新 selection 且新 human smoke 被用户接受

## Stop rule

提交 Gate artifacts、proposals 与 per-ticket handoff 后停止。不得生成 Wave 最终 handoff/bundle/tag，不得运行 provider shards、重新 selection、执行 human smoke 或启动 W7。
