# TOOL-046-W — Worker Child Provider Profile Contract

**Thread type:** `implementer`

**Wave:** `W5R2`

**Base SHA:** 由 Integrator 填写，并应用 `TEST-046-P` dependency commit。

## Goal

恢复 worker acceptance tests，并验证 parent/child native profile 生命周期。先证明 W5R 的四个 event-wait failure 是否由 profile 前置退出造成；不得预设 worker event 产品逻辑已回归。

## Contract

- parent 与 child session 都必须在 NativeSessionRecorder 前拥有明确 profile。
- child profile 的 provider/model/wire identity 与实际 client 一致。
- child `tool_schema` 必须匹配 child 最终启用的 readonly/worker tool profile；不得盲目复制 parent 的 schema。
- 如正式 `build_child_runtime` 不能满足该契约，可在唯一允许的生产文件中做最小修复。

## Deliverables

- worker profile lifecycle 回归测试
- 原四个 event waits 确实进入 blocking fake request 的证据
- 全部 worker acceptance tests 结果
- 如修改 production，说明缺陷、行为变化与安全不变量
- handoff

## Acceptance checklist

- [ ] 不修改既有 worker test 名称、断言或 timeout
- [ ] async worker request 实际启动，event wait 不再被 profile 前置错误遮蔽
- [ ] worker notification、send-message、stop、clear-session 语义通过原断言
- [ ] child profile/tool schema identity 有直接断言
- [ ] 不放宽 session profile requirement，不持久化 SDK objects
- [ ] 若 profile 修复后仍有失败，handoff 将其作为独立产品缺陷报告

## Commands

```bash
uv run pytest tests/test_native_worker_profile.py tests/test_agent_workers_acceptance.py -q
uv run ruff check pico/core/worker_runtime.py tests/test_native_worker_profile.py tests/test_agent_workers_acceptance.py
```

## Stop rule

完成 commit、测试与 handoff 后停止；不得修改 TUI、provider adapter 或正式 STATUS/FREEZE。
