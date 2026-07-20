# EVAL-081-A — 最终 Evidence Bundle 与简历 Claim 生成

**Thread type:** `integrator`  
**Wave:** `W10`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-050-S`
- `TOOL-062-G`
- `EVAL-021-M`
- `EVAL-031-G`
- `EVAL-050-M`
- `EVAL-061-M`
- `EVAL-080`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

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

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

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

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
