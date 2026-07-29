# TOOL-012-QA-R — SDK Spike：Qwen / Anthropic Messages

**Thread type:** `run_shard`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-012-A`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

使用本地配置 profile `<QWEN_ANTHROPIC_PROFILE>` 运行 SDK viability cases；只判断 anthropic-messages + anthropic SDK 的 wire 兼容性，不作为最终模型能力排名。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-sdk-spike/<RUN_SHA>/TOOL-012-QA-R/**`
- `.codex/eval/handoffs/TOOL-012-QA-R.json`

## Forbidden write paths

- `所有源码`
- `pyproject.toml`
- `uv.lock`
- `本地配置写入`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- manifest
- rows.jsonl
- sanitized raw-response evidence
- handoff

## Acceptance checklist

- [ ] 源码 clean
- [ ] SDK max_retries=0
- [ ] 每个 case 3 次或记录明确 infrastructure exclusion
- [ ] call/result ID 与 unknown blocks 可审计
- [ ] 不保存 secret/opaque thinking 内容

## Commands

```bash
uv run --with anthropic python scripts/run_sdk_viability_probe.py --profile <QWEN_ANTHROPIC_PROFILE> --dialect anthropic-messages --repetitions 3 --output <ARTIFACT_ROOT>/native-sdk-spike/<RUN_SHA>/TOOL-012-QA-R
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
