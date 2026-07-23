# W6R2 — WSL Native Conformance Evidence Recovery

W6R2 从 W6R blocked handoff 恢复。W6R canonical、正式 blocked 状态、FREEZE、handoff 与 artifacts 保持不可变；本 Wave 不把 Windows 失败升级为修复工作。

依次执行 `TOOL-055-E → EVAL-056-H → TOOL-057-A → TOOL-058-G`。第一项使 OpenAI Responses 与 Anthropic Messages 在仓库内使用同一冻结八案例和同等断言，并让正式 evidence 自身携带 `validate → repetition → permission → policy → execute` 的有序结构化证明。第二项将该证明纳入 artifact contract，并明确本地私有配置只通过 `PICO_NATIVE_PROVIDER_CONFIG` 定位。第三项只读复审双 dialect 对称性、证据闭环与凭据隔离。

`TOOL-058-G` 只以 Ubuntu WSL2/Python 3.12 fresh clone 作为 canonical Gate；Windows 可不运行且不影响结果。Gate 不发 provider HTTP，通过后由 Wave Integrator冻结新的 immutable `run_snapshot_sha`。

随后三个 R2 shards 从同一 snapshot 在 WSL 并行运行，并由 `TOOL-050-S-R1` 聚合。至少一个 profile eligible 后，本 Wave 提供 human smoke 的 profile 与 canonical commit 并停止；不得启动 W7。
