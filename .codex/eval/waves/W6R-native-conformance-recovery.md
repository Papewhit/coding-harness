# W6R — Native Conformance Harness Repair 与 Gate N1 Recovery

W6R 从 W6 blocked handoff 恢复，不修改或覆盖 W6 的 canonical tag、selection、48 条 infrastructure rows、handoff 与外部 artifacts。W6 证据只用于说明 pre-HTTP contract failure，不得作为新的 conformance 分母或成功证据。

先串行执行 `TOOL-051-L → EVAL-052-H`。前者实现固定、可审计的 production live runner 和 local-provider/public-profile binding；后者统一评测 harness 的 argparse、三次 repetition 与目录型 artifact bundle。正式 live 命令使用 `--provider` 选择 `.pico.toml` 中的本地 profile，使用 `--expected-profile` 绑定不含凭据的公开身份；不得继续使用含义冲突的 `--profile`，也不得接受任意 `--runner-plugin module:callable`。

`TOOL-053-A` 对调用链和 evidence 进行只读审计。只有它确认命令从固定 harness 进入 production Pico Runtime、所有工具执行经过既有 `validate → repetition → permission → policy → execute` 安全链、没有 SDK-managed tool execution，`TOOL-054-G` 才能运行新的 deterministic/preflight Gate。

`TOOL-054-G` 不发 provider HTTP。它在 Windows 和 Ubuntu WSL2/Python 3.12 fresh clone 中复验代码，生成并校验三个候选 profile 的 sanitized public manifests，冻结 cases、evaluator、live runner、CLI contract、artifact schema、profile manifests 与新的 immutable `run_snapshot_sha`。WSL 使用用户 `papewhit`、仓库位于 `~/dev/`，不得使用 `sudo`。

Gate accepted 后，三个 R2 run shards 从同一新 `run_snapshot_sha` 并行运行。每个 case 执行三次，row key 为 `(case_id, repetition)`。若命令在任何 case 启动前失败，只生成 run-level preflight failure manifest，rows 为 0、指标为 `not_computable`；不得为未发生的执行人工制造 24 条 rows。一旦开始执行，每个已调度 row 的 provider/infrastructure failure 都必须保留。

最后由 `TOOL-050-S-R1` 聚合新 artifacts 并执行 Gate N1。它写入新的 `selection-w6r.json`，不得覆盖 W6 `selection.json`。至少一个完整 profile eligible 才能设置 `native_eval_ready=accepted`，并输出供用户进行 human smoke 的 profile 与 canonical commit。Wave Integrator 随后停止，不启动 W7；W7 还需要用户明确确认 human smoke 结果。
