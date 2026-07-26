# EVAL-050-R — Local Task Pilot Review 与正式参数冻结

**Plan type:** `reviewer` — 使用 `reviewer` Thread；可以写本 Ticket 明确允许的 review/proposal Artifact
**Wave:** `W7`
**Review binding:** 由 `integrator` 填写精确 `base_sha`、`candidate_sha` 与 Artifact hashes。

## Start conditions

- Dependency Ticket: `EVAL-050-P`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

审查 task/verifier/runner/profile 的有效性，冻结正式 run 的预算、Pico attempts、temperature 和 failure taxonomy；不得按 pilot 结果删题。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-pilot/review.md`
- `.codex/eval/proposals/EVAL-050-R.freeze.json`
- `.codex/eval/handoffs/EVAL-050-R.json`

## Forbidden write paths

- `产品源码、taskset、raw rows`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- pilot review
- formal run config freeze

## Acceptance checklist

- [ ] 无 hidden verifier 泄漏
- [ ] 无文本 fallback 或 protocol mismatch
- [ ] 基础设施失败与任务失败区分
- [ ] 不基于表现修改 task prompt/oracle
- [ ] 正式 shard 参数完全冻结

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

只运行本 Ticket 所需的短时只读 evidence/verifier 检查。长时、重复或 live 命令由 `reviewer` 提交精确 Process manifest，`integrator` 启动 Process。完整日志写文件；handoff 只记录命令、exit code、数量摘要、路径和 SHA-256。不得运行无关 full suite。

## Notes

- 无额外说明。

## Completion rule

按 `templates/REVIEW.md` 与 `templates/HANDOFF.md` 返回一份 review handoff。Finding 必须分类为 `implementation_defect|measurement_defect|evaluation_failure|change_request`。`reviewer` 不修改产品实现、不设置 Wave 状态；同一 Candidate 的后续 revision 可以在本 Thread 继续 review。
