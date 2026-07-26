# Pico v3 Evaluation：W6R4 以后执行入口

当前控制修订为 `eval-control-v4.2`，在 W6R4 close 完成后立即生效；W6R4 的 Wave 文件、执行记录、handoff 和 Artifact 不追溯改写。本修订只改变 `program_supervisor`/`integrator` 的 Thread 位置、单 Wave 生命周期、沟通方式，以及 `waiting`/`blocked` 的处理边界；Native Tool Calling、安全链、SDK 边界、冻结输入、canonical 环境和证据完整性要求不变。

## 从哪里开始

任何后续 `integrator` 先读取：

1. 仓库根 `AGENTS.md`；
2. `.codex/eval/CONTROL.md`；
3. `.codex/eval/CURRENT.md`；
4. CURRENT 指向的当前 Wave 文件、当前动作涉及的 Ticket 文件和最新权威 handoff。

`PLAN.json` 是机器 registry；运行 `validate_plan.py` 校验，只有排查不一致时才读取当前 Wave/Ticket 的精确条目。`implementer`/`reviewer` 只读取 AGENTS、CONTROL、CURRENT、dispatch 列出的 Ticket，以及精确列出的 commits/Freeze/handoff/Artifact。不要默认读取完整 `PLAN.json`、`STATUS.json`、全部旧 handoff 或旧长方案。

## 当前控制原则

所有固定角色、动作、状态、原因、Finding 类型和 review verdict 都集中定义在 `CONTROL.md` 第 1–2 节；`PLAN.json.enums` 仅作为机器可校验镜像。新增固定值必须先同时修改这两处。

- Ticket 是工作、提交、验收和 handoff 单位，不是 Thread 生命周期单位。
- 一个 `implementer` Thread 可以按 dispatch 顺序完成多个 Tickets；每个 Ticket 仍有独立 commit、测试摘要和 handoff。
- 每个 Wave 使用一个新的、用户可见的顶层 `integrator` Thread；`program_supervisor` 是独立、长期保留的顶层 Thread。详细边界以 `CONTROL.md` 为准。
- `thread_type=run_shard` 由 `integrator` 启动本地 Process；`[xN]` 是 N 个 Process，不是 N 个模型对话。
- `thread_type=integrator` 由当前 `integrator` 直接执行。
- `reviewer` 必须把 Finding 分类为 `implementation_defect`、`measurement_defect`、`evaluation_failure` 或 `change_request`。
- `evaluation_failure` 是结果，不自动触发产品修复。
- `.codex/eval/CURRENT.md` 是当前状态入口；`state/STATUS.json` 只保留 W6R3 及以前历史。
- Human review 使用 `base..candidate` 源码 diff 和短 review summary，不要求阅读 handoff JSON 或控制提交树。

## 两个 Gate

- `native_eval_ready`：W6R4 使用 W6R3 accepted source 完成 profile reselection、授权 human smoke 和 `program_supervisor` 接受后才可为 `accepted`。
- `native_resume_ready`：`TOOL-062-G` 通过后才可为 `accepted`。

Gate 状态使用 `pending|accepted|rejected`。Wave 状态使用 `not_started|running|waiting|passed|blocked`；需要用户授权、凭据或外部服务时使用 `waiting`，不使用 `blocked`。

## W6R4 与后续 Wave 的交接

W6R4 已按 `waves/W6R4-profile-reselection-human-smoke.md` 和当时有效规则执行并 close；该 Wave 文件与其执行记录、handoff 和 Artifact 保持不变。v4.2 适用于此后启动的第一个 Wave 及所有后续 Wave，包括需要新增的 W6R5。每个后续 Wave 由用户在新的顶层 Thread 中启动。实时 Gate 和下一动作只以 `CURRENT.md` 为准。

## 计划校验

```bash
python .codex/eval/validate_plan.py
```

旧 `docs/enhancements/pico-v3-evaluation-codex-phased-plan.md` 和 W6R3 及以前控制材料只作为历史设计与审计来源。
