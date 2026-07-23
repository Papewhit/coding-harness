# AUDIT-059-A — Oracle v2 与 Responses Recovery 只读复审

**Thread type:** `reviewer`
**Wave:** `W6R3`

## Start conditions

- `EVAL-059-O`
- `TEST-059-C`
- `TOOL-059-O`
- `EVAL-059-H`
- `TOOL-059-R`

## Goal

只读复审 Oracle v2、Responses transcript、human-smoke v2 与 repetition 修复。确认责任归属没有重新混入 profile selection，且所有关键 evidence 可从 source/tests/artifacts 重建。

## Allowed write paths

- `.codex/eval/handoffs/AUDIT-059-A.json`

## Forbidden write paths

- 除 handoff 外的所有路径

## Acceptance checklist

- [ ] Runtime 前拒绝不进入执行安全链分母
- [ ] Runtime `execute=completed` 语义没有被 evaluator 改写
- [ ] OpenAI 与 Anthropic 多轮上下文测试严格度对称
- [ ] Responses transcript 不重复或丢失 call/result
- [ ] smoke manifest 不泄露判定意图，verifier 无双重 literal
- [ ] 历史 adjudication 未覆盖或晋级 W6R2 artifacts
- [ ] 无 live HTTP、凭据泄漏或 SDK-managed execution

## Stop rule

提交 review handoff 后停止；发现缺陷只报告，不直接修复。
