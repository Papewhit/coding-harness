# EVAL-063-R — Authorized Human-smoke v4 Process

**Plan type:** `run_shard` — 由当前 `integrator` 启动本地 Process
**Wave:** `W6R5`
**Base/Candidate SHA:** 使用 TOOL-063-G accepted source，不得在运行目录修改源码。

## Start conditions

- Dependency Ticket: `TOOL-063-G`
- `program_supervisor` 已明确授权 selected configured profile、Artifact root、frozen attempt/retry budget 和一次 live human-smoke v4
- `private_config_locator_provided_out_of_band=true`

## Goal

对 W6R4 selected profile 执行一次 grounded human-smoke v4，生成可审计的 semantic result 和 durable public `.pico` trajectory。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-human-smoke-v4/<SOURCE_SHA>/**`
- `<ARTIFACT_ROOT>/native-provider-human-smoke-v4/process-manifests/**`
- `.codex/eval/handoffs/EVAL-063-R.json`

## Forbidden write paths

- `所有 Git-tracked source、tests、fixtures 与 control files（EVAL-063-R handoff 除外）`
- `W6R4 与更早 Artifacts`
- `raw .pico session JSON 或 private continuation public copy`
- `private config locator value、secret、raw endpoint 或展开后的命令`

未列出的写路径默认禁止。

## Commands

Process manifest 必须保留未展开的环境变量引用：

```bash
uv run python scripts/run_v3_native_human_smoke_v4.py \
  --authorized-live \
  --provider <SELECTED_PROFILE_NAME> \
  --config "$PICO_NATIVE_PROVIDER_CONFIG" \
  --frozen-profile <FROZEN_PUBLIC_PROFILE_JSON> \
  --output-dir <ARTIFACT_ROOT>/native-provider-human-smoke-v4/<SOURCE_SHA>
```

命令由 `integrator` 作为一个 local Process 启动；不为每个 Process 创建单独 handoff。本逻辑 Ticket 只生成一份 `EVAL-063-R` handoff。

## Acceptance checklist

- [ ] Process manifest 绑定 source/tree、v4 manifest/runner/tests、selected profile、SDK 与 retry/attempt budget
- [ ] 只执行一次已授权 live smoke；不得因 semantic FAIL 自动重跑
- [ ] 若 measurement 无效，只作废受影响结果并按 `measurement_defect` 返回 EVAL-063-H
- [ ] summary HTTP attempts 等于 scenario attempts 之和，SDK hidden retry 为 0
- [ ] result、public session events、run trace/report 与 safety evidence 通过 call ID 一一闭合
- [ ] 临时 workspace 删除后 durable public trajectory 仍存在、可解析且 inventory hash 匹配
- [ ] secret、raw endpoint、expanded locator、private continuation 和 executable text envelope 扫描为 0 hits
- [ ] semantic PASS/FAIL 均作为结果保留

## Completion rule

Process 结束后验证 exit files、JSON/JSONL、HTTP accounting、call-ID binding、durable evidence 和 inventory，写一份 EVAL-063-R handoff后停止。不得修改产品或 measurement contract。
