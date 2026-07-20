# Evaluation Control Plane v3

## 1. 状态与文档分层

旧详尽方案是设计规范；本文件是永久执行规则；`PLAN.json` 是依赖 DAG；ticket 是单线程工作包；Git commit、handoff、freeze 与 artifact 是跨线程状态。禁止用长对话记忆替代这些状态源。

## 2. Native Tool Calling 硬约束

- 正式在线 Evaluation 不得经过 `<tool>/<final>` 文本协议。
- Runtime 必须直接消费结构化 tool call，并用 provider call ID 返回结构化 tool result。
- 每个 call 必须恰好得到一个 result，包括参数错误、未知工具、权限拒绝、安全拒绝、预算拒绝和未执行调用。
- 所有调用继续经过 Pico 既有 `validate → repetition → permission → policy → execute` 安全链。
- endpoint 不支持声明方言的 native tools 时标记 `eligible=false`；不得静默降级。
- `TOOL-050-S` 前，在线 Evaluation 只能作为 SDK/native conformance probe，不得进入正式效果结论。
- `TOOL-062-G` 前，不得运行正式进程中断/Resume 结果集。

## 3. SDK 边界

- Provider-neutral contracts 和 Core 不得 import OpenAI/Anthropic SDK 类型。
- Session/Checkpoint 不得保存 SDK 对象、pickle、runner state 或迭代器；Adapter 必须转为可 JSON 序列化的 Pico contract 和 opaque provider continuation。
- 官方 SDK 优先作为 HTTP/wire codec；禁止 Tool Runner、Agents Runner 或自动执行 Pico 工具的 SDK 功能。
- SDK Spike 不直接改生产依赖，使用隔离 `uv run --with ...`；`TOOL-019-D` 是唯一依赖锁 owner。
- typed SDK 不兼容时，只能按 `sdk_transport_decision` 选择 SDK raw-response 或窄化 raw HTTP；仍必须保持 native call/result。
- Evaluation profile 固定 SDK package/version、wire dialect、adapter mode、base URL fingerprint、model、capabilities 和 retry 设置。

## 4. 线程类型

### Program Supervisor

当前 plan-level thread，作为用户决策与 Wave 结果汇总入口。它不实现 ticket、不维护运行中 Wave 的共享状态，也不得用聊天记忆替代 Git、`STATUS/FREEZE`、handoff 或 artifact。

### Wave Integrator

每个 Wave 由用户新建一个非 ticket 的 Integrator thread。它从上一 Wave 的不可变 handoff 启动，冻结 `wave_base_sha`，分发 ticket threads，按 `integration_order` 验收并集成，运行 Exit Gate，并且是该 Wave 唯一可写正式 `STATUS.json` 与 `FREEZE.json` 的角色。完成 `wave-handoff.json` 后停止；下一个 Wave 必须使用新的 Integrator thread。

### Integrator Ticket / Aggregator

`PLAN.json` 中 `thread_type=integrator` 的 ticket 仍遵守“一 thread 一 ticket”。它负责聚合、selection 或 Gate 计算，只输出 summary、handoff 以及 `status_proposal` / `freeze_proposal`；不得直接写正式 `STATUS/FREEZE`。Wave Integrator 验证 proposal 后统一落盘。不得顺手承担大块产品实现。

### Implementer

一个 thread 对应一个 ticket、worktree 和 branch。只修改 `allowed_write_paths`，完成测试、commit 和 handoff 后停止。

### Fixture Builder

只写自己的 fixture、reference patch、hidden verifier 或 fragment；共享总清单由唯一 assembler 生成。

### Run Shard

从不可变 `run_snapshot_sha` 运行；源码必须 clean；只写：

```text
<ARTIFACT_ROOT>/<phase>/<run_snapshot_sha>/<shard-id>/
```

manifest 必须包含 source/evaluator/taskset/provider profile/native conformance/SDK decision hash。

### Reviewer

只读 diff、测试和 artifact；发现缺陷输出 review handoff，修复另开 ticket。

## 5. Git 与 Worktree

W0 必须保留当前 `pico/core/runtime_checkpoints.py` 既有工作区修改，记录原 diff hash，并创建所有 worktree 共用的 bootstrap snapshot commit。不得从纯净基准 commit 覆盖该文件。

同一 Wave 所有线程从同一 `wave_base_sha` 创建分支并先验证共同基线。若 ticket 依赖同 Wave 已验收的代码提交，Wave Integrator 必须在 instance manifest 中列出精确 `dependency_commits`；下游线程只能在共同 base 上应用这些提交，不得吸收 integration branch 的其他新提交。handoff 分开记录 dependency commits 与本 ticket 自有 commits。非琐碎冲突必须另开 integration-fix ticket。

每个 ticket instance 必须在启动 handoff/manifest 中记录 ticket ID、instance ID、role、base SHA、branch/worktree、dependency handoff/freeze hash、allowed paths 与 prompt hash。重复 shard 必须使用唯一 instance ID。

## 6. 核心文件所有权

并行时以下路径为单 owner：

- `pico/providers/contracts.py`：`TOOL-010`
- `pico/tools/registry.py`、`pico/tools/schemas.py`：`TOOL-011`
- `pyproject.toml`、`uv.lock`、provider transport wrapper：`TOOL-019-D`
- OpenAI Adapter：`TOOL-020-O`
- Anthropic Adapter：`TOOL-020-A`
- `pico/core/engine.py`、`engine_helpers.py`：`TOOL-030-E`
- session exchange/event files：`TOOL-031-S`
- `pico/core/context_manager.py`、Native request composition、首次 `runtime.py` prompt 拆分：`TOOL-032-C`
- 最终 Runtime/Adapter wiring：`TOOL-040-I`
- parser/legacy fixture 清理：`TOOL-041-M`
- `pico/core/runtime_checkpoints.py` 原生 Resume 改造：`TOOL-060-R`
- `STATUS.json`、`FREEZE.json`：当期 Wave Integrator
- 共享 registries/selection/taskset/cases：ticket 指定 owner；若该 ticket 还需要状态变更，只提交 proposal

需要 scope 外共享文件时停止并提交 ownership change request。

## 7. Evaluation 运行参数

正式 conformance 与效果评测默认：

```text
stream = false
parallel tool execution = false
SDK max_retries = 0
Pico provider attempts = 1（除非 selection artifact 明确冻结其他值）
```

每次真实 HTTP attempt、Pico retry、call ID、tool result、protocol error、unknown block type 都必须写入 evidence。SDK 隐式重试会使 shard 无效。

Opaque reasoning/thinking 只保存在 private continuation；公开 trace/report 只记录 type/count/hash/token usage，不记录内容。任何需要继续回传的 block 不得被摘要、裁剪或原地脱敏；若本地策略不允许保存，应禁用该能力而不是篡改。

## 8. 冻结、修复与版本

每项工作遵循：fixture/oracle/metric → baseline → hash freeze → 产品修复（可选）→ 同版重跑。产品修复不得修改 frozen 输入。Oracle 错误必须提升版本并保留旧结果。

Native 改造额外冻结：contract、tool schema、SDK transport decision、SDK lock、deterministic gate、provider selection、Resume contract/gate。

## 9. Stop / Block

以下阻断对应下游：

- 所有候选 profile 均不满足 native conformance；
- call ID/result 不完整或出现 result 后重复同一调用；
- Runtime/online evaluator 仍包含可执行文本协议 fallback；
- SDK runner 绕过 Pico 工具安全链；
- opaque continuation 丢失或泄漏到公开 artifact；
- architecture/safety/permissions/tool-policy 测试退化；
- hidden verifier 可被任务 workspace 访问；
- Resume kill 前不能证明 native batch/checkpoint 已落盘；
- `executing` 的副作用调用在 crash 后被自动重放。

不相关 lane 可继续。例如 native live probe 阻塞时，Dream fixtures、Context deterministic cases 和 mini repo 仍可建设。

## 10. Handoff

每个 handoff 至少包含：ticket/base/head/commits/files/tests/outputs/hashes/defects/risks/ownership request。Native 相关 ticket 还必须填写 contract/schema/SDK/profile/gate hash，以及是否观察到 text envelope、隐式 retry、unknown block loss 和 safety bypass。

每个 Wave 结束时必须生成 `wave-handoff.json`，至少包含 integration SHA、STATUS/FREEZE hash、accepted/blocked tickets、artifact/handoff 索引、Exit Gate 结果、风险和待用户决策。下一 Wave 只能从该文件与持久化状态恢复，不得依赖上一 Wave 的对话。

W0 Exit Gate 额外要求一次 fresh-controller reconstruction：使用全新只读 thread，仅根据 Git、`STATUS/FREEZE` 和 handoff 重建 integration SHA、accepted tickets、frozen hashes 与 W1 ready set；结果一致后才允许进入 W1。
