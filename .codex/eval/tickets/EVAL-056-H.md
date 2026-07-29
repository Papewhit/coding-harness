# EVAL-056-H — Native Harness Evidence and Private-config Contract

**Thread type:** `implementer`
**Wave:** `W6R2`
**Base SHA:** 由 Integrator 填写，并应用已验收的 `TOOL-055-E` dependency commit。

## Start conditions

- `TOOL-055-E`
- `EVAL-052-H`

## Goal

把有序安全链证明纳入正式 conformance bundle，并冻结 public provider identity 与私有运行配置之间无歧义的启动契约。

## Allowed write paths

- `pico/evaluation/native_provider.py`
- `scripts/run_native_provider_conformance.py`
- `tests/test_native_provider_evaluator.py`
- `tests/test_native_provider_cli.py`
- `.codex/eval/handoffs/EVAL-056-H.json`

## Forbidden write paths

- `benchmarks/v3/native-provider/cases.json`
- `pico/cli.py`、`pico/config/**`、provider adapters
- 动态 runner injection、SDK-managed tool execution
- 本地配置、credential、raw URL 或配置路径写入公开 artifact

## Frozen launch contract

- `--provider` 只标识本地 Pico profile name。
- `--expected-profile` 只接受冻结的 sanitized public profile JSON。
- 私有配置文件只由 `PICO_NATIVE_PROVIDER_CONFIG` 定位；正式 shard 必须显式设置，locator 值不得持久化。
- locator 缺失、文件不可读或 public identity 不匹配时 fail closed，产生 0-row `not_computable` preflight bundle。

## Acceptance checklist

- [ ] 每个 row/evidence entry 绑定 `case_id`、`repetition`、native call ID 与完整有序安全链
- [ ] aggregate/verifier 检查阶段顺序、完整性与 bypass，不能仅接受汇总计数
- [ ] OpenAI Responses 与 Anthropic Messages 产物 schema、指标和验证规则完全一致
- [ ] CLI tests 覆盖 locator 缺失、private/public mismatch、0-row failure 与成功路径
- [ ] manifest 记录 locator mechanism 与 public-profile hash，但不记录 locator 值、配置文件 hash、credential 或 raw URL
- [ ] JSON/JSONL bundle 写入后重新解析并验证 hashes；脱敏不破坏格式
- [ ] frozen cases 字节不变

## Commands

```bash
uv run pytest tests/test_native_provider_evaluator.py tests/test_native_provider_cli.py -q
uv run python scripts/run_native_provider_conformance.py --help
uv run ruff check pico/evaluation/native_provider.py scripts/run_native_provider_conformance.py tests/test_native_provider_evaluator.py tests/test_native_provider_cli.py
```

## Stop rule

完成实现、测试、commit 与 handoff 后停止；不得生成 live artifacts、修改 R2 结果或更新正式状态。
