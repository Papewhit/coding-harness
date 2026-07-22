# TOOL-043-R — Structured Retry-after-read Policy Remediation

**Thread type:** `implementer`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；必须等于 W5R `wave_base_sha`。

## Start conditions

- `TOOL-040-I`
- `TOOL-041-M`
- W5 blocked handoff 中 `TOOL-042-G-NEW-001` 的证据

## Goal

修复 native loop 中 `prior_read_required → successful read_file → identical mutation retry` 被误判为 `repeated_identical_call` 的回归。Repetition policy 只消费结构化 result metadata，不解析面向用户的渲染文本。

## Allowed write paths

- `pico/core/tool_repetition.py`
- `pico/core/session_lifecycle.py`
- `tests/test_native_tool_repetition.py`
- `.codex/eval/handoffs/TOOL-043-R.json`

## Forbidden write paths

- protected tests
- provider adapters、Context fixtures、FREEZE
- validation、repetition、permission、ToolPolicy、execute 的既有执行顺序
- 文本错误前缀或 JSON 显示文本解析 fallback

## Deliverables

- 持久化到 internal history 的结构化 `tool_status` / `tool_error_code`
- 仅允许已由同路径成功 fresh read 解锁的 `prior_read_required` mutation retry
- 新增的正反例测试及每项覆盖目的
- handoff

## Acceptance checklist

- [ ] 相同路径的 successful `read_file` 可解锁此前 `prior_read_required` mutation
- [ ] failed read、不同路径 read、其他错误码均不可解锁
- [ ] 已成功或不确定执行的真正重复 mutation 仍被拒绝
- [ ] 不解析 `content`、错误前缀或 JSON 字符串判断内部状态
- [ ] protected retry test 在修复后通过
- [ ] 安全链顺序及拒绝 metadata 不变

## Commands

```bash
uv run pytest tests/test_native_tool_repetition.py tests/test_tool_policy_acceptance.py::test_rejected_patch_can_be_retried_after_informing_read -q
```

```bash
uv run pytest tests/test_native_tool_loop.py tests/test_native_runtime_integration.py tests/test_tool_policy_acceptance.py -q
```

```bash
uv run ruff check pico/core/tool_repetition.py pico/core/session_lifecycle.py tests/test_native_tool_repetition.py
```

## Stop rule

完成 commit 与 handoff 后停止；不得修改正式 STATUS/FREEZE 或开始下游 Gate。
