# TEST-046-P — Explicit Scripted Provider Profile Migration

**Thread type:** `implementer`

**Wave:** `W5R2`

**Base SHA:** 由 Integrator 填写；必须等于 W5R2 `wave_base_sha`。

## Goal

完成普通 Runtime tests 的显式 scripted-native provider profile 迁移，消除 W5R full suite 中直接抛出 `native Runtime requires a locked provider_profile` 的 fixture 前置失败。

## Scope

迁移 PLAN 允许的九个测试模块及共享 `tests/native_fixtures.py`。每个 Runtime builder 必须显式锁定 deterministic test profile，或显式使用携带同等 profile identity 的 named native fake。不得依赖 import-time、autouse 或 recorder monkey patch。

## Deliverables

- 可复用且明确命名的 scripted-native profile fixture contract
- 普通测试 builders 的机械迁移
- 既有测试名称与 assertion AST 对照 artifact
- missing-profile negative control 与 profile/tool-schema identity tests
- handoff

## Acceptance checklist

- [ ] 未恢复 `tests/conftest.py` 或任何 global/autouse patch
- [ ] 既有测试只改 imports、fixture/client/agent construction
- [ ] 既有测试名称、断言与安全语义保持不变
- [ ] fake client/profile 不包含 SDK objects，session 内容 JSON-safe
- [ ] missing profile 仍被 Runtime 明确拒绝
- [ ] 本 ticket 所有目标模块不再出现 locked-provider-profile 前置失败
- [ ] 不新增 Runtime fallback、skip 或 xfail

## Commands

```bash
uv run pytest tests/test_provider_profile_fixture_integrity.py tests/test_pico.py tests/test_engine_acceptance.py tests/test_context_governance_acceptance.py tests/test_release_smoke.py tests/test_v3_runtime.py tests/test_skills_acceptance.py tests/test_runtime_evidence_acceptance.py tests/test_usage.py tests/test_todo_ledger_acceptance.py -q
uv run ruff check tests/native_fixtures.py tests/test_provider_profile_fixture_integrity.py
rg -n "monkeypatch.*NativeSessionRecorder|testing\.ScriptedModelClient|pytest_collection" tests
```

## Stop rule

完成 commit、artifact 与 handoff 后停止；不得处理 worker/TUI 专属失败、修改生产源码或正式 STATUS/FREEZE。
