# Pico Evaluation v2 使用指南

## 文档角色

本文记录当前已经交付的 Evaluation v2 用户入口、运行边界和结果解释。阶段顺序与授权 见 [`evaluation-v2-plan.md`](evaluation-v2-plan.md)，指标公式见 [`evaluation-v2-metrics.md`](evaluation-v2-metrics.md)，证据与分类规则见 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。

本文只描述当前可用接口，不保留已经失效的旧参数或旧命令。

## P1 确定性模块基线

### 适用目的与不适用范围

`scripts/run_evaluation_v2_modules.py` 用于生成或复核 context、working memory、 recovery 和 harness regression 的确定性模块基线。

它不运行真实端到端编码任务，不执行 `pilot-v1` 或 `baseline-v1`，不能衡量真实模型 或 provider 的编码成功率，也不提供 P3/P4 live 授权。

### 生成命令

在用户接受的 source commit 对应的 WSL2 fresh clone 中运行：

```bash
uv run --frozen --python 3.12 python scripts/run_evaluation_v2_modules.py \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/<source-sha>
```

`--output-root` 是必填参数。生成模式要求：

- 使用 Python 3.12；
- Git checkout 是 clean checkout；
- 当前完整 Git HEAD 等于 `<source-sha>`，且 `<source-sha>` 是 40 位小写 commit SHA；
- 目标目录不存在或为空。

目标目录第一次产生内容后不得覆盖或复用。运行中途失败时保留已有内容，不删除后 重跑同一目录。

### 只验证既有 Artifact

```bash
uv run --frozen --python 3.12 python scripts/run_evaluation_v2_modules.py \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/<source-sha> \
  --verify-only
```

`--verify-only` 只读取既有 Artifact。它从输出目录名取得 source SHA，再与报告记录 互相核对；不要求当前 checkout clean，也不要求当前 HEAD 等于 Artifact source。 它不会运行 evaluator、写入或修复 Artifact、读取 provider 配置或发起 provider HTTP。

复核内容包括固定五个 JSON 的路径、字节数和 SHA-256，报告 schema、cohort、source 与离线证据边界，以及 Markdown 是否能从报告 JSON 确定性重建。

### 调用范围

生成模式依次调用：

- `pico.evaluation.evaluator.run_harness_regression_v2`；
- `pico.evaluation.metrics.run_context_ablation_v2(repetitions=5)`；
- `pico.evaluation.metrics.run_memory_ablation_v2(repetitions=5)`；
- `pico.evaluation.metrics.run_recovery_ablation_v2(repetitions=3)`；
- `pico.evaluation.metrics.write_benchmark_core_report`。

这些入口使用 scripted/offline 模型路径。wrapper 明确不调用 provider profile resolver、provider client、SDK transport、`LocalLiveTaskRunner` 或任何 provider HTTP 请求。Harness 的临时 workspace 在运行结束后清理；正式输出只写入指定的外部 `--output-root`。

### 产物入口

首选人工阅读入口：

```text
reports/pico-module-baseline-v2.md
```

机器可读报告源：

```text
reports/pico-module-baseline-v2.json
```

模块事实和复核清单：

```text
public/modules/harness-regression-v2.json
public/modules/context-ablation-v2.json
public/modules/memory-ablation-v2.json
public/modules/recovery-ablation-v2.json
public/modules/checksums.json
```

报告 JSON 记录 cohort、完整 source SHA、样本量、模块指标、公式引用、排除项和证据 路径；Markdown 必须由该 JSON 生成。`checksums.json` 覆盖四个模块 JSON 和报告 JSON，不把自身计入清单。

### 结果解释

- Harness 指标只说明固定 runtime/harness 合同。
- Context、memory 和 recovery 指标只说明对应模块在确定性实验中的行为。
- `provider_http_requests: 0` 表示该批次没有真实 provider 请求，不代表 provider 能力或质量。
- `is_end_to_end_coding_result: false` 表示这些结果不得进入 `pilot-v1` 或 `baseline-v1` 的真实编码成功率分母。
- 单项指标异常或 harness 产品失败应原样记录，不能为了得到通过结果而修改产品或 覆盖本批次。
