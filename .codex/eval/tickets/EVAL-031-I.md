# EVAL-031-I — Structured Context Asset Evaluator Core

**Thread type:** `implementer`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-030`
- `TOOL-010`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

实现对 ModelRequest 的 sentinel 激活、system/messages/tools section attribution、retention/drop/duplication/pointer/metadata 判定和 fragment merge；不调用在线模型。

## Allowed write paths

- `pico/evaluation/context_eval.py`
- `scripts/run_context_asset_evaluation.py`
- `tests/test_context_asset_evaluator.py`
- `.codex/eval/handoffs/EVAL-031-I.json`

## Forbidden write paths

- `pico/core/context_manager.py`
- `pico/core/runtime.py`
- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- structured context evaluator
- script/tests
- fragment merge

## Acceptance checklist

- [ ] 逐资产逐 case 判定
- [ ] current request preservation 独立硬 Gate
- [ ] pointer 验证真实文件
- [ ] tools schema 与 system prompt 分开计量
- [ ] 不读取 opaque continuation 内容

## Commands

```bash
uv run pytest tests/test_context_asset_evaluator.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
