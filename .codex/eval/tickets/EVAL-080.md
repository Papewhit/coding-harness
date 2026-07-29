# EVAL-080 — Evidence Bundle、Native Claim Registry 与 Hash Compatibility

**Thread type:** `implementer`  
**Wave:** `W2`  
**Base SHA:** 由 Integrator 在启动 prompt 中填写；实现 ticket 必须等于本波 `wave_base_sha`，run shard 必须等于冻结的 `run_snapshot_sha`。

## Start conditions

- `EVAL-001`

只读取上述依赖的 handoff/freeze；不要读取其他 ticket 的完整对话。

## Goal

扩展 bundle/claim registry，使 Native Tool Calling、SDK transport、selected profile、Auto-dream、Local Task、Resume 和 Context claims 都能绑定 rows/hash/formula/限制；支持 live 结果尚未产生的 synthetic tests。

## Allowed write paths

- `pico/evaluation/evidence_bundle.py`
- `scripts/build_v3_evidence_bundle.py`
- `tests/test_evidence_bundle.py`
- `tests/fixtures/evidence_bundle/**`
- `.codex/eval/handoffs/EVAL-080.json`

## Forbidden write paths

- `产品 Runtime`
- `.codex/eval/state/STATUS.json`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时停止并提交 `ownership_change_request`。

## Deliverables

- bundle module/script/tests
- native claim schema

## Acceptance checklist

- [ ] 所有数字可追到 rows/hash/formula
- [ ] 失败/exclusion 不丢失
- [ ] Native claim 必须引用 recovered Gate N1 `TOOL-050-S-R1`
- [ ] Resume claim 必须引用 TOOL-062-G
- [ ] 支持缺少可选 Context Ablation
- [ ] Multi-agent claim experimental_only

## Commands

由本 ticket 的实现和依赖决定；至少运行受影响测试与 ruff。

## Notes

- 无额外说明。

## Stop rule

完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止。不得 merge/rebase、更新 `STATUS.json`/`FREEZE.json`（Integrator ticket 除外）或开始下游工作。
