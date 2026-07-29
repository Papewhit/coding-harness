## Pico v3 Evaluation 与 Native Tool Calling（eval-control-v4.2）

- 从 W6R4 起以 `.codex/eval/CONTROL.md`、`CURRENT.md` 和当前 Wave 文件为执行入口；`PLAN.json` 只作机器 registry，需要时只读取当前条目；`state/STATUS.json` 只作 W6R3 及以前历史记录。
- Ticket 是提交、验收和 handoff 单位，不是 Thread 生命周期单位；一个 `implementer` Thread 可以按明确 dispatch 顺序完成多个 Tickets。
- 每个 Wave 使用一个全新的用户可见顶层 `integrator` Thread。持久化的 `program_supervisor` 是一个单独的顶层 Thread。二者通过 Codex 跨 Thread 消息交互，禁止建立 parent-child Agent 关系。决策边界详见 `.codex/eval/CONTROL.md`。
- `reviewer` 必须把 Finding 分类为 `implementation_defect`、`measurement_defect`、`evaluation_failure` 或 `change_request`；有效测量中的任务失败不得自动触发产品修复。
- 当前 `integrator` 是 `CURRENT.md` 与 `FREEZE.json` 的唯一写入者。禁止为 dispatch、accept、waiting 或普通状态更新创建 commit。
- 正式 Runtime 与在线 Evaluation 不得新增或保留可执行 `<tool>/<final>` fallback。
- Provider SDK 只能位于 Adapter/transport 边界；禁止 SDK Tool Runner、Agents Runner 和 SDK 自动执行 Pico 工具。
- Core、Session、Checkpoint 不得保存 SDK 对象；只保存 Pico contract 与 JSON-safe opaque continuation。
- native tool call/result 必须按 provider call ID 一一匹配，并继续经过现有安全链。
- Testing/Evaluation canonical 环境为 Ubuntu WSL2/Python 3.12 fresh clone；Windows 只作 best-effort 兼容检查。
- `native_eval_ready=accepted` 前禁止正式在线效果评测；`native_resume_ready=accepted` 前禁止正式 Resume 评测。
- 并发 `implementer` 执行序列各用独立 worktree/branch；Process 不修改 Git-tracked files，只写独占 Artifact 目录。
- fixture/oracle/metric 先 Freeze，产品修复独立提交；不得为了改善结果修改 frozen 输入。
- 下游只通过精确 Git SHA、CURRENT、Freeze、handoff 和 Artifact 接续，不通过长对话记忆接续。
- 保留既有 `pico/core/runtime_checkpoints.py` 工作区修改；不得 reset 或覆盖。
