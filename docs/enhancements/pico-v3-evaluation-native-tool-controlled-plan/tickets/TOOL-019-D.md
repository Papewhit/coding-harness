# TOOL-019-D — SDK 依赖锁、Lazy Import 与 Transport Wrapper

**Thread type:** `implementer`  
**Wave:** `W3`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-013-S`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

按冻结的 SDK transport decision 更新依赖与 lock，提供 client construction/raw-response/retry/timeout/request-id 的窄 transport wrapper。优先 optional extras + lazy import，缺失时给出明确配置错误。

## Allowed write paths

- `pyproject.toml`
- `uv.lock`
- `pico/providers/provider_transport.py`
- `pico/providers/sdk_imports.py`
- `tests/test_provider_transport.py`
- `.codex/eval/handoffs/TOOL-019-D.json`

## Forbidden write paths

- `pico/core/**`
- `pico/providers/openai_responses.py`
- `pico/providers/anthropic_messages.py`
- `任何 Agent/Tool Runner dependency`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- locked dependency policy
- transport wrapper
- missing-extra diagnostics tests

## Acceptance checklist

- [ ] 版本与 decision artifact 一致
- [ ] Evaluation 可设置 SDK max_retries=0
- [ ] 每个 HTTP attempt 可观测
- [ ] 无自动工具执行
- [ ] `uv sync --extra providers` 或决策指定命令可复现

## Commands

```bash
uv sync --extra providers
```

```bash
uv run pytest tests/test_provider_transport.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
