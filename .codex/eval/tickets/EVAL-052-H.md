# EVAL-052-H — Versioned Native Conformance Harness Contract

**Thread type:** `implementer`
**Wave:** `W6R`
**Base SHA:** 由 Integrator 填写，必须等于本波 `wave_base_sha`；Integrator 另行提供 `TOOL-051-L` dependency commit。

## Start conditions

- `TOOL-051-L`
- `TOOL-049-I`
- `TOOL-050-S`

## Goal

将正式 conformance harness 统一为一套无歧义、可冻结的 argparse 与 artifact 契约，并原生实现 `(case_id, repetition)` 维度。

## Allowed write paths

- `pico/evaluation/native_provider.py`
- `scripts/run_native_provider_conformance.py`
- `tests/test_native_provider_evaluator.py`
- `tests/test_native_provider_cli.py`
- `.codex/eval/handoffs/EVAL-052-H.json`

## Forbidden write paths

- `benchmarks/v3/native-provider/cases.json`
- `pico/cli.py`、`pico/config/**`、provider adapters
- 全局 evaluation artifact contract
- 任意 `module:callable` formal runner injection

## Frozen CLI contract

```text
--case-set <frozen cases JSON>
--provider <local Pico profile name>
--expected-profile <sanitized public profile JSON>
--repetitions <positive integer>
--artifact-dir <exclusive shard directory>
```

可保留 `--case` 进行诊断性选择，但正式 shard 不得改变冻结的八案例集合。正式 CLI 不再接受含义冲突的 `--profile`、单文件 `--output` 或 `--runner-plugin`。

## Acceptance checklist

- [ ] `--help`、parser failures、public-profile mismatch 和输出路径行为有独立 CLI tests
- [ ] 默认正式命令调用 `TOOL-051-L` 的固定 live runner
- [ ] repetition 为 evaluator 原生维度；顺序固定为 case order × repetition order
- [ ] 每行分别记录 `case_id`、从 1 开始的 `repetition` 与唯一 `row_id`
- [ ] artifact bundle schema 版本化，并原子写入 `manifest.json`、`rows.jsonl`、`evidence-index.json`、`summary.json`
- [ ] manifest 绑定 source/evaluator/cases/live-runner/public-profile/native-gate/SDK-decision hashes
- [ ] case 启动后的 exception 保留对应 infrastructure row
- [ ] parser/profile binding 等 preflight failure 在零 case 启动时写 run-level manifest、0 rows、`not_computable`
- [ ] 公开 artifact 只保留 opaque block 的 hash/type/count，不含 credential/raw URL
- [ ] `cases.json` 内容与既有 frozen hash 完全不变

## Commands

```bash
uv run pytest tests/test_native_provider_evaluator.py tests/test_native_provider_cli.py -q
uv run ruff check pico/evaluation/native_provider.py scripts/run_native_provider_conformance.py tests/test_native_provider_evaluator.py tests/test_native_provider_cli.py
uv run python scripts/run_native_provider_conformance.py --help
```

## Stop rule

完成测试、commit 与 handoff 后停止；不得生成 live artifacts、更新正式状态或启动 reviewer。
