# EVAL-081-G — 最终 Full Gate 与集成收口

**Thread type:** `integrator`  
**Wave:** `W10`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-081-R`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

运行 ruff、全测试、静态 native gate、full human scenario 和 bundle build，记录最终 commit 与 release evidence hash。

## Allowed write paths

- `.codex/eval/proposals/EVAL-081-G.status.json`
- `.codex/eval/proposals/EVAL-081-G.freeze.json`
- `.codex/eval/handoffs/EVAL-081-G.json`

## Forbidden write paths

- `frozen fixture/oracle/taskset，除非版本升级并重跑`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- final gate handoff
- release SHA/hash
- ready/not-ready decision

## Acceptance checklist

- [ ] ruff/pytest 全通过
- [ ] architecture/safety/permissions/tool-policy 通过
- [ ] Runtime/online evaluator 无文本协议路径
- [ ] Gate N1/N2 accepted
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

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新正式 `STATUS.json`/`FREEZE.json` 或开始下游工作；所需状态变化只写 proposal。
