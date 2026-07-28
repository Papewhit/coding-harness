# Pico Evaluation v2 使用指南

## 文档角色

本文记录当前已经交付的 Evaluation v2 用户入口、运行边界和结果解释。阶段顺序与授权见 [`evaluation-v2-plan.md`](evaluation-v2-plan.md)，指标公式见 [`evaluation-v2-metrics.md`](evaluation-v2-metrics.md)，证据与分类规则见 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。

本文只描述当前可用接口，不保留已经失效的旧参数或旧命令。

## P1 确定性模块基线

### 适用目的与不适用范围

`scripts/run_evaluation_v2_modules.py` 用于生成或复核 context、working memory、 recovery 和 harness regression 的确定性模块基线。

它不运行真实端到端编码任务，不执行 `pilot-v1` 或 `baseline-v1`，不能衡量真实模型或 provider 的编码成功率，也不提供 P3/P4 live 授权。

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

目标目录第一次产生内容后不得覆盖或复用。运行中途失败时保留已有内容，不删除后重跑同一目录。

### 只验证既有 Artifact

```bash
uv run --frozen --python 3.12 python scripts/run_evaluation_v2_modules.py \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/<source-sha> \
  --verify-only
```

`--verify-only` 只读取既有 Artifact。它从输出目录名取得 source SHA，再与报告记录互相核对；不要求当前 checkout clean，也不要求当前 HEAD 等于 Artifact source。它不会运行 evaluator、写入或修复 Artifact、读取 provider 配置或发起 provider HTTP。

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

报告 JSON 记录 cohort、完整 source SHA、样本量、模块指标、公式引用、排除项和证据路径；Markdown 必须由该 JSON 生成。`checksums.json` 覆盖四个模块 JSON 和报告 JSON，不把自身计入清单。

### 结果解释

- Harness 指标只说明固定 runtime/harness 合同。
- Context、memory 和 recovery 指标只说明对应模块在确定性实验中的行为。
- `provider_http_requests: 0` 表示该批次没有真实 provider 请求，不代表 provider 能力或质量。
- `is_end_to_end_coding_result: false` 表示这些结果不得进入 `pilot-v1` 或 `baseline-v1` 的真实编码成功率分母。
- 单项指标异常或 harness 产品失败应原样记录，不能为了得到通过结果而修改产品或覆盖本批次。

## P2 编码任务桥接与 run config

### 适用目的与不适用范围

`scripts/run_local_coding_tasks.py` 现有离线模式保持不变；Evaluation v2 模式用于验证冻结的 9-task taskset、生成或只读核验隔离的 `pilot-vN` 与 `baseline-v1` run config，并在用户明确要求开始相应 P3/P4 阶段后启动真实 Pico Runtime。`pilot-v1`、`pilot-v2`、`pilot-v3` 和 `pilot-v4` 均为不可变历史批次。

P2 source `b51b4a1a38b76da6cfa8403366ffec54990cfefa` 下的旧 `baseline-v1` 配置早于 Evaluation prompt 入口规范化修复，不得用于 P4。P4 必须使用包含提交 `6460508c688383102f9dc205d8a04a5681b078dd` 的新 source 重新生成独立配置；该 source 的 live client 在调用 Runtime 前按标准用户入口语义去除 prompt 首尾空白。

P2 和后续配置冻结只运行 fake client、hidden verifier 和确定性证据检查。生成或验证 run config 不解析 provider credential、不构造 provider transport，也不发起 provider HTTP。展示配置不是签名或单独接受步骤；用户明确要求开始 P3 时，G0 才由首条 T01 live row 验证。

### 配置生成条件

- 在 WSL2 fresh clone 中运行，当前 tracked 文件必须 clean，HEAD/tree 将作为完整 source 身份写入配置；untracked 文件不阻断生成。
- 使用 providers extra 安装依赖。生成器记录当时的 Python、操作系统和 OpenAI SDK 事实，但不因解释器别名、符号链接、clone 绝对路径、操作系统补丁版本、SDK 当前版本或 locator 当前状态阻断。
- `benchmarks/v3/local-repos/taskset.json`、`taskset.lock.json`、仓库 base snapshot、task doc、hidden verifier 和 reference patch 必须全部通过锁文件重算。
- 固定 Artifact 根目录为 `/mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2`，对应 Windows 的 `F:\dev\llm\pico-eval-artifacts\evaluation-v2`。目标 `<cohort-id>/<source-sha>` 必须不存在或为空。

生成配置不要求 `PICO_NATIVE_PROVIDER_CONFIG` 已设置。配置只记录生成时 locator 的存在性和类型事实，不记录 locator 或 credential 值。

依赖准备：

```bash
uv sync --frozen --extra providers --python 3.12
```

### 生成指定 canonical run config

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --prepare-run-configs \
  --cohort-id pilot-v4 \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2

uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --prepare-run-configs \
  --cohort-id baseline-v1 \
  --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2
```

该命令只创建：

```text
pilot-v4/<source-sha>/public/run-config.json
pilot-v4/<source-sha>/public/run-config.sha256
```

JSON 使用排序键、2 空格缩进和末尾换行；`.sha256` 是 JSON 文件字节的小写 SHA-256。配置固定 source/tree、taskset、`dashscope-o` public profile、`qwen3.6-plus`、OpenAI Responses、SDK 版本、预算、timeout、重试策略、工具白名单、bubblewrap 网络隔离、Artifact 路径、client 哈希、允许的 row 身份和 P3/P4 完整启动命令。配置只记录 locator 变量名及存在/文件类型检查结果，不记录 locator 或 credential 值。

### 只读验证

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v4/<source-sha>/public/run-config.json \
  --verify-only

uv run --frozen --extra providers --python 3.12 \
  python scripts/run_local_coding_tasks.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/<source-sha>/public/run-config.json \
  --verify-only
```

该 `--verify-only` 只检查 canonical JSON、既有 v1 schema 和旁路哈希，不执行任务、不读取 locator、不解析 provider、不探测 sandbox、不构造 Runtime/client，也不要求当前 checkout 对应配置 source。它拒绝 `--cohort-id`、`--stage`、`--task`、`--repo` 和 `--repetitions` 等 live 选择参数。

### Evaluation v2 live 参数与启动验证

正式入口接受：

- `--run-config`：冻结配置；
- `--cohort-id`：当前实现接受 `pilot-v1`、`pilot-v2`、`pilot-v3`、`pilot-v4` 或 `baseline-v1`，必须与配置一致；
- `--stage`：供 row 记录的 `P3-G0`、`P3-remainder`、`P4A`、`P4B` 或 `P4C`；
- `--task`、`--repo`：可重复使用的任务或仓库过滤器；
- `--repetitions`：请求的重复次数，省略时为 1；
- `--resume-missing`：只允许 `baseline-v1` 的冻结 P4 命令使用；从当前阶段选择中排除 private 或 public row 目录已经存在的身份。

正式 live 命令在创建首条 row 和首次 provider HTTP 前只调用一次 `validate_live_start`。它只阻断五类情况：配置 JSON/schema/旁路哈希失败；tracked source 不 clean 或 HEAD/tree 不符；请求 row/Artifact 越界或目标 row 已存在；locator 不是文件或 provider/profile/model 不符；正式 bubblewrap 加 `--unshare-net` 的单次最小 marker 探针失败。它不重建配置、不构造 Runtime/client、不推导 HTTP 上限，也不要求请求集合等于某阶段的完整 row 集合。

P3/P4 的顺序和完整 row 集合由计划与配置中的冻结命令约束；runner 只要求每条请求都在 `allowed_rows` 内，并按 repetition-major、task ID 升序执行。P4 的冻结命令自始携带 `--resume-missing`：首次执行时九条 row 均不存在，因此执行完整阶段；若 measurement defect 触发停止，只有满足计划中的纯离线修复条件且用户明确要求继续后，才能原样重发同一命令，它只执行仍为 missing 的 row。任何已有 private 或 public row 目录的身份都会被跳过，不能用于重跑 invalid、failed 或 passed row。不得手工拼装遗漏 row 的替代命令。

用户明确要求开始某阶段即允许执行该阶段计划内的冻结命令，不创建或检查授权文件、授权环境变量或 status 授权记录。仅因全部选中 row 已存在而没有 missing row 时，命令确定性输出空列表，不运行 live validator、Runtime 或 provider。

live 启动时，`PICO_NATIVE_PROVIDER_CONFIG` 只在 launcher 进程内指向一个文件。若 WSL 未继承该变量，只在当前 Windows launcher 进程的 `WSLENV` 中追加 `PICO_NATIVE_PROVIDER_CONFIG/p`；不得把 locator 写入命令行、仓库、Artifact 或持久化 shell 配置。子进程会为实际执行再次读取 provider 配置，但不重复作 profile 启动判定。

### Runtime 与写入范围

薄 client `scripts/run_pico_live_task_client.py` 从 `PICO_LIVE_TASK_PROMPT` 读取 prompt，按非交互、REPL 和 Textual TUI 三个标准用户入口的共同语义先去除首尾空白，再把 prompt 交给 Pico Runtime；纯空白 prompt 在构建请求前拒绝。client 把 provider-neutral `ClientResult` 原子合并到 `PICO_LIVE_EVIDENCE_PATH`，直接装配现有 provider adapter 与 `Pico` Runtime，不使用 SDK Tool Runner 或 Agents Runner。

固定 Runtime 策略为：`approval=auto`、workspace-only write scope、关闭 auto-dream、最大输出 4096 token、最多 50 个工具步骤、provider timeout 300 秒、单行 timeout 600 秒、stream=false、并行工具=false、SDK retry=0、Pico provider attempts=1、semantic rerun=0。只开放 `list_files`、`read_file`、`search`、`run_shell`、`write_file`、`patch_file` 和三个 todo 工具；子 agent、交互询问和 plan 工具不可用。

`run_shell` 必须通过 bubblewrap，并对工具子进程添加 `--unshare-net`。工具进程只能写 fresh task workspace；当前 Python venv 只读挂载。provider transport 不进入该网络命名空间，仍由外层 client 联网。启动验证只执行一次与正式配置相同的最小 marker 探针；工具路径、挂载和其他安全性质由离线测试覆盖，不在 live 前扩展为 sandbox conformance suite。

### Row Artifact 与结果解释

后续 live row 使用固定 ID：Pilot 为 `pilot-vN-<task>-r1`，Baseline 为 `baseline-v1-<task>-r<1..3>`。既有 private/public row 目录永不覆盖。

主要公开入口：

```text
public/rows/<row-id>/run-record.json
public/rows/<row-id>/evidence-view.json
public/rows/<row-id>/checksums.json
public/rows/<row-id>/verifier/
public/rows/<row-id>/original/
```

私有原件位于 `private/rows/<row-id>/original/`。workspace 清理前复制 session、events 和 Pico run state；public 只选择 session events、task state、trace 和 report。raw SDK/provider 网络响应不会复制到 private 或 public。

`run-record.json` 是阶段、source、退出码、精确 provider request 次数、失败位置和现有证据位置的最小记录。client 完成后的 verifier、复制或清理阶段即使失败，runner 也会从已原子持久化的 `client_result` 恢复 request attempts，并交叉验证 attempt 序号、精确标记和汇总计数；无法一致恢复时标记 measurement failure，不把请求数回退为可信的 0。

client/runtime 原始失败同时记录 `failure_origin`、`failure_stage` 和 `error_type`。live-task client 是这些字段的唯一作者；外层 `CommandClient` 只追加 process exit code。汇总固定采用“测量记录损坏、原始 client/runtime 失败、协议失败、verifier 失败、成功”的优先级。HTTP 请求数只是计量事实，不能单独决定失败来源：完整的 `runtime + pre_request` 零请求异常是可信产品失败，client 无法启动或原始异常丢失则是没有产品结论的 invalid 测量。

P2 fake client 仍用于验证目录、checksum、敏感值扫描和 hidden verifier 编排，但它会直接修改 workspace 和构造结果，不能证明真实桥接。生产桥接另由离线回归覆盖真实 `CommandClient → 子进程 → live-task client → Pico Runtime`，只把最末端 provider transport 替换成确定性无网络实现。

`evidence-view.json` 只做确定性导航：它从 session exchange、tool result、session events 和 trace 核对 call ID、工具名和终态，并记录原始路径与稳定位置；它不替代原件或 Codex 审计。private/public `checksums.json` 是完整文件 inventory，不只是已列文件的抽样哈希；验证同时检查 schema、唯一且安全的规范相对路径、实际文件集合、字节数和 SHA-256，任何未列或缺失文件都会失败。

凭据检查使用本次实际 locator、credential 和测试 sentinel 的完整值做精确字节扫描，只持久化通过布尔值、扫描文件数和不含敏感值的位置。缺失原件、请求次数不精确、call/result 不闭合或扫描命中都会保留最小记录并标记 measurement failure。`product_result=passed/failed` 只表示 hidden verifier 的确定性结果；最终 `valid + passed`、`valid + failed` 或 `invalid` 分类仍按 evidence protocol 和后续审计产生。

### P3 Pilot 审计与报告

P3 使用独立的纯离线 finalizer 将 Codex 审计追加到已经完成捕获的 Pilot row，并生成一页 Pilot 报告。它不装配 Runtime、不读取任务 prompt、不调用 provider，也不修改 `run-record.json`、`evidence-view.json`、verifier 输出或原始 `.pico` 证据。

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/finalize_evaluation_v2_pilot.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v1/<source-sha>/public/run-config.json \
  --audit-input <codex-audit-input.json>
```

`--audit-input` 可重复使用。输入必须使用 `pico-evaluation-v2-codex-audit-v1` schema，固定 row 身份、证据充分性、测量结果、产品结果、最终分类、失败类别、理由、证据引用和用户决定状态。finalizer 先验证已有 row checksum 和确定性事实，再原子写入 `public/rows/<row-id>/codex-audit.json`；既有 audit 拒绝覆盖。新增 audit 后只重新封存该 row 的公开 checksum，原始测量文件保持不变。

Codex 审计只有在开放歧义确实需要用户判断时才能写入 `user_decision=required`。此时报告保留 `pending decision`，后续使用可重复的 `--user-decision-input <user-decision.json>` 追加决定；没有对应 audit 或 audit 不要求用户决定时，该输入会被拒绝。

finalizer 每次从 row 事实和审计重新生成：

```text
reports/pilot-report.json
reports/pilot-report.md
```

JSON 是机器可读单一数据源，Markdown 必须逐字节可重建。报告列出三条冻结 Pilot row；未启动 row 显示为 `no result`，不能解释为产品失败。指标只聚合最终 valid row；invalid row 的局部事实单独保留但不进入产品指标。

如果冻结命令在创建第一条 row 前停止，可用纯离线初始化模式生成三条均为 `no result` 的报告：

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/finalize_evaluation_v2_pilot.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v2/<source-sha>/public/run-config.json \
  --initialize-report
```

`--initialize-report` 不接受 audit 或 user decision 输入，不解析 provider 配置、不写 row，也不发起 provider HTTP。它只写入尚不存在或可确定性重建的 Pilot 报告；G0 保持 `pending`，阶段停止原因由 status 记录。

只读复核命令为：

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/finalize_evaluation_v2_pilot.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v1/<source-sha>/public/run-config.json \
  --verify-only
```

这里的 finalizer `--verify-only` 与前述 run-config CLI 是两个不同入口：它验证配置、每条既有 row 的完整 checksum、audit/decision 合同、报告重算和 Markdown 重建。它不读取 provider locator 或 credential，不写文件，也不发起 provider HTTP。

## P4 Baseline 审计与部分指标

### 适用目的与边界

`scripts/finalize_evaluation_v2_baseline.py` 为 `baseline-v1` 追加 Codex audit 或 user decision，并从既有 27 条冻结身份确定性计算当前 P4 阶段与整个 cohort 的摘要。它不生成 P5 的 `evaluation-report.json` 或 `evaluation-report.md`，不构造 Runtime，不读取 prompt，不调用 provider。

### 追加审计或决定

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/finalize_evaluation_v2_baseline.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/<source-sha>/public/run-config.json \
  --stage P4A \
  --audit-input <codex-audit-input.json>
```

`--stage` 必须是 `P4A`、`P4B` 或 `P4C`；`--audit-input` 和 `--user-decision-input` 均可重复。输入使用与 Pilot 相同的通用 audit/decision schema，目标 row 必须属于冻结的 27 条 baseline identities。finalizer 先复核已有 checksum 和确定性事实，再 append-only 写入并重新封存当前公开 row；既有 audit 或 decision 拒绝覆盖。写入模式解析当前 provider 配置只为取得实际 locator/credential 值并拒绝其出现在新审计内容中，不发起 provider HTTP。

### 只读复核与摘要

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/finalize_evaluation_v2_baseline.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/<source-sha>/public/run-config.json \
  --stage P4A \
  --verify-only
```

`--verify-only` 不接受 audit/decision 输入，不读取 provider 配置且不写文件。stdout JSON 同时包含本阶段九条 row 和整个 27-row cohort 的分类计数、valid-run rate、verified-run success、stable task status、failure category、provider 请求、tool steps、repeated reads、elapsed time 和 G1 状态。工具与耗时只聚合最终 valid row；invalid、no result、待审计和待决定均按指标文档单列。每阶段将这份确定性摘要发布到 status，P5 再从相同 row 证据生成唯一正式总报告。

## P5 正式基线报告

### 构建边界

P5 只读消费已经封存的 `module-baseline-v1`、`baseline-v1` 以及用于边界观察的 `pilot-v3`、`pilot-v4` Artifact。它不运行 coding row、不构造 Runtime、不修改审计或历史分类，也不发起 provider HTTP。构建入口读取当前实际 provider locator 与 API key 的完整值仅用于最终公开候选字节的精确扫描；这些值不进入报告。

正式指标只来自以下两个根目录：

```text
module-baseline-v1/dcd8ea110c6c4dad5c09943fab26b8197142ae29
baseline-v1/542f97a023218ee04c00225de994f152bfed748e
```

`pilot-v3` 和 `pilot-v4` 仅支持 `prompt-normalization-scope` 边界观察，不进入正式成功率、排序、三项改进机会或简历结论。两个 Pilot 的 source 与 bridge 不同，因此不能解释为严格 A/B。

### 构建与发布

在已设置 `PICO_NATIVE_PROVIDER_CONFIG` 且该 locator 指向实际 provider 配置文件的进程中运行：

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/build_evaluation_v2_report.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json \
  --module-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/dcd8ea110c6c4dad5c09943fab26b8197142ae29 \
  --publish-doc docs/evaluation/evaluation-report-v2.md
```

构建器先完成并哈希正式指标子树，再验证两个 Pilot 并添加独立边界观察。随后它对全部被引用的公开 Artifact 以及三个最终候选执行一次实际值扫描；任何命中都会在写入前终止。扫描通过后，构建器生成：

```text
baseline-v1/<source-sha>/reports/evaluation-report.json
baseline-v1/<source-sha>/reports/evaluation-report.md
docs/evaluation/evaluation-report-v2.md
```

JSON 是唯一机器可读数据源；两份 Markdown 都从它确定性渲染，并且字节一致。不得人工追加或修订 Markdown。

### 只读复核

```bash
uv run --frozen --extra providers --python 3.12 \
  python scripts/verify_evaluation_v2_report.py \
  --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json \
  --module-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/dcd8ea110c6c4dad5c09943fab26b8197142ae29 \
  --publish-doc docs/evaluation/evaluation-report-v2.md
```

verifier 不读取 locator 或 credential、不写文件、不调用 provider。它重新验证 run config、27 条 row 的 public/private checksum、audit/decision、原件路径与运行时凭据扫描覆盖，复核 P1 module checksum 和两个 Pilot 报告，再从证据重算完整 JSON、正式指标哈希与 Markdown，并要求仓库镜像与外部 Markdown 字节一致。

G2 的确定性部分只有在上述复核通过时才成立。最终 G2 还要求一次只读 claims-to-evidence review 没有未解决的“结论缺少证据” Finding；review 不得自动修改报告、产品或历史 Artifact。
