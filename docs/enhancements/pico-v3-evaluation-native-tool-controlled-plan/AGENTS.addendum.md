## Pico v3 Evaluation 与 Native Tool Calling 规则

- 当前 plan-level thread 只汇总用户决策和 Wave 结果；每个 Wave 使用新的非 ticket Integrator thread。
- 按 `.codex/eval/PLAN.json` 和单个 ticket 工作；一个 ticket thread 只完成一个 ticket。
- 当期 Wave Integrator 是正式 `STATUS/FREEZE` 的唯一写入者；ticket 只能提交 `status_proposal` / `freeze_proposal`。
- 正式 Runtime 与在线 Evaluation 不得新增或保留 `<tool>/<final>` fallback。
- Provider SDK 只能位于 Adapter/transport 边界；禁止 SDK Tool Runner、Agents Runner 和自动执行 Pico 工具。
- Core、Session、Checkpoint 不得保存 SDK 对象；只保存 Pico contract 与 JSON-safe opaque continuation。
- 所有 native tool call/result 必须以 provider call ID 一一匹配，并继续经过现有安全链。
- `TOOL-050-S` 前禁止正式在线效果评测；`TOOL-062-G` 前禁止正式 Resume 评测。
- 每个写入 ticket 使用独立 worktree/branch，从不可变 base SHA 开始；共享文件只由指定 owner 修改。
- fixture/oracle/metric 先冻结，产品修复独立提交；不得为了改善结果同步改题。
- run shard 不改源码，只写自己的 artifact 目录，记录 source/evaluator/taskset/provider/native gate hash。
- 下游只通过 Git SHA、STATUS/FREEZE hash、handoff 和 artifact 接续，不通过上一段长对话接续。
- 保留既有 `pico/core/runtime_checkpoints.py` 工作区修改；不得 reset 或覆盖。
