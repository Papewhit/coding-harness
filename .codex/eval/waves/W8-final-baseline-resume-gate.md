# W8 — Final Baseline、Native Restart 与 Resume Predicate Freeze

**Entry Gate:** `native_eval_ready=accepted`，W7=`passed`。

- `EVAL-050-F[x3]` 和 `TOOL-062-R` 由 `integrator` 作为 Processes 启动，不创建模型 Threads。
- `EVAL-050-M` 与 `TOOL-062-G` 由当前 `integrator` 直接执行。
- `EVAL-061-P` 只有在 `native_resume_ready=accepted` 后才适用，并使用一个 `reviewer` Thread。若 `native_resume_ready=rejected`，`integrator` 对尚未启动的 `EVAL-061-P` 执行 `mark_not_applicable`，reason=`required_gate_rejected`，binding 指向 `native_resume_ready` Artifact/hash；不生成 handoff。
- `EVAL-070-I` 使用一个 `implementer` Thread；它只实现 runner，不运行正式 live Rows。
- 有效 Final Baseline 任务失败进入正式分母；不得据此删题或自动修产品。

## Exit Gate

27 个 local task Rows（含有效失败）已聚合；`native_resume_ready` 有明确 `accepted|rejected` 结论；accepted 时 Resume task/predicate hashes 已 Freeze；`EVAL-070-I` 可审查；所有适用 Tickets=`accepted`，不适用 Tickets=`not_applicable`。
