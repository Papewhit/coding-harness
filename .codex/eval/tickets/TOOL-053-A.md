# TOOL-053-A — Native Conformance Harness Safety and Evidence Audit

**Thread type:** `reviewer`
**Wave:** `W6R`
**Base SHA:** 由 Integrator 填写，并应用已验收的 `TOOL-051-L` 与 `EVAL-052-H` dependency commits。

## Start conditions

- `TOOL-051-L`
- `EVAL-052-H`

## Goal

只读审计 repaired harness 是否真实经过 production Runtime、安全链和版本化 evidence contract。发现缺陷只写 review handoff，不修改实现。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-harness-audit/**`
- `.codex/eval/handoffs/TOOL-053-A.json`

## Forbidden write paths

- 所有产品、evaluator、test 与 frozen input 源码
- `STATUS.json`、`FREEZE.json`
- live provider HTTP

## Acceptance checklist

- [ ] 记录 `script → fixed live runner → provider client → Engine → tool loop → safety chain` 的静态与动态调用链
- [ ] 证明 formal CLI 不存在任意 runner injection、SDK Tool Runner 或 SDK Agent Runner
- [ ] fake transport 端到端覆盖八案例、两种 wire dialect、multi-call、denial、repair 与 opaque continuation
- [ ] 检查 call ID/result 一一对应和 `validate → repetition → permission → policy → execute` 顺序
- [ ] 检查 local provider 与 expected public profile 的 fail-closed binding
- [ ] 重建一个多 repetition artifact bundle，并验证四个文件、row keys、hashes 与 aggregate
- [ ] 使用 credential sentinel 扫描所有公开输出
- [ ] 确认 W6 frozen cases 字节与哈希未变

## Commands

运行依赖 handoff 中全部 targeted tests、受影响 safety tests、Ruff、`git diff --check`，并将精确命令与结果写入 audit artifact。

## Stop rule

审计通过则输出 `ready_for_preflight_gate=true`；否则列出 blocking defects 与修复 ownership request。不得顺手修复或启动 Gate。
