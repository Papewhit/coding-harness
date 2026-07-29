# TOOL-021-P — Provider Profile、Wire Dialect 与 Capability Validation

**Thread type:** `implementer`  
**Wave:** `W3`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `TOOL-010`
- `TOOL-013-S`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

把含糊的 provider protocol 拆为明确 wire dialect 与 capabilities；配置只引用本地 profile，不按 host 猜测。session 创建后锁定 model/profile/dialect/schema。

## Allowed write paths

- `.pico.toml.example`
- `pico/config/__init__.py`
- `pico/providers/__init__.py`
- `pico/cli.py`
- `tests/test_provider_protocol.py`
- `docs/configuration.md`
- `.codex/eval/handoffs/TOOL-021-P.json`

## Forbidden write paths

- `pico/core/**`
- `adapter 实现文件`
- `本地密钥配置`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- config schema
- startup validation
- inspect output and docs

## Acceptance checklist

- [ ] coding profile 的 native_tools=false 为启动错误
- [ ] strict/parallel/reasoning-thinking capabilities 分开记录
- [ ] profile identity 不含 secret
- [ ] 不自动切 endpoint/dialect
- [ ] 旧配置有明确迁移错误或映射

## Commands

```bash
uv run pytest tests/test_provider_protocol.py -q
```

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
