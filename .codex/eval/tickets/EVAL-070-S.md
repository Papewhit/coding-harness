# EVAL-070-S — Context Ablation Case Selection

**Plan type:** `reviewer` — 使用 `reviewer` Thread；可以写本 Ticket 明确允许的 review/proposal Artifact
**Wave:** `W9`
**Review binding:** 由 `integrator` 填写精确 `base_sha`、`candidate_sha` 与 Artifact hashes。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Required Gate: `native_resume_ready=accepted`
- Dependency Ticket: `EVAL-050-M`
- Dependency Ticket: `EVAL-061-M`
- Dependency Ticket: `EVAL-070-I`
- 可选分支：只有 `program_supervisor` 明确决定执行 Context Ablation 后，本 Ticket 才适用；未选择时 `integrator` 执行 `mark_not_applicable`，reason=`optional_branch_not_selected`。
- 适用条件：若 `native_resume_ready=rejected`，reason=`required_gate_rejected` 优先，本 Ticket 不启动。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Ticket-local terms

- **Worker notification**：Context contract 中已有的 worker-event 通知资产；它只用于选择依赖该资产的 case，不用于计算收益。

## Goal

选择 4–6 个确实依赖 resume/working-control/durable/skills assets 的 case，并记录结构化依赖理由。

## Allowed write paths

- `benchmarks/v3/context-ablation/selection.json`
- `.codex/eval/proposals/EVAL-070-S.freeze.json`
- `.codex/eval/handoffs/EVAL-070-S.json`

## Forbidden write paths

- `frozen taskset、Runtime、结果 rows`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- selection.json
- freeze hash

## Acceptance checklist

- [ ] 每 case 有依赖理由
- [ ] 不加入无关任务扩大样本
- [ ] Worker notification 不用于收益对比
- [ ] 最多 6 cases
- [ ] selection 绑定 Context contract 与 native profile hash

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

只运行本 Ticket 所需的短时只读 evidence/verifier 检查。长时、重复或 live 命令由 `reviewer` 提交精确 Process manifest，`integrator` 启动 Process。完整日志写文件；handoff 只记录命令、exit code、数量摘要、路径和 SHA-256。不得运行无关 full suite。

## Notes

- 无额外说明。

## Completion rule

先把 `benchmarks/v3/context-ablation/selection.json` 形成一个语义 commit；`.codex/eval/proposals/EVAL-070-S.freeze.json`、handoff 和其他 `.codex/eval/**` 控制文件不得进入该 commit。随后按 `templates/REVIEW.md` 与 `templates/HANDOFF.md` 返回 review handoff。Finding 必须分类为 `implementation_defect|measurement_defect|evaluation_failure|change_request`。`reviewer` 不修改产品实现、不设置 Wave 状态。
