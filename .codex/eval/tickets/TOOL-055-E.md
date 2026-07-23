# TOOL-055-E — Dual-Dialect Runner Parity and Safety-chain Evidence

**Thread type:** `implementer`
**Wave:** `W6R2`
**Base SHA:** 由 Integrator 填写，必须等于本波 `wave_base_sha`。

## Start conditions

- `TOOL-051-L`
- `EVAL-052-H`
- `TOOL-053-A`

## Goal

使 OpenAI Responses 与 Anthropic Messages 的固定 production runner 回归验证严格对称，并从真实 Pico 工具执行路径产生可关联、可排序的结构化安全链证据。

## Allowed write paths

- `pico/evaluation/native_provider_live.py`
- `pico/core/tool_executor.py`
- `tests/test_native_provider_live.py`
- `tests/test_native_safety_chain_evidence.py`
- `.codex/eval/handoffs/TOOL-055-E.json`

## Forbidden write paths

- `benchmarks/v3/native-provider/cases.json`
- provider adapters、ToolPolicy 规则、permission 行为
- `pico/evaluation/native_provider.py` 与正式 artifact writer
- 本地配置、public profile 与凭据

## Acceptance checklist

- [ ] 两种 wire dialect 在仓库测试中运行同一冻结八案例，case、repetition 与断言集合一致
- [ ] 两种 dialect 都覆盖 call/result、batch、denial、repair、opaque continuation、retry、unknown block 与 text-envelope
- [ ] 每次工具调用产生绑定 `case_id`、`repetition`、native call ID 的结构化阶段证据
- [ ] 阶段证据可证明 `validate → repetition → permission → policy → execute` 的到达、拒绝或完成顺序
- [ ] evidence 来自 production Pico 执行路径，不依赖 monkey patch、显示文本解析或 SDK-managed tool execution
- [ ] 不改变既有安全链顺序、判定语义或冻结 cases

## Commands

```bash
uv run pytest tests/test_native_provider_live.py tests/test_native_safety_chain_evidence.py -q
uv run ruff check pico/evaluation/native_provider_live.py pico/core/tool_executor.py tests/test_native_provider_live.py tests/test_native_safety_chain_evidence.py
```

## Stop rule

完成实现、测试、commit 与 handoff 后停止；不得修改 artifact contract、运行 live provider 或更新正式状态。若所需证据必须扩大 Core ownership，提交 ownership change request 后停止。
