# EVAL-050-M — Local Task Final 聚合与 Baseline Freeze

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W8`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `EVAL-050-F`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

汇总 27 rows，同时报告 run-level success 与每题至少 2/3 成功的 stable task success；保留 native protocol 和 infrastructure 失败分类。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-4-local-tasks-final/summary.json`
- `<ARTIFACT_ROOT>/phase-4-local-tasks-final/summary.md`
- `.codex/eval/handoffs/EVAL-050-M.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `产品源码、raw rows、taskset`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- summary/evidence index/baseline freeze

## Acceptance checklist

- [ ] 27 rows 全部可追踪
- [ ] run/stable task 两种口径并列
- [ ] 协议失败不伪装成任务失败
- [ ] 不外推大型仓库/复杂重构能力

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 直接完成本 Ticket，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md`；本 Ticket 列出 `FREEZE.json` 时直接更新正式 Freeze，不写 status/freeze proposal。依赖满足时继续下一动作，不因 Ticket 完成或 Wave 边界自动停止。
