# `implementer` / `reviewer` Prompt（eval-control-v4）

**Role:** `<implementer|reviewer>`
**Dispatch sequence:** `<TICKET_IDS_IN_ORDER>`
**Current Candidate:** `<CANDIDATE_SHA>`

开始前只读取：

1. 仓库根 `AGENTS.md`；
2. `.codex/eval/CONTROL.md`；
3. `.codex/eval/CURRENT.md`；
4. dispatch 列出的 Ticket 文件；
5. dispatch 精确列出的 commits、handoff、Freeze 条目和 Artifact。

禁止默认读取完整 `PLAN.json`、`STATUS.json`、全部旧 handoff 或旧设计长文。

## `implementer`

- 只执行 dispatch 中列出的 Tickets 和顺序；不得自行开始其他 Ticket。
- 使用指定 worktree/branch。每个 Ticket 开始时核验自己的 base SHA 和 dependency commits。
- 每个 Ticket 单独形成 Git-tracked 变更、targeted test 摘要和一份 handoff；不得把多个 Tickets 混成一个提交或 handoff。
- 先提交本 Ticket 在 `.codex/eval/**` 之外的 Git-tracked 变更，再写 handoff；handoff 和其他控制文件不得进入该语义 commit。
- 当前 Ticket 完成后返回 `integrator` 验收。只有 `integrator` 已复制并验证 handoff、清理本 Ticket 的未提交控制文件，并给出下一 Ticket 的精确 base/dependencies 后，才在同一 Thread 继续 dispatch sequence。
- Finding 为 `implementation_defect|measurement_defect` 时，在原 Ticket/worktree 上执行 `remediate`；handoff 递增 revision 并记录 superseded hash。
- 需要 scope 外路径、改变 Freeze/contract 或新所有权时，输出 `change_request`，不得自行扩展。

## `reviewer`

- 针对 dispatch 指定的精确 `base..Candidate` 和 Artifact 检查；只写 Ticket 明确允许的 review、proposal、selection 或 audit 输出。
- 使用 `templates/REVIEW.md`。每个 Finding 必须分类为 `implementation_defect`、`measurement_defect`、`evaluation_failure` 或 `change_request`。
- 不修改产品实现，不调度修复，不把有效评测失败写成 blocker。
- 长时、重复或 live 命令不在模型 Thread 中守候。向 `integrator` 提交精确 Process manifest，由 `integrator` 启动 Process；收到 Artifact 后继续 review。
- Ticket 若明确允许修改 `.codex/eval/**` 之外的 Git-tracked selection/audit 文件，先形成一个语义 commit，再写 handoff；控制文件不得进入该 commit。
- 可以在同一 Thread 中 review 同一 Candidate 的后续 revision。

## 共同约束

不得引入 `<tool>/<final>` fallback，不得让 Provider SDK 自动执行 Pico 工具，不得把 SDK 对象写入 Core/Session/Checkpoint。完整日志写文件；对话与 handoff 只保留命令摘要、路径和 hash。不得更新 `CURRENT.md`、`STATUS.json` 或正式 `FREEZE.json`。
