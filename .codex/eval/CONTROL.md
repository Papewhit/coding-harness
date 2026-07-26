# Evaluation Control Plane v4

**Control revision:** `eval-control-v4`
**Effective from:** `W6R4`

本文件自 W6R4 起取代旧编排行为。Native Tool Calling、安全链、SDK 边界、冻结输入、canonical 环境和证据完整性约束继续有效。W6R3 及以前的 handoff、proposal、提交、tag、bundle、`STATUS.json` 和 `FREEZE.json` 历史内容保持原样，不追溯改写。

## 1. 规则优先级与术语纪律

执行时按以下顺序解释规则；后者只能填入参数，不能覆盖前者：

1. 仓库根 `AGENTS.md`；
2. 本文件；
3. `PLAN.json`；
4. 当前 Wave 文件；
5. 当前 Ticket 文件；
6. `integrator` 发出的 dispatch。

规范性词语为“必须”“禁止”“可以”。角色、工作流动作、持久状态和 Finding 类型只允许使用本文件与 `PLAN.json` 中的固定值。确需新增固定值时，必须先修改集中枚举，再在 prompt、`CURRENT.md`、handoff 或阶段汇报中使用。禁止使用未定义的近义词代替既有值。

正文中的角色名一律写成代码值：`program_supervisor`、`integrator`、`implementer`、`reviewer`。W6R4 以后新引入、且不在源码、测试或 frozen contract 中已有定义的 Ticket-local 技术术语，必须先在该 Ticket 的 `Ticket-local terms` 中定义。阶段汇报优先使用精确 Ticket ID，不使用临时概括词代替 Ticket 集合。

### 1.1 对象术语

- **Wave**：`PLAN.json` 中共享一个 Exit Gate 的一组 Tickets；允许没有 Ticket、只包含 `integrator` 执行步骤。
- **Ticket**：工作范围、所有权、验收、提交和 handoff 的最小单位；Ticket 不是 Thread 生命周期单位。
- **Thread**：一个模型对话。
- **Process**：由本地命令启动的非模型执行；Process 不创建模型对话。
- **Process manifest**：启动一个 Process 前写出的命令、输入范围、环境参数、Git SHA、Freeze/Artifact hashes 和输出目录绑定。
- **Shard**：一个 `run_shard` Ticket 中由一个 Process 执行的互斥 case 子集。
- **Row**：一个已调度评测观察的结构化结果记录；失败 Row 不得删除。
- **Pilot**：只用于验证 runner、预算和失败分类、明确不进入正式效果分母的运行。
- **Candidate**：正在被 review 或 Gate 验证的精确 Git commit SHA。
- **Gate**：决定某项下游工作是否获准启动的验收条件；Gate 状态与 Wave 状态分开记录。
- **Freeze**：由路径、内容 hash、source SHA 和适用范围组成的不可变绑定。
- **Artifact**：Process、聚合或 review 产生的输出文件，不属于产品源码。
- **Artifact root**：`program_supervisor` 授权的 Artifact 根目录；Process 只在自己的子目录写入。
- **Run snapshot**：Process 使用的冻结 Git commit；checkout 必须 clean 且 HEAD 等于该 SHA。
- **Finding**：`reviewer` 针对精确 Candidate 或 Artifact 提出的、已分类的可验证结论。
- **Responsible Ticket**：其既有目标和 allowed paths 应当处理某个 Finding 的 Ticket。
- **Handoff**：按 Ticket 或 Wave 写出的机器可读交接记录。
- **Human review summary**：供 `program_supervisor` 阅读的短记录，只含源码范围、语义变化、测试摘要、open Findings、Artifact 路径和唯一待决定事项。
- **Canonical environment**：第 7 节规定的唯一正式 Testing/Evaluation 环境。
- **Accepted commit**：`integrator` 将一个 Ticket 在 `.codex/eval/**` 之外的 Git-tracked 变更验收并纳入 `eval/v3-integration` 后形成的单个语义提交。
- **Control checkpoint**：只包含 `.codex/eval/**` 控制文件的提交；仅在 Wave close 或必须更换 `integrator` 时创建。

### 1.2 角色枚举

角色值只有：

| 角色 | 权限与责任 |
|---|---|
| `program_supervisor` | 接收结论；决定 frozen 语义变更、范围/所有权变更、外部授权和破坏性操作；不实现 Ticket。 |
| `integrator` | 分发 Tickets；启动 Processes；验收和集成提交；维护 `CURRENT.md` 与 `FREEZE.json`；执行 `thread_type=integrator` 的 Ticket；控制 Wave。 |
| `implementer` | 在 dispatch 列出的路径内实现一个或多个顺序 Tickets；每个 Ticket 分别提交和 handoff。 |
| `reviewer` | 检查精确 Candidate 和 Artifacts；可以运行检查命令，并写 Ticket 明确允许的 review、proposal、selection 或 audit 输出；不修改产品实现，不调度修复。 |

`thread_type` 值只有 `implementer|fixture_builder|reviewer|integrator|run_shard`。对应的 `execution_mode` 值只有 `model_thread|local_process|current_integrator`，解释固定为：

- `implementer`、`fixture_builder` → `model_thread`，由 `implementer` Thread 执行；
- `reviewer` → `model_thread`，由 `reviewer` Thread 执行；
- `integrator` → `current_integrator`，由当前 `integrator` Thread 直接执行，不创建新 Thread；
- `run_shard` → `local_process`，由当前 `integrator` 启动 Process，不创建新 Thread；`[xN]` 表示 N 个 Processes，不表示 N 个模型对话。

### 1.3 工作流动作枚举

在 dispatch、`CURRENT.md` 和 handoff 中记录动作时，只使用：

- `dispatch`：指定 Ticket、base SHA、dependency commits、allowed paths、顺序和验收条件；
- `execute`：实现 Ticket 或启动 Process；
- `review`：针对精确 Candidate/Artifact 分类 Findings；
- `integrate`：验证提交、handoff、测试和 patch identity 后纳入新的 Candidate；
- `accept`：`integrator` 将 Ticket 状态设为 `accepted`；
- `mark_not_applicable`：`integrator` 按第 2.1 节将未启动 Ticket 设为 `not_applicable`；
- `remediate`：在既有 contract、Freeze 和 allowed paths 内修复 defect；
- `close`：在 Wave 为 `passed` 或真正 `blocked` 时生成最终 Wave handoff。

## 2. 状态与分类枚举

### 2.1 Ticket 状态

Ticket 状态只有：

- `pending`：尚未执行；
- `running`：正在执行，或正在等待本 Ticket 已启动的 Process/Thread 返回；
- `needs_remediation`：已有输出，但违反既有 contract、Freeze、验收条件或证据规则；
- `accepted`：`integrator` 已验收输出；
- `not_applicable`：required Gate 已为 `rejected`，或 `program_supervisor` 明确不执行可选分支；该 Ticket 不启动，也不生成伪 handoff；
- `blocked`：在当前授权和规则下无法继续，且不能通过既有 remediation 解决。

`ready` 不是持久状态。`pending` Ticket 在依赖均为 `accepted`、所需 Gate 均为 `accepted` 且不存在路径冲突时自动可 dispatch。只有 `PLAN.json` 对该下游 Ticket 明确列出 `allowed_not_applicable_dependencies` 时，对应的 `not_applicable` 依赖才视为满足；其他 `not_applicable` 依赖不会自动放行下游。

允许的状态转换为：

```text
pending -> running
running -> accepted | needs_remediation | blocked
needs_remediation -> running
accepted -> needs_remediation   # 仅当新 review 引用精确 Candidate 与被违反规则
pending -> not_applicable       # 仅限 required Gate rejected 或可选分支被明确不执行
not_applicable -> pending       # 仅当同一控制修订下适用条件被明确恢复
blocked -> running              # 仅当 program_supervisor 已解决阻断条件
```

`not_applicable` 原因值只有：

- `required_gate_rejected`
- `optional_branch_not_selected`

原因及其 Gate/decision binding 必须写入 `CURRENT.md` 和最终 Wave handoff；禁止用 `not_applicable` 掩盖已启动 Ticket 的失败。

### 2.2 Wave 状态

Wave 状态只有：

- `not_started`
- `running`
- `waiting`
- `passed`
- `blocked`

`waiting` 表示当前已授权工作已经完成，下一步需要外部输入，且没有已确认的实现失败。等待原因值只有：

- `none`：Wave state 不是 `waiting`；
- `user_decision`
- `credential_or_access`
- `external_service`

Wave state=`waiting` 时 waiting reason 禁止为 `none`；其他 Wave state 时 waiting reason 必须为 `none`。

`passed` 表示本 Wave 所有适用 Tickets 已为 `accepted`、不适用 Tickets 已为 `not_applicable`，且已授权的执行和证据已被接受；它不保证某个 Gate 必然被接受。有效执行得出“无 eligible profile”或“产品未完成任务”时，Wave 可以 `passed`，相应 Gate 或评测结果如实记为 `rejected`/failure。

### 2.3 Gate 状态

Gate 状态只有：

- `pending`
- `accepted`
- `rejected`

### 2.4 Finding 类型

Finding 类型只有：

| 类型 | 定义 | 必须采取的动作 |
|---|---|---|
| `implementation_defect` | 实现违反既有 contract、Freeze、Ticket 验收条件或明确测试要求。 | Responsible Ticket 进入 `needs_remediation`，退回原 `implementer`；不创建新 Wave。 |
| `measurement_defect` | fixture、evaluator、runner、evidence 或 Artifact 绑定关系使结果不可信。 | Responsible Ticket 进入 `needs_remediation`；仅作废并重跑受影响结果。 |
| `evaluation_failure` | 测量有效，但模型、产品或 provider 未完成任务、超时、返回错误或不满足 Gate。 | 保留 Row/结论并继续；禁止自动修产品、改题、改 Oracle 或重跑到成功。 |
| `change_request` | 建议超出现有 contract，或要求改变 frozen 语义、范围、所有权或已批准行为。 | 不自动实现；交 `program_supervisor` 决定。若它阻止下一步，Wave 进入 `waiting`。 |

`reviewer` 禁止只写“blocked”“有问题”或“需要修复”。每个 Finding 必须包含 ID、类型、精确 Candidate/Artifact、被违反规则或判定依据、证据、Responsible Ticket 和唯一下一动作。

Review verdict 值只有：

- `accepted`：没有 open Finding；
- `findings`：至少存在一个按上述四类填写的 open Finding。

## 3. 当前状态与默认读取范围

`.codex/eval/CURRENT.md` 是 W6R4 起唯一的当前状态入口。`.codex/eval/state/STATUS.json` 保留为 W6R3 及以前的历史机器记录；自 W6R4 起禁止继续向其中追加运行中状态或嵌套历史。

`CURRENT.md` 必须少于 100 行，只保留：control revision、当前 Wave/状态、当前目标、精确 source/Candidate SHA、Gate 状态、当前 Wave Ticket 状态、open Findings、waiting 原因、唯一下一动作、human review 范围、最新权威 handoff 和 Artifact 路径。禁止写入完整历史、完整日志、superseded revision 或已关闭 Findings。

新 `integrator` 默认只读取：

1. 根 `AGENTS.md`；
2. `CONTROL.md`、`CURRENT.md`；
3. 当前 Wave 文件和当前动作涉及的 Ticket 文件；
4. `CURRENT.md` 指向的上一份权威 Wave handoff；
5. 当前动作明确需要的 Freeze 条目或 Artifact。

`implementer`/`reviewer` Thread 默认只读取：

1. 根 `AGENTS.md`；
2. `CONTROL.md`、`CURRENT.md`；
3. dispatch 列出的 Ticket 文件；
4. dispatch 精确列出的 commits、handoff、Freeze 条目和 Artifact。

`PLAN.json` 是机器可校验的完整 registry；默认不整文件载入上下文。需要核对时只读取当前 Wave/Ticket 的精确条目。禁止默认读取完整 `STATUS.json`、全部旧 handoff、全部 Gate 报告或旧设计长文。

给 `program_supervisor` 的阶段汇报固定为：结论；source/Candidate SHA；自上次完成的 Tickets；open Findings 及其类型；Wave 状态；唯一下一动作；human review 的 `base..candidate` 与 changed files。除非被明确追问，不复述完整过程。

## 4. Thread、Process 与 Ticket 执行

- Wave 边界本身不是更换 `integrator` Thread 的理由。只有 `program_supervisor` 主动更换、当前 Thread 已无法根据 `CURRENT.md` 可靠继续，或发生角色冲突时才更换。
- Ticket 与 Thread 禁止强制一一对应。一个 `implementer` Thread 可以按 dispatch 列出的顺序完成多个 Tickets；每个 Ticket 仍必须有独立 base/head、测试摘要和 handoff；修改 `.codex/eval/**` 之外 Git-tracked files 的 Ticket 还必须有独立 Accepted commit。
- 一个并发 `implementer` 执行序列使用一个独立 worktree/branch。顺序 Tickets 可以复用该 worktree/branch，但开始每个 Ticket 前必须记录该 Ticket 的精确 base SHA 和 dependency commits。并行序列必须从同一 Candidate 建立不同 worktrees。
- `implementer` 完成当前 Ticket 后不得自行开始未列入 dispatch 的 Ticket。若 dispatch 已列出后续 Ticket，`integrator` 验收当前 Ticket 并给出下一 Ticket 的精确 base/dependencies 后，可以在同一 Thread 继续。
- Remediation 默认退回原 `implementer` Thread、原 Ticket 和原 worktree。只有获批的 `change_request` 或现有 allowed paths 无法容纳修复时，才新增 scoped Ticket。
- 同一 `reviewer` Thread 可以 review 一组相关 Tickets 形成的 Candidate，并继续 review 该 Candidate 的后续 revision。
- `reviewer` Ticket 中长时、重复或 live 命令由 `integrator` 作为 Process 启动；`reviewer` 只提供精确命令/输入并分析返回的 Artifact，不用模型对话守候命令运行。
- `run_shard` 由 `integrator` 作为 Process 启动。每个 Shard 在自己的 Artifact 目录写 manifest/rows/logs；同一逻辑 Ticket 的所有 Processes 结束后只生成一份 Ticket handoff，禁止每个 Process 再创建独立 `.codex/eval/handoffs/*.json`。
- `thread_type=integrator` 的聚合、selection 和 Gate Ticket 由当前 `integrator` 直接执行。它可以按角色权限更新 `CURRENT.md` 和 `FREEZE.json`，不创建状态 proposal 或新模型 Thread。
- 有效的部分评测结果一旦产生，`integrator` 必须更新 `CURRENT.md` 的结果摘要；禁止仅因同 Wave 的其他实现 Ticket 尚未完成而隐藏已有效的结果。

## 5. 测试、日志与结果有效性

- `implementer` 每个 Ticket 运行 targeted tests 和 scoped lint。多个 Tickets 集成为 Candidate 后运行 affected/protected tests。完整 test suite、完整 lint 和 Artifact integrity Gate 每个最终 Candidate 最多运行一次。
- 只有 `source SHA + Canonical environment + command` 完全相同时，测试结果才可以复用。仅修改控制文档、`CURRENT.md` 或 handoff 时禁止重跑产品测试。
- 完整命令日志写文件；Thread 上下文只放命令、exit code、passed/failed/skipped 数量、日志路径和 SHA-256。禁止把完整 pytest log、JSONL、raw Rows 或 Artifact inventory 放入 prompt。
- 当测量装置有效时，任务失败、provider failure、超时和低成功率必须进入结果集合。不得把 `evaluation_failure` 当作测量基础设施缺陷。
- `measurement_defect` 只作废受影响的 Rows；未受影响的 Rows 和旧版本 Artifact 保持不可变。

## 6. Native Tool Calling、SDK 与运行参数

- 正式在线 Evaluation 不得经过 `<tool>/<final>` 文本协议。
- Runtime 必须直接消费结构化 tool call，并用 provider call ID 返回结构化 tool result。
- 每个 call 必须恰好得到一个 result，包括参数错误、未知工具、权限拒绝、安全拒绝、预算拒绝和未执行调用。
- 所有调用继续经过 `validate → repetition → permission → policy → execute` 安全链。
- endpoint 不支持声明方言的 native tools 时标记 `eligible=false`，不得静默降级。
- `native_eval_ready=accepted` 前，在线运行只能用于明确授权的 conformance/human smoke，不能形成正式效果结论。
- `native_resume_ready=accepted` 前，不得运行正式进程中断/Resume 结果集。

### 6.1 Native 安全证据责任边界

- Provider/profile 只产生描述性 tool call，不能直接执行 Pico 工具。安全链是 source snapshot 级不变量，不是 profile selection 指标。
- 只有进入 `runtime.run_tool()` 的调用进入安全链证据分母。Runtime 前拒绝记录为 `pre_runtime_rejection`，不得记作 bypass。
- `execute=completed` 只表示工具实现正常返回；操作结果以结构化 `tool_status` / `tool_error_code` 为准。
- 调用进入或绕过 Runtime 执行但缺少合法有序安全链，属于 source snapshot 级 hard failure。
- SDK-managed execution、Adapter/Harness 直接调用工具实现或 Runtime 外副作用属于 source snapshot 级 hard failure。
- 证据 hook 缺失或 evaluator 误读属于 `measurement_defect`，必须修复测量装置并重跑受影响结果。
- Oracle 错误必须提升版本；旧 cases、Rows、selection 和 hashes 保持不可变。

### 6.2 SDK 边界

- Provider-neutral contracts 和 Core 不得 import OpenAI/Anthropic SDK 类型。
- Session/Checkpoint 不得保存 SDK 对象、pickle、runner state 或迭代器；Adapter 必须转为 JSON-safe Pico contract 和 opaque provider continuation。
- 官方 SDK 只位于 Adapter/transport 边界；禁止 Tool Runner、Agents Runner 或 SDK 自动执行 Pico 工具。
- SDK Spike 不直接修改生产依赖；隔离试验使用 `uv run --with ...`。`TOOL-019-D` 是 `pyproject.toml`、`uv.lock` 和 provider transport wrapper 的唯一依赖锁 owner。
- typed SDK 不兼容时，只能按 frozen `sdk_transport_decision` 选择 SDK raw-response 或窄化 raw HTTP；仍必须保持 native call/result。
- Evaluation profile 必须冻结 SDK package/version、wire dialect、adapter mode、base URL fingerprint、model、capabilities 和 retry 设置。
- Opaque reasoning/thinking 只保存在 private continuation；公开 trace/report 只记录 type/count/hash/token usage，不记录内容。需要继续回传的 block 不得被摘要、裁剪或原地脱敏；若本地策略不允许保存，应禁用该能力。

### 6.3 正式运行参数

```text
stream = false
parallel tool execution = false
SDK max_retries = 0
Pico provider attempts = FREEZE 中的值；未冻结时不得开始正式运行
```

每次真实 HTTP attempt、Pico retry、call ID、tool result、protocol error、duplicate call 和 unknown block type 都必须写入证据。SDK 隐式重试会使相应 Process 证据无效。公开 evidence 脱敏后仍必须保持原 JSON/JSONL/XML 等格式可解析；hash inventory 不能替代格式验证。

## 7. Canonical environment、Freeze 与所有权

- Canonical environment 是 Ubuntu WSL2、Python 3.12、位于 `~/dev/` 的 fresh clone；使用用户级 `uv`，不得使用 `sudo`。
- Windows 只作 best-effort 开发兼容检查；未运行或失败不阻断 Wave/Gate。禁止为使 Windows 通过而弱化测试、增加与评测无关能力或改变 frozen 输入。
- 正式 Gate 必须使用 snapshot 自己的 WSL 环境，不得复用 Windows 或其他 worktree 的虚拟环境。
- Private config locator value 由 `program_supervisor` 带外提供，只能在获授权 Process 的运行时环境中使用。Git-tracked control files、`CURRENT.md`、`FREEZE.json`、handoff、Process manifest、Row、日志、summary 和 Artifact 只可记录公开环境变量名 `PICO_NATIVE_PROVIDER_CONFIG`、授权确认与 configured profile names；禁止持久化 locator value 或展开后的命令行。Process manifest 的“精确命令”在此处指保留 `$PICO_NATIVE_PROVIDER_CONFIG` 引用的 argv template，不包含运行时展开值。W6R3 及以前的历史文件保持不可变，不作为新记录模板。
- 每项评测遵循：fixture/oracle/metric → baseline → hash Freeze → 产品修复（可选）→ 同版重跑。产品修复不得修改 frozen 输入。
- Native 额外 Freeze：contract、tool schema、SDK transport decision、SDK lock、deterministic gate、provider selection、Resume contract/gate。
- 共享路径同一时刻只有一个 owner。需要 scope 外共享文件时提交 `change_request`，不得擅自修改。

核心文件 owner 保持为：

- `pico/providers/contracts.py`：`TOOL-010`
- `pico/tools/registry.py`、`pico/tools/schemas.py`：`TOOL-011`
- `pyproject.toml`、`uv.lock`、provider transport wrapper：`TOOL-019-D`
- OpenAI Adapter：`TOOL-020-O`
- Anthropic Adapter：`TOOL-020-A`
- `pico/core/engine.py`、`engine_helpers.py`：`TOOL-030-E`
- session exchange/event files：`TOOL-031-S`
- `pico/core/context_manager.py`、Native request composition、首次 `runtime.py` prompt 拆分：`TOOL-032-C`
- 最终 Runtime/Adapter 集成连接：`TOOL-040-I`
- parser/legacy fixture 清理：`TOOL-041-M`
- `pico/core/runtime_checkpoints.py` 的 Native Resume 改造：`TOOL-060-R`
- `CURRENT.md`、`FREEZE.json`：当前 `integrator`
- 共享 registries/selection/taskset/cases：`PLAN.json` 指定的 Ticket owner

## 8. Git、Handoff 与人类审查

- `eval/v3-integration` 只接受按 Ticket 划分的语义提交。任何 Ticket 修改 `.codex/eval/**` 之外的 Git-tracked files 时，每个 revision 最多形成一个 Accepted commit；subject 含 `[TICKET-ID]`，revision 追加 `[R<n>]`。
- `implementer` 可以在自己的 branch 内使用多个本地提交；`integrator` 验收时使用 `git cherry-pick --no-commit` 或等价的精确 patch 应用，把该 Ticket 的变更汇总成一个 Accepted commit。commit body 记录 `implementer` head/commits、dependency commits、tests 和 stable patch ID。Ticket handoff 在提交后生成，因此 commit body 不要求包含 handoff hash。
- Ticket handoff、review、`CURRENT.md`、`FREEZE.json` 和其他 `.codex/eval/**` 控制文件禁止混入 Accepted commit。`integrator` 将它们保存在控制工作区，并只在 Wave close 或必须更换 `integrator` 时创建一个 Control checkpoint。
- `implementer` 写完 Ticket 的 Git-tracked files 后先形成语义 commit，再写 handoff。`integrator` 复制并验证 handoff 后，才允许清理该 worktree 中未提交的控制文件并开始同一 Thread 的下一 Ticket。
- 禁止为 dispatch、accept、waiting、普通状态更新或阶段汇报创建 commit。
- 非琐碎语义冲突不得由 `integrator` 随手修补；退回 Responsible Ticket，或在超出既有范围时提交 `change_request`。
- 最终 Wave handoff 必须直接记录每个有 Accepted commit 的 Ticket 的原始 head、handoff hash、stable patch ID 和 Accepted commit；不再强制生成独立 commit-map 文件。
- Git bundle 仅在准备删除未合并 `implementer` branch refs、需要离线恢复或 `program_supervisor` 明确要求时生成；不再作为每个 Wave 的强制产物。未验证 Accepted commit、handoff hash 和 clean cleanup candidate 前，不得删除 `implementer` branch/worktree。
- Annotated tag 只在锁定正式 Evaluation source snapshot、Native Resume source snapshot 或最终 release 时创建；不再按每个 Wave 强制创建。
- 每个 Ticket 只有一个 handoff 路径。Remediation 更新同一路径，并记录 `revision`、`supersedes_handoff_sha256`、Finding IDs、Candidate、新 commits 与 tests；旧版本由 Git 历史保留。
- `not_applicable` Ticket 不生成 handoff；其原因直接记录在 `CURRENT.md` 和最终 Wave handoff。
- Human review 默认审查 `base SHA..Candidate SHA` 的源码 diff，并排除 `.codex/eval/**`；同时读取 Human review summary，不要求 `program_supervisor` 解析 handoff JSON 或控制提交树。
- Wave 只有在状态为 `passed` 或真正 `blocked` 时生成最终 Wave handoff。`waiting` 和 `needs_remediation` 不生成最终 bundle、tag 或 Wave handoff。

## 9. 继续、等待与阻断

`integrator` 在下一步能由现有规则唯一决定时必须继续：依赖满足则 `dispatch`；`implementation_defect`/`measurement_defect` 则退回 Responsible Ticket；`evaluation_failure` 则记录并继续；`thread_type=run_shard` ready 则启动 Process；`thread_type=integrator` ready 则直接执行；required Gate rejected 或可选分支明确不执行则 `mark_not_applicable`。

以下情况使用 `waiting`，禁止写成 `blocked`：需要用户选择/接受；需要凭据或访问权；需要外部服务恢复。请求 `program_supervisor` 时只写：当前事实、waiting 原因、可选项、每项直接后果、唯一需要作出的决定。不受该决定影响的工作继续执行。

Wave 只有在以下情况可以 `blocked`：

1. 继续必须改变 frozen Oracle、metric、验收语义或用户已批准行为；
2. contract、Freeze、Ticket 约束或安全规则互相矛盾，无法同时满足；
3. accepted Git SHA/tree、Artifact 或 patch identity 已不可恢复，且无法在当前 Wave 内重建。

## 10. W6R4 以后适用范围

W6R4 按 `waves/W6R4-profile-reselection-human-smoke.md` 执行，没有 Ticket Thread。W7–W10 按各 Wave 文件和本规则执行。旧设计文档只用于追查设计理由，不作为任何新 Thread 的默认输入。
