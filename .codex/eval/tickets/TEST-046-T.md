# TEST-046-T — Explicit TUI Native Profile Fixture Recovery

**Thread type:** `implementer`

**Wave:** `W5R2`

**Base SHA:** 由 Integrator 填写，并应用 `TEST-046-P` dependency commit。

## Goal

让 TUI tests 显式使用 scripted-native provider profile，并重新验证 W5R 中直接报错或间接 timeout 的七项交互。

## Acceptance checklist

- [ ] 只修改 TUI test fixture construction
- [ ] 不修改生产 TUI，不放大 timeout
- [ ] final rendering、transcript layout、tool card、approval、ask-user 与 subagent 测试通过原断言
- [ ] 不修改既有测试名称、断言或交互语义
- [ ] 无 global/autouse patch、skip 或 xfail
- [ ] profile 修复后仍存在的失败作为独立产品缺陷记录

## Commands

```bash
uv run pytest tests/test_tui.py -q
uv run ruff check tests/test_tui.py
```

## Stop rule

完成 commit、测试与 handoff 后停止；不得修改生产源码或正式 STATUS/FREEZE。
