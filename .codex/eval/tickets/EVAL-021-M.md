# EVAL-021-M — Auto-dream 结果聚合与 Freeze

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W7`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `EVAL-021-R`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

合并两个 native live shard 与生命周期证据，输出事实保留/更新/过滤/幂等指标、协议失败明细和产品缺陷。

## Allowed write paths

- `<ARTIFACT_ROOT>/phase-1-auto-dream/summary.json`
- `<ARTIFACT_ROOT>/phase-1-auto-dream/summary.md`
- `.codex/eval/handoffs/EVAL-021-M.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `Dream 产品源码`
- `frozen fixtures/oracle`
- `raw rows`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- summary/evidence index/freeze entry

## Acceptance checklist

- [ ] 24 个语义 run 均有 row 或明确 exclusion
- [ ] 4 个生命周期 case 均入 artifact
- [ ] native protocol failures 与 Dream semantic failures 分开
- [ ] 不外推 Coding Task 成功率

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 直接完成本 Ticket，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md`；本 Ticket 列出 `FREEZE.json` 时直接更新正式 Freeze，不写 status/freeze proposal。依赖满足时继续下一动作，不因 Ticket 完成或 Wave 边界自动停止。
