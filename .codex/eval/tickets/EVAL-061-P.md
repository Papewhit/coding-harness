# EVAL-061-P — Resume Pilot 与 Native 中断谓词冻结

**Plan type:** `reviewer` — 使用 `reviewer` Thread；可以写本 Ticket 明确允许的 review/proposal Artifact
**Wave:** `W8`
**Review binding:** 由 `integrator` 填写精确 `base_sha`、`candidate_sha` 与 Artifact hashes。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Required Gate: `native_resume_ready=accepted`
- Dependency Ticket: `EVAL-050-R`
- Dependency Ticket: `EVAL-060`
- Dependency Ticket: `TOOL-062-G`
- 适用条件：若 `native_resume_ready=rejected`，不得启动本 Ticket；`integrator` 执行 `mark_not_applicable`，reason=`required_gate_rejected`。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

从 9 tasks 选择 3 个轨迹稳定且 native-resume-eligible 的任务，运行 uninterrupted pilot，冻结 K1/K2 事件谓词。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-5-resume-pilot/**`
- `.codex/eval/proposals/EVAL-061-P.freeze.json`
- `.codex/eval/handoffs/EVAL-061-P.json`

## Forbidden write paths

- `taskset、runner source、产品 Runtime`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- selected task IDs
- pilot traces
- resume predicate freeze

## Acceptance checklist

- [ ] 覆盖 bugfix/patch-validation/small feature 或 CLI
- [ ] K1 在首次 mutation 前且 native batch/checkpoint 落盘
- [ ] K2 在首次有效 mutation/result 后且 checkpoint 落盘
- [ ] 不使用时间点 kill
- [ ] predicate 引用 `native_resume_ready` Gate hash

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

`reviewer` 提交精确 Process manifest；`integrator` 在 Gate 与 live 授权有效时启动 Pilot Process。`reviewer` 不在模型 Thread 中守候命令，只分析返回的 Artifact，并仅运行必要的短时只读 verifier。完整日志写文件；handoff 只记录命令、exit code、数量摘要、路径和 SHA-256。

## Notes

- 无额外说明。

## Completion rule

按 `templates/REVIEW.md` 与 `templates/HANDOFF.md` 返回一份 review handoff。Finding 必须分类为 `implementation_defect|measurement_defect|evaluation_failure|change_request`。`reviewer` 不修改产品实现、不设置 Wave 状态；同一 Candidate 的后续 revision 可以在本 Thread 继续 review。
