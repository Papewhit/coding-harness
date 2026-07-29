# TOOL-057-A — Dual-Dialect Evidence Closure Audit

**Thread type:** `reviewer`
**Wave:** `W6R2`
**Base SHA:** 由 Integrator 填写，并应用已验收的 `TOOL-055-E` 与 `EVAL-056-H` commits。

## Start conditions

- `TOOL-055-E`
- `EVAL-056-H`

## Goal

只读证明两种 dialect 的仓库回归强度相同，正式 bundle 能独立重建安全链顺序，且 private config 不进入公开证据。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-harness-audit/W6R2-TOOL-057-A-01/**`
- `.codex/eval/handoffs/TOOL-057-A.json`

## Forbidden write paths

- 所有产品、evaluator、tests 与 frozen inputs
- `STATUS.json`、`FREEZE.json`
- live provider HTTP

## Acceptance checklist

- [ ] OpenAI Responses 与 Anthropic Messages 对同一八案例运行同一断言矩阵
- [ ] 两种 dialect 的 multi-repetition bundle 均可由独立 verifier 重建
- [ ] 每个执行/拒绝结果都能从 artifact 自身证明安全链顺序，无外部 monkey patch 或临时 instrumentation
- [ ] locator 缺失与 profile mismatch 均 fail closed 为 0-row、`not_computable`
- [ ] credential/raw URL/config locator value 扫描无匹配
- [ ] 所有 JSON、JSONL 与测试 XML evidence 在脱敏后仍可解析
- [ ] frozen cases 与 W6R FREEZE 不变

## Stop rule

通过则输出 `ready_for_wsl_preflight_gate=true`；否则只记录 blocking defects 与 ownership request，不得修复或启动 Gate。
