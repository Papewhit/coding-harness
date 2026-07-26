# EVAL-063-H — Grounded Human-smoke v4 与 Durable Public Trajectory

**Plan type:** `fixture_builder` — 使用 `implementer` Thread
**Wave:** `W6R5`
**Base/Candidate SHA:** 由 `integrator` 在 dispatch 中填写；不得从 integration branch 吸收未列出的变化。

## Start conditions

- Dependency Ticket: `EVAL-059-H`

只读取 W6R4 accepted source、W6R4 human-smoke Artifact、`EVAL-059-H` 最新 accepted handoff 和本 Ticket 明确引用的文件。

## Ticket-local terms

- **grounded instruction**：任务所需的目标值和解释语义由 prompt 或 fixture 中明确可读的权威来源提供，不要求模型猜测 hidden Oracle。
- **durable public trajectory**：临时 workspace 清理后仍保存在 Artifact root 中、经过 public projection 与敏感信息检查的 `.pico` session-event/run evidence；不包含 raw session JSON 或 private provider continuation。

## Goal

发布 versioned human-smoke v4，修复 HSMOKE-V3-A 的 hidden target，并在清理临时 workspace 前耐久保存足以复核 model-exchange、Runtime、安全链和文件变化的 public trajectory。

## Allowed write paths

- `benchmarks/v3/native-provider/human-smoke-v4.json`
- `scripts/run_v3_native_human_smoke_v4.py`
- `tests/test_v3_native_human_smoke_v4.py`
- `<ARTIFACT_ROOT>/native-provider-human-smoke-v4/**`
- `.codex/eval/handoffs/EVAL-063-H.json`

## Forbidden write paths

- `benchmarks/v3/native-provider/human-smoke-v2.json`
- `benchmarks/v3/native-provider/human-smoke-v3.json`
- `scripts/run_v3_native_human_smoke.py`
- `scripts/run_v3_native_human_smoke_v3.py`
- `tests/test_v3_native_human_smoke.py`
- `tests/test_v3_native_human_smoke_v3.py`
- `pico/core/**`
- `pico/providers/**`
- `W6R4 Artifacts`
- `.codex/eval/CURRENT.md`
- `.codex/eval/state/FREEZE.json`

未列出的写路径默认禁止。需要扩展 scope 时提交 `change_request`；不得自行修改。

## Deliverables

- human-smoke v4 manifest、runner 与 fake/stub tests
- grounded HSMOKE-V4-A
- durable public trajectory copier、validator 与 hash inventory
- EVAL-063-H handoff

## Acceptance checklist

- [ ] HSMOKE-V4-A prompt 明确给出应把 `pico setup` 改为 `pico sync`，以及依赖已准备好的简短解释语义
- [ ] expected postcondition 与 semantic order 仍由同一 manifest 驱动，不存在 runner 内第二份 hidden literal
- [ ] v2/v3 文件和 W6R4 Artifact bytes 保持不变
- [ ] runner 在临时目录清理前复制 `.pico/sessions/*.events.jsonl` 和 `.pico/runs/**` public evidence
- [ ] raw `.pico/sessions/*.json`、private continuation、secret、raw endpoint 和 expanded locator 不进入 public Artifact
- [ ] durable event/run JSON 与 JSONL 均可解析，并与 result 中 model call、Runtime result 和 safety call ID 一一对应
- [ ] 单元测试证明临时 workspace 已删除后 durable trajectory 仍存在且 inventory hashes 匹配
- [ ] fake/stub tests 覆盖 PASS、semantic FAIL、证据缺失、call-ID mismatch、private payload 拒绝和 Artifact 解析失败
- [ ] fake/stub tests 的 provider HTTP attempts 为 0

## Commands

```bash
uv run pytest tests/test_v3_native_human_smoke_v4.py -q
uv run ruff check scripts/run_v3_native_human_smoke_v4.py tests/test_v3_native_human_smoke_v4.py
```

## Completion rule

运行 targeted tests 与 scoped lint。先把 `.codex/eval/**` 之外的 Git-tracked 变更形成一个语义 commit，再按 `templates/HANDOFF.md` 写 handoff；handoff 和其他控制文件不得进入该 commit。返回 `integrator` 验收后停止，不得执行 live smoke。
