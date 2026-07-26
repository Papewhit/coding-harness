# EVAL-063-M — Human-smoke v4 Adjudication 与 native_eval_ready Gate

**Plan type:** `integrator` — 由当前 `integrator` 直接执行
**Wave:** `W6R5`
**Base/Candidate SHA:** 使用 EVAL-063-R Process manifest 绑定的精确 source。

## Start conditions

- Dependency Ticket: `EVAL-063-R`

## Goal

验证 human-smoke v4 Artifact，区分 measurement validity 与 semantic outcome，并在 `program_supervisor` 决定后形成新的 `native_eval_ready` 状态。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-human-smoke-v4/<SOURCE_SHA>/adjudication/**`
- `.codex/eval/handoffs/EVAL-063-M.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `产品源码、tests、fixtures 与 runner`
- `W6R4 与更早 Artifacts`
- `.codex/eval/CURRENT.md`
- `.codex/eval/state/STATUS.json`

未列出的写路径默认禁止。

## Acceptance checklist

- [ ] source、profile、manifest、runner、tests、selection reuse proof、Process manifest、result 与 inventory hashes 完整
- [ ] grounded instruction、workspace before/after、semantic order 和 durable trajectory 可人工复核
- [ ] measurement defect 不被记为 semantic FAIL，也不直接改变 Gate
- [ ] valid semantic FAIL 被记录为 `evaluation_failure`，不得自动修改产品或重跑到成功
- [ ] grounded scenario 中的无进展只读探索若复现，引用 durable trajectory 记录为新的产品 `change_request`
- [ ] `program_supervisor` 的接受或拒绝通过跨 Thread 消息取得并记录
- [ ] accepted result 设置 `native_eval_ready=accepted`；rejected/valid FAIL 设置 `native_eval_ready=rejected`
- [ ] W6R5 close handoff绑定 W6R4 selection 与 W6R5 smoke；W7 尚未启动

## Commands

由当前 `integrator` 执行只读 Artifact/hash/format/secret checks；不发 provider HTTP。

## Completion rule

写入 adjudication、EVAL-063-M handoff并由当前 `integrator` 更新 `FREEZE.json` 与 `CURRENT.md`。W6R5 close 后发送一次结论性 Wave 汇报并停止；不得启动 W7。
