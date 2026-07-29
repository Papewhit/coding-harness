# TOOL-054-G — Native Conformance Deterministic Preflight and Run Snapshot Gate

**Thread type:** `integrator`
**Wave:** `W6R`
**Base SHA:** 由 Integrator 填写，并应用 W6R 已验收的实现 commits。

## Start conditions

- `TOOL-042-G-R2`
- `TOOL-051-L`
- `EVAL-052-H`
- `TOOL-053-A`

## Goal

在发出任何 live provider HTTP 前，重新验证 repaired harness，生成 sanitized public profile manifests，并提出新的 immutable run snapshot freeze。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-preflight/**`
- `.codex/eval/proposals/TOOL-054-G.freeze.json`
- `.codex/eval/proposals/TOOL-054-G.status.json`
- `.codex/eval/handoffs/TOOL-054-G.json`

## Forbidden write paths

- 产品源码、tests、frozen cases
- 正式 live provider conformance HTTP
- raw URL、API key 或其他 credential artifact
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 验证 dependency commits、clean tree、cases Git-blob hash 与 W6 frozen input 一致
- [ ] Windows 运行 targeted evaluator/live-runner/safety tests、Ruff 与 full suite
- [ ] Ubuntu WSL2/Python 3.12 fresh clone 运行相同 deterministic/full Gate；用户 `papewhit`，仓库位于 `~/dev/`，不使用 `sudo`
- [ ] 对 `dashscope-o`、`dashscope-a`、`deepseek` 只通过受审计代码解析本地配置并输出 sanitized public manifest
- [ ] 每个 manifest 与重新解析的 resolved config 精确绑定；profile 缺失则显式 exclusion
- [ ] 验证 SDK package/version、`max_retries=0`、stream/parallel=false
- [ ] fake transport CLI smoke 产生完整 8×3 bundle
- [ ] credential/raw-URL pattern scan 无匹配
- [ ] freeze proposal 记录 source、cases、evaluator、live runner、CLI contract、bundle schema、public manifests、SDK decision 和 audit hashes
- [ ] 只有 required tests 全部通过且至少一个完整 public profile 可绑定，才提出 `run_snapshot_approved_for_live_conformance=true`

Public manifest 统一通过以下评测专用入口生成，不能手工拼接：

```bash
uv run python scripts/build_native_provider_profile.py --provider <LOCAL_PROFILE_NAME> --manifest-out <PREFLIGHT_ARTIFACT_DIR>/<LOCAL_PROFILE_NAME>.public.json
```

## Stop rule

完成 proposals 与 handoff 后停止。Wave Integrator 验证并写入正式状态、创建 immutable run snapshot 后，才能分发三个 R2 shards。
