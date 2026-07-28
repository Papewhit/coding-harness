# Pico Evaluation v2 指标定义

## 文档角色

本文固定 Evaluation v2 的指标口径、分母和证据边界。阶段与 Gate 以 [`evaluation-v2-plan.md`](evaluation-v2-plan.md) 为准，评测行有效性和证据保存以 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md) 为准。本文不包含实际结果；实际值只能从对应批次的不可变证据计算。

## 批次隔离

以下批次分别报告，禁止合并分母或共同表述为一个成功率：

- `module-baseline-v1`：P1 的确定性模块评测，不是真实 provider 编码结果；
- `pilot-v1`：P3 的三任务 Pilot，只验证测量链和 G0，不进入正式基线；
- `pilot-v2`：评测桥接修复后另行授权、但在创建 row 和首次 provider HTTP 前停止的 P3 Pilot；与 `pilot-v1` 分开报告，三条计划 row 均为 `no result`；
- `pilot-v3`：修复冻结配置解释器身份后预留的下一次 P3 Pilot；只有取得新的明确授权后才可生成配置或执行，与此前 Pilot 分开报告；
- `baseline-v1`：P4A–P4C 的 27 条正式编码评测行，是正式编码成功率的唯一分母。

W6R5 的 R-01、R-02、R-03 是历史无效测量，不属于上述任何批次。后续补充批次和 post-fix 批次也必须独立报告，不得回写 `baseline-v1`。

## 编码任务指标

### 结果计数

每条已最终分类的评测行只能是 `valid + passed`、`valid + failed` 或 `invalid`。 `missing`、`no result`、待审计和待用户决定不是最终分类，必须单列。

- **valid-run rate（有效运行率）**： `(valid + passed 的行数 + valid + failed 的行数) / 已最终分类的行数`。分母只含 valid 和 invalid；missing 数量始终另列。G1 时全部 27 条主评测行都已最终分类，因此分母必须为 27。
- **verified-run success（验证成功率）**： `valid + passed 的行数 / 全部 valid 行数`。`invalid` 和 missing 不进入分母。若 valid 行数为 0，结果记为不可计算而不是 0%。
- **failure category（失败类别）**：只对 `valid + failed` 计数，并按最终审计记录中的产品行为、模型行为、provider、协议或基础设施原因分解。测量装置问题属于 invalid 原因，必须在 measurement quality 中另表报告。

所有比率同时发布分子、分母和百分比，不能只发布百分比。

### 三次重复的稳定状态

每个任务按固定的三条主评测行分类：

- `stable-pass`：三条都为 `valid + passed`；
- `stable-fail`：三条都为 `valid + failed`；
- `mixed-valid`：三条都 valid，但 passed/failed 混合；
- `insufficient-evidence`：任一条为 invalid、missing、待审计或待决定。

不得只用有效子集替代缺失或 invalid 的重复来声称任务稳定。

### 工具与耗时

- **tool steps（工具步骤）**：读取 Pico 运行报告中的工具步骤计数，不从自然语言输出推断。
- **repeated reads（重复读取）**：同一评测行内，对同一个规范化 workspace 相对路径的成功 `read_file` 调用，从第二次起每次计 1。不同路径、失败调用和无法从 trace 可靠定位路径的调用不计入该值。
- **elapsed time（执行耗时）**：从调用 Pico live client/Runtime 前开始，到其返回时结束；不包含 fixture 复制、隐藏检查程序、Codex 审计或用户决定耗时。

三项指标保留逐行原值。每个阶段或批次发布可用样本数、算术均值和中位数； repeated reads 另发布总数。invalid 行即使留下局部可信字段，也只能在独立的“invalid 行可观察事实”表中列出，不进入产品聚合。

## P1 确定性模块指标

P1 调用现有 `pico/evaluation/metrics.py` 实现，不在 wrapper 中重写公式。

### Harness regression

证据文件：`public/modules/harness-regression-v2.json`。

- `pass_rate`：passed 行数 / 全部固定任务行数；
- `within_budget_rate`：工具步骤未超过预算的行数 / 全部固定任务行数；
- `verifier_pass_rate`：隐藏检查通过的行数 / 全部固定任务行数；
- `failure_category_counts`：按现有 evaluator 分类的失败计数。

这些指标只证明固定 harness 合同，不证明真实 provider 效果。

### Context ablation

证据文件：`public/modules/context-ablation-v2.json`。覆盖 12 组配置，每组重复 5 次。

- 单次 `compression_ratio = (raw_prompt_chars - full_prompt_chars) / raw_prompt_chars`；
- 每组配置分别计算 `avg_full_prompt_chars`、`avg_raw_prompt_chars` 和 `avg_prompt_compression_ratio`；
- 汇总平均值对 12 组配置等权取算术均值；
- `max_prompt_compression_ratio` 是 12 个配置级平均压缩率的最大值；
- 每组先计算最新请求保留率；汇总 `current_request_preserved_rate` 等于五次运行全部保留最新请求的配置数 / 12。

### Working-memory ablation

证据文件：`public/modules/memory-ablation-v2.json`。覆盖 12 个任务、3 个 variant，每个 variant 每任务重复 5 次。

- `repeated_reads`：各行重复读取数之和；
- `avg_tool_steps`：各行工具步骤的算术均值；
- `correct_rate`：结果正确的行数 / 该 variant 全部行数；
- `memory_hit_rate`：重复读取数为 0 的行数 / 该 variant 全部行数。

`memory_on`、`memory_off` 和 `memory_irrelevant` 分开报告，不把 variant 合并成一个成功率。

### Recovery ablation

证据文件：`public/modules/recovery-ablation-v2.json`。覆盖 10 个任务、2 个 variant，每个 variant 每任务重复 3 次。

- `resume_success_rate`：resume 成功行数 / 该 variant 全部行数；
- `stale_reanchor_rate`：成功重新锚定的 `partial_stale` 行数 / 全部 `partial_stale` 行数；
- `workspace_drift_detection_rate`：检测到 drift 的 `workspace_mismatch` 行数 / 全部 `workspace_mismatch` 行数；
- `resume_false_accept_rate`：错误接受的无效 resume 行数 / `partial_stale`、`workspace_mismatch` 和 `schema_mismatch` 行数。

分母为 0 时按现有 evaluator 结果记录，并在报告中展示样本数，不把缺少场景解释为产品能力。

### P1 文件与报告边界

上述四个模块 JSON 与 `public/modules/checksums.json` 是模块事实来源。 `reports/pico-module-baseline-v2.json` 是机器可读汇总， `reports/pico-module-baseline-v2.md` 必须从该 JSON 确定性生成。模块指标不得进入 `pilot-v1` 或 `baseline-v1` 的真实编码成功率分母。

## 报告通用规则

- 每项聚合同时给出 cohort、source SHA、样本数、公式和排除原因。
- 原始行证据优先于汇总报告；确定性证据视图只用于导航。
- 产品效果、测量质量和公开导出质量分层报告，不能用一层的成功替代另一层。
- 无法从证据复算的值不得发布；无法计算时明确写出原因和受影响样本。
