# W6R5 — Grounded Human Smoke 与 Durable Trajectory Recovery

## Program-supervisor decision

`program_supervisor` 接受 W6R4 后续复核提出的 `change_request`，新增本 Wave，但不追溯改写 W6R4 的执行记录、Artifact、`W6R4-EF-001` 或 control checkpoint。

本 Wave 记录三个相互区分的 Findings：

- `W6R5-MD-001`（`measurement_defect`）：HSMOKE-V3-A 要求精确写入 `pico sync`，但 prompt 与 fixture 没有向模型提供该目标值，混合了模型知识与 native tool harness 能力。
- `W6R5-MD-002`（`measurement_defect`）：v3 runner 在临时 workspace 中生成 `.pico/` 后删除原目录，只保留结果投影，无法从 durable public evidence 复核完整的 model-exchange、Runtime 与安全事件顺序。
- `W6R5-CR-001`（`change_request`）：用户长期观察到 Agent 可能在已经取得足够任务信息后继续进行无进展的只读探索。W6R4 的四次不同调用是该现象的定性信号，但受 `W6R5-MD-001` 和 `W6R5-MD-002` 影响，不能单独证明产品根因。

## Repair boundary

- 修复对象是 human-smoke measurement contract 与 durable public evidence，不修改确定性 repetition guard、Runtime/Core 或 Provider Adapter。
- human-smoke v2/v3、W6R4 Artifacts 与其 hashes 保持不可变；使用新 v4 manifest、runner、tests 和 Artifact root。
- HSMOKE-V4-A 必须在 prompt 中明确给出目标命令和解释语义。Verifier 仍检查 `read → edit → verify` 与文件后置条件，但不得依赖模型从隐藏 Oracle 猜答案。
- runner 必须在临时 workspace 清理前，将 `.pico/sessions/*.events.jsonl` 与 `.pico/runs/**` 的 public evidence 复制到 durable Artifact，并保持 JSON/JSONL 可解析、call ID 可关联和 hash inventory 完整。
- `.pico/sessions/*.json` 包含 private provider continuation，禁止复制到 public Artifact。需要的 session 诊断信息只能通过既有 public event/run projection 持久化。

## Execution order

1. `EVAL-063-H`：实现并冻结 human-smoke v4 measurement contract；只运行 fake/stub tests，不发 provider HTTP。
2. `AUDIT-063-A`：只读复审 grounded instruction、durable evidence、private/public 边界及 W6R4 历史不变性。
3. `TOOL-063-G`：在 Ubuntu WSL2/Python 3.12 fresh clone 执行 deterministic Gate，并证明 W6R4 selection 可在 production Runtime/Adapter/profile identity 未变化时复用；provider HTTP attempts 必须为 0。
4. `EVAL-063-R`：获得新的明确授权后，对 W6R4 selected profile 执行一次 human-smoke v4 Process。
5. `EVAL-063-M`：验证 Artifact 并请求 `program_supervisor` 接受或拒绝结果，形成新的 `native_eval_ready` 决定。

## Live authorization boundary

创建和实现 W6R5 不等于授权 provider HTTP。`EVAL-063-R` 启动前必须另行取得：

- selected configured profile name；
- Artifact root；
- frozen retry/attempt budget；
- 一次 human-smoke v4 的明确 live authorization；
- private config locator value 已由 `program_supervisor` 带外提供的确认。

控制文件和公开 Artifact 只记录环境变量名 `PICO_NATIVE_PROVIDER_CONFIG`，禁止记录 locator value、secret、raw endpoint 或展开后的命令。

## Gate adjudication

- measurement 无效：相关 Ticket 进入 `needs_remediation`，只作废并重跑受影响的 v4 结果；Gate 不据此接受或拒绝。
- measurement 有效且 grounded smoke 通过，并被 `program_supervisor` 接受：`native_eval_ready=accepted`。
- measurement 有效但仍出现语义失败：保留为 `evaluation_failure`，`native_eval_ready=rejected`。若 durable trajectory 支持产品归因，再由 `program_supervisor` 创建独立产品 `change_request`；不得在本 Wave 自动修改产品。
- W6R5 close 后当前 `integrator` 发送结论性 Wave 汇报并停止。W7 只能由用户在新的顶层 Thread 中启动。

## Exit Gate

human-smoke v4 的 manifest/runner/tests、grounded semantics、durable public trajectory、selection reuse proof、Process manifest、HTTP accounting、Artifact inventory 与 `program_supervisor` 决定均可审计；W6R4 历史不变；`CURRENT.md` 只有一个下一动作。
