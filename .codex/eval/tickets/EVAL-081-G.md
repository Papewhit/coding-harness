# EVAL-081-G — 最终 Full Gate 与集成收口

**Plan type:** `integrator` — 由当前 `integrator` 直接执行，不创建新模型 Thread
**Wave:** `W10`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Required Gate: `native_eval_ready=accepted`
- Dependency Ticket: `EVAL-081-R`
- Gate 条件：`native_resume_ready` 必须已经是 `accepted|rejected`；rejected Gate 必须报告，但不阻止本 Ticket。

只读取上述 Gate/依赖的精确 handoff、Freeze 条目和 commits；不要读取其他 Ticket 的完整对话。

## Goal

运行 ruff、全测试、静态 native gate、full human scenario 和 bundle build，记录最终 commit 与 release evidence hash。

## Allowed write paths

- `.codex/eval/handoffs/EVAL-081-G.json`
- `.codex/eval/state/FREEZE.json`

## Forbidden write paths

- `frozen fixture/oracle/taskset，除非版本升级并重跑`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- final gate handoff
- release SHA/hash
- Wave `passed|blocked` decision

## Acceptance checklist

- [ ] ruff/pytest 全通过
- [ ] architecture/safety/permissions/tool-policy 通过
- [ ] Runtime/online evaluator 无文本协议路径
- [ ] `native_eval_ready=accepted`；`native_resume_ready` 已决定且 claim scope 与其结论一致
- [ ] human scenario full gate 结果记录
- [ ] 无 secret/opaque continuation 泄漏
- [ ] 所有主张可追踪

## Commands

```bash
uv run ruff check .
```

```bash
uv run pytest tests -q
```

```bash
grep -RInE "<tool>|<final>" pico scripts benchmarks && exit 1 || true
```

```bash
uv run python scripts/run_v3_human_scenario_gate.py --suite full
```

```bash
uv run python scripts/build_v3_evidence_bundle.py --artifact-root <ARTIFACT_ROOT> --output <ARTIFACT_ROOT>/release-<id>
```

## Notes

- 无额外说明。

## Completion rule

当前 `integrator` 运行最终 Gate，写一份 handoff，并在同一次状态转换中更新 `CURRENT.md` 与正式 `FREEZE.json`。通过后按 CONTROL 执行 W10 `close`，创建最终 Control checkpoint；只有最终 release snapshot 才创建 annotated tag。不得因 `native_resume_ready=rejected` 伪造 Resume claim 或把该已记录结论改成实现 blocker。
