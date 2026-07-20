# EVAL-081-R — 独立 Evidence 与 Native Protocol Audit

**Thread type:** `reviewer`  
**Wave:** `W10`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-081-A`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

独立复核 claim 到 artifact/rows/hash/formula 的链路，并审计无文本 fallback、SDK 边界、call-result 完整性、retry 口径、secret 与禁止外推。

## Allowed write paths

- `docs/metrics/pico-v3-evaluation-audit.md`
- `.codex/eval/handoffs/EVAL-081-R.json`

## Forbidden write paths

- `产品源码、raw artifact`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- audit report
- accept/changes_requested/block

## Acceptance checklist

- [ ] 抽查每类主 claim 至少一个原始 row
- [ ] 确认失败未删除
- [ ] 确认 Native claim 不等同于任务能力提升
- [ ] 确认 Multi-agent 无收益百分比
- [ ] 检查旧 90% recovery/字符压缩/文本协议数字未误用
- [ ] opaque continuation 无泄漏

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
