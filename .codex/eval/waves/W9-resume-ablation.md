# W9 — Resume 与可选 Context Ablation Live Runs

**Entry Gate:** `native_eval_ready=accepted`，且 `native_resume_ready` 已有 `accepted|rejected` 结论。

- 若 `native_resume_ready=rejected`，`integrator` 对尚未启动的 `EVAL-061-R`、`EVAL-061-M`、`EVAL-070-S`、`EVAL-070-R`、`EVAL-070-M` 执行 `mark_not_applicable`，reason=`required_gate_rejected`，binding 指向 `native_resume_ready` Artifact/hash；W9 不创建模型 Thread 或 Process。
- 若 `native_resume_ready=accepted`，执行 `EVAL-061-R[x3] → EVAL-061-M`。
- Context Ablation 是可选分支。只有 `program_supervisor` 明确决定执行后，`EVAL-070-S → EVAL-070-R[x2-4] → EVAL-070-M` 才适用；明确不执行时，这三个 Tickets 执行 `mark_not_applicable`，reason=`optional_branch_not_selected`，binding 指向该决定记录。
- 适用的 `EVAL-061-R[x3]` 与 `EVAL-070-R[x2-4]` 由 `integrator` 启动 Processes；每个逻辑 Ticket 只写一份 handoff。
- 适用的 `EVAL-061-M`、`EVAL-070-M` 由当前 `integrator` 直接执行。
- 适用的 `EVAL-070-S` 使用一个 `reviewer` Thread，写 selection/freeze proposal；不得根据期望收益调整 case。
- Resume Rows 必须引用 `native_resume_ready` Gate Artifact/hash、selected profile、taskset 和 predicate hashes。
- Context Ablation 只选择确实依赖目标 assets 的 4–6 个 cases；没有稳定提升时如实记录无收益结论，不自动改题。

## Exit Gate

所有适用 Resume/Context Tickets=`accepted`，不适用 Tickets=`not_applicable`，每个 `not_applicable` Ticket 都有精确 reason 与 binding；有效失败完整保留。
