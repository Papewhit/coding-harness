# TOOL-059-R — Repetition Path Fingerprint 规范化

**Thread type:** `implementer`
**Wave:** `W6R3`

## Start conditions

- `EVAL-059-O`

## Goal

修复同一 workspace 路径使用绝对路径、相对路径或 `.` 别名时绕过 repetition fingerprint 的问题。规范化只服务重复调用判定，不得放宽 workspace、permission 或 ToolPolicy。

## Allowed write paths

- `pico/core/tool_repetition.py`
- `pico/core/runtime.py`
- `tests/test_native_tool_repetition.py`
- `.codex/eval/handoffs/TOOL-059-R.json`

## Forbidden write paths

- Provider adapters、evaluation oracle/fixtures
- permission、ToolPolicy 与 workspace containment 实现
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 同一文件的绝对/相对/规范化路径共享 repetition fingerprint
- [ ] 不同实际路径不得碰撞
- [ ] retry-after-read 仍使用结构化 status/error metadata
- [ ] 路径规范化不替代 workspace containment 或权限检查
- [ ] 既有 repetition 与 tool-policy tests 不退化

## Stop rule

提交 scoped Core 修复、tests 与 handoff 后停止。
