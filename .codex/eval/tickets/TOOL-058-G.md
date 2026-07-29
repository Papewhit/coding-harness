# TOOL-058-G — WSL Canonical Native Preflight and Run Snapshot Gate

**Thread type:** `integrator`
**Wave:** `W6R2`
**Base SHA:** 由 Integrator 填写，并应用 W6R2 已验收的实现 commits。

## Start conditions

- `TOOL-042-G-R2`
- `TOOL-055-E`
- `EVAL-056-H`
- `TOOL-057-A`

## Goal

在不发 provider HTTP 的前提下，只用 Ubuntu WSL2/Python 3.12 fresh clone 完成 canonical preflight，生成 sanitized public profiles，并提出新的 immutable run snapshot。

## Allowed write paths

- `<ARTIFACT_ROOT>/native-provider-preflight/W6R2-TOOL-058-G-01/**`
- `.codex/eval/proposals/TOOL-058-G.freeze.json`
- `.codex/eval/proposals/TOOL-058-G.status.json`
- `.codex/eval/handoffs/TOOL-058-G.json`

## Forbidden write paths

- 产品源码、tests、frozen cases
- live provider HTTP
- raw URL、credential、private config path
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 在用户 `papewhit` 的 `~/dev/` fresh clone 中验证精确 source SHA，使用独立 `uv sync`，不使用 `sudo`
- [ ] WSL Ruff、targeted、protected、deterministic 与 full suite 均 exit 0；只允许已记录的 live-opt-in skips
- [ ] 双 dialect 固定 runner 的八案例 × 三次 fake-transport bundles 均通过同一 verifier
- [ ] artifact 自身可重建完整安全链顺序、call/result 与 batch completeness
- [ ] 三个候选 provider 的 public manifest 由受审计 builder 生成并与 private config 精确绑定
- [ ] Gate 启动环境显式设置 `PICO_NATIVE_PROVIDER_CONFIG`，但公开产物不保存其值
- [ ] JSON、JSONL、XML 产物脱敏后重新解析，credential/raw URL 扫描无匹配
- [ ] Windows 检查为可选 best-effort，不执行或失败都不影响 Gate
- [ ] freeze proposal 绑定 source、cases、runner、evaluator、CLI、bundle schema、public profiles、SDK decision 与 audit hashes

## Stop rule

完成 proposals 与 handoff 后停止。只有 Wave Integrator 验收 Gate、写入正式状态并冻结新 `run_snapshot_sha` 后，才可分发三个 R2 shards。
