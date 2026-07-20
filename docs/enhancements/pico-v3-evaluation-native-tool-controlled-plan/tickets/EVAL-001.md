# EVAL-001 — 统一 Artifact Contract、Native Protocol 字段与脱敏基础设施

**Thread type:** `implementer`  
**Wave:** `W0`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-000`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

扩展统一 artifact contract，使所有后续 rows 能记录 source/profile/wire dialect/adapter mode/SDK version/capabilities/retry/HTTP attempts/call-result 指标，同时保持旧字段语义与分母可审计。

## Allowed write paths

- `pico/evaluation/contracts.py`
- `tests/test_evaluation_contracts.py`
- `.codex/eval/handoffs/EVAL-001.json`

## Forbidden write paths

- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`
- `pico/evaluation/__init__.py`
- `pico/evaluation/metrics.py`
- `产品 Runtime`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- contract schema/version
- native protocol metadata schema
- sanitization tests

## Acceptance checklist

- [ ] 新增字段不静默改变旧字段
- [ ] ratio 含 numerator/denominator/excluded
- [ ] 记录 native_tool_call_observed、call_id_result_match、batch completeness、duplicate after result、protocol errors、HTTP attempts、SDK/Pico retry
- [ ] profile identity 不含 secret
- [ ] opaque continuation 只允许 hash/type/count

## Commands

```bash
uv run pytest tests/test_evaluation_contracts.py -q
```

```bash
uv run ruff check pico/evaluation/contracts.py tests/test_evaluation_contracts.py
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
