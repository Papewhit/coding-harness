# TOOL-062-G — `native_resume_ready` Gate

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W8`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `TOOL-061-T`
- Dependency Ticket: `TOOL-062-R`

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

合并 deterministic crash contract 与 selected-profile restart evidence，冻结 native Resume contract/gate；只在所有安全硬约束满足时允许正式 Resume Evaluation。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-resume-conformance/summary.json`
- `<ARTIFACT_ROOT>/native-resume-conformance/summary.md`
- `.codex/eval/handoffs/TOOL-062-G.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `产品源码`
- `raw rows`
- `frozen contract`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- native_resume_gate
- summary
- `CURRENT.md` Gate transition and `FREEZE.json` entry

## Acceptance checklist

- [ ] pending/completed/uncertain 状态恢复正确
- [ ] provider continuation roundtrip=100%
- [ ] completed call replay=0
- [ ] uncertain risky call replay=0
- [ ] profile/dialect mismatch 安全拒绝
- [ ] 至少两个 live restart cases 通过

## Result handling

测量有效但任务、provider 或产品表现失败时，记录为 `evaluation_failure` 并继续；只有 evaluator/runner/evidence/Artifact 绑定关系使结论不可信时才记录 `measurement_defect`。

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 不把 no-checkpoint 计入可恢复成功率分母。

## Completion rule

当前 `integrator` 直接完成本 Ticket，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md`；本 Ticket 列出 `FREEZE.json` 时直接更新正式 Freeze，不写 status/freeze proposal。依赖满足时继续当前 Wave 内的下一动作。当前 Wave close 后停止，不得进入下一 Wave。
