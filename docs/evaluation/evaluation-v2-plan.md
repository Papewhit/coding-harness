# Pico 评测方案 v2——可直接执行版

## 文档状态

本文已于 2026-07-27 获用户批准，当前处于**已批准、可执行**状态，启动暂停已经 解除。当前阶段、完成情况和精确下一动作以 [`evaluation-v2-status.md`](evaluation-v2-status.md) 为准；初始执行权限只覆盖 P0–P2 的离线工作，不包含任何真实 provider 请求。

本文规定阶段、顺序和 Gate。已经单独接受的 `docs/evaluation/evaluation-v2-evidence-protocol.md` 只维护证据与判定规则； `pico-evaluation-reset-plan-v2-zh.md` 只作为方案形成背景，不承担执行约束。本文 现为唯一的活动执行计划。

本文不得无解释地引入新名词。确需使用技术名词时，第一次出现必须先用普通中文 说明含义，并给出与 Pico 相关的例子。

## 当前起点

本方案从以下已经发生的历史状态出发，不追溯改写：

- W6R5 已完成 revision 5 和 replacement Process R-03。
- R-03 的 HSMOKE-V4-A 实际完成了 `read_file -> patch_file -> read_file`，但整句英文的字面 `contains` 检查把 语义等价的结果判为失败，因此最终更正为 `measurement_defect`，即测量装置缺陷。
- R-01、R-02、R-03 均为无效测量记录，不构成 Pico 产品效果结论。
- W6R5 已在 control checkpoint `2876cd53e17fd2b6eb089dbfaf14cd67615498fc` 以 `blocked` 关闭。
- `native_eval_ready` 和 `native_resume_ready` 均保持 `pending`；W7 未获授权。
- revision 5 source `e65f370e49fe2ef749e017f33f509997eb1a0cd5` 只作为历史实现保留。

## 本文用语

- **评测行（row）**：一个任务的一次独立执行记录。例如 T01 的第 2 次重复执行是 一条评测行。
- **基线（baseline）**：产品修复前冻结并永久保留的一组评测行，用来与后续改进 结果比较。
- **批次（cohort）**：在同一 source、任务版本、provider 配置和参数下产生的一组 评测行。例如 27 条正式 coding rows 共同组成 `baseline-v1` 批次。
- **主评测行**：正式基线预先列出的 27 条评测行之一，身份固定为任务 T01–T09 各自的第 1、2、3 次运行。主评测行开始后即使测量无效，也保留原身份和结果， 不用同名重跑覆盖。
- **补充批次**：首份基线完成后，为回答新增问题而另行授权的一组评测行。它使用 新的批次名和评测行身份，不能替代或改写主评测行。
- **评测器（evaluator）**：负责启动任务并记录客观事实的程序。它记录文件变化、 测试输出、工具调用和请求次数，不自行判断开放式自然语言是否“表达得足够好”。
- **隐藏检查程序（hidden verifier）**：执行任务的模型看不到、运行结束后才执行的 检查程序。例如运行 mini repo 的测试来判断代码是否工作。
- **判定规则（Oracle）**：把实际结果与预期结果比较的规则。例如检查旧命令已经 消失、新命令已经出现。要求整句话逐字相同的规则称为 exact-string Oracle； W6R5-A 已证明它会误判语义等价的句子。
- **阶段完成条件（Gate）**：判断一个阶段是否已经达到预定交付条件的规则。例如 G1 要求 27 条计划评测行都实际产生最终分类；它不是要求产品全部成功。
- **证据文件（Artifact）**：保存在评测目录中的结果文件，例如原始执行记录、 verifier 输出、公开 trace 和 workspace diff。
- **provider 配置身份（profile）**：用于绑定模型、协议、SDK 版本和公开 endpoint fingerprint 的公开配置身份；不包含 API key 或私有配置路径。
- **执行脚本（runner）**：按任务清单建立 workspace、调用 Pico、运行隐藏检查程序 并收集证据的脚本。
- **任务清单（taskset）**：任务、fixture、workspace 和隐藏检查程序之间的版本化 对应关系。
- **薄连接层（bridge）**：只负责把 runner 的 prompt/workspace 输入交给 Pico Runtime，再把结果交还 runner 的小型适配代码；它不重新实现 Runtime。
- **Codex 审计**：任务运行结束后，Codex 读取原始记录，另行填写判断结果和理由； 它不得覆盖原始记录。
- **代码修订轮次（revision）**：针对同一问题进行的第几版代码修改。例如 W6R5 revision 5 是 human-smoke-v4 runner 的第五次修改。
- **审查结论（Finding）**：审查时记录的一个具体问题，包含唯一编号、证据、影响 范围和下一动作。
- **独立运行（Process）**：不创建新模型对话、由本地命令启动的一次隔离执行。 R-03 就是一次独立运行。
- **只读审查者（reviewer）**：只检查本阶段代码、测试和证据，不修改实现或扩张 工作范围的审查角色。
- **结论—证据核对（claims-to-evidence review）**：逐条检查报告结论是否指向存在 且匹配的证据，并核对样本数、公式和限制；它不重新设计评测。
- **定向测试（targeted tests）**：只运行与当前修改直接相关的测试。
- **限定范围的静态检查（scoped lint）**：只检查当前修改文件的格式和代码问题。
- **运行配置文件（run config）**：P2 生成、用户在 live 运行前确认的 `public/run-config.json`。它固定 source、任务清单、profile、模型参数、重试、 timeout、执行环境和输出目录；live 授权绑定其 SHA-256 哈希。

## 目标

产出一份可审计、可复现、可用于简历和项目改进的评测基线。不得继续执行 W6R5， 也不得按原方案直接启动 W7。

每个阶段由一个新的 Codex 顶层线程负责，使用 GPT-5.6 Sol 作为主要执行模型。 阶段范围应规划为大约 2 小时可以产生一个用户能够直接检查的可见增量；两小时是 规划粒度，不是必须停止的硬期限。只要流程仍在按既定范围正常推进，就可以继续完成 当前阶段。

这里不设置严格的 token、额度或时间上限。真正需要限制的是：递归审查、重复推理、 无界返工，以及一次小问题触发整套阶段审查、状态冻结、交接和重新授权流程。

本文当前可执行范围只包括 P0–P5，并在 P5 完成 G2 检查、向用户报告后停止。 Auto-dream、产品改进和 Native Resume 只保留为后续路线图，不属于本文授权的自动 后续阶段。

## 固定决策

- W6R5 已以 `blocked` 关闭。revision 5、R-03 和三次无效测量均作为历史保留； 不得再创建 W6R5 revision、reviewer、Gate 或 live rerun。
- 原 W7 必须拆分。Native Resume 的实现移到首份评测基线报告之后，不得继续阻塞 正式评测。
- 只有在本文获批且 P0 完成后，`.codex/eval/**` 才降级为只读历史材料，不再作为 活动执行控制面。
- W6R5 专用 manifest、runner 和 tests 从新评测活动路径退役；不得把它们复制为 v2 runner。可以继承的只有从历史问题中提炼出的明确规则与测试场景。
- 用户已接受 `docs/evaluation/evaluation-v2-evidence-protocol.md` 中的七条规则。本文 只能引用规则编号，不得另写一套不同的证据、verifier 或结果分类规则。
- 只要 provider、Runtime、profile 和 SDK 身份没有变化，就复用 W6R4 的 `dashscope-o` profile selection 结论；公开 profile ID 固定为 `sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`。 不重新执行完整 profile reselection。P3 的第一条 T01 Pilot 同时验证 G0，不另发 一次“预检”请求。
- 产品失败是有效的评测数据。只有结果本身不可信时，才能判为测量缺陷。
- 基线数据一经产生即不可覆盖。27 条主评测行中的 `invalid` 也不在同一基线内重跑； 如以后需要补充观察，必须在 P5 之后经用户决定建立独立补充批次。产品修复后必须 创建独立的 post-fix cohort，不得回写或美化原始 baseline。
- 初始执行权限只覆盖 P0–P2 的离线工作，不授权 provider HTTP。P3、P4A、P4B、 P4C 分别需要一次明确的 live 授权；前一阶段的授权不能传递到后一阶段。

## 活动文档

后续评测只使用以下六份活动文档：

- `docs/evaluation/evaluation-v2-plan.md`：本执行计划。
- `docs/evaluation/evaluation-v2-evidence-protocol.md`：已经接受的证据保存、确定性 检查、Codex 审计和结果分类规则。
- `docs/evaluation/evaluation-v2-status.md`：当前阶段和人类可读进度。
- `docs/evaluation/evaluation-v2-user-guide.md`：面向用户的最新评测框架调用方式、调用范围、产物入口和结果解释。
- `docs/evaluation/evaluation-v2-metrics.md`：指标定义和证据边界。
- `docs/evaluation/evaluation-report-v2.md`：最终评测报告。

不得同步改写 reset plan。P0 已建立 status、metrics 和 report；user guide 从 P1 开始随实际交付建立并动态更新。任何活动文档都不能与本文并行维护另一套阶段、Gate、证据规则或指标公式。

## Artifact 根目录与 live 配置冻结

所有 Evaluation v2 Artifact 使用同一外部根目录：

- Windows：`F:\dev\llm\pico-eval-artifacts\evaluation-v2`
- Ubuntu WSL：`/mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2`

P1–P4 的命令以 Ubuntu WSL2、Python 3.12 fresh clone 为规范环境；Windows 路径只是 同一外部 Artifact 目录的宿主机表示。

每个批次的实际根目录是 `<外部根目录>/<cohort-id>/<source-sha>`。本计划使用：

- P1：`module-baseline-v1/<source-sha>`
- P3：原始 cohort 为 `pilot-v1/<source-sha>`；评测桥接修复后的重新授权 cohort 为 `pilot-v2/<source-sha>`，两者禁止合并或互相覆盖
- P4A–P5：`baseline-v1/<source-sha>`

`<source-sha>` 必须是启动该批次前用户接受的完整 Git commit SHA。批次目录在首次 写入配置前必须不存在或为空；live 开始前可以只包含已接受的 run config，所有 评测行目录都必须尚不存在。已产生的评测行目录不可变；确定性汇总报告可以从这些 行重新生成，但不能反向改写行证据。补充批次不在本次执行范围内；若以后建立，必须 使用新的 `cohort-id`。

P2 必须为 `pilot-v1` 和 `baseline-v1` 各生成一份 `public/run-config.json` 及其 `public/run-config.sha256`。配置至少固定：

- source commit 和 tree；
- taskset 与 `taskset.lock.json` 的路径和 SHA-256；
- profile 名 `dashscope-o`、上述公开 profile ID、模型名、协议类型和 SDK 版本；
- 模型支持的采样参数、最大输出 token、最大工具步数、单行 timeout；
- `stream`、并行工具执行、SDK 自动重试、Pico provider attempt/retry 设置；
- Ubuntu WSL 和 Python 版本；
- Windows 与 WSL Artifact 路径；
- Pico live client command 及其文件哈希。

SDK 自动重试固定为 0，评测行不做自动语义重跑。某项参数若 provider 不支持，配置中 必须明确写成“不适用”，不能省略后由执行者猜测。私有配置 locator 使用 `PICO_NATIVE_PROVIDER_CONFIG`，只通过 launcher 的进程内存带外注入规范 WSL 进程；配置文件只记录变量和目标文件的存在性、类型检查结果，绝不记录 locator 或 credential 值。若 WSL 已关闭 Windows 环境变量继承，launcher 只能在自身进程内 设置 `WSLENV` 的 `PICO_NATIVE_PROVIDER_CONFIG/p` 映射，不得把 locator 写入仓库、 Artifact、命令行参数或持久化的 shell 配置。

用户必须在 P3 前看到并接受这两份配置的内容与哈希。P3、P4A、P4B、P4C 的每次 live 授权都必须绑定：run-config 哈希、source/tree、profile ID、任务和重复编号、 独占输出目录，以及该阶段允许的 provider HTTP 范围。任一绑定项变化都必须停止该 阶段并重新取得授权。

## 证据边界

评测必须明确分成三层，三层之间不得互相替代。

### 运行、Codex 审计与用户决定

评测器只运行任务并记录客观事实。它可以执行隐藏检查程序、测试和明确的状态检查， 但只记录检查内容、退出码和输出；对于开放式语义，不得在运行过程中自动生成最终 成功或失败结论。

Codex 在运行结束后读取不可变的原始执行记录，并在独立的审计记录中填写：

- 这条记录是否足以支持判断；
- 任务结果是否通过、失败或仍有歧义；
- 判断所依据的具体证据；
- 失败属于产品行为、模型行为、provider、基础设施还是测量装置；
- 哪些问题需要用户决定。

用户查看原始执行记录和 Codex 审计记录后作最终决定。Codex 的判断不得覆盖原始 记录；用户决定也必须另行记录。

以下事实通常不需要 Codex 判断：HTTP 次数、call ID 是否对应、工具是否执行或被 拒绝、文件是否存在、隐藏检查程序和测试的退出结果、修改文件范围、耗时和工具调用 次数。

以下内容才需要 Codex 审计：两段自然语言是否表达同一意思、开放式文档修改是否 满足任务意图、摘要是否遗漏关键事实，以及没有确定性检查时应如何解释结果。

本方案不预先实现一个通用的自动自然语言判分系统。P3/P4 编码任务如果已有可靠的 隐藏检查程序，通常不需要额外的自然语言判定；只有隐藏检查无法覆盖的开放式要求或 争议结果，才交给 Codex 审计和用户判断。

### 1. 产品效果层

只回答：

- hidden verifier 是否通过；
- 同一任务多次运行是否稳定；
- 使用了多少工具步骤；
- 是否发生重复读取；
- 执行耗时如何；
- 失败属于什么类型。

### 2. 测量与协议层

只回答：

- 原生工具调用的 call/result 是否闭合；
- provider 实际请求了多少次；
- SDK 和 Pico 各自发生了多少次重试；
- 当前评测行是否可信。

它不负责判断任务是否在语义上完成。

### 3. 公开导出层

只负责：

- 原样复制 Pico 已去敏的 session events、trace 和 report；
- 从私有原件按需生成公开的去敏副本；
- 由确定性脚本生成文件索引、哈希和证据视图；
- 在最终公开目录执行一次实际凭据扫描。

禁止按字段名递归扫描任意 provider/session JSON，也禁止根据陌生字段名称推断其是否 敏感。完整 `session.json`、长工具输出和场景声明的其他原始状态保存在私有证据目录， 不得为了公开导出而改写运行中的 `.pico` 文件。raw SDK/provider 网络响应不得进入 公开证据。

公开导出和私有原件的固定目录结构、文件名及保存规则以 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md) 为准。

每个评测行只能属于以下三种状态之一：

- `valid + passed`：测量可信，任务通过；
- `valid + failed`：测量可信，任务失败，必须进入产品成功率分母；
- `invalid`：结果不可解释，不进入产品成功率分母，但必须单独报告。

评测器生成原始记录时可以暂不填写最终状态。最终状态由确定性检查事实、Codex 审计 和必要的用户决定共同确定，同时保留三者各自的原始记录。

## 已接受的证据与判定协议

详细规则、历史原因、正反场景和固定目录结构保存在 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。 下表只建立执行计划到协议的索引，不替代规则正文。

| 协议规则 | 本计划中的约束位置 | 首次必须验证的 Gate |
| --- | --- | --- |
| 规则 1：provider 请求次数是计量事实 | P2 计量记录、P3 live 运行 | G0 |
| 规则 2：测量失败后保留最小记录和原始证据 | P2 bridge 与 runner | G0 |
| 规则 3：原生工具调用通过 call ID 一一闭合 | P2 bridge 与确定性测试 | G0 |
| 规则 4：私有原件、公开证据和证据视图分层保存 | P2 证据保存、P3 Pilot | G0、G2 |
| 规则 5：确定性证据视图只负责导航 | P2 evidence view、P5 报告 | G0、G2 |
| 规则 6：verifier 只判断明确事实 | P1 verifier、P3–P5 结果审计 | G1、G2 |
| 规则 7：按最小评测行分类结果 | P3–P5 汇总与报告 | G1、G2 |

任何阶段若改变上述规则，必须先修改 evidence protocol 并取得用户确认；不能通过 runner 的局部实现或阶段说明静默改变协议。

## Gate 定义

### G0：测量就绪（Measurement Ready）

P2 的 fake end-to-end 测试通过，并且 P3 的第一条 T01 Pilot 可以按照协议规则 1–5 生成证据完整、可由确定性脚本复算的评测行。T01 是产品 Pilot 本身，不额外运行一个 只为 G0 服务的 live preflight。

若 T01 测量有效，则无论产品结果是 `passed` 还是 `failed`，G0 均可通过；若 T01 测量无效，则 G0 不通过，P3 停止。G0 不要求任务语义成功。

### G1：基线完整（Baseline Complete）

编码任务定义在 [`benchmarks/v3/local-repos/taskset.json`](../../benchmarks/v3/local-repos/taskset.json)， 完整性锁定在 [`taskset.lock.json`](../../benchmarks/v3/local-repos/taskset.lock.json)： 共 9 个任务 T01–T09。P4 为每个任务执行 3 次独立重复，因此 27 条主评测行的身份 在运行前即固定。

G1 通过要求这 27 条评测行全部实际产生最终分类： `valid + passed`、`valid + failed` 或 `invalid`。`missing`、`no result` 或仍待审计的 评测行都表示尚未得到评测结果，因此阻止 G1。产品失败和 `invalid` 结果本身不阻止 G1，但必须按协议分别进入或排除产品成功率统计。补充批次不能用于填补、替代或改变 这 27 条主评测行的 G1 分类。

### G2：评测证据就绪（Portfolio Ready）

G2 通过要求确定性报告检查程序同时证明：

1. 27 条编码评测行都能定位到协议固定的原始证据、`evidence-view.json`、 `checksums.json` 和最终分类；报告引用的 P1 模块结果能定位到固定的五个 JSON 文件及其 `checksums.json`；
2. 报告中的样本数、通过数、失败数、`invalid` 数和聚合指标可以从评测行记录重新 计算，且重算值与报告一致；
3. 所有公开证据链接存在，文件哈希可复算，最终公开目录的凭据扫描通过；
4. 需要 Codex 审计或用户决定的评测行具有对应记录，报告没有把待决定事项写成确定 结论；
5. P5 的一次只读 claims-to-evidence review 已完成，且没有未解决的“结论缺少证据” Finding。
6. `evaluation-v2-user-guide.md` 已覆盖 P1–P5 实际交付的所有评测入口，其命令参数、调用范围、前置条件、产物入口和结果解释与最终 CLI `--help`、测试及 Artifact 结构一致。

## 阶段 P0——停止旧控制面并恢复可见性

### 目标

禁用旧的递归控制路径，让后续 Codex 不再自动恢复 W6R5 或按原计划进入 W7。

### 工作内容

- 以 clean control checkpoint `2876cd53e17fd2b6eb089dbfaf14cd67615498fc` 为历史起点；不再重复处理已经提交的 `CURRENT.md`、`FREEZE.json` 或 W6R5 Wave handoff。
- 从活动路径移除 W6R5 专用的三个文件：
  - `benchmarks/v3/native-provider/human-smoke-v4.json`
  - `scripts/run_v3_native_human_smoke_v4.py`
  - `tests/test_v3_native_human_smoke_v4.py`
- 更新 `AGENTS.md`，明确 `.codex/eval/**` 是历史材料；评测活动入口只有 v2 plan、 evidence protocol 和 v2 status。
- 在 `evaluation-v2-status.md` 的起点说明中，将 R-01、R-02、R-03 均记录为无效 测量尝试并从所有产品指标中排除；R-03 的 exact-string Oracle 问题必须作为主要 结论保留。不再新增一份内容重复的 W6R5 复盘文档。
- 保持本文为 `docs/evaluation/evaluation-v2-plan.md`，并创建 `evaluation-v2-status.md`、`evaluation-v2-metrics.md` 和报告骨架；已经接受的 evidence protocol 保持为单独的规范附件。不得保留两个同时活动的 plan。
- 验证 plan、evidence protocol 和 taskset 的相对链接目标逐一存在。

### 验证

- 运行 `git diff --check`；
- 不运行全仓测试；
- 不发起 provider 请求。

### 阶段交付物

一个只包含 P0 预定改动的 Conventional Commit、提交后的 clean 工作区，以及一份 状态页，明确列出：

- 已经完成的能力；
- 尚未完成的工作；
- P1 是下一项精确动作。

## 阶段 P1——确定性模块基线

### 目标

把已有的 context、memory 和 recovery 工作转化为第一份用户可见、可复现的指标报告。

### 工作内容

- 新增薄 CLI wrapper `scripts/run_evaluation_v2_modules.py`；wrapper 只负责编排、指定 输出路径和生成清单，必须调用现有 evaluator，不得复制实现。
- 使用命令 `uv run python scripts/run_evaluation_v2_modules.py --output-root <module-root>` 依次调用：
  - `pico.evaluation.evaluator.run_harness_regression_v2`；
  - `pico.evaluation.metrics.run_context_ablation_v2(repetitions=5)`，覆盖 12 组配置；
  - `pico.evaluation.metrics.run_memory_ablation_v2(repetitions=5)`，覆盖 12 个任务；
  - `pico.evaluation.metrics.run_recovery_ablation_v2(repetitions=3)`，覆盖 10 个任务；
  - `pico.evaluation.metrics.write_benchmark_core_report`。
- `<module-root>` 固定为 `F:\dev\llm\pico-eval-artifacts\evaluation-v2\module-baseline-v1\<source-sha>`； 对应 WSL 路径使用前述根目录映射。
- 在 `<module-root>/public/modules/` 生成 `harness-regression-v2.json`、`context-ablation-v2.json`、 `memory-ablation-v2.json`、`recovery-ablation-v2.json` 和 `checksums.json`，并在 `<module-root>/reports/` 生成 `pico-module-baseline-v2.json` 与 `pico-module-baseline-v2.md`。
- 在报告中明确标注：这些结果属于确定性、模块级证据，不属于真实端到端编码任务结果。
- 创建 `docs/evaluation/evaluation-v2-user-guide.md`，记录 wrapper 实际支持的完整命令和参数（包括只验证既有 Artifact 的参数）、clean checkout 与输出目录前置条件、调用的现有 evaluator、明确不调用的 provider/网络范围、产物入口和结果解释。

### 验证

- `uv run pytest tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`；
- `uv run ruff check scripts/run_evaluation_v2_modules.py tests/test_evaluation_v2_modules.py`；
- 对五个 JSON 文件重算哈希，并验证 Markdown 可由报告 JSON 确定性重建；
- 核对 wrapper 的 CLI `--help`、targeted tests 与 user guide 中的参数、前置条件和示例一致；
- 不发起 provider 请求。

### 修复规则

测量 wrapper 最多允许一次修订。若发现的是产品逻辑失败，应记录结果，不得在本阶段反复修改产品直至通过。P1 完成后先发布模块报告、状态页和 user guide，再进入 P2。

## 阶段 P2——最小真实编码桥接

### 目标

将冻结的 9-task suite 接入真实 Pico Runtime。

### 现有工具复用决定

G0 不重新构建一套 evaluator。以下现有实现是 P2 的起点：

- `pico/evaluation/live_tasks.py` 中的 `LocalLiveTaskRunner`、`TaskSpec` 和 `ClientResult`；
- `scripts/run_local_coding_tasks.py` 的隔离 workspace、外部 client command 和 hidden verifier 调用流程；
- `tests/test_live_task_evaluator.py` 的现有 runner 测试。

它们已经提供 fresh workspace、hidden verifier 隔离、provider-neutral client 结果、HTTP 尝试与 call/result ID 字段以及基础 `evidence.json`。P2 只补齐以下已知 缺口：

- 当前 loader 只接受顶层 `tasks`，不能直接读取实际 `benchmarks/v3/local-repos/taskset.json` 的 `repositories -> tasks` 结构；
- 尚无把真实 Pico Runtime 接入 `PICO_LIVE_EVIDENCE_PATH` 的薄 client command；
- 当前输出目录和单一 `evidence.json` 不符合已接受的证据协议；
- 测量中途失败时还不能保证最小记录、私有原件和确定性证据视图全部留存；
- 当前 trace 去敏逻辑仍按字段名处理，需要由协议规定的公开原件选择与最终凭据扫描 取代。

P2 不得丢弃上述可复用实现后从零重写 runner。

### 唯一允许实施的三项工作

1. 将现有 `repositories -> tasks` 嵌套 taskset 标准化为 `TaskSpec`；不得创建第二份重复 manifest。
2. 实现一个薄 Pico client command：接收 prompt 和 workspace，调用真实 Runtime，并把 `ClientResult` 写入 `PICO_LIVE_EVIDENCE_PATH`。
3. 按协议规则 2–5 保存私有原件、选择公开原始证据，并由确定性脚本生成 `run-record.json`、`evidence-view.json` 和 `checksums.json`；不得复制 raw SDK/provider 网络响应。同时生成前述 `public/run-config.json` 和哈希，供用户在 P3 前确认。

第 2 项的文件固定为 `scripts/run_pico_live_task_client.py`。它必须：

- 在 runner 提供的 fresh workspace 中运行；
- 从 `PICO_LIVE_TASK_PROMPT` 读取任务文本；
- 调用真实 Pico Runtime 和现有 provider adapter，不得使用 SDK Tool Runner 或 Agents Runner；
- 把 provider 请求次数和 `ClientResult` 原子写入 `PICO_LIVE_EVIDENCE_PATH`；
- 对失败原样记录有限字段 `failure_origin`、`failure_stage` 和 `error_type`；外层只能追加 process exit code，不得覆盖这些字段或原始失败类别；
- 保留 workspace 中本次运行产生的 `.pico` 原始文件，供 runner 在清理前按协议复制。

`scripts/run_local_coding_tasks.py` 必须在保留现有离线接口的同时，为 Evaluation v2 明确接受 `--run-config`、`--cohort-id`、`--task`、`--repo` 和 `--repetitions`。 P2 在 run config 中保存 P3、P4A、P4B、P4C 的完整 WSL launch command；后续阶段 只能填入已经绑定的 source/output 路径，不得临时拼装另一条命令。

优先复用：

- `LocalLiveTaskRunner`；
- `run_local_coding_tasks.py`；
- 现有 provider、Runtime 和 profile loader。

### 验证

- `uv run pytest tests/test_live_task_evaluator.py tests/test_evaluation_v2_evidence.py -q`，覆盖：
  - nested taskset loader；
  - fake client、workspace、hidden verifier 的完整端到端流程；
  - 原生 call/result 闭合；
  - 协议固定目录和文件名；
  - 私有原件哈希、确定性 evidence view，以及已知 credential/locator 在私有、 公开和日志中的零持久化检查；
  - run config 完整性、哈希和“不含 locator/credential 值”；
  - fake client 的 provider HTTP 次数必须为 0。
- 另以真实 `CommandClient → 子进程 → live-task client → Pico Runtime` 路径执行离线桥接回归，只在最末端将 provider transport 换成确定性无网络实现。fake client 仍用于证据目录和 verifier 测试，但不得再作为生产桥接可靠性的证明。
- `uv run ruff check pico/evaluation/live_tasks.py scripts/run_local_coding_tasks.py scripts/run_pico_live_task_client.py tests/test_live_task_evaluator.py tests/test_evaluation_v2_evidence.py`。

### 复杂度边界

- 不得新增另一个巨型 runner；
- 新文件超过 500 行，或新函数超过 100 行时，必须拆分，除非留下明确且具体的理由；
- P2 不运行真实 provider。

### 阶段出口

P2 只有在 fake end-to-end、协议测试和 run config 检查全部通过后才能结束。结束时 向用户展示 `pilot-v1` 与 `baseline-v1` 两份 run config 的内容、哈希和 scoped diff； 用户未接受前不得进入 P3。

## 阶段 P3——三任务 Pilot 与 G0

### 目标

获得第一批真实的产品效果评测行。

### 执行内容

- 在用户接受对应 Pilot run config 后，取得只绑定 P3 的一次 live 授权；初始 cohort 使用 `pilot-v1`，评测桥接修复后的新 source 使用独立 `pilot-v2`；
- 复用 `dashscope-o` 和已固定的公开 profile ID；
- 固定运行 T01、T04、T07，各 1 次；先只运行 T01，由它直接完成 G0 测量；
- 使用 run config 中固定的模型参数、预算、timeout、SDK 自动重试 0 和 Pico provider attempt/retry 设置；
- 每条评测行按 evidence protocol 的固定目录保存原始证据和确定性证据视图；
- 由确定性程序生成 `reports/pilot-report.json`，再从它生成 `reports/pilot-report.md`，作为 Pilot 的一页人工可读入口。

### 结果处理规则

- T01 若测量有效，无论 `passed` 或 `failed`，均完成 G0，然后继续 T04、T07；
- T01 若为 `invalid`，保留该行并立即停止 P3；不得启动 T04、T07；
- T04 或 T07 为 `valid + failed` 时记录产品结果并继续；
- 任一行发生基础设施失败或 measurement defect 时，保留已经产生的最小记录，不做 自动 provider HTTP 重试，也不覆盖该行；
- 失败汇总采用固定优先级：测量记录损坏、原始 client/runtime 失败、协议失败、 verifier 失败、成功。后层不得覆盖前层；不能仅按 HTTP 请求数推断失败来源；
- Pico Runtime 在构建首个请求前抛错，只要原始来源、阶段、异常类型、精确请求数和其他协议证据完整，就属于可信的产品失败，可审计为 `valid + failed`。client 无法启动或原始异常丢失时没有产品结论，必须记为 `invalid`；
- 测量问题只能在停止 P3 后提出离线修复方案，不能自动进入新的 revision/reviewer 循环。任何 replacement live 运行都必须使用新的评测行身份和输出目录，并另行 取得用户授权；原 `invalid` 行永久保留；
- 不得为让 Pilot 任务通过而修改 Pico 产品行为。

评测桥接修复后的停止条件是：同类产品异常一旦能稳定形成可信的 `valid + failed`，即停止修补评测器并继续 Pilot；只有仍不能形成可信分类时，才视为新的 measurement defect。

### G0 通过条件

T01 必须满足协议规则 1–5，并可从 `reports/pilot-report.md` 追溯到原始证据。 任务语义成功不是必要条件。不能用 T04、T07 或额外 preflight 替代无效的 T01 来 追认 G0。

## 阶段 P4A、P4B、P4C——正式编码任务基线

任务身份以 [`benchmarks/v3/local-repos/taskset.json`](../../benchmarks/v3/local-repos/taskset.json) 为准。每个阶段只执行一个仓库，共 3 个任务 × 3 次重复 = 9 条评测行：

- P4A：tinyconfig，T01–T03；
- P4B：miniqueue，T04–T06；
- P4C：logslice，T07–T09。

### 共同规则

- P4A、P4B、P4C 启动前分别取得一次 live 授权；每次授权只覆盖本阶段的 9 条主 评测行，并绑定已接受的 `baseline-v1` run-config 哈希；
- P4A 开始前冻结 runner、suite、profile、模型参数和预算，P4B/P4C 只能验证冻结 身份未变，不能静默改动；
- 主评测行 ID 固定为 `baseline-v1-<task-id>-r<1..3>`，例如 `baseline-v1-T01-r1`；
- 每条评测行使用独立 fresh workspace；
- hidden verifier 和 reference patch 不得暴露给 agent；
- 禁止“重跑到通过”；
- SDK 自动重试固定为 0；基础设施失败和 measurement defect 都不自动重跑；
- 产品失败不得停止 batch；
- 正式运行阶段代码冻结，不得边跑边修；
- 出现 measurement defect 时：
  - 保留已经完成和已经无效的主评测行；
  - 若缺陷可能影响尚未启动的行，停止当前阶段；
  - 不自动建立 P4F、revision 或 reviewer；先向用户说明缺陷、受影响行和拟修改 文件；
  - 只有缺陷能从既有不可变原始证据做离线后处理修复、且 run config 完全不变时， 用户接受修复后才可在新的 live 授权下继续未启动、仍为 `missing` 的主评测行；
  - 若修复会改变 Pico Runtime、live client/runner、prompt、fixture、verifier、 profile、模型参数或证据捕获方式，则不得在 `baseline-v1` 中继续；本计划以 G1 未通过停止，由用户另行决定是否建立新基线；
  - 已启动后成为 `invalid` 的主评测行不得在 `baseline-v1` 内重跑；
  - 如需再次观察该任务，只能在 P5 后由用户决定是否建立新的补充批次；补充结果 不改变 G1 的原主评测行分类。

### 每阶段必须发布的部分指标

- valid-run rate；
- verified-run success；
- stable task status；
- failure category；
- tool steps；
- repeated reads；
- elapsed time。

### G1 通过条件

T01–T09 各 3 次重复形成的 27 条计划评测行全部实际得到最终分类： `valid + passed`、`valid + failed` 或 `invalid`。任何 `missing`、`no result` 或待审计 评测行都表示 G1 尚未通过。可计算指标必须完成聚合；因 `invalid` 无法计算的指标必须 明确记录缺失原因和受影响样本。G1 只检查这 27 条预先固定的主评测行，不接受补充 批次代填。

## 阶段 P5——首份项目评测基线报告

### 目标

在开发任何新的 Resume 功能前，先交付可用于简历、项目说明和后续改进的正式证据。

### 报告内容

- 27 条真实编码任务结果；
- 按 repo、task 和 failure category 的分解；
- measurement quality 和 invalid rows，且与产品成功率分开；
- context、memory、recovery 的确定性指标表；
- 三个最重要的已观察改进机会；
- 简历结论映射表：结论、工件、样本数、公式、限制。

报告必须先生成机器可读的 `reports/evaluation-report.json`，其中逐条列出评测行、 聚合指标和结论—证据映射；再由确定性程序从它生成 `reports/evaluation-report.md`。写入仓库的 `docs/evaluation/evaluation-report-v2.md` 只能由该 Markdown 报告发布，不能 独立编辑另一套数据。

### Review

只进行一次只读的 claims-to-evidence review。

Reviewer 不得：

- 重设计 runner；
- 扩张评测范围；
- 启动完整审计循环。

### 验证

- targeted aggregation tests；
- `scripts/verify_evaluation_v2_report.py` 检查评测行引用、文件哈希、聚合重算、 Codex 审计/用户决定记录和公开凭据扫描结果；
- 检查 `reports/evaluation-report.md` 可由 `reports/evaluation-report.json` 确定性重建；
- 发布或合并前运行一次全仓测试。

### 证据整合设计目标

一个不了解历史计划的新读者，可以在十分钟内解释：

- 评测 suite 是什么；
- 一条 row 表示什么；
- 如何判断通过或失败；
- 证据存储在哪里；
- 聚合指标如何得到。

### G2 可验证条件

运行 Gate 定义中的确定性报告检查程序，确认所有证据路径与哈希有效、聚合指标重算 一致、公开凭据扫描通过、所需审计和用户决定记录齐全，并确认 claims-to-evidence review 没有未解决的“结论缺少证据” Finding。

### 本计划的终点

P5 完成 G2 检查后，只向用户报告结果、限制、未解决问题和后续可选方向，然后停止。 不得自动修改产品、建立补充批次、启动 Auto-dream 或进入 Native Resume。

## 后续路线图

以下内容只说明 P5 之后可能另行规划的方向，不属于本计划的执行授权。它们没有阶段编号， 不是 G2 的组成部分，也不能因为 P5 完成而自动启动。

### Auto-dream（优先）

现有 `benchmarks/v3/auto-dream/fragments/D01-D04.json` 和 `D05-D08.json` 只是分片，当前没有冻结的 `cases.json`，因此尚不具备可直接执行的 任务清单。若用户在 P5 后选择该方向，必须先用新的计划明确：

- 如何组装并冻结 D01–D08；
- repetition、确定性检查和指标；
- `.pico/memory/` 等额外状态的证据声明；
- 独立 Artifact 批次和执行授权。

Auto-dream 结果不得被表述为编码任务成功率。

### 产品改进

用户可以根据 P5 的真实结果选择边界清晰、具有共同根因的失败，再为单个根因建立 新的实现计划。任何修复后评测都必须创建独立的 `post-fix` 批次，并保持任务和参数 可比；不得覆盖 `baseline-v1`。

### Native Resume

Resume 需要在 P5 后另建计划。候选工作包括 checkpoint schema、native batch resume policy、真实 subprocess crash/restart contract、最小真实重启案例，以及 Resume 与 Cold 的配对评测；这些候选项的范围、顺序和授权尚未决定。

后续 Resume 工作无论成功或失败，都只能改变 Resume 相关结论，不能追溯改写已完成 的 SDK 接入、原生工具调用、模块指标或编码任务基线证据。

## Codex 执行契约

- 本契约只适用于 P0–P5；后续路线图不因本文获批而获得执行授权；
- 每个阶段使用一个新的顶层线程，并设置一个主要负责人；
- 代码阶段仅在末尾可选一个只读 reviewer；
- run-only 阶段不创建 reviewer；
- 实现阶段运行 targeted tests 和 scoped lint；
- 全仓测试只在 P5 执行一次；
- 每个阶段按“大约 2 小时可以产生一个可观察结果”的范围规划，但这不是停止计时器；
- 正常推进中的阶段可以继续完成，不得仅因到达两小时而中断；
- 当工作偏离既定范围、开始重复返工或准备自动进入新一轮完整审查时，应先停止扩张 范围并向用户报告；
- 不得自动启动下一轮 audit、revision 或 reviewer 循环；
- P3、P4A、P4B、P4C 必须在各自授权前停下并展示准确绑定；不得把计划批准、上一 阶段批准或已有 credential 推断为 provider HTTP 授权；
- live 阶段获得结果后，只完成该阶段的记录、审计和报告，不自动修改产品；
- P5/G2 完成后必须停止并等待用户决定。

### Status 与 user guide 更新策略

`evaluation-v2-status.md` 采用混合更新策略：顶部“当前状态”只保留最新现状并原位更新；当前活动阶段按阶段 ID 建立或更新同一条记录；阶段关闭后该记录冻结，后续不得静默改写，只能追加带原因和 commit 的更正说明。因此 status 同时是当前现状基准和简洁阶段账本，但不承担评测框架使用手册的职责。

`evaluation-v2-user-guide.md` 采用当前版本更新策略：按已交付评测框架维护唯一章节，只描述当前可用接口，不保留已经失效的旧参数或旧命令，历史变化由 Git 保存。每个阶段结束前都必须检查本阶段是否新增或改变评测入口、参数、前置条件、调用范围、Artifact 结构或结果解释；有变化时必须在同一阶段提交中更新对应章节，没有变化时在 status 中明确记录“user guide 无变化”。

每个 user guide 章节至少包含：适用目的与不适用范围、完整命令和参数、运行前置条件、会调用和明确不会调用的组件、写入范围、首选产物入口、结果字段如何解释以及不能推出的结论。指标公式和证据规则分别链接 metrics 与 evidence protocol，不在 user guide 中复制第二套正文。

阶段结束前必须核对 CLI `--help`、相关测试、实际执行命令和 user guide 一致；任何新增参数只存在于代码或测试而没有进入 user guide 时，该阶段不得标记完成。

每阶段必须更新 `evaluation-v2-status.md`，至少包含：

```text
阶段结论
起始与结束 commit
实际修改文件和 diff stat
执行过的命令与测试
新增 rows 与 metrics
有效产品失败
invalid rows
当前 blocker
下一阶段的精确第一步
```

状态页必须字面记录阶段起始 commit 的完整 SHA。阶段结束 commit 无法在自身内容中记录自己的最终 SHA，因此在该 commit 内统一写作“承载本状态条目的 commit”；提交完成后，交付消息必须报告其完整 SHA，下一阶段再把该 SHA 字面记录为自己的起点。不得仅为回填结束 SHA 而创建或 amend 额外 commit。

SHA、JSON 和 inventory 只能作为辅助证据，不能代替人类可读状态说明。

## 应直接复用的现有资产

- Provider SDK adapter、contract 和 transport；
- 原生 Runtime/tool loop 及 W6R3 修复；
- W6R4 已选 `dashscope-o` profile 和公开 profile ID；
- local-repo taskset；
- 三个 mini repo；
- hidden verifier 和 reference patch；
- `LocalLiveTaskRunner`；
- context、memory、recovery metrics。

Auto-dream fixture 和 evaluator 只列入后续路线图资产，不属于 P0–P5 的直接复用范围。

## 从活动路径退役的内容

- W6R5 human-smoke-v4；
- 全局语义 Gate `native_eval_ready`；
- 对任意公开字段的递归扫描；
- 每个微小修复触发的 reviewer → Gate → Freeze → handoff → authorization 循环；
- 原 W7 中让 Resume 新功能阻塞 baseline 的依赖关系。

在 P5 之前，不重构大型历史 evaluator。首先将它们从活动命令路径移除；首份报告完成后，再根据真实调用关系决定删除、拆分或保留。
