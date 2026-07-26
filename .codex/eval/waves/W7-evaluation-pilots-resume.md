# W7 — Evaluation Pilots 与 Native Resume 实现

**Entry Gate:** `native_eval_ready=accepted`，并绑定 accepted W6R4 handoff、selection hash、human smoke hash 和 source SHA。

## Execution mapping

- `EVAL-021-R[x2]`：`integrator` 启动 2 个 Processes；全部 Processes 只生成一份 `EVAL-021-R` handoff。
- `EVAL-021-M`：当前 `integrator` 直接聚合并更新 Freeze。
- `EVAL-050-P[x3]`：`integrator` 启动 3 个 Processes；全部 Processes 只生成一份 `EVAL-050-P` handoff。
- `EVAL-050-R`：1 个 `reviewer` Thread；`evaluation_failure` 保留为 Pilot 结果，不自动请求产品修复。
- `TOOL-060-R`：1 个 `implementer` Thread。
- `TOOL-061-T` 与 `EVAL-060`：`TOOL-060-R` accepted 后，可以由同一 `implementer` Thread 顺序完成，也可以在无路径冲突时由两个 `implementer` Threads 并行完成；每个 Ticket 仍有独立 Git-tracked 变更、测试摘要和 handoff。

评测 Processes 与 Resume 实现可在各自依赖满足后同时执行。有效 Dream/Pilot 结果产生后立即更新 CURRENT 摘要，不等待 Resume Tickets 或 Wave close。

## Exit Gate

`EVAL-021-R`、`EVAL-021-M`、`EVAL-050-P`、`EVAL-050-R`、`TOOL-060-R`、`TOOL-061-T`、`EVAL-060` 均为 `accepted`；Dream summary、Pilot review、Native Resume deterministic contract 和 interruption runner 可审查。有效评测失败不阻止 Ticket acceptance。
