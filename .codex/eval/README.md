# Pico v3 Evaluation：Native Tool Calling 受控多线程执行方案

本版本把 **Native Tool Calling** 提升为所有正式在线 Evaluation 的硬前置，同时保留 Auto-dream fixture、Context deterministic、mini repo 等可独立建设的并行 lane。

旧 1200+ 行方案继续作为设计参考，不作为线程启动 prompt。每个 Codex thread 默认只读取：

1. 仓库根 `AGENTS.md`；
2. `.codex/eval/CONTROL.md`；
3. 自己的 `tickets/<ticket-id>.md`；
4. ticket 明确列出的 handoff/freeze。

## 两个硬 Gate

**Native Eval-ready — recovered Gate N1 `TOOL-050-S-R1` + user-authorized human smoke**

要求 Runtime 端到端使用结构化 tool call/result、call ID 完整匹配、无文本 fallback，并至少有一个真实 provider profile 通过 native conformance。通过后才允许 Auto-dream Live、Local Coding Task 和 Context Ablation 正式运行。

**Native Resume-ready — `TOOL-062-G`**

要求 pending/executing/completed/rejected/uncertain 状态可持久化，provider continuation 可跨进程恢复，副作用工具在不确定状态下不自动重放。通过后才允许正式 Resume Evaluation。

## SDK 的位置

- Provider-neutral contract 与 Pico 自有工具状态机先冻结。
- OpenAI/Anthropic SDK viability 同期 Spike。
- SDK decision 冻结后再实现生产 Adapter。
- SDK 只负责传输、请求类型、响应解码和 raw response；Pico 继续负责安全链、权限、工具执行、session/checkpoint、Resume 和 Evaluation evidence。
- 禁止 SDK Tool Runner、Agents SDK 自动循环和 SDK 对 Pico 工具函数的自动执行。
- 正式 Evaluation：`stream=false`、自动并行工具关闭、SDK retry=0；Pico retry 策略显式冻结并逐次记录。

## 多线程执行

- 当前 plan-level thread 只汇总用户决策和 Wave 结果；每个 Wave 由用户手动创建一个新的非 ticket Integrator thread。
- Wave Integrator 负责分发 workers、验收、cherry-pick、Gate、正式 `STATUS/FREEZE` 与 `wave-handoff.json`；完成后停止。
- 所有 ticket（包括 `thread_type=integrator`）仍是一 thread 一 ticket；聚合/Gate ticket 只输出状态 proposal。
- 只保留一个 `eval/v3-integration` 集成分支。
- 同一 Wave 的实现线程从相同 `wave_base_sha` 建立独立 worktree。
- 同一核心文件同一时刻只有一个 owner。
- run shard 不修改源码，只写独占 artifact 目录。
- fixture/oracle/metric 先冻结，产品修复独立提交，再用同版输入重跑。
- Testing 与 Evaluation 以 Ubuntu WSL2/Python 3.12 fresh clone 为 canonical 环境；Windows 仅作 best-effort 开发兼容检查。

## 首次使用

1. 将本目录复制为仓库根目录下的 `.codex/eval/`。
2. 将 `AGENTS.addendum.md` 追加/覆盖到仓库根规则。
3. 运行 `python .codex/eval/validate_plan.py`。
4. 使用 `templates/WAVE_INTEGRATOR_PROMPT.md` 手动启动新的 W0 Wave Integrator，由它分发 `EVAL-000`，验收后再分发 `EVAL-001`。
5. 按 `waves/W*.md` 推进；一个 thread 只完成一个 ticket。
