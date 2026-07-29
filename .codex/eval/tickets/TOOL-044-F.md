# TOOL-044-F — Protected Native Fixture Migration Without Global Patches

**Thread type:** `implementer`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；必须等于 W5R `wave_base_sha`。

## Start conditions

- `TOOL-041-M`
- W5 blocked snapshot 与 `tests/conftest.py` audit
- 用户已授权仅机械修改 protected test 的 fixture construction

## Goal

删除 W5 引入的全局 pytest monkey patches，让 protected tests 直接构造 native `ModelResponse`、native client 与显式 provider profile。保持 protected test 的名称、断言和安全语义不变。

## Allowed write paths

- `tests/conftest.py`（删除）
- `tests/native_fixtures.py`
- `tests/test_tool_policy_acceptance.py`
- `tests/test_safety_invariants.py`
- `tests/test_permissions_acceptance.py`
- `tests/test_fixture_migration_integrity.py`
- `<ARTIFACT_ROOT>/w5r-fixture-migration/**`
- `.codex/eval/handoffs/TOOL-044-F.json`

## Forbidden write paths

- production source 与 `pico/testing.py`
- protected test 名称、`assert`、权限矩阵或安全语义
- skip、xfail、条件绕过、测试收集 hook
- autouse monkey patch、import-time replacement 或 legacy text adapter

## Deliverables

- 删除全局 conftest shim
- protected tests 的显式 native fixture construction
- protected test 名称与 assertion AST 对照报告
- fixture-only negative-control artifact
- 新增控制测试及每项覆盖目的
- handoff

## Acceptance checklist

- [ ] `tests/conftest.py` 不存在
- [ ] protected tests 不再输入 `<tool>/<final>` fixture
- [ ] CLI fake 显式实现 native request contract
- [ ] provider profile 在构造 agent/session 时显式提供
- [ ] protected test 名称和 assertion AST 与 W5 blocked snapshot 一致
- [ ] 不删除既有测试函数或断言，不新增 skip/xfail
- [ ] fixture-only snapshot 未应用 TOOL-043-R 时仍精确捕获 retry-after-read 回归
- [ ] 不存在全局或 autouse Runtime/client patch

## Commands

```bash
uv run pytest tests/test_fixture_migration_integrity.py -q
```

```bash
uv run pytest tests/test_safety_invariants.py tests/test_tool_policy_acceptance.py tests/test_permissions_acceptance.py -k "not test_rejected_patch_can_be_retried_after_informing_read" -q
```

```bash
rg -n "<tool|<final>|monkeypatch.*NativeSessionRecorder|testing\.ScriptedModelClient" tests
```

## Negative control

在 Ubuntu WSL2 的隔离 fresh clone 中，将本 ticket patch 应用于 W5 blocked snapshot，但不应用 `TOOL-043-R`。运行 protected suite并记录 JUnit；retry-after-read 必须保持为唯一的产品语义失败，其他 fixture migration 不得引入新失败。Negative control 不得修改本 ticket 分支；不得使用 sudo、skip、xfail 或失败重分类。

## Stop rule

完成 commit、negative-control artifact 与 handoff 后停止；不得实现 retry fix、修改正式 STATUS/FREEZE 或开始 Gate。
