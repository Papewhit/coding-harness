# TOOL-063-G — Human-smoke v4 Deterministic Gate 与 Selection Reuse Proof

**Plan type:** `integrator` — 由当前 `integrator` 直接执行
**Wave:** `W6R5`
**Base/Candidate SHA:** 使用已集成并通过 `AUDIT-063-A` 的精确 Candidate。

## Start conditions

- Dependency Ticket: `AUDIT-063-A`

## Goal

在 Ubuntu WSL2/Python 3.12 fresh clone 验证 human-smoke v4 measurement contract，并证明仅 measurement files 变化时可以复用 W6R4 selected profile，而无需重跑 profile reselection。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-human-smoke-v4-gate/<SOURCE_SHA>/**`
- `.codex/eval/handoffs/TOOL-063-G.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `产品源码`
- `human-smoke v2/v3 source 与历史 Artifacts`
- `provider selection Artifacts`
- `.codex/eval/CURRENT.md`
- `.codex/eval/state/STATUS.json`

未列出的写路径默认禁止。

## Acceptance checklist

- [ ] fresh clone、Python 3.12、uv identity、source SHA/tree 和命令日志可审计
- [ ] EVAL-063-H tests、affected/protected tests、scoped Ruff、compileall、PLAN validator 与 diff check 通过
- [ ] fake/stub v4 Artifact 在临时 workspace 删除后仍保留可解析 durable public trajectory
- [ ] manifest、runner、tests、public profile、SDK、selection 与 Gate inputs 的 hashes 已记录
- [ ] W6R4 selection reuse proof 确认 production Runtime、Provider Adapter、conformance evaluator、public profile identity 与 selection-critical inputs 未变化
- [ ] provider HTTP attempts 为 0
- [ ] 不读取或持久化 private config locator value

## Commands

由 `integrator` 在 dispatch/执行记录中填写精确 WSL commands；不得启动 live provider Process。

## Completion rule

验证 deterministic evidence，写入 TOOL-063-G handoff，并由当前 `integrator` 更新 `FREEZE.json`。若 Gate accepted，W6R5 在尚未取得 live authorization 时进入 `waiting/user_decision`；不得自行启动 `EVAL-063-R`。
