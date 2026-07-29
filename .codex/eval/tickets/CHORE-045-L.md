# CHORE-045-L — Readable Session Repository Ruff Baseline Repair

**Thread type:** `implementer`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；必须等于 W5R `wave_base_sha`。

## Start conditions

- W5 Gate 的 repository Ruff artifact

## Goal

机械清理 `scripts/readable_session.py` 中既有的 F401/F541，使 `uv run ruff check .` 可作为真实 Gate。不得改变脚本行为或输出。

## Allowed write paths

- `scripts/readable_session.py`
- `.codex/eval/handoffs/CHORE-045-L.json`

## Forbidden write paths

- Ruff 配置、规则禁用、`noqa`
- 脚本行为、输出文本或 CLI contract 变化
- 其他源码与 tests

## Deliverables

- unused import 删除
- placeholder-free f-string 机械还原为普通字符串
- handoff

## Acceptance checklist

- [ ] 变更只对应 F401/F541
- [ ] 脚本输出常量逐字不变
- [ ] repository Ruff 通过

## Commands

```bash
uv run ruff check .
```

```bash
git diff --check
```

## Stop rule

完成 commit 与 handoff 后停止；不得修改 Ruff 配置或正式状态。
