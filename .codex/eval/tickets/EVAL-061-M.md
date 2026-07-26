# EVAL-061-M — Native Resume Paired 聚合

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W9`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Required Gate: `native_resume_ready=accepted`
- Dependency Ticket: `EVAL-061-R`
- 适用条件：若 `native_resume_ready=rejected`，不得启动本 Ticket；`integrator` 执行 `mark_not_applicable`，reason=`required_gate_rejected`。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

聚合 Resume vs Cold 的最终完成、额外工具步骤、重复 read/search/test、冲突写入和 protocol errors；no-checkpoint 等 contract cases 不进入可恢复分母。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-5-resume/summary.json`
- `<ARTIFACT_ROOT>/phase-5-resume/summary.md`
- `.codex/eval/handoffs/EVAL-061-M.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `产品源码、raw rows、frozen predicates`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- paired summary
- evidence index
- resume freeze

## Acceptance checklist

- [ ] pair 数与 exclusions 明确
- [ ] 最终成功和重复工作同时报告
- [ ] protocol/restart failure 独立分类
- [ ] 不复用旧 90% recovery 口径

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 直接完成本 Ticket，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md`；本 Ticket 列出 `FREEZE.json` 时直接更新正式 Freeze，不写 status/freeze proposal。依赖满足时继续当前 Wave 内的下一动作。当前 Wave close 后停止，不得进入下一 Wave。
