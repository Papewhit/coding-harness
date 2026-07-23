# TOOL-050-DA-R2 — Recovered Native Conformance：DeepSeek / Anthropic Messages

**Thread type:** `run_shard`
**Wave:** `W6R2`
**Base SHA:** 必须等于 `TOOL-058-G` 后正式 FREEZE 中新的 `run_snapshot_sha`。

## Start conditions

- `TOOL-058-G`
- `EVAL-056-H`
- `TOOL-020-A`

## Goal

使用本地 `deepseek` 配置与冻结 public manifest，执行八案例 × 三次正式 native conformance。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-conformance/<RUN_SHA>/TOOL-050-DA-R2/**`
- `.codex/eval/handoffs/TOOL-050-DA-R2.json`

## Forbidden write paths

- 所有源码、frozen cases、public profile manifests、本地配置写入

## Command

```bash
PICO_NATIVE_PROVIDER_CONFIG=<PRIVATE_CONFIG_PATH> uv run python scripts/run_native_provider_conformance.py --case-set benchmarks/v3/native-provider/cases.json --provider deepseek --expected-profile <TOOL-058-G_PUBLIC_PROFILE_JSON> --repetitions 3 --artifact-dir <ARTIFACT_ROOT>/native-provider-conformance/<RUN_SHA>/TOOL-050-DA-R2
```

## Acceptance checklist

- [ ] checkout clean、HEAD 与所有 frozen hashes 完全匹配
- [ ] 在 canonical WSL 环境运行；private config locator 已设置且不进入公开 artifact
- [ ] 成功启动时生成 24 个唯一 `(case_id, repetition)` rows
- [ ] preflight failure 时只生成 0-row failure manifest，不伪造执行 rows
- [ ] 每次真实 HTTP attempt、call/result、retry、protocol error、unknown block 均入 evidence
- [ ] SDK max_retries=0、stream=false、parallel=false
- [ ] 无 text envelope、SDK-managed tool execution 或安全链旁路
- [ ] bundle 四文件与 handoff hashes 可重建，公开输出不含 credential/raw URL

## Stop rule

完成 run artifact 与 handoff 后停止；不提交源码、不汇总其他 profile、不更新正式状态。
