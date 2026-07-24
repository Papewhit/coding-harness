# TOOL-059-A-R1 — Anthropic 完整无状态 Transcript 修复

**Thread type:** `implementer`
**Wave:** `W6R3`
**Remediation finding:** `AUDIT-059-A-P1-001`

## Start conditions

- `AUDIT-059-A`

## Goal

当前 W6R3 没有负责 Anthropic Adapter 的既有 worker，因此本 ticket 是唯一新增 owner。先用独立测试稳定复现三轮 context loss 并记录 red baseline，再修复 Anthropic Messages Adapter，使无 server-side state 的每次请求按 Anthropic message ordering 保存并重放原始 Runtime prompt、全部 assistant blocks 与匹配 tool results。不可恢复的旧 continuation必须明确 fail closed。

## Allowed write paths

- `pico/providers/anthropic_messages.py`
- `tests/test_anthropic_stateless_transcript.py`
- `.codex/eval/handoffs/TOOL-059-A-R1.json`

## Forbidden write paths

- OpenAI Responses Adapter、Core/Runtime
- 其他 tests、Oracle、cases、human-smoke fixtures
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] source 修改前记录精确、可复现的三轮 stateless transcript red baseline
- [ ] 同一 ticket 的产品修复使该 red test 变 green
- [ ] 多轮 user/assistant message ordering 合法且完整
- [ ] prompt、call 或 result 不重复、不丢失
- [ ] continuation 只保存 JSON-safe Pico contract，不保存 SDK 对象
- [ ] 不启用 provider storage 或 SDK-managed tool execution
- [ ] 不完整旧 continuation 在 transport 前 fail closed

## Stop rule

提交测试、产品修复与 per-ticket handoff 后停止；handoff 分别记录 red baseline commit 与修复 commit，Integrator 最终按 revision 归一化 canonical payload。不得修改其他 dialect。
