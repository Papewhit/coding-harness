# TOOL-051-L — Fixed Production Native Conformance Live Runner

**Thread type:** `implementer`
**Wave:** `W6R`
**Base SHA:** 由 Integrator 填写，必须等于本波 `wave_base_sha`。

## Start conditions

- `TOOL-042-G-R2`
- `TOOL-040-I`
- `TOOL-049-I`
- `TOOL-050-S`

读取 W6 handoff 与上述依赖的持久化 handoff/freeze；不要依赖 W6 长对话。

## Goal

实现固定、可审计的 live case runner，并明确区分本地运行配置与评测公开身份。runner 必须调用 production Pico Runtime，而不是 SDK Tool/Agent Runner 或重新实现工具循环。

## Allowed write paths

- `pico/evaluation/native_provider_live.py`
- `pico/evaluation/native_provider_profiles.py`
- `scripts/build_native_provider_profile.py`
- `tests/test_native_provider_live.py`
- `tests/test_native_provider_profile_cli.py`
- `benchmarks/v3/native-provider/profile.schema.json`
- `benchmarks/v3/native-provider/profile.example.json`
- `.codex/eval/handoffs/TOOL-051-L.json`

## Forbidden write paths

- `benchmarks/v3/native-provider/cases.json`
- `pico/cli.py`
- provider adapters、Core Runtime、ToolPolicy
- 动态 runner plugin 或 SDK-managed tool execution
- 本地配置与凭据写入

未列出的写路径默认禁止；若现有 Runtime 无法提供结构化 observation，停止并提交 ownership change request。

## Acceptance checklist

- [ ] 本地 profile 由现有 config resolver 按名称解析；API key/raw URL 只存在于运行时内存
- [ ] public profile 使用版本化 schema，包含 profile name/id、model、endpoint fingerprint、wire dialect、adapter mode、SDK package/version、capabilities、retry/stream/parallel
- [ ] runner 从 resolved config 重新生成 public identity，并与 frozen expected manifest 精确比较
- [ ] 评测专用 profile builder 使用 `--provider` 与 `--manifest-out`，只写 canonical sanitized manifest
- [ ] 每个 case 使用隔离、可重建的 workspace 和明确 approval policy
- [ ] 调用 production `Pico`/`Engine`，工具执行保持既有安全链顺序
- [ ] observation 来自结构化 ModelResponse、session exchange、tool result 与 HTTP-attempt metadata，不解析显示文本
- [ ] native call ID/result、opaque continuation、retry 和 unknown block 均可审计
- [ ] 固定 `stream=false`、`parallel=false`、SDK `max_retries=0`、Pico attempts=1
- [ ] fake transport 覆盖八个 scenario、profile mismatch、secret sentinel 与安全链旁路检测
- [ ] 不发真实 provider HTTP

## Commands

```bash
uv run pytest tests/test_native_provider_live.py -q
uv run pytest tests/test_native_provider_profile_cli.py -q
uv run python scripts/build_native_provider_profile.py --help
uv run ruff check pico/evaluation/native_provider_live.py pico/evaluation/native_provider_profiles.py scripts/build_native_provider_profile.py tests/test_native_provider_live.py tests/test_native_provider_profile_cli.py
```

## Stop rule

完成测试、提交清晰 commit 与 handoff 后停止；不得修改 harness CLI、正式状态或开始下游 ticket。
