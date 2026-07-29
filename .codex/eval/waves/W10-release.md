# W10 — Evidence、Audit 与 Release Gate

**Entry Gate:** `native_eval_ready=accepted`，且 `native_resume_ready` 已有 `accepted|rejected` 结论。`native_resume_ready=rejected` 不阻止 W10；它限制 Resume claim 的范围。

串行执行 `EVAL-081-A → EVAL-081-R → EVAL-081-G`：

- `EVAL-081-A` 由当前 `integrator` 直接构建 evidence bundle 和 claim registry。`EVAL-061-M=not_applicable` 仅在 `native_resume_ready=rejected` 且 binding 完整时可作为已满足的可选依赖；此时不得生成 Resume 效果 claim。
- `EVAL-081-R` 使用一个 `reviewer` Thread，按四类 Finding 输出审计。
- `EVAL-081-G` 由当前 `integrator` 直接运行 final Gate。

最终 Claim Registry 必须分别说明 Native Tool Calling、Auto-dream、Local Coding、Resume、Context 的证据范围；没有证据的部分写明 unavailable/not applicable，不生成数字；Multi-agent 保持 `experimental_only`。Human review 使用 Git `base..candidate` diff、短 summary 和 Artifact paths，不要求阅读控制提交树。

## Exit Gate

全量测试、架构/安全 Gate、human scenario、evidence hashes 和 claim audit 完成；`native_eval_ready`、`native_resume_ready` 和每项 claim 的适用范围可追踪；被 rejected 的 Gate 如实写入 limitations。
