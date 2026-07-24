# AUDIT-059-A-R1 — W6R3 Remediation 只读复审

**Thread type:** `reviewer`
**Wave:** `W6R3`

## Start conditions

- `TOOL-059-A-R1`
- `TOOL-059-O-R1`
- `EVAL-059-H-R1`
- 已验收的 W6R3 Oracle v2 与 repetition 修复

## Goal

只读复审双 dialect stateless transcript、Responses call/result closure 与 human-smoke v3 evidence contract。Reviewer 只报告；发现可由既有约定唯一决定的问题时标记 `needs_remediation`，由 Wave Integrator 在同一 W6R3 继续分发。

## Allowed write paths

- `.codex/eval/handoffs/AUDIT-059-A-R1.json`

## Forbidden write paths

- 除 per-ticket handoff 外的所有路径

## Acceptance checklist

- [ ] OpenAI 与 Anthropic 三轮 transcript 保留原 prompt、全部 call/result，且严格度对称
- [ ] 当前 unresolved call/result 精确一一对应，合法重排按 call order 规范化
- [ ] human-smoke v3 live verifier 不依赖 fake call ID 或唯一完整工具序列
- [ ] 场景 B 命令明确且不泄露 denial/verifier 意图
- [ ] programmatic 与 CLI live guard 均 fail closed
- [ ] artifact 可绑定 source、manifest、profile、HTTP attempts 与可人工复核的前后状态
- [ ] human-smoke v2、Oracle v2 与历史 artifacts 未覆盖
- [ ] 无 live HTTP、凭据泄漏、SDK-managed execution 或文本协议 fallback

## Stop rule

提交 review handoff 后停止。通过则允许 `TOOL-059-G`；失败只报告 finding，不直接修改实现或生成 Wave 级 artifact。
