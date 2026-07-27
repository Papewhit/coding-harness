# Pico Evaluation v2：证据与判定协议

## 文档状态

本文是
[`evaluation-v2-plan.md`](evaluation-v2-plan.md) 的规范性附件。
用户已接受本文规则；后续 Evaluation v2 的证据保存、检查边界和结果分类必须遵守本文。

本文与 executable plan 的职责严格分开：

- executable plan 规定阶段、执行顺序、Gate 和授权边界；
- 本文只规定证据、确定性检查、Codex 审计和结果分类；
- executable plan 通过规则编号引用本文，不复制或改写规则正文。

Evaluation v2 executable plan 已于 2026-07-27 获批但暂停启动。本文本身不提供任何
独立执行授权，并且：

- 不重新开启 W6R5；
- 不授权修改 Pico 产品、运行新评测或发起 provider 请求；
- 后续对本文规则的修改仍需用户确认。

本文把 W6R5 实际暴露的问题及用户确认的取舍转化为正式规则，不再维护一套相互冲突
的 W6R5 复盘规则。

## 术语

- **评测行**：一个任务的一次独立运行。结果分类、证据有效性和失败影响都以评测行
  为最小单位。
- **原始证据**：Pico 在运行时实际写出的 `.pico` session events、session state、
  run trace、report 和长工具输出。评测器不得为改善结果而改写这些文件。
- **私有原始证据**：原样保留、只供用户和 Codex 诊断的 session 与 run 文件。其中
  可以包含完整会话状态、长工具输出和 provider 续接数据，但不得包含评测器注入的
  provider credential、认证值或私有配置 locator。
- **公开原始证据**：可以进入公开评测目录的原始文件。通常只包括 Pico 已经去敏的
  session events、trace 和 report，不包括完整 `session.json` 和长工具输出原文。
- **确定性证据视图**：由普通程序从原始证据中提取的导航摘要，例如工具调用顺序、
  call ID、退出码、diff 和原始文件位置。相同输入必须得到相同输出；它不是第二份
  权威轨迹。
- **verifier（检查程序）**：检查文件、测试、退出码或其他明确事实的程序。它只能
  判断其检查范围内的事实。
- **Codex 审计**：Codex 在运行结束后阅读确定性证据视图，并在必要时追溯原始证据，
  另行写出解释、结果判断和原因。
- **测量无效**：评测装置没有留下足以解释该评测行的证据。它既不等于产品通过，也
  不等于产品失败。

## 结果与证据的逻辑结构

每个评测行采用以下固定结构。`<artifact-root>` 是本次评测的外部证据根目录，
`<row-id>` 是评测行的稳定标识，`<session-id>` 和 `<run-id>` 使用 Pico 实际生成的
标识。

下面固定私有原件、公开原件、确定性记录、审计和报告的目录与文件名。executable
plan 只能决定 `<artifact-root>` 的实际路径，不能为每个阶段另造一套命名。

```text
<artifact-root>/
├─ private/
│  └─ rows/<row-id>/
│     ├─ original/
│     │  ├─ .pico/sessions/<session-id>.json
│     │  ├─ .pico/sessions/<session-id>.events.jsonl
│     │  ├─ .pico/runs/<run-id>/
│     │  └─ declared-state/             场景预先声明的其他原始状态
│     └─ checksums.json                 私有原件的文件清单与哈希
├─ public/
│  ├─ run-config.json                  本批次冻结的公开运行配置
│  ├─ run-config.sha256
│  └─ rows/<row-id>/
│     ├─ original/
│     │  ├─ .pico/sessions/<session-id>.events.jsonl
│     │  └─ .pico/runs/<run-id>/
│     │     ├─ task_state.json
│     │     ├─ trace.jsonl
│     │     └─ report.json
│     ├─ published-files/               运行后按需生成的去敏副本
│     ├─ verifier/
│     │  ├─ invocation.json
│     │  ├─ stdout.txt
│     │  ├─ stderr.txt
│     │  └─ result.json
│     ├─ run-record.json
│     ├─ evidence-view.json
│     ├─ checksums.json                 公开文件的文件清单与哈希
│     ├─ codex-audit.json
│     └─ user-decision.json
└─ reports/
   ├─ pilot-report.json
   ├─ pilot-report.md
   ├─ evaluation-report.json
   └─ evaluation-report.md
```

`run-config.json` 是执行前由确定性程序生成的批次配置，固定 source、taskset、公开
profile 身份、模型参数、重试、timeout、执行环境、client command 和 Artifact
路径；`run-config.sha256` 记录其 SHA-256。它不得包含私有配置 locator、credential
或其展开值。executable plan 负责规定具体字段、路径、用户确认和 live 授权边界。

用户不应从原始 `.pico` 文件开始阅读。Pilot（正式批量评测前、只运行少量固定任务的
小规模试运行）应通过 `reports/pilot-report.md` 提供一页人工可读结果；完整评测通过
`reports/evaluation-report.md` 提供唯一总入口。对应的 `.json` 是由确定性程序生成
的机器可读报告源，保存评测行引用、聚合值和结论—证据映射；`.md` 必须从同一 JSON
生成，不能独立填写另一套数据。

总报告中的每个评测行必须显示最终状态、一句话结果、原因以及上述各层证据的链接。
JSON、哈希和 `.pico` 只用于追溯核查。需要写入仓库的最终公开报告可以从该总报告
发布到 executable plan 指定的 `docs/evaluation/` 路径，但不得形成内容独立演化的
第二份报告。

## 规则 1：真实 provider 请求次数是计量事实，不是产品正确性判据

### 规则

1. 真实 provider 的每一次 transport 调用尝试都必须由确定性代码计数。
2. 计数必须在后续 verifier、证据复制、公开导出或清理可能失败之前原子落盘。
3. 每个评测行记录自己的精确次数，汇总值必须等于各评测行之和。
4. 同时记录 SDK 重试配置和 Pico 自身重试次数，避免把隐式重试误认为一次请求。
5. fake provider 的合法真实 HTTP 请求次数为 0。

### 为什么保留

R-01 在模型调用完成后因测量装置失败，只能证明真实请求“至少发生过一次”；R-02 和
R-03 修补后分别留下了精确次数。这说明请求计数必须先于容易失败的验证步骤保存。

计数的用途是解释成本、延迟、重试和授权是否被消费。它不能证明模型回答正确、工具
调用有效或产品通过。

### 场景

- **应通过**：评测行 A 记录 4 次、B 记录 2 次，汇总为 6 次，三处记录一致。
- **计量无效**：异常后只能恢复 `unknown` 或 `>=1`。该评测行不能参与请求次数、
  成本或重试指标。
- **不得连带推出**：请求次数不可恢复，不应自动推翻证据完整的产品语义结果；只有
  依赖请求计数的指标和授权审计无效。

### 必须记录

评测行身份、请求次数、计数是否精确、SDK 与 Pico 重试配置、开始与结束时间、计数
记录文件的哈希。

## 规则 2：测量失败后仍必须保留最小记录和已经产生的原始证据

### 规则

1. 评测器必须在开始运行前创建最小运行记录，至少写入评测行身份、源码身份、开始
   时间和当前阶段。
2. 后续发生 runner、provider、verifier、证据保存或清理错误时，必须更新该记录，
   写明失败阶段、错误类型、已知退出码、已知请求次数和已有证据位置。
3. 已产生的私有原始证据必须尽可能原样保留；不能因为最终验证失败而删除整个输出
   目录。
4. 只有证据完整且 verifier 合法的失败才能记作产品失败；测量装置自身失败应记为
   `invalid`。

### 为什么保留

R-01 失败后只留下空目录，无法知道具体失败阶段和精确请求次数。后续 revision 增加
部分结果后，R-02 即使轨迹验证失败，仍能说明 A 已运行、B 未启动以及请求次数。这种
部分记录不能把测量故障变成产品结论，但能防止证据完全消失。

### 场景

- **应通过**：A 在证据保存阶段失败，运行记录仍显示 Pico 退出状态、verifier 是否
  启动、请求次数和已有私有证据；B 明确标为未启动。
- **应判测量无效**：只剩 stderr 或空目录，不能确定运行到了哪一步。
- **不得连带推出**：A 测量无效不能把 B 记为失败，也不能抹掉其他独立评测行的有效
  结果。

### 必须记录

运行是否开始、当前阶段、错误类型、Pico 与 verifier 退出码、请求次数是否精确、
原始证据是否存在、相关文件路径和确定性哈希。

## 规则 3：每次原生工具调用必须通过 call ID 一一闭合

### 规则

1. 每次模型工具调用必须有非空且在该评测行中唯一的 call ID。
2. 模型提出的调用、工具结果、Runtime 完成记录以及选入证据的 run trace 必须使用
   同一个 call ID 和工具名。
3. 各证据层的 call ID 集合不得缺失、多出、重复或交叉配对。
4. 工具成功、被拒绝和执行错误都属于终态，都必须用原调用的 call ID 闭合。
5. 以上对应关系、顺序和集合比较必须由确定性程序计算，不能交给 LLM 填写。

### 为什么保留

W6R5 多个 revision 都需要检查这一对应关系。只要把一个 `tool_finished` 的 call ID
改成其他值，就可能把别的工具结果或安全记录拼到当前调用上，形成表面完整但实际
错配的轨迹。

普通 `permission_decision` 事件当前没有直接携带 call ID，而 W6R5 通过额外评测
记录补足了对应关系。这说明产品的权限审计可观测性仍可改进，但它不是已经证实的
权限绕过。权限判断本身是否正确，应由产品安全测试回答。

### 场景

- **应通过**：同一评测行连续出现两个同名 `read_file`，虽然完成事件顺序不同，仍
  能根据各自 call ID 正确对应结果。
- **应判相关轨迹无效**：一个 Runtime 完成记录缺少 call ID、重复使用另一个调用的
  ID，或工具名与该 ID 对应的模型调用不同。
- **不得连带推出**：call ID 全部闭合只能证明证据没有错配，不能证明工具参数正确、
  副作用符合任务意图或最终答案良好。

### 必须记录

模型调用、工具结果、Runtime 完成记录和 run trace 的原始位置；确定性程序生成的
call ID 集合、调用顺序、工具名匹配结果以及相关原始文件哈希。

## 规则 4：运行原件、公开证据和确定性证据视图必须分层保存

### 规则

1. 每个场景必须在运行前声明需要持久保存的产品状态路径。默认包括本评测行对应的
   `.pico/sessions/` 和 `.pico/runs/`；Dream、Plan 或其他状态型场景必须再明确列出
   `.pico/memory/`、`.pico/plans/` 或相应目录。
2. 临时 workspace 删除前，必须原样保存已声明路径，并由确定性脚本生成原路径、
   文件清单、大小和 SHA-256 哈希。sessions/runs 保持原目录结构；额外路径复制到
   `private/rows/<row-id>/original/declared-state/`，同时记录其 workspace 相对路径。
3. 私有原始证据是诊断材料，保留完整 `session.json`、长工具输出以及 provider
   续接状态。它不自动参与通过或失败判定。
4. 评测器注入的 provider credential、认证值和私有配置 locator 不是诊断材料，
   任何情况下都不得写入 `.pico`、私有 Artifact、公开 Artifact 或日志。Pico 的
   session events、trace 和 report 必须继续使用现有持久化去敏路径；评测器只针对
   本次进程已知的实际配置敏感值做精确命中检查，不按陌生字段名猜测。若复制前发现
   命中，不得把命中文件复制到持久 Artifact，只能留下不含命中值的 `invalid` 记录。
   这条规则不授权评测器改写模型仍可能读取的普通工具输出。
5. 运行中的 `.pico/runs/.../artifacts/*.txt` 可能被模型随后读取，评测器不得在运行
   期间修改或去敏这些文件，否则会改变产品行为。
6. 公开原始证据只选择 Pico 已去敏的 session events、trace 和 report。完整
   `session.json` 与长工具输出原文默认不进入公开目录。
7. 如果公开结论确实需要引用长工具输出或已声明的额外状态，只能在运行结束后另行
   生成去敏副本并放入 `public/rows/<row-id>/published-files/`；私有原件保持不变。
8. 公开导出前执行一次普通的凭据扫描，检查实际 credential、token 和认证值；不得
   恢复 W6R5 那种按任意 JSON 字段名猜测隐私含义的递归扫描器。
9. 清理临时 workspace 后，必须核对保存文件的哈希和清单。无需重新解释整棵
   `.pico` 事件树。

### 为什么保留

W6R5 使用临时 workspace。如果只在 workspace 存活时验证，清理后就无法复盘。但
W6R5 随后把“证据耐久”扩展成了复制、重新解析、隐私推断和重新构造整棵公开事件树，
导致多个 measurement defect。

Pico 已经区分公开事件和私有 session：session events 与 run trace 在正常路径中
经过 `redact_artifact`，完整 session 则用于恢复并保留私有 continuation。后续评测
应利用这项现有分层，而不是建立第二套 provider 字段解释器。

### 场景

- **应通过**：临时 workspace 删除后，私有原件仍可供用户/Codex 诊断；公开 events、
  trace 和 report 可由哈希证明未被改写。
- **应判相关证据无效**：清理后缺少原件、文件哈希变化、任一持久化目录出现评测器
  注入的实际 provider credential/locator，或为了公开去敏而在运行期间改写模型
  可能读取的工具输出。
- **不得连带推出**：证据保存完整不表示任务语义通过，也不表示所有私有内容适合
  公开。

### 必须记录

私有与公开证据目录、场景预先声明的状态路径、原始 workspace 相对路径、文件清单、
文件大小、SHA-256、复制和清理时间、凭据扫描结果、公开副本与私有原件的对应关系。

## 规则 5：确定性证据视图负责导航，原始证据仍是事实来源

### 规则

1. 评测器不得重造另一套被当作权威来源的精简轨迹。
2. 确定性脚本可以从原始证据生成证据视图，帮助 Codex 和用户避免先阅读全量
   session。
3. 证据视图至少列出工具调用顺序、call ID、工具状态、修改文件与 diff、最终回答、
   verifier 输出及退出码、provider 请求次数，以及每项事实的原始文件位置。
4. 文件清单、哈希、session/run 对应关系、调用顺序、计数和退出码必须由确定性程序
   计算；LLM 不得填写、修复或覆盖这些内容。
5. 每个提取事实必须指回原始文件和稳定位置。原始证据与证据视图冲突时，以原始证据
   为准并把冲突记为测量问题。
6. Codex 先阅读人工报告和证据视图；只有遇到歧义、诊断失败原因或核查提取结果时，
   才追溯公开原件或私有 session。

### 场景

- **应通过**：证据视图显示 `read_file -> patch_file -> read_file`，每一步都带 call
  ID、状态、原始事件位置和文件哈希；Codex 无需先读取完整 session。
- **应判视图无效**：LLM 自行总结调用顺序、脚本生成的哈希无法复算、视图遗漏原始
  记录中的工具调用，或视图中的事实没有原始位置。
- **不得连带推出**：证据视图生成成功只能证明导航材料可复算，不能代替 verifier、
  Codex 审计或用户决定。

## 规则 6：verifier 只判断明确事实，开放语义交给 Codex 审计和用户

### 规则

1. verifier 可以检查文件是否存在、命令/API/路径是否精确、测试退出码、工具是否
   执行或被拒绝、文件修改范围以及其他具有唯一机械答案的事实。
2. 只有任务或规范明确要求逐字一致时，才允许整句 exact-string 检查。
3. 允许同义表达的说明文字、摘要和开放式文档修改，不得因整句措辞不同而自动判为
   产品失败。
4. 评测器只运行并记录 verifier 的命令、输入身份、退出码和输出；它不自动生成开放
   语义结论。
5. Codex 在独立审计记录中判断自然语言是否满足任务意图、证据是否足够，并说明原因；
   有争议或需要价值判断的结论交给用户决定。
6. Codex 审计和用户决定不得覆盖原始记录、确定性证据视图或 verifier 输出。

### 为什么保留

R-03 的文件实际写成：

`Run pico sync before opening the workspace so that all dependencies are ready.`

旧 verifier 只接受：

`Run pico sync before opening the workspace so dependencies are ready.`

两句表达相同含义，唯一差异是 `that all`，却被判为失败。这是 verifier 测量缺陷，
不是产品失败。

### 场景

- **应通过确定性检查**：要求把命令改为 `pico sync`，结果不再包含 `pico setup`，
  文件存在且测试通过。
- **应交给 Codex 审计**：要求说明依赖应在打开 workspace 前准备好，实际文字使用了
  不同但可能等价的表达。
- **可以合法 exact-string 失败**：任务明确要求写入固定协议字符串、API 字段、命令、
  路径或逐字声明，而实际内容不同。
- **不得连带推出**：纠正一次错误的 exact-string 判定不能证明模型在其他文档任务中
  都会成功。

### 必须记录

任务原文、verifier 的每个检查项、命令与退出码、stdout/stderr、修改前后文件哈希、
统一 diff、最终文件内容位置，以及 Codex 判断所引用的具体证据。

## 规则 7：结果必须按最小评测行区分有效通过、有效失败和测量无效

### 规则

每个已经完成判断的评测行只能属于以下三种结果之一：

- `valid + passed`：证据可信，任务通过；
- `valid + failed`：证据可信，任务失败；
- `invalid`：证据不足或测量装置故障，不能判断产品通过或失败。

此外：

- 未启动的评测行是 `no result`，不是产品失败；
- 等待 Codex 或用户判断的评测行可以暂记为“待审计/待决定”，但这不是最终结果；
- 分类必须落到最小评测行，不能用一个评测行的 measurement defect 抹掉另一行的
  独立结果；
- `invalid` 不进入产品成功率分母，但必须单独报告数量、原因和受影响范围。

### 场景

- A 的测量装置失败、B 有完整 PASS 证据、C 尚未启动时，必须分别保留
  `invalid`、`valid + passed`、`no result`。
- verifier 合法、证据完整且任务未完成时，必须记为 `valid + failed`，不能为了避免
  产品失败而改记为测量无效。
- 单独一个 PASS 评测行不能推出整个 suite 通过。

### 必须记录

评测行是否启动、证据是否足够、确定性检查结果、Codex 审计状态、用户决定状态、最终
分类、分类原因以及受影响的统计范围。

## 支持性实现条件

以下内容应保留为基本 runner 条件，不需要提升为核心评测原则：

1. fake 与 live 模式必须明确标识，fake 结果不得冒充真实模型结果，fake 模式真实
   HTTP 请求次数必须为 0。
2. 执行、原始证据保存、确定性证据视图、verifier、公开导出和汇总应分成清楚的职责；
   不再由一个 `run_manifest()` 同时承担 provider、agent、verifier、trajectory、
   scanner、inventory 和最终结论。
3. “危险工具被拒绝后继续执行”属于具体产品安全场景，不是通用评测协议。其 call ID
   对应要求已包含在规则 3；权限是否正确和拒绝后是否安全继续，由产品安全测试覆盖。

## 明确不继承的 W6R5 做法

1. 不再对任意 JSON 按字段名递归猜测隐私含义。
2. 不再为上述扫描器持续增加 provider 字段形状例外及对应测试。
3. 不再复制后重新解释完整 `.pico` 公开事件树；只原样保存原件、确定性计算哈希，并
   生成带原始位置的导航视图。
4. 不再把整句自然语言 exact-string 当作默认语义 verifier。
5. 不允许 LLM 计算或填写文件清单、哈希、调用顺序、计数和退出码。
6. 不为公开去敏而改写运行中的 `.pico` 文件；私有原件保持不变，公开副本在运行结束
   后另行选择或生成。
7. 不继承 W6R5 的固定场景名、Process ID、source/profile 绑定、一次性授权或 scripted
   response 文本作为 Evaluation v2 的永久协议。

## 由 executable plan 决定的事项

本文只确定可复用规则，不在此重复：

- Evaluation v2 的实际 Artifact 根路径和批次名；
- Pilot 与正式评测的具体任务集合；
- live 运行的分阶段授权、冻结参数和是否允许重跑；
- 是否以及何时修改产品自身的权限审计事件；
- executable plan 中各阶段如何安排实现与审查。

这些事项必须由活动 executable plan 明确，不能从 W6R5 历史实现自动继承。plan
可以收紧执行范围，但不得改变本文的证据事实来源、分层保存和结果分类规则。
