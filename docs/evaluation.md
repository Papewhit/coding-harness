# Coda 综合测评报告

## 报告说明

本报告综合 Coda v3 真人场景评测与 Evaluation v2 正式编码基线与确定性模块评测两组已完成评测，报告中的数字均来自相应冻结材料或执行记录。

两组评测面向不同问题：v3 真人场景评测检查公开入口、功能组合和安全边界能否端到端工作；Evaluation v2 使用冻结代码、固定任务、重复运行、隐藏验证和逐行审计衡量编码结果与测量质量。各批次保留自己的样本范围和统计口径。

## 执行摘要

- **v3 真人场景评测**：50 个进程级场景全部通过，覆盖真实业务、CLI/REPL/TUI 入口、Plan mode、工具策略、审批与沙箱、Skills、子 Agent、记忆、上下文、Provider、恢复和安全边界。同期 `ruff` 通过，pytest 结果为 `224 passed, 2 skipped`。
- **Evaluation v2 正式编码基线**：27/27 条计划行全部完成最终分类并且测量有效，26 条通过隐藏验证、1 条失败、0 条 invalid；verified-run success 为 `26/27 (96.30%)`。
- **Evaluation v2 测量质量**：27/27 条运行具有精确 Provider 请求计数和通过的运行时凭据扫描，SDK retry、应用侧 retry 和协议错误均为 0；G1 与 G2 均通过。
- **确定性模块评测**：Harness 12/12 通过；Context 在 12 组配置、每组 5 次重复中取得 10.66% 的平均字符压缩率和 100% 的当前请求保留率；Working memory 的 `memory_on` 重复读取为 0、正确率为 100%；Recovery 的 `resume_enabled` 恢复成功率为 90%、workspace drift 检出率为 100%、false accept 为 0%。
- **同期全仓回归**：Evaluation v2 报告发布前的全仓测试结果为 `654 passed, 2 skipped`，仅有 6 条 `datetime.utcnow()` deprecation warning。

综合来看，现有证据显示 Coda 在记录的版本与固定环境中具备完整的公开入口工作流、较稳定的工具与安全控制，以及较高的固定本地编码任务验证成功率。

## 评测体系

| 评测 | 日期 | 代码快照 | Provider | 样本范围 | 验证方式 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| v3 真人场景评测 | 2026-05-13 | `v3` 分支；执行记录未记载 commit SHA | 默认 `deepseek` | 50 个公开入口场景 | 独立进程驱动 CLI、REPL、PTY/TUI，并检查命令输出和运行工件 | 50 passed / 0 failed；pytest 224 passed / 2 skipped |
| Evaluation v2 模块基线 | 2026-07-27 冻结 source | `dcd8ea110c6c4dad5c09943fab26b8197142ae29` | 无 Provider HTTP；scripted/fake evaluator | Harness 12 次；Context 60 次；Working memory 180 次；Recovery 60 次 | 确定性 evaluator、JSON 事实文件、checksum 和可重建报告 | 四类模块评测完成并通过独立复核 |
| Evaluation v2 正式编码基线 | 2026-07-28 | `542f97a023218ee04c00225de994f152bfed748e` | `dashscope-o` / `qwen3.6-plus` | 3 个本地仓库、9 个任务、每个任务 3 次，共 27 行 | 真实 Provider、原生工具调用、隐藏确定性 verifier、逐行审计和 checksum | 27 valid；26 passed / 1 failed / 0 invalid |

Evaluation v2 的单行评测结果分类如下：

- **valid-run rate**：有效运行数除以已最终分类行数。本批次为 `27/27 (100%)`。
- **verified-run success**：隐藏验证通过数除以全部有效运行数。本批次为 `26/27 (96.30%)`。
- **stable-pass**：同一任务的三次重复均为 `valid + passed`。
- **mixed-valid**：三次重复均有效，但通过和失败混合。

## v3 真人场景评测

### 设计与取证

场景 runner 从用户可见入口启动独立进程，不直接导入 Runtime：

- one-shot CLI 执行一次性编码和故障处理任务；
- REPL 与 PTY-style stdin 执行 slash command、多轮交互和 session 生命周期场景；
- TTY smoke 检查默认终端入口能进入 TUI；
- 每个场景使用独立临时 Git workspace，收集 stdout、stderr、`task_state.json`、`trace.jsonl`、`report.json` 和 session events；
- 验证器只读取场景 workspace 与 Coda 自己生成的运行工件。

最终 50 个场景的分组结果如下：

| 分组 | 场景范围 | 结果 | 主要覆盖 |
| --- | --- | ---: | --- |
| 真实业务场景 | R01-R05 | 5/5 | CRUD 脚手架、bugfix、发布审查、事故续接、CSV 导入 |
| 入口与交互 | S06-S14 | 9/9 | TUI、REPL、one-shot、session、usage、model、clear |
| Plan mode | S15-S20 | 6/6 | active plan、final gate、路径约束、Explore/Worker 权限 |
| Tool policy / permission / sandbox | S21-S30 | 10/10 | read-before-write、重复调用、审批、沙箱降级与 fail closed |
| Skills / subagent / worker | S31-S38 | 8/8 | Skills 参数、allowed-tools、fork、Explore 与写入范围 |
| Todo / memory / context | S39-S45 | 7/7 | Worker 续接和停止、daily log、Dream、敏感记忆拒绝 |
| Provider / recovery / safety | S46-S50 | 5/5 | compact、workspace mismatch、Provider profile、错误审计、路径与脱敏 |
| **合计** | **R01-R05、S06-S50** | **50/50** | **完整 full suite** |

### 评测驱动修复

历史执行过程暴露了以下工程问题：

| 问题 | 影响 | 处理 |
| --- | --- | --- |
| 场景 workspace 位于项目目录内时会向上发现真实 Git 根目录 | 测试文件可能写入真实项目，破坏隔离 | 默认输出移至项目外部临时目录；每个场景初始化独立 Git 仓库；拒绝项目内输出路径 |
| 被权限或策略拒绝的相同工具调用可能持续重复 | 无效调用耗尽 step budget | 将重复调用检查移动到 permission / policy 之前，并写入明确错误码 |
| 文件改写重试只按参数是否相同判断 | 补读后的合法重试被拒绝，或成功 patch 被旧 write 重放回滚 | 错误调用后完成同路径读取时允许重试；成功的相同改写禁止重放 |
| 非法 plan 路径异常直接传播 | REPL 崩溃退出 | 捕获路径校验异常并返回用户可见错误 |
| Runner 使用旧字段或错误位置读取证据 | 长输出、run 是否启动等场景可能误判 | 统一通过 RunEvidence 读取实际 report、trace 和 events |

评测暴露的上述产品问题经补丁修复，最终 50/50 是问题修复后相关场景重跑的干净结果。

### 同期代码验证

v3 执行记录给出的最终验证为：

```text
Human scenario full suite: 50 passed / 0 failed
Ruff: passed
Pytest: 224 passed, 2 skipped, 6 warnings in 68.50s
```

## Evaluation v2 正式编码基线

### 冻结配置

- Cohort：`baseline-v1`
- Source commit：`542f97a023218ee04c00225de994f152bfed748e`
- Source tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`
- Run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`
- 模型：`qwen3.6-plus`
- Provider profile：`dashscope-o`
- Python：CPython 3.12.13
- Provider SDK：OpenAI SDK 2.46.0
- Taskset：`tinyconfig`、`miniqueue`、`logslice` 三个固定 Python mini-repo，各 3 个任务，每个任务执行 3 次

每条运行都保存公开与私有证据、执行记录、隐藏 verifier 结果、审计结论和 checksum。正式聚合只使用 27 条预先冻结的主评测行，没有 replacement row、失败后重跑或结果回写。

### 总体结果

| 指标 | 结果 |
| --- | ---: |
| Planned / final classified | 27 / 27 |
| Valid passed | 26 |
| Valid failed | 1 |
| Invalid | 0 |
| Valid-run rate | 27/27 (100.00%) |
| Verified-run success | 26/27 (96.30%) |
| Provider requests | 284 |
| Tool steps | mean 11.78 / median 10 |
| Repeated reads | total 21 / mean 0.78 / median 1 |
| Runtime elapsed | mean 58,250.48 ms / median 54,892 ms |

### 按仓库分解

| 仓库 | Passed | Failed | Invalid | Verified success | Provider requests | Mean tool steps | Repeated reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tinyconfig` | 8 | 1 | 0 | 8/9 (88.89%) | 77 | 9.67 | 6 |
| `miniqueue` | 9 | 0 | 0 | 9/9 (100.00%) | 101 | 12.33 | 10 |
| `logslice` | 9 | 0 | 0 | 9/9 (100.00%) | 106 | 13.33 | 5 |
| **合计** | **26** | **1** | **0** | **26/27 (96.30%)** | **284** | **11.78** | **21** |

### 任务稳定性与唯一失败

T01、T03-T09 的三次运行全部通过，状态为 `stable-pass`。T02 两次通过、一次失败，状态为 `mixed-valid`。

唯一失败行为发生在 `baseline-v1-T02-r1`：

- Runtime 正常完成，测量完整，并精确记录 12 次 Provider 请求；
- hidden verifier 发现实现没有让 malformed database section 抛出 `ConfigError`；
- 审计将其归类为 `valid + failed / model_behavior`；
- 私有 session 记录证明该问题源于模型推理错误；
- 没有 Runtime、Provider、协议或测量错误，也没有为该行创建替代结果。

### 测量与公开证据质量

| 检查项 | 结果 |
| --- | ---: |
| Runtime evidence valid | 27/27 |
| Exact Provider request counts | 27/27 |
| Runtime credential scans passed | 27/27 |
| SDK retry / 应用侧 retry | 0 / 0 |
| Protocol-error rows | 0 |
| Pending audit / pending decision / no result | 0 / 0 / 0 |
| G1 正式行完整性与聚合门 | passed |
| G2 确定性报告与 claims-to-evidence review | passed |

最终公开候选使用实际敏感值扫描 413 个文件，命中 0。独立 verifier 能重新计算 27 条行级分类和聚合结果、重建 Markdown，并确认仓库中的正式报告镜像与 canonical Artifact 一致。

### 同期回归测试

正式报告发布前执行了一次全仓测试：

```text
654 passed, 2 skipped, 6 warnings in 232.24s
```

6 条 warning 均来自既有 `datetime.utcnow()` deprecation。该结果对应 Evaluation v2 的冻结发布阶段，不是本报告编写时对当前 HEAD 的重新验证。

## Evaluation v2 确定性模块评测

模块基线使用 source `dcd8ea110c6c4dad5c09943fab26b8197142ae29`，在 CPython 3.12.13 fresh clone 中运行。全过程使用 scripted/fake evaluator，Provider HTTP 请求数为 0；事实 JSON、checksum、机器可读报告和 Markdown 均通过独立 `--verify-only` 复核。

| 模块 | 设计 | 结果 |
| --- | --- | --- |
| Harness regression | 12 个固定任务、12 次运行 | 12 passed / 0 failed；pass rate、verifier pass rate、within-budget rate 均为 100% |
| Context ablation | 12 configs × 5，共 60 次 | 平均 raw prompt 9,998.67 字符，平均 full prompt 8,740 字符；平均压缩率 10.66%，最大压缩率 22.46%，当前请求保留率 100% |
| Working-memory ablation | 12 tasks × 3 variants × 5，共 180 次 | 三个 variant 的 correct rate 均为 100%；`memory_on` memory hit rate 100%、repeated reads 0、平均 tool steps 0；`memory_off` 和 `memory_irrelevant` repeated reads 均为 60、平均 tool steps 均为 1 |
| Recovery ablation | 10 tasks × 2 variants × 3，共 60 次 | `resume_enabled` success 90%、stale reanchor 100%、workspace drift detection 100%、false accept 0%；`resume_disabled` 四项均为 0 |

模块结果与正式编码结果使用独立样本和分母。Harness 衡量固定合同，Context 指标以字符而非 token 计算，Working-memory 实验聚焦 session 内工作记忆，Recovery 实验聚焦模块级恢复行为。

## 综合判断

### 公开入口与端到端集成

v3 的 50 个场景覆盖了主要用户入口、Runtime 控制面、文件和 shell 工具、安全策略、Skills、子 Agent、记忆、上下文和恢复路径。所有场景在缺陷修复后通过，说明该发布快照具备较完整的功能组合验收和运行工件取证能力。

### 固定编码任务效果

Evaluation v2 在一个模型、一个 Provider profile、三个本地 Python mini-repo 和三次重复的固定范围内取得 `26/27 (96.30%)` 的隐藏验证成功率，且 27 条运行全部测量有效。8 个任务为 `stable-pass`，T02 为 `mixed-valid`，说明整体结果较稳定，但嵌套配置错误处理仍存在一次可复现到行级证据的模型行为遗漏。

### Context、记忆与恢复

确定性模块实验显示 Context 裁剪在保留当前请求的同时减少了 prompt 字符量；Working memory 在脚本化 follow-up 任务中消除了重复读取；Recovery 对 stale reanchor 和 workspace drift 具有完整检出结果。它们为对应模块提供了量化基线，也为后续真实编码路径实验提供了可比较的起点。

### 评测与审计能力

Evaluation v2 将产品结果、测量有效性、失败分类和公开导出质量分层处理。冻结 source、run config、固定行身份、逐行审计、checksum、敏感值扫描和可确定性重建报告共同构成了完整的证据链；invalid 与产品失败不会被混为同一类结果。

## 优先改进建议

1. **提高 T02 边界行为稳定性**：在独立 post-fix cohort 中验证 malformed nested section、缺失字段和错误类型，不修改或回写 `baseline-v1`。
2. **调查 T09 执行成本长尾**：T09 三次合计 45 次 Provider 请求，平均 19 个工具步骤；应在相同配置的独立 cohort 中区分规划、搜索、实现和验证阶段成本。
3. **减少 miniqueue 重复读取**：9 条运行累计 10 次重复读取；可结合 Working-memory 模块指标，测量真实编码路径上的记忆命中与重复读取关系。
4. **增加跨模型与开放任务验证**：在保留冻结 taskset 的同时增加不同 Provider、不同模型和更大真实仓库，形成可比较而非覆盖原结果的补充 cohort。
5. **补充长期记忆与多 Agent 对照**：分别量化跨 session 记忆质量、长期事实保真度，以及多 Agent 相对单 Agent 的成功率、步骤和成本。
6. **提高证据可移植性与新鲜度**：为历史场景保存可归档的公开证据包，并在发布节点以当前 source 重新执行明确版本化的离线回归和最小真人场景门禁。

## 适用范围与限制

- v3 真人场景结果对应来源提交 `850b27b` 和默认 `deepseek` 配置；执行记录没有固定 commit SHA。
- 50 个场景混合了真实 Provider 任务、交互入口检查、错误路径和无需模型运行的控制面检查，因此该数字是 acceptance suite 结果。
- v3 原始运行工件位于执行记录中的外部临时输出目录，未随仓库提交；仓库内保留测试设计、执行记录、runner 说明和逐场景检查清单。
- Evaluation v2 正式编码结果仅覆盖一个模型、一个 Provider profile、一组参数、三个固定 Python mini-repo 和每任务三次重复。
- Evaluation v2 的 canonical Artifact 位于仓库外；仓库保留正式 Markdown 镜像、控制文档、任务集和实现，外部 Artifact 通过 checksum 与冻结 Git 对象建立身份。
- Context 的 10.66% 是字符压缩率，不等同于 token、费用或延迟下降。
- Working-memory 数据来自脚本化 session 内任务，没有覆盖 durable topic、自动整理或跨 session 长期记忆质量。
- Recovery 数据是模块级确定性实验，不是完整交互入口下的长期恢复统计。
- Prompt 规范化的两个 Pilot 使用不同 source 和 bridge，不构成严格 A/B；它们不进入 27 条正式编码结果。
- 两次 pytest 数字分别属于各自历史代码快照；本报告没有对当前 HEAD 重跑全仓测试、真人场景或正式编码评测。

## 材料索引

### v3 真人场景

- [测试包说明](../release/v3/testing/README.md)
- [测试设计与 50 个场景定义](../release/v3/testing/01-test-design.md)
- [全量执行记录](../release/v3/testing/02-execution-record.md)
- [Runner 与证据说明](../release/v3/testing/03-runner-and-evidence.md)
- [50 场景检查清单](../release/v3/testing/04-scenario-checklist.md)

### Evaluation v2

- [正式基线报告](evaluation/evaluation-report-v2.md)
- [评测计划与阶段门](evaluation/evaluation-v2-plan.md)
- [证据协议](evaluation/evaluation-v2-evidence-protocol.md)
- [指标定义](evaluation/evaluation-v2-metrics.md)
- [执行状态与冻结记录](evaluation/evaluation-v2-status.md)
- [评测框架使用说明](evaluation/evaluation-v2-user-guide.md)
