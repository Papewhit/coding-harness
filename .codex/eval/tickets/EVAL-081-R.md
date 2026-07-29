# EVAL-081-R — 独立 Evidence 与 Native Protocol Audit

**Plan type:** `reviewer` — 使用 `reviewer` Thread；可以写本 Ticket 明确允许的 review/proposal Artifact
**Wave:** `W10`
**Review binding:** 由 `integrator` 填写精确 `base_sha`、`candidate_sha` 与 Artifact hashes。

## Start conditions

- Dependency Ticket: `EVAL-081-A`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

独立复核 claim 到 artifact/rows/hash/formula 的链路，并审计无文本 fallback、SDK 边界、call-result 完整性、retry 口径、secret 与禁止外推。

## Allowed write paths

- `docs/metrics/pico-v3-evaluation-audit.md`
- `.codex/eval/handoffs/EVAL-081-R.json`

## Forbidden write paths

- `产品源码、raw artifact`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- audit report
- `accepted|findings` review verdict

## Acceptance checklist

- [ ] 抽查每类主 claim 至少一个原始 row
- [ ] 确认失败未删除
- [ ] 确认 Native claim 不等同于任务能力提升
- [ ] 确认 Multi-agent 无收益百分比
- [ ] 检查旧 90% recovery/字符压缩/文本协议数字未误用
- [ ] opaque continuation 无泄漏

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

只运行本 Ticket 所需的短时只读 evidence/verifier 检查。长时、重复或 live 命令由 `reviewer` 提交精确 Process manifest，`integrator` 启动 Process。完整日志写文件；handoff 只记录命令、exit code、数量摘要、路径和 SHA-256。不得运行无关 full suite。

## Notes

- 无额外说明。

## Completion rule

先把 `docs/metrics/pico-v3-evaluation-audit.md` 形成一个语义 commit；handoff 和其他 `.codex/eval/**` 控制文件不得进入该 commit。随后按 `templates/REVIEW.md` 与 `templates/HANDOFF.md` 返回 review handoff。Finding 必须分类为 `implementation_defect|measurement_defect|evaluation_failure|change_request`。`reviewer` 不修改产品实现、不设置 Wave 状态。
