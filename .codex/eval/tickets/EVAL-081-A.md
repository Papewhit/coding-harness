# EVAL-081-A — 最终 Evidence Bundle 与简历 Claim 生成

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W10`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Dependency Ticket: `TOOL-050-S-R1`
- Dependency Ticket: `TOOL-062-G`
- Dependency Ticket: `EVAL-021-M`
- Dependency Ticket: `EVAL-031-G`
- Dependency Ticket: `EVAL-050-M`
- Dependency Ticket: `EVAL-061-M`
- Dependency Ticket: `EVAL-080`
- Gate 条件：`native_resume_ready` 必须已经是 `accepted|rejected`。
- 依赖例外：只有 `EVAL-061-M=not_applicable` 的 reason=`required_gate_rejected` 且绑定被拒绝的 `native_resume_ready` Gate 时，才视为满足该依赖。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

构建最终 bundle 和 claim registry；Context Ablation 若完成则纳入，否则标记 optional missing。单独生成 Native Tool Calling 技术与证据说明。

## Allowed write paths

- `docs/metrics/pico-v3-evaluation-report.md`
- `docs/metrics/pico-v3-resume-claims.md`
- `docs/metrics/pico-v3-native-tool-calling.md`
- `docs/metrics/pico-v3-evaluation-limitations.md`
- `<ARTIFACT_ROOT>/release-<id>/**`
- `.codex/eval/handoffs/EVAL-081-A.json`

## Forbidden write paths

- `frozen evaluator/taskset/raw artifacts`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- release bundle
- reports
- claim registry

## Acceptance checklist

- [ ] source/taskset/evaluator/profile/native gate 兼容
- [ ] 每个数字含分子分母适用范围
- [ ] Native claim 区分 protocol conformance 与 coding effectiveness
- [ ] limitations 含小仓库/单语言/单 selected profile/无网络/有限复杂度
- [ ] 不臆造占位符数字

## Commands

当前 `integrator` 使用既有 runner/聚合脚本执行本 Ticket，并验证输入/输出 hashes。若 source 未改变，不重跑产品 full suite；只运行直接相关的格式、公式、Artifact integrity 或 Gate 检查。

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 先生成并验证 release docs/Artifacts；把四个 `docs/metrics/*.md` 的 Git-tracked 变更形成一个 Accepted commit，排除 handoff、CURRENT、FREEZE 和其他 `.codex/eval/**` 文件；再写 handoff 并更新 `CURRENT.md`。当 `native_resume_ready=rejected` 时，Resume 报告只记录 Gate 结论与 limitation，不生成效果 claim。依赖满足时继续 `EVAL-081-R`。
