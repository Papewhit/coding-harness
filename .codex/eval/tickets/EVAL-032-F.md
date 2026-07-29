# EVAL-032-F — Versioned Structured Context Freeze Binding Repair

**Thread type:** `integrator`
**Wave:** `W5R`
**Base SHA:** 由 Integrator 填写；应用所有已验收 W5R remediation commits。

## Start conditions

- `TOOL-043-R`
- `TOOL-044-F`
- `ARCH-045-B`
- `CHORE-045-L`
- `EVAL-031-G`
- W5 Gate 的 Context hash mismatch evidence

## Goal

在不修改 `cases.json` 或 frozen fragments 的前提下，发布 versioned Context binding。新 binding 明确使用 canonical Git blob bytes，并保留旧 `d69dfc…` 声明及其 invalidated 原因。随后从绑定输入重新生成 structured Context artifact。

## Allowed write paths

- `benchmarks/v3/context-assets/cases-v2.binding.json`
- `scripts/verify_context_freeze.py`
- `tests/test_context_freeze_integrity.py`
- `<ARTIFACT_ROOT>/phase-2-context-assets-w5r/**`
- `.codex/eval/proposals/EVAL-032-F.freeze.json`
- `.codex/eval/handoffs/EVAL-032-F.json`

## Forbidden write paths

- `benchmarks/v3/context-assets/cases.json`
- frozen fragments 与产品 Runtime
- 覆盖、删除或伪装旧 `d69dfc…` 声明
- 使用 checkout bytes 作为跨平台 canonical hash

## Deliverables

- v2 binding，包含 source path、Git blob OID、`git_blob_bytes` SHA-256、schema 和 supersession metadata
- fresh-clone verifier
- 重新生成的 evaluation artifact、manifest 与 hashes
- freeze proposal 与 handoff
- 新增完整性测试及每项覆盖目的

## Acceptance checklist

- [ ] W5 canonical cases blob OID `5e9bdf06e75f6661660947e880f07edfe7480880` 可验证
- [ ] Git blob SHA-256 `e08066749520a52af5bb14a9435e359f4a85d3f3ae6e8dd0e962001f99c2df17` 可从 fresh clone 重建
- [ ] LF/CRLF checkout 差异不改变 canonical binding
- [ ] 旧声明保留并标记 invalidated/superseded
- [ ] evaluator 实际读取的输入与 binding 指向同一 Git blob
- [ ] artifact 记录 source SHA、file SHA、artifact SHA 与 run snapshot

## Commands

```bash
uv run pytest tests/test_context_freeze_integrity.py tests/test_context_asset_evaluator.py tests/test_native_request_context.py -q
```

```bash
uv run python scripts/verify_context_freeze.py --binding benchmarks/v3/context-assets/cases-v2.binding.json
```

```bash
uv run python scripts/run_context_asset_evaluation.py --cases benchmarks/v3/context-assets/cases.json --workspace-root <ARTIFACT_ROOT>/phase-2-context-assets-w5r --artifact <ARTIFACT_ROOT>/phase-2-context-assets-w5r/structured-context-evaluation.json --shard-id W5R-EVAL-032-F --repetition 1
```

## Stop rule

完成 artifact、proposal 与 handoff 后停止；不得写正式 FREEZE/STATUS 或运行 final Gate。
