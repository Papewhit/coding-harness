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

## P2 编码任务桥接与 run config

### 适用目的与不适用范围

`scripts/run_local_coding_tasks.py` 现有离线模式保持不变；Evaluation v2 模式用于验证冻结的 9-task taskset、生成或只读核验 `pilot-v1` 与 `baseline-v1` run config，并在后续独立授权的 P3/P4 阶段启动真实 Pico Runtime。

P2 自身只运行 fake client、hidden verifier 和确定性证据检查。生成或验证 run config 不解析 provider credential、不构造 provider transport，也不发起 provider HTTP。run config 获用户接受不等于 G0；G0 仍由另行授权的 P3 首条 T01 live row 验证。

### 运行前置条件

- 在 Ubuntu 26.04 WSL2 的 clean fresh clone 中运行，HEAD 必须是拟冻结的完整 source commit，Python 必须为 CPython 3.12.13。
- 使用 providers extra 安装依赖；OpenAI SDK 必须精确为 `2.46.0`。
- `benchmarks/v3/local-repos/taskset.json`、`taskset.lock.json`、仓库 base snapshot、task doc、hidden verifier 和 reference patch 必须全部通过锁文件重算。
- `PICO_NATIVE_PROVIDER_CONFIG` 只在 launcher 进程内指向一个存在的文件。若 WSL 未继承该变量，只在当前 Windows launcher 进程的 `WSLENV` 中追加 `PICO_NATIVE_PROVIDER_CONFIG/p`；不得把 locator 写入命令行、仓库、Artifact 或持久化 shell 配置。
- 固定 Artifact 根目录为 `/mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2`，对应 Windows 的 `F:\dev\llm\pico-eval-artifacts\evaluation-v2`。目标 `<cohort-id>/<source-sha>` 必须不存在或为空。

依赖准备：

```bash
uv sync --frozen --extra providers --python 3.12
```

### 生成两份 canonical run config

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --prepare-run-configs \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2
```

该命令只创建：

```text
pilot-v1/<source-sha>/public/run-config.json
pilot-v1/<source-sha>/public/run-config.sha256
baseline-v1/<source-sha>/public/run-config.json
baseline-v1/<source-sha>/public/run-config.sha256
```

JSON 使用排序键、2 空格缩进和末尾换行；`.sha256` 是 JSON 文件字节的小写 SHA-256。配置固定 source/tree、taskset、`dashscope-o` public profile、`qwen3.6-plus`、OpenAI Responses、SDK 版本、预算、timeout、重试策略、工具白名单、bubblewrap 网络隔离、Artifact 路径、client 哈希、允许的 row 身份和 P3/P4 完整启动命令。配置只记录 locator 变量名及存在/文件类型检查结果，不记录 locator 或 credential 值。

### 只读验证

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v1/<source-sha>/public/run-config.json \
  --verify-only

uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/<source-sha>/public/run-config.json \
  --verify-only
```

只读验证不执行任务。它核对 canonical JSON、旁路哈希、clean checkout 的 source/tree、运行环境、taskset 与仓库树、profile selection、client 文件、固定策略、row 清单和 launch command；任一漂移都会在创建评测行目录和首次 provider HTTP 之前失败。

### Evaluation v2 live 参数与授权边界

正式入口接受：

- `--run-config`：已接受的 canonical 配置；
- `--cohort-id`：`pilot-v1` 或 `baseline-v1`，必须与配置一致；
- `--stage`：配置冻结的 `P3-G0`、`P3-remainder`、`P4A`、`P4B` 或 `P4C`；
- `--task`、`--repo`：可重复使用的任务或仓库过滤器；
- `--repetitions`：该阶段冻结的重复次数。

runner 要求请求集合与该阶段的冻结集合精确相同，按 repetition-major、task ID 升序执行。P3/P4 不得手工拼装新命令；应直接使用对应 `run-config.json` 的 `launch_commands`。截至 P2，这些命令只是冻结内容，未获执行授权。

### Runtime 与写入范围

薄 client `scripts/run_pico_live_task_client.py` 从 `PICO_LIVE_TASK_PROMPT` 读取 prompt，把 provider-neutral `ClientResult` 原子合并到 `PICO_LIVE_EVIDENCE_PATH`。它直接装配现有 provider adapter 与 `Pico` Runtime，不使用 SDK Tool Runner 或 Agents Runner。

固定 Runtime 策略为：`approval=auto`、workspace-only write scope、关闭 auto-dream、最大输出 4096 token、最多 50 个工具步骤、provider timeout 300 秒、单行 timeout 600 秒、stream=false、并行工具=false、SDK retry=0、Pico provider attempts=1、semantic rerun=0。只开放 `list_files`、`read_file`、`search`、`run_shell`、`write_file`、`patch_file` 和三个 todo 工具；子 agent、交互询问和 plan 工具不可用。

`run_shell` 必须通过 bubblewrap，并对工具子进程添加 `--unshare-net`。工具进程只能写 fresh task workspace；当前 Python venv 只读挂载。provider transport 不进入该网络命名空间，仍由外层 client 联网。bubblewrap 或 network namespace 不可用时在首次 provider HTTP 之前停止。

### Row Artifact 与结果解释

后续 live row 使用固定 ID：Pilot 为 `pilot-v1-<task>-r1`；Baseline 为 `baseline-v1-<task>-r<1..3>`。既有 private/public row 目录永不覆盖。

主要公开入口：

```text
public/rows/<row-id>/run-record.json
public/rows/<row-id>/evidence-view.json
public/rows/<row-id>/checksums.json
public/rows/<row-id>/verifier/
public/rows/<row-id>/original/
```

私有原件位于 `private/rows/<row-id>/original/`。workspace 清理前复制 session、events 和 Pico run state；public 只选择 session events、task state、trace 和 report。raw SDK/provider 网络响应不会复制到 private 或 public。

`run-record.json` 是阶段、source、退出码、精确 provider request 次数、失败位置和现有证据位置的最小记录。`evidence-view.json` 只做确定性导航：它从 session exchange、tool result、session events 和 trace 核对 call ID、工具名和终态，并记录原始路径与稳定位置；它不替代原件或 Codex 审计。

凭据检查使用本次实际 locator、credential 和测试 sentinel 的完整值做精确字节扫描，只持久化通过布尔值、扫描文件数和不含敏感值的位置。缺失原件、请求次数不精确、call/result 不闭合或扫描命中都会保留最小记录并标记 measurement failure。`product_result=passed/failed` 只表示 hidden verifier 的确定性结果；最终 `valid + passed`、`valid + failed` 或 `invalid` 分类仍按 evidence protocol 和后续审计产生。
