# W8 — Final Baseline、Native Restart 与 Resume Predicate Freeze

三个 repo final shards 与 selected-profile restart conformance 并行。`TOOL-062-G` 通过后才能运行 `EVAL-061-P` 冻结 K1/K2。Context ablation runner 可同期实现，但不运行正式 live rows。

Exit Gate：27 个 local task rows 聚合；`native_resume_ready=accepted`；Resume task/predicate hash 冻结。
