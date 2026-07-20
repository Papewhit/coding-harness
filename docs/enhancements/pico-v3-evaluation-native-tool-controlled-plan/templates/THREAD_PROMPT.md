你正在执行 Pico v3 Evaluation / Native Tool Calling 的单一 ticket：`<TICKET_ID>`。

开始前只读取：
1. 仓库根 `AGENTS.md`；
2. `.codex/eval/CONTROL.md`；
3. `.codex/eval/tickets/<TICKET_ID>.md`；
4. ticket 明确列出的 dependency handoff/freeze。

确认 HEAD 等于指定 base SHA，并在独立 worktree/branch 中工作。只修改 `allowed_write_paths`；出现 scope 外修改需求时停止并提交 ownership change request。

不得引入 `<tool>/<final>` fallback，不得让 Provider SDK 自动执行 Pico 工具，不得把 SDK 对象写入 Core/Session/Checkpoint。完成验收命令和 handoff 后停止；不要 merge/rebase、更新正式 STATUS/FREEZE 或开始下游 ticket。若 ticket 要求状态变更，只在 handoff/artifact 中输出 `status_proposal` / `freeze_proposal`，由 Wave Integrator 验证并落盘。
