# TOOL-050-QO-R — Native Conformance：Qwen / OpenAI Responses

**Thread type:** `run_shard`  
**Wave:** `W6`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-042-G-R2`
- `TOOL-049-I`
- `TOOL-020-O`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

从 deterministic gate 的同一 run snapshot，使用 `<QWEN_OPENAI_PROFILE>` 执行正式 native conformance，每 case 3 次。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-conformance/<RUN_SHA>/TOOL-050-QO-R/**`
- `.codex/eval/handoffs/TOOL-050-QO-R.json`

## Forbidden write paths

- `所有源码`
- `frozen cases`
- `本地配置写入`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- manifest
- rows.jsonl
- sanitized evidence index

## Acceptance checklist

- [ ] SDK max_retries=0、stream=false、parallel=false
- [ ] 每个 tool-required row 有 native call ID 与 result
- [ ] 失败与 infrastructure rows 全保留
- [ ] text envelope seen 和 hidden SDK retry 可检测
- [ ] opaque continuation 仅记录 hash/type/count

## Commands

```bash
uv run python scripts/run_native_provider_conformance.py --profile <QWEN_OPENAI_PROFILE> --repetitions 3 --output <ARTIFACT_ROOT>/native-provider-conformance/<RUN_SHA>/TOOL-050-QO-R
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
