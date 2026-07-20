# TOOL-049-I — Native Provider Conformance Evaluator 与 Runner

**Thread type:** `implementer`  
**Wave:** `W5`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-040-I`
- `EVAL-001`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现正式 native conformance case set、runner、rows 和聚合输入；指标替代旧的文本标签合法率。

## Allowed write paths

- `pico/evaluation/native_provider.py`
- `scripts/run_native_provider_conformance.py`
- `tests/test_native_provider_evaluator.py`
- `benchmarks/v3/native-provider/**`
- `.codex/eval/handoffs/TOOL-049-I.json`

## Forbidden write paths

- `provider adapter/Core Runtime`
- `本地密钥配置`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- 8-case conformance suite
- runner and metric definitions
- synthetic evaluator tests

## Acceptance checklist

- [ ] 覆盖 final、single call、unicode、invalid args repair、permission denial、multi-round patch/verify、unexpected multi-call、opaque block roundtrip
- [ ] 输出 call_id_result_match、batch completeness、duplicate after result、protocol errors、HTTP attempts、text envelope seen
- [ ] 不把 infrastructure failure 静默删除
- [ ] 不包含 process restart（由 Gate N2 覆盖）

## Commands

```bash
uv run pytest tests/test_native_provider_evaluator.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
