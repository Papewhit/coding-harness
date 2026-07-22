# W6 — Live Native Conformance 与 Profile Selection

三个 profile shard 必须等待 `TOOL-042-G-R1`，并从其冻结的同一 `run_snapshot_sha` 运行：Qwen/OpenAI Responses、Qwen/Anthropic Messages、DeepSeek/Anthropic Messages。缺少本地配置的 profile 必须记录 exclusion，不得伪造结果。

`TOOL-050-S` 只选择通过硬 Gate 的完整 profile（model + endpoint + dialect + adapter mode + SDK version + capabilities）。至少一个 profile 合格才设置 `native_eval_ready=accepted`。
