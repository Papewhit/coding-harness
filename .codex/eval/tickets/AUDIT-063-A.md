# AUDIT-063-A — Human-smoke v4 Measurement 只读复审

**Plan type:** `reviewer` — 使用 `reviewer` Thread
**Wave:** `W6R5`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；只审查精确 Candidate 与列出的 Artifact。

## Start conditions

- Dependency Ticket: `EVAL-063-H`

## Goal

确认 human-smoke v4 将模型知识与 harness 能力分离，durable public trajectory 足以复核执行路径，同时不会公开 raw session/private continuation，也不会追溯改变 W6R4 历史。

## Allowed write paths

- `.codex/eval/handoffs/AUDIT-063-A.json`

## Forbidden write paths

- `除 AUDIT-063-A handoff 外的所有路径`

未列出的写路径默认禁止。

## Acceptance checklist

- [ ] HSMOKE-V4-A 的目标修改由 prompt 明确提供，不要求模型猜测 hidden Oracle
- [ ] manifest 是 prompt、fixture、postcondition 与 semantic order 的唯一事实源
- [ ] v2/v3 source bytes 与 W6R4 Artifact hashes 未变化
- [ ] 临时 workspace 删除后，public session events 和 run evidence 仍位于 durable Artifact
- [ ] public trajectory 与 result 的 model call、Runtime result、安全事件通过真实 call ID 闭合
- [ ] raw session JSON 和 private continuation 未进入 public Artifact；敏感信息扫描为 0 hits
- [ ] fake/stub execution 的 provider HTTP attempts 为 0
- [ ] Finding 使用 `implementation_defect|measurement_defect|evaluation_failure|change_request` 精确分类

## Commands

```bash
uv run pytest tests/test_v3_native_human_smoke_v4.py -q
uv run ruff check scripts/run_v3_native_human_smoke_v4.py tests/test_v3_native_human_smoke_v4.py
git diff --check <BASE_SHA>..<CANDIDATE_SHA>
```

## Completion rule

写入 `.codex/eval/handoffs/AUDIT-063-A.json` 后停止。发现问题只报告 Finding，不修改 manifest、runner、tests、产品源码或 formal state。
