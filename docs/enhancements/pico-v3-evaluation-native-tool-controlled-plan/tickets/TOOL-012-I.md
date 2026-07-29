# TOOL-012-I — SDK Viability Probe 通用 Harness

**Thread type:** `implementer`  
**Wave:** `W1`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现不依赖产品 Runtime 的 SDK viability harness、case schema、raw response capture、脱敏 manifest 与 shard runner。SDK 通过 `uv run --with` 临时加载，不修改生产依赖。

## Allowed write paths

- `pico/evaluation/sdk_probe.py`
- `scripts/run_sdk_viability_probe.py`
- `tests/test_sdk_probe.py`
- `benchmarks/v3/sdk-viability/**`
- `.codex/eval/handoffs/TOOL-012-I.json`

## Forbidden write paths

- `pyproject.toml`
- `uv.lock`
- `pico/providers/**`
- `产品 Runtime`
- `本地密钥文件`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- probe case schema
- generic runner and artifact contract
- fake transport tests

## Acceptance checklist

- [ ] 支持 final/native call/result roundtrip/invalid args/unicode/opaque block cases
- [ ] 支持 profile 和 dialect plugin
- [ ] raw response 只保存脱敏内容或 hash
- [ ] 记录 SDK retry 与 HTTP attempt
- [ ] 不实现模型选择或产品 Adapter

## Commands

```bash
uv run pytest tests/test_sdk_probe.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
