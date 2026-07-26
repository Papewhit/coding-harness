# EVAL-070-M — Context Ablation 聚合

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W9`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Required Gate: `native_resume_ready=accepted`
- Dependency Ticket: `EVAL-070-R`
- 可选分支：只有 `EVAL-070-S` 的分支决定选择 Context Ablation 后，本 Ticket 才启动。
- 适用条件：若 `native_resume_ready=rejected`，不得启动本 Ticket；reason=`required_gate_rejected`。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

逐 case 展示 Full/off 的 success、steps、重复工作、provider/tool retries 和 protocol errors，不用单一均值掩盖方向相反结果。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-6-context-ablation/summary.json`
- `<ARTIFACT_ROOT>/phase-6-context-ablation/summary.md`
- `.codex/eval/handoffs/EVAL-070-M.json`

## Forbidden write paths

- `源码、raw rows、selection`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- summary/evidence index

## Acceptance checklist

- [ ] 无稳定提升时明确写未观察到任务收益
- [ ] 不把 prompt chars 当 token/cost
- [ ] 不把 native protocol 失败归因于 Context 功能

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 直接完成本 Ticket，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md`；本 Ticket 列出 `FREEZE.json` 时直接更新正式 Freeze，不写 status/freeze proposal。依赖满足时继续下一动作，不因 Ticket 完成或 Wave 边界自动停止。
