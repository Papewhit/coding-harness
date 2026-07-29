# Pico Evaluation v2 状态

## 文档角色

本文记录 Evaluation v2 当前阶段和人类可读进度。规范性阶段、Gate 和授权边界见 [`evaluation-v2-plan.md`](evaluation-v2-plan.md)，证据与结果分类规则见 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。本文不创建新的阶段、Gate 或评测规则。

## 当前状态

- 当前阶段：P5 已完成；正式基线报告已从封存的 P1/P4 Artifact 确定性生成并发布，G2 已通过。
- 阶段结论：正式 coding cohort 为 27/27 valid、26/27 verified passed、1 条 `valid + failed / model_behavior`、0 条 invalid、284 次 provider 请求；外部 JSON/Markdown 与仓库 Markdown 镜像通过确定性重建和字节一致性校验。Prompt 规范化问题仅作为非指标边界观察记录。
- 历史控制 checkpoint： `2876cd53e17fd2b6eb089dbfaf14cd67615498fc`。
- 计划中的 P0 起点： `44677cd7f6a9535c1a74e8628078e9d4967594b5`。
- 实际 P0 起始 commit： `758eeaf7360f09296bc8a87567b021e68ca097d7`。该提交只解除 Evaluation v2 启动暂停并更新文档状态；P0 在检查其 diff 后从该 clean commit 开始。
- P0 结束 commit：`747feb384dbcdbe1b4d3b9e04e9590111970254f`。
- P1 起始 commit：`57eb0d4f15621ebfe01c6e1cda66ab6f145e160d`。
- 原 P1 候选 source commit：`2abc0c30badd619151b99f01abdab82331482824`； user guide 计划更新和 verifier revision 后已失效，未作为批次 source 接受，也未运行 Artifact。
- P1 已接受 source commit： `dcd8ea110c6c4dad5c09943fab26b8197142ae29`。
- P1 结束 commit：承载本状态条目的 commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- P1 实际结束 commit：`91a578d74439bd643b0dcb693a3b55a806b71f34`。
- P2 实际起始 commit：`4a70016101ffab6f777e53f938c472b5fe1e405d`；它相对 P1 结束 commit 只重排 Markdown 和补充对应文档规则，不改变 Evaluation v2 语义。
- P2 初始实现候选 source：`8c571834f6f297da3679aba1d279461bee06a517`，tree `614482ffa3515550878efeb87db05922ec5af07c`；用户接受前的审查发现两项证据完整性问题，因此该 source 及其两份配置已作废，不得用于 P3。
- P2 已接受 source：`b51b4a1a38b76da6cfa8403366ffec54990cfefa`，tree `8c5379d22ecef141af29291ba90a6d77db95207f`。
- P2 结束 commit：承载本阶段关闭记录的独立 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- P4 frozen source：`542f97a023218ee04c00225de994f152bfed748e`；tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`；Baseline run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`。
- P5 起始 commit：`2545f113ad4160b4a99717d8e3aaebdb87a196f3`；起始 tree：`e01789d7dfad5ffba6b0017b3092456496fdc85d`。
- P5 报告门实现 commit：`79032005cbc29d4a79fd9f96a23fb96db4cb9ca4`。
- P5 结束：承载本状态条目与正式报告镜像的 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- 正式 Artifact： `F:\dev\llm\pico-eval-artifacts\evaluation-v2\module-baseline-v1\dcd8ea110c6c4dad5c09943fab26b8197142ae29`。
- 正式 Baseline Artifact：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\baseline-v1\542f97a023218ee04c00225de994f152bfed748e`。
- 正式报告：上述 Baseline Artifact 的 `reports/evaluation-report.json` 与 `reports/evaluation-report.md`；仓库镜像为 [`evaluation-report-v2.md`](evaluation-report-v2.md)。
- wrapper revision 使用量：`0/1`。`dcd8ea1` 是正式测量前由总体方案和 user guide 交付要求驱动的实现对齐，不是测量 wrapper 缺陷修订。
- 当前边界：P5 与 Evaluation v2 正式基线交付已关闭。`pilot-v1`、`pilot-v2`、`pilot-v3`、`pilot-v4` 及 `baseline-v1` 的 27 条 row 均不得重跑、覆盖或重新分类；正式基线配置、证据与报告保持冻结。
- 下一动作：无自动后续。Runtime prompt 规范化修复、Auto-dream、Native Resume 或 post-fix cohort 都需要独立计划和用户授权，不由本阶段启动。

## 历史无效测量

R-01、R-02、R-03 都是 W6R5 的历史无效测量尝试，不是 Evaluation v2 评测行，也不进入任何产品成功率、稳定性、耗时或工具使用指标。

R-03 的主要结论是测量装置缺陷：HSMOKE-V4-A 实际完成了 `read_file -> patch_file -> read_file`，但旧检查要求整句英文逐字包含，因而把语义等价的结果误判为失败。这一记录不能作为 Pico 产品效果结论，也不得通过重新解释而并入 Evaluation v2 基线。

## P0 阶段记录

### 阶段结论

- 旧 `.codex/eval/**` 控制面已降级为只读历史材料。
- W6R5 专用 manifest、runner 和 tests 已从活动路径删除。
- v2 status、metrics 和最终报告占位文档已建立。
- 未修改产品实现、taskset、证据协议规则或外部 Artifact。

### 起始与结束 commit

- 起始：`758eeaf7360f09296bc8a87567b021e68ca097d7`。
- 结束：`747feb384dbcdbe1b4d3b9e04e9590111970254f`。

### 实际修改文件和 diff stat

- `M AGENTS.md`
- `D benchmarks/v3/native-provider/human-smoke-v4.json`
- `A docs/evaluation/evaluation-report-v2.md`
- `A docs/evaluation/evaluation-v2-metrics.md`
- `M docs/evaluation/evaluation-v2-plan.md`
- `A docs/evaluation/evaluation-v2-status.md`
- `D scripts/run_v3_native_human_smoke_v4.py`
- `D tests/test_v3_native_human_smoke_v4.py`
- 汇总：8 files changed, 305 insertions(+), 1858 deletions(-)。

### 执行过的命令与测试

- 起点保护检查确认工作区 clean、历史 checkpoint 是 HEAD 的祖先；计划 HEAD 已前移，因而先停止执行并检查 `44677cd..758eeaf` 的完整 diff。
- 漂移检查确认 `758eeaf` 只解除启动暂停和更新文档状态，随后将其记录为实际起点。
- 三个退役路径的存在性检查通过，活动源码、脚本和测试中的残留引用搜索为 0。
- plan、evidence protocol、status、metrics 和 report 共 5 份文档的相对链接检查通过，taskset 与 `taskset.lock.json` 目标存在。
- 从实际起点检查 `.codex/eval/**`、evidence protocol 和 taskset 均无 P0 diff。
- `git diff --check` 和 `git diff --cached --check` 通过。

按照 P0 约束，没有运行 pytest、全仓测试、live smoke 或 provider 请求。

### 新增 rows 与 metrics

- 新增 Evaluation v2 rows：0。
- 新增实测 metrics：0。
- 本阶段只固定指标定义，没有生成或发布指标值。

### 有效产品失败

0。P0 没有运行产品评测。

### invalid rows

- Evaluation v2 invalid rows：0。
- 历史无效测量：R-01、R-02、R-03，共 3 次；全部排除在 Evaluation v2 产品指标之外。

### 当前 blocker

无。P1 仍是纯离线阶段，不需要 provider HTTP 授权。

### 下一阶段的精确第一步

从 P0 结束 commit 启动新的 P1 顶层任务，只实现并运行 `scripts/run_evaluation_v2_modules.py` 所编排的确定性模块基线；输出到 `module-baseline-v1/<source-sha>`，不得发起 provider HTTP。

## P1 阶段记录（已完成）

### 阶段结论

- 已新增薄模块 runner，固定编排 harness、context、memory 和 recovery evaluator。
- 已将报告收敛为结构化 JSON 单一数据源，并由确定性 renderer 生成 Markdown。
- 已将五个事实 JSON、报告合同和 Markdown 的复核逻辑抽为 P5/G2 可组合调用的纯 verifier；`--verify-only` 不再依赖当前 checkout 或 HEAD。
- 已创建当前版本的 `evaluation-v2-user-guide.md`，并核对 CLI `--help`、测试和文档中的参数、前置条件、调用范围、产物入口与结果边界。
- 用户接受完整 source `dcd8ea110c6c4dad5c09943fab26b8197142ae29` 后，已在 WSL2、CPython 3.12.13 fresh clone 中生成正式 `module-baseline-v1` Artifact。
- 独立 `--verify-only` 已验证固定五个事实 JSON 的精确清单、字节数和 SHA-256，并由报告 JSON 逐字节重建 Markdown。Artifact 边界记录 provider HTTP 请求数为 0，且明确不是端到端编码结果。

### 起始与结束 commit

- 起始：`57eb0d4f15621ebfe01c6e1cda66ab6f145e160d`。
- 初始实现：`2abc0c30badd619151b99f01abdab82331482824`。
- user guide 计划更新：`6fac7ca01a9af075e56d3d226ae3113ec08157a3`。
- 已接受 source：`dcd8ea110c6c4dad5c09943fab26b8197142ae29`，tree `b7bfcc173cf0e1725efe4a3c44d5d8ff2b2f02a1`。
- 结束：承载本状态条目的 commit；完整 SHA 在提交后的交付消息中报告。

### 实际修改文件和 diff stat

- `M docs/evaluation/evaluation-v2-plan.md`
- `M docs/evaluation/evaluation-v2-status.md`
- `A docs/evaluation/evaluation-v2-user-guide.md`
- `M pico/evaluation/metrics.py`
- `A pico/evaluation/module_baseline.py`
- `A scripts/run_evaluation_v2_modules.py`
- `A tests/test_evaluation_v2_modules.py`
- `M tests/test_metrics.py`
- 阶段汇总：8 files changed, 1359 insertions(+), 67 deletions(-)。
- wrapper revision 使用量为 `0/1`。`dcd8ea1` 同时承载了已批准总体方案新增的 living user guide 要求和测量前 verifier 边界调整；它发生在 source 接受和首次正式测量之前，不计为测量 wrapper 缺陷修订。

### 执行过的命令与测试

- WSL2 使用 CPython 3.12.13；`uv run --frozen --python 3.12 ruff check` 对上述 revision Python 文件执行 scoped lint，结果通过。
- 第一次 targeted pytest 运行得到 `7 passed, 3 failed`；失败只涉及 canonical JSON 排序后公式字段顺序变化，导致 Markdown 字节重建不一致。
- 固定 renderer 的公式排序后，重新运行 `tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`，初始实现结果为 `11 passed`。
- 本次 revision 首次测试为 `17 passed, 1 failed`；唯一失败是 user guide 将 `provider HTTP` 跨行拆分，导致精确文档边界检查未匹配。修正文档后重新运行为 `18 passed`。六条 `datetime.utcnow()` deprecation warning 来自既有时间戳实现，不影响本阶段结果。
- 实际 CLI `--help` 只包含 `--output-root` 和 `--verify-only`，与 user guide 和 targeted tests 一致。
- source 接受后，在 `/home/papewhit/pico-eval-clones/p1-dcd8ea110c6c4dad` 建立 detached fresh clone，确认 HEAD 为已接受 source、tree 为上述 tree、checkout clean、Python 为 3.12.13。
- fresh clone 中显式运行 `uv sync --frozen --python 3.12`；随后运行 `uv run --frozen --python 3.12 pytest tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`，结果为 `18 passed`，并出现上述 6 条既有 deprecation warning。
- fresh clone 中对 `pico/evaluation/module_baseline.py`、 `scripts/run_evaluation_v2_modules.py`、两个对应测试文件和 `pico/evaluation/metrics.py` 执行 scoped Ruff，结果通过；再次执行实际 CLI `--help`，仍只包含 user guide 已记录的两个参数。
- 正式运行命令为 `uv run --frozen --python 3.12 python scripts/run_evaluation_v2_modules.py --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/dcd8ea110c6c4dad5c09943fab26b8197142ae29`，运行前再次确认 checkout clean、HEAD 正确且目标目录不存在。
- 独立复核命令为同一命令追加 `--verify-only`；结果为 source 和 cohort 一致、 `verified_json_files=5`、`markdown_rebuilt=true`。
- 正式 Artifact 包含 4 个模块 JSON、`public/modules/checksums.json`、报告 JSON 和报告 Markdown。manifest 精确覆盖 5 个事实 JSON，没有额外项；所有哈希为 64 位 SHA-256，所有字节数重算一致。
- 首次选择的 `/tmp` fresh clone 在后续 WSL 调用前被环境清理；随后对 `/mnt/f` fresh clone 的创建命令在宿主等待 120 秒后超时。两次都没有启动 evaluator 或创建 Artifact；最终使用上述 WSL 用户目录 fresh clone 完成正式运行。
- 完成实际运行后再次核对 user guide；CLI、前置条件、调用范围、Artifact 结构和结果解释均未变化，因此本次结束提交中 user guide 无变化。
- 全过程只使用 scripted/fake evaluator；未读取 provider locator，provider HTTP 请求数为 0。

### 新增 rows 与 metrics

- 新增 Evaluation v2 rows：0。
- 模块报告入口： `F:\dev\llm\pico-eval-artifacts\evaluation-v2\module-baseline-v1\dcd8ea110c6c4dad5c09943fab26b8197142ae29\reports\pico-module-baseline-v2.json`。
- harness：12 个固定任务、12 次运行，passed 12、failed 0、pass rate 100%、 verifier pass rate 100%、within-budget rate 100%。
- context：12 个 config × 5 次重复，共 60 次运行；current-request preserved rate 100%，平均 full prompt 8740 字符，平均 raw prompt 9998.67 字符，平均压缩率 10.66%，最大压缩率 22.46%。
- working memory：12 个任务 × 3 个 variant × 5 次重复，共 180 次运行。三个 variant 的 correct rate 均为 100%；`memory_on` 的 memory hit rate 为 100%、 repeated reads 为 0、平均 tool steps 为 0，`memory_off` 和 `memory_irrelevant` 的 memory hit rate 均为 0、repeated reads 均为 60、平均 tool steps 均为 1。
- recovery：10 个任务 × 2 个 variant × 3 次重复，共 60 次运行。 `resume_enabled` 的 resume success rate 为 90%、stale reanchor rate 为 100%、 workspace drift detection rate 为 100%、false accept rate 为 0； `resume_disabled` 四项均为 0。
- 四个模块的 exclusions count 均为 0。上述指标只属于确定性模块证据，不进入 `pilot-v1` 或 `baseline-v1` 的编码成功率分母。

### 有效产品失败

- harness 明确分类的有效产品失败为 0。
- 其他三个 ablation evaluator 输出指标而不作开放语义 passed/failed 分类，因此 verifier 不把它们自动转成产品失败。特别是 recovery 中 3 个 `schema_mismatch_missing` 重复按 fixture 得到 `no-checkpoint`，使 `resume_enabled` 的聚合 resume success rate 为 90%；其 false accept 均为 0。本记录保留该事实，不替用户作额外语义判分。

### invalid rows

0。P1 不创建 Evaluation v2 编码评测行；所有正式模块 Artifact 均完整并通过独立复核。前述两次环境准备中断发生在 evaluator 启动前，不是测量行，也不产生 `invalid`。

### 当前 blocker

无。P1 已完成，wrapper revision 使用量为 `0/1`，正式 Artifact 不覆盖、不重跑。

### 下一阶段的精确第一步

从 P1 结束 commit 启动新的 P2 顶层任务，以 `pico/evaluation/live_tasks.py` 的 `LocalLiveTaskRunner`、`TaskSpec` 和 `ClientResult` 为起点，先补充实际 `repositories -> tasks` taskset 的 loader 测试；后续只实施计划限定的 client/证据留存与 run config 工作，不发起 provider HTTP。

## P2 阶段记录（实现候选，待配置接受）

### 阶段结论

- 复用 `LocalLiveTaskRunner`，将正式 `repositories -> tasks` taskset 映射为隔离的 `TaskSpec`，并在创建 row 目录前重算 taskset、任务输入和仓库树锁。
- 新增薄 Runtime client，直接使用现有 provider adapter 和 Pico Runtime；没有引入 SDK Tool/Agents Runner，也没有保留可执行文本工具 fallback。
- 固定 `approval=auto`、workspace write scope、auto-dream=false、4096 output token、50 tool steps、300 秒 provider timeout、600 秒 row timeout和最小工具白名单。`run_shell` 使用 required bubblewrap `--unshare-net`，子 agent、ask-user 和 plan 工具不开放。
- 实现 immutable row、失败最小记录、private/public 原件选择、verifier 独立证据、workspace hash/diff、四层 call ID/工具名/终态核对、实际值凭据扫描和清理后 checksum 复算。
- CLI 保留旧离线模式，新增 run config 生成、只读验证及 Evaluation v2 的 cohort/stage/task/repo/repetition 参数；Pilot 和 Baseline row 身份及 repetition-major 顺序在配置中冻结。
- user guide 已同步 P2 的命令、前置条件、调用边界、Artifact 入口和结果解释。
- 当前本地 fake 流程的 provider HTTP 请求数为 0；尚未创建任何正式 row，尚未运行 P3。

### 起始与候选 commit

- 起始：`4a70016101ffab6f777e53f938c472b5fe1e405d`，tree `9c49e65e2702cd0a301ce9e9046054218809cf85`。
- 实现候选：承载本状态条目的 commit；完整 commit 和 tree 在提交后的交付消息中报告。
- P2 结束：尚未发生。用户接受两份 run config 后另建独立 docs commit 关闭 P2；不 amend、不回填候选 source。

### 实际修改文件和 diff stat

- 修改 `pico/evaluation/live_tasks.py`、`scripts/run_local_coding_tasks.py`、`tests/test_live_task_evaluator.py`、本 user guide 和 status。
- 新增 taskset/配置/调度/证据/row capture/live client 模块、`scripts/run_pico_live_task_client.py` 和 `tests/test_evaluation_v2_evidence.py`。
- 精确候选 diff stat：15 files changed, 3321 insertions(+), 114 deletions(-)。
- `.codex/eval/**`、taskset、taskset lock、evidence protocol 和 Runtime 核心语义均未修改。

### 已执行的命令与测试

- `uv run --extra providers pytest tests/test_live_task_evaluator.py tests/test_evaluation_v2_evidence.py -q`：当前本地 targeted 结果 30 passed；加入 `tests/test_architecture_boundaries.py` 和 `tests/test_safety_invariants.py` 后为 41 passed。
- scoped `uv run --extra providers ruff check`：通过。
- 两个实际 CLI `--help`：通过；主 runner 显示 `--run-config`、`--prepare-run-configs`、`--verify-only`、`--cohort-id`、`--stage`、`--task`、`--repo` 和 `--repetitions`，薄 client 只接受 `--run-config`。
- bubblewrap 实际探针：本地命令退出 0，`--unshare-net` 内对外 socket 以 `Network is unreachable` 失败。
- WSL fresh clone 的 targeted tests、architecture boundary、safety invariant、scoped Ruff、CLI help 和两份配置只读验证尚待候选提交后执行。

### 新增 rows 与 metrics

- 新增 Evaluation v2 正式 rows：0。
- 新增真实产品 metrics：0。
- fake T01 只验证 runner、workspace、hidden verifier 和证据协议，不进入产品成功率分母。
- provider HTTP 请求：0。

### 有效产品失败

0。P2 不运行真实产品评测。

### invalid rows

0。故障注入测试产生的临时记录只属于 pytest fixture，不是 Evaluation v2 正式 row。

### 当前 blocker

- 候选 source 尚未提交和在 WSL fresh clone 复核。
- `pilot-v1/<source>/public/run-config.*` 与 `baseline-v1/<source>/public/run-config.*` 尚未冻结和展示。
- 用户尚未接受两份配置；P3 没有 live 授权。

### 下一阶段的精确第一步

创建实现候选提交并取得完整 commit/tree；在 detached WSL fresh clone 中执行最终离线验收。只有验收全部通过才生成两份配置；展示后停止，等待用户明确接受。P3 的第一步仍是单独授权且绑定已接受配置哈希的 T01 live row。

## P2 审查修订记录（历史）

### 审查结论

- `evaluation_v2_artifacts.py` 的异常处理曾在 client 已持久化、但 verifier 或证据复制随后失败时使用尚未赋值的默认 `ClientResult`，从而把真实非零请求数写成 0/不精确。
- `evaluation_v2_evidence.py` 的 checksum verifier 曾只核对 manifest 已列文件，无法发现目录中的额外未列文件，也没有完整验证 schema、重复路径和安全相对路径。
- 两项均为 P1 finding，结论成立。初始 source `8c571834f6f297da3679aba1d279461bee06a517` 对应的 Pilot SHA-256 `97bf942d24d6c6645b058f79bdbf8fb2d3441fb498cb154e3eec6e2d667250e4` 和 Baseline SHA-256 `ea486987ab9484e364e8f95917156696740551bc1228a421e5c9f7deb7c1904e` 从未获用户接受、没有 row 或 HTTP 记录，现明确作废。

### 修订内容

- 异常处理从已有 `run-record.json` 恢复完整 `ClientResult`，验证 HTTP attempt 是唯一连续序号，验证精确标记为布尔值，并将 attempt 数与已持久化 summary 交叉核对。恢复不一致会作为 measurement error 保留，不能伪装成准确的 0。
- checksum verifier 要求固定 schema 和字段集合，验证唯一、安全、规范的相对路径、非负整数大小和小写 SHA-256，并比较实际文件集合与 manifest 集合。额外未列文件、缺失文件、symlink、重复或越界路径均失败。
- 新增“1 次 HTTP 后 evidence copy 失败仍恢复 count=1/exact=true”“汇总计数矛盾时拒绝恢复”和“额外未列文件”等回归测试。
- 将原超过 500 行的证据测试 fixture 拆到 `tests/evaluation_v2_helpers.py`；修订后的所有新实现和测试文件均不超过 500 行，函数不超过 100 行。
- 修订 scoped diff：7 files changed, 577 insertions(+), 265 deletions(-)。

### 修订时状态与下一动作

- 修订本地 targeted tests 为 34 passed；加入 architecture boundary 和 safety invariant 后为 45 passed。scoped Ruff、两个 CLI help 和 `git diff --check` 均通过。
- 修订候选的 detached WSL fresh-clone 复核尚未执行。
- 新候选提交后必须重新建立 detached WSL fresh clone，并以新 source/client 哈希创建新的 `pilot-v1/<source>` 和 `baseline-v1/<source>` 配置目录。
- 旧配置保留为未接受的历史候选，不覆盖、不用于 live；P3 仍未授权，provider HTTP 仍为 0。

## P2 阶段关闭记录（已完成）

### 接受边界

- 用户于 2026-07-28 明确接受修订 source 对应的两份 canonical run config。
- 已接受 source 为 `b51b4a1a38b76da6cfa8403366ffec54990cfefa`，tree 为 `8c5379d22ecef141af29291ba90a6d77db95207f`。
- Pilot 配置路径为 `F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v1\b51b4a1a38b76da6cfa8403366ffec54990cfefa\public\run-config.json`，文件字节 SHA-256 为 `827b4c786a6d5a98a9d53d1273422f7e4b0d9acb2f7f3d526ff5653aeb7d74c6`。
- Baseline 配置路径为 `F:\dev\llm\pico-eval-artifacts\evaluation-v2\baseline-v1\b51b4a1a38b76da6cfa8403366ffec54990cfefa\public\run-config.json`，文件字节 SHA-256 为 `34e837412d36c3402afd11aee38636e62424186718716b278eef918a9b5954ac`。
- 两个 source 目录均只含 `public/run-config.json` 和 `public/run-config.sha256`；没有 `private`、row 目录或 provider HTTP 记录。
- 初始 source `8c571834f6f297da3679aba1d279461bee06a517` 的两份配置继续保留为未接受、不可运行的历史候选。
- 本次接受只关闭 P2，不授权 P3，不等于 G0；G0 仍须由 P3 首条 T01 live row 验证。

### 最终离线验收

- detached WSL fresh clone 位于 `/home/papewhit/pico-eval-clones/p2-b51b4a1a38b76da6`，环境为 Ubuntu 26.04、CPython 3.12.13 和 OpenAI SDK 2.46.0。
- `tests/test_live_task_evaluator.py`、`tests/test_evaluation_v2_evidence.py`、`tests/test_architecture_boundaries.py` 和 `tests/test_safety_invariants.py` 共 45 项测试通过。
- scoped Ruff、两个 CLI `--help`、`git diff --check` 和两份 run config 的只读验证均通过。
- 实际值扫描确认没有持久化 credential 或 locator；fake 路径没有调用 provider resolver/transport。
- P2 正式 rows 为 0，真实产品 metrics 为 0，provider HTTP 请求为 0。
- P2 user guide 已在 source 中与最终 CLI 和 Artifact 合同对齐，因此关闭提交不再修改 user guide。

### 阶段结束

- P2 结束 commit：承载本关闭记录的独立 docs commit；完整 SHA 在提交后的交付消息中报告，不 amend 已接受 source，也不回填两份配置。
- 关闭提交只修改 `docs/evaluation/evaluation-v2-status.md`；精确 diff stat 为 1 file changed, 36 insertions(+), 7 deletions(-)。
- 当前唯一 blocker 是尚未获得 P3 的独立 live 授权。
- 下一阶段的精确第一步：用户另行明确授权 P3，并同时绑定 source `b51b4a1a38b76da6cfa8403366ffec54990cfefa`、tree `8c5379d22ecef141af29291ba90a6d77db95207f` 和 Pilot 配置 SHA-256 `827b4c786a6d5a98a9d53d1273422f7e4b0d9acb2f7f3d526ff5653aeb7d74c6` 后，才执行冻结配置中的 P3 G0 T01 命令；在此之前保持停止。

## P3 阶段记录（已完成，G0 未通过）

### 授权与冻结边界

- 用户已明确授权完整 P3；授权不延伸到 P4A。
- P3 起始 commit：`32867e4be44ea76ecf2b65d2051462c26321d325`。
- live source：`b51b4a1a38b76da6cfa8403366ffec54990cfefa`；tree：`8c5379d22ecef141af29291ba90a6d77db95207f`。
- Pilot run config SHA-256：`827b4c786a6d5a98a9d53d1273422f7e4b0d9acb2f7f3d526ff5653aeb7d74c6`。
- 只允许 `pilot-v1-T01-r1`、`pilot-v1-T04-r1`、`pilot-v1-T07-r1`；不允许语义重跑、replacement row、额外 preflight HTTP 或 P4 请求。

### 阶段结论

- 新增纯离线 Pilot audit/report finalizer；它不参与 live Runtime，也不改变冻结 source、runner、prompt、taskset、verifier 或 provider 参数。
- T01 只运行一次。runner 进程退出码为 1，命令摘要先显示 `failure_category=task`；原始 `run-record.json` 同时记录 client category 为 `provider`、精确 HTTP 次数为 0、无 call ID、无最终回答和无 workspace 修改。
- 私有 trace 只有 `run_started`，session events 只到 context usage，没有 `model_requested`。client 的原始异常类型没有进入持久证据，因而无法解释为何模型 transport 从未启动。
- hidden verifier 对未修改的 base fixture 失败，不构成 Pico 产品失败证据。Codex 审计将 T01 分类为 `invalid`；G0 未通过，P3 按计划立即停止，T04/T07 没有启动。
- `reports/pilot-report.json` 是机器可读单一来源，`pilot-report.md` 已从它确定性生成。finalizer 只读复核和新增公开文件的实际敏感值扫描均通过。

### 起始与结束 commit

- P3 起始 commit：`32867e4be44ea76ecf2b65d2051462c26321d325`。
- 离线 finalizer 实现：`7d5ec3ba0339effeae8095f37b227cfceffd9cef`。
- 审计边界修复：`9af69dba6151e1e83034bcdd45ca07070fb2d14d`，允许 Codex 将机械捕获完成但仍缺少关键解释证据的 row 判为 invalid，同时禁止把机械 invalid 提升为 valid。
- 控制/live 解释器解耦修复：`9a2c4c78f8cd28cebae60ef0190640356a91fb57`；完整 source/environment 重建仍由冻结 live 预检负责。
- P3 结束：承载本状态条目的 commit；完整 SHA 在提交后的交付消息中报告。

### 实际修改文件和 diff stat

- 新增 `pico/evaluation/pilot_audit.py`、`pico/evaluation/pilot_report.py`、`scripts/finalize_evaluation_v2_pilot.py` 和 `tests/test_evaluation_v2_pilot_report.py`。
- 更新本 status 和 `evaluation-v2-user-guide.md`。
- 没有修改冻结 live source、run config、taskset、verifier、Runtime、provider adapter 或 `.codex/eval/**`。
- 阶段汇总：6 files changed, 1180 insertions(+), 4 deletions(-)。

### 执行过的命令与测试

- 离线 finalizer 初始测试为 6 passed；加入既有 evidence tests 后为 26 passed，scoped Ruff 和实际 CLI `--help` 通过。
- T01 后新增“机械 complete 仍可由 Codex 判定证据不足”和“控制解释器不得重建 live client command”回归测试；最终 Pilot targeted tests 为 8 passed，连同既有 Evaluation v2 evidence tests 共 28 passed，scoped Ruff 通过。
- 冻结预检确认：控制 checkout clean；live clone HEAD/tree 正确且 clean；CPython 3.12.13、OpenAI SDK 2.46.0、config SHA-256、私有 profile、locator 文件、bubblewrap `--unshare-net` 和三个 row 目录均符合冻结配置。
- 唯一 live 命令是 run config 的 `launch_commands.p3_g0`。没有运行 `p3_remainder`，没有 retry、replacement row、额外 preflight HTTP 或 P4 请求。
- finalizer `--verify-only` 结果为 `g0_status=failed`、Markdown 可重建。公开 row 13 个文件和 reports 2 个文件的实际 locator/credential 精确扫描均通过。

### 新增 rows 与 metrics

- 新增正式 Pilot row：1，`pilot-v1-T01-r1`。
- 最终分类：invalid 1；valid passed 0；valid failed 0；no result 2；pending 0。
- valid-run rate：0/1（0%）；verified-run success：无 valid 分母，不可计算。
- 精确 provider HTTP 请求：0。SDK retry 0，Pico retry 0。
- tool steps、repeated reads 和 Runtime elapsed time 没有 valid 样本，不发布聚合值。
- 报告入口：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v1\b51b4a1a38b76da6cfa8403366ffec54990cfefa\reports\pilot-report.md`。

### 有效产品失败

0。hidden verifier 的失败发生在模型未执行、workspace 未修改的前提下，不能记作有效产品失败。

### invalid rows

- `pilot-v1-T01-r1`：invalid。原因是 pre-HTTP client 异常的原始类型没有留存，并被外层 runner 误标为 provider；现有证据不足以解释结果。
- 该 row 永久保留，不得在 `pilot-v1` 内重跑或覆盖。

### 当前 blocker

G0 未通过。P4A 不得启动。

### P3 后续评测桥接修复（纯离线）

- 已确认产品根因是 current request 尾部换行被 prompt 组装的 `.strip()` 删除，随后精确保真检查在首个 `ModelRequest` 前抛出 `ValueError`。本次不修改 Pico prompt 行为。
- live-task client 现在原子记录有限的 `failure_origin`、`failure_stage` 和 `error_type`。同一异常将机械记录为 `task / runtime / pre_request / ValueError`，精确 HTTP 次数为 0。
- `CommandClient` 只追加 process exit code，不再把非零退出覆盖为 provider。client 无法启动、超时、原始失败记录缺失或字段矛盾时保留证据并令 row invalid，不产生产品结论。
- 汇总采用单一固定优先级：测量记录损坏、原始 client/runtime 失败、协议失败、verifier 失败、成功。verifier 不再覆盖更早的 client/runtime 失败。
- 新增真实 `CommandClient → 子进程 → live-task client → Pico Runtime` 的离线桥接测试；测试使用生产 `NativeProviderModelClient` 和 OpenAI Responses adapter，只把最末端 transport 替换成确定性无网络实现。当前 prompt bug 经整条路径后保留为可信 Runtime pre-request 失败。
- WSL CPython 3.12.13 下，`test_live_task_evaluator.py`、Evaluation v2 evidence、Pilot report 和生产桥接共 49 项 targeted tests 通过；最后修改后的桥接 3 项复跑通过，scoped Ruff 通过。既有 Pilot finalizer `--verify-only` 仍为 G0 failed、1 invalid、2 no result，Markdown 可重建。
- 本修复没有执行 provider HTTP，没有重跑、覆盖或重新分类 `pilot-v1-T01-r1`。既有 Pilot 报告和 G0 结论保持不变。

### 下一阶段的精确第一步

由用户决定是否授权使用新 source、新 run config、新 cohort 和新 row 身份进行修复后 live 观察。停止条件是首条 row 能形成可信的 `valid + failed` 或 `valid + passed`；出现可信产品失败时继续 cohort，不修改 Pico 产品直至通过。原 `pilot-v1-T01-r1` 永久保留为 invalid。

## P3 `pilot-v2` 重新授权（已停止，未产生评测行）

### 授权与冻结身份

- 用户已授权在新 source 上再次开展完整 P3；授权仅覆盖 `pilot-v2-T01-r1`、`pilot-v2-T04-r1`、`pilot-v2-T07-r1`，不延伸至 P4。
- live source：`bf16b97c1b6889023b530f82aef073286884ef10`；tree：`5be797cb9543aba14ceb2267bcf888f5b0b25de4`。
- Pilot run config SHA-256：`398322eaed8e4d82bd4fffe49abbabee170591bb3747ca8b1992784f17298428`；profile ID：`sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`。
- 独占输出目录：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v2\bf16b97c1b6889023b530f82aef073286884ef10`。
- `pilot-v1` 的 source、配置、row、审计和报告保持不可变。

### 执行结论

- fresh WSL clone、source/tree、CPython 3.12.13、OpenAI SDK 2.46.0、配置哈希、locator 文件、bubblewrap 网络隔离和三个 row 目录不存在等预检均通过。
- 冻结的 `launch_commands.p3_g0` 只执行一次，在创建 T01 row 和首次 provider transport 之前退出：运行时重建配置将同一 venv 的解释器拼写为 `bin/python3`，冻结配置记录为 `bin/python`，精确身份检查因此报 `run config does not exactly match its source, environment, and schedule`。
- 这是配置生成器的确定性身份缺陷，不是 Pico 产品结果。精确 provider HTTP 请求数为 0，新增 row 为 0；`pilot-v2` 三条计划 row 全部为 `no result`，G0 没有可判定的 T01，保持未通过/未完成。
- 按一次性命令和禁止 replacement 的边界，没有重跑 T01，没有执行 `p3_remainder`，也没有启动 P4。

### 离线收口与下一步

- run config 现统一记录虚拟环境的稳定 `bin/python`（Windows 为 `Scripts/python.exe`）别名，避免 direct Python 与 `uv run` 对同一解释器采用不同字面路径。
- Pilot finalizer 新增 `--initialize-report`，用于命令在首条 row 前停止时确定性生成全 `no result` 报告；该模式不解析 provider 配置、不写 row、不调用 provider。
- 离线修复 commit：`f10b4b5ea822af7f0374260553ba610965498509`。WSL CPython 3.12.13 下，真实桥接、Evaluation v2 evidence、Pilot report 与 live evaluator 共 55 项 targeted tests 通过，scoped Ruff 通过。
- `pilot-v2` 报告已由上述提交生成并通过 `--verify-only`：`g0_status=pending`、planned 3、final classified 0、no result 3，Markdown 可逐字节重建。valid-run rate 与 verified-run success 均无分母；provider 请求合计为 0，tool steps、repeated reads 与 Runtime elapsed time 没有可用样本。
- 公开 Artifact 共 4 个文件：run config、旁路哈希和两份报告。实际 locator 与 credential 共 2 个敏感值的精确扫描命中 0；`public/rows` 目录不存在。
- `pilot-v3` 已作为新的隔离 cohort 身份加入离线实现。本次后续工作先提交并验收启动验证职责修复，再生成和展示新的 source/tree、配置哈希、三条 row 与独占输出目录；展示后停止，等待用户明确要求开始 P3。

## P3 `pilot-v3` 启动验证职责收敛与配置冻结

### 实现边界

- run-config 生成器只要求当前 tracked source clean；Python 解释器别名、符号链接、clone 绝对路径、操作系统补丁、SDK/locator 当前状态只作为事实记录，不作为生成阻断。
- `verify_run_config(path)` 和 run-config CLI 的 `--verify-only` 只检查 canonical JSON、既有 v1 schema 与旁路哈希；该 CLI 拒绝 live 选择参数，不读取 locator，不解析 provider，不探测 sandbox，也不构造 Runtime/client。
- 新的 `validate_live_start` 是 row 创建和首次 provider HTTP 前唯一的机械启动验证器。它只检查配置/哈希、tracked source HEAD/tree、请求 row 与 Artifact 边界、locator 与公开 provider/profile/model，以及一次正式 bubblewrap `--unshare-net` marker 探针。
- runner、row capture 和 live-task client 不再重建整份配置或重复 profile/sandbox 启动判断。row evidence validator 只处理运行后证据和分类。
- 校验器不解析冻结 argv、不检查阶段完整 row 集合、不预构造 Runtime/client、不推导 HTTP 上限；已知 prompt `ValueError` 的真实生产桥接仍保留为可信的 `runtime / pre_request` 产品失败。

### 冻结身份

- source commit：`e1c5652592588464bc808504188169053445d007`；tree：`d83406c26b77e5a3e0e86205c91e90a8b0db2eb7`。
- run config SHA-256：`175a723bc5d7f8560203f9b2ae21a61dbf9dcab0c15bfb107d69f874ec50206f`。
- profile：`dashscope-o`；profile ID：`sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`；model：`qwen3.6-plus`；wire dialect：OpenAI Responses；SDK：OpenAI `2.46.0`。
- planned rows：`pilot-v3-T01-r1`、`pilot-v3-T04-r1`、`pilot-v3-T07-r1`。
- 独占输出目录：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v3\e1c5652592588464bc808504188169053445d007`。
- 公开配置目录只有 `run-config.json` 与 `run-config.sha256`；`pilot-v1`、`pilot-v2` 的配置、row、报告和结论没有修改。

### 离线验收

- source A 在新的 detached WSL clone `/mnt/f/dev/llm/pico-eval-live-v3` 中复验；tracked 状态 clean，HEAD/tree 与上述冻结身份一致。
- 复验环境记录为 Ubuntu 26.04、CPython 3.12.13、OpenAI SDK 2.46.0。Evaluation v2 live evaluator、evidence、Pilot report、生产桥接和 live-start 共 71 项定向测试通过，scoped Ruff 通过。
- 配置生成后，run-config CLI 的纯格式 `--verify-only` 通过；独立 SHA-256 重算与旁路哈希一致。未调用 `validate_live_start`、sandbox 探针、Runtime/client 或 provider；provider HTTP 为 0。

### 冻结命令

G0：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v3/e1c5652592588464bc808504188169053445d007/public/run-config.json --cohort-id pilot-v3 --stage P3-G0 --task T01 --repo tinyconfig --repetitions 1
```

remainder：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v3/e1c5652592588464bc808504188169053445d007/public/run-config.json --cohort-id pilot-v3 --stage P3-remainder --task T04 --task T07 --repetitions 1
```

### Live 执行与审计结论

- `p3_g0` 与 `p3_remainder` 各启动一次，没有 retry、replacement row 或额外 live 命令。Codex 外层终端等待均在 19 秒返回超时，但唯一 WSL 子进程继续运行至完成；执行者只监控原进程，没有重启命令。
- T01 测量为 `complete`，原始失败为 `task / runtime / pre_request / ValueError`，provider 请求精确为 0。Codex 审计将其分类为 `valid + failed / product_behavior`；G0 因测量有效而通过。
- G0 通过后原样执行 remainder。T04 与 T07 同样为 `complete`、`runtime / pre_request / ValueError`、精确 0 请求，并分别审计为 `valid + failed / product_behavior`。
- 三条 row 均无 provider attempt、SDK retry、Pico retry、tool call 或任务 workspace 代码修改。hidden verifier 对未修改 fixture 失败是下游事实，不覆盖更早的 Runtime 失败来源。
- 没有 invalid、no result、pending audit 或 pending decision；没有请求用户作开放式结果判断。

### 指标与复核

- final classified：3/3；valid passed 0；valid failed 3；invalid 0；no result 0。
- valid-run rate：3/3（100%）；verified-run success：0/3（0%）。
- failure category：`product_behavior` 3。
- provider 请求总数：0；SDK retry 0；Pico retry 0。
- repeated reads：总数 0，mean 0，median 0。tool steps 与 Runtime elapsed time 均为 unavailable，不作推断。
- Pilot finalizer `--verify-only` 通过，G0 为 passed，报告 JSON 可确定性重算，Markdown 可逐字节重建。
- 使用实际 locator 与 credential 共 2 个敏感值扫描 `public/` 35 个文件和 `reports/` 2 个文件，命中 0。
- 报告入口：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v3\e1c5652592588464bc808504188169053445d007\reports\pilot-report.md`。

### 阶段停止

P3 在此关闭。保留已知 Pico prompt bug，不自动进入 P4A；若修复产品，应使用独立 post-fix cohort 验证，不修改或覆盖本次 Pilot 记录。

## P3 `pilot-v4` Evaluation prompt 入口修复与重新执行

### 发现与修复边界

- 后续代码下探确认三个标准用户入口均在调用 Runtime 前去除用户 prompt 的首尾空白：非交互入口对拼接后的 argv 调用 `strip()`，REPL 对 `input()` 结果调用 `strip()`，Textual TUI 对输入框值调用 `strip()`。
- Evaluation live bridge 先前直接把 taskset 中带末尾换行的原始 prompt 交给 Runtime。Runtime 的最终 prompt 装配会去除整体末尾空白，而请求上下文校验仍持有原始 task prompt，因此在首个 provider 请求前形成内部不一致；这不是标准用户入口可触发的同路径产品结果。
- 本次只在 `scripts/run_pico_live_task_client.py` 的 Evaluation 边界复用标准入口语义：交给 Runtime 前调用 `strip()`，并拒绝裁剪后的空 prompt。不修改 Pico Runtime、prompt builder、request context 或 taskset。
- 生产桥接离线测试使用真实 `CommandClient → 子进程 → live-task client → Pico Runtime → provider adapter` 路径，只把最终网络 transport 替换成确定性无网络实现；测试要求带首尾空白的原始 prompt 以裁剪后的精确值到达 wire request，并保留完整请求与 verifier 证据。

### 授权与执行边界

- 用户已授权在新的 source、run config、cohort 和 row 身份上重新执行 P3 三任务 Pilot。
- 只允许 `pilot-v4-T01-r1`、`pilot-v4-T04-r1`、`pilot-v4-T07-r1`；每条冻结命令只执行一次，不创建 replacement row，不修改或重新分类旧 Pilot。
- T01 测量有效即通过 G0，无论产品结果成功或失败；随后原样执行 T04/T07 remainder。完成审计和报告后停止，不自动进入 P4A。

### 冻结身份与离线验收

- source commit：`6460508c688383102f9dc205d8a04a5681b078dd`；tree：`487ca361a80ebdab9d661876db8d8985f64396a7`。
- run config SHA-256：`e4c4187207ad18022e3ce154bf7e5bed7761f24f8431ea02ce842d9ea372f19a`。
- profile：`dashscope-o`；profile ID：`sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`；model：`qwen3.6-plus`；wire dialect：OpenAI Responses。
- 独占输出目录：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v4\6460508c688383102f9dc205d8a04a5681b078dd`。
- source 在新的 detached WSL clone `/mnt/f/dev/llm/pico-eval-live-v4` 中复验；tracked 状态 clean，CPython 3.12.13、OpenAI SDK 2.46.0，72 项 Evaluation v2 定向测试和 scoped Ruff 通过。
- 配置生成及纯格式 `--verify-only` 期间没有运行 live validator、Runtime 或 provider；provider HTTP 为 0。

### 冻结命令

G0：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v4/6460508c688383102f9dc205d8a04a5681b078dd/public/run-config.json --cohort-id pilot-v4 --stage P3-G0 --task T01 --repo tinyconfig --repetitions 1
```

remainder：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/pilot-v4/6460508c688383102f9dc205d8a04a5681b078dd/public/run-config.json --cohort-id pilot-v4 --stage P3-remainder --task T04 --task T07 --repetitions 1
```

### Live 执行与审计结论

- `p3_g0` 与 `p3_remainder` 的冻结命令各实际执行一次，没有 retry、replacement row、语义重跑或额外 live 命令。
- T01 测量完整，client exit 0，精确 provider 请求 7 次，hidden verifier 通过；审计为 `valid + passed`，因此 G0 通过。
- G0 通过后原样执行 remainder。T04 与 T07 均测量完整、client exit 0、hidden verifier 通过，精确 provider 请求分别为 9 和 10 次；二者均审计为 `valid + passed`。
- 三条 row 均无 client failure、protocol error、measurement error、SDK retry、Pico retry 或敏感值命中；没有 invalid、no result、pending audit 或 pending decision。

### 指标与只读复核

- final classified：3/3；valid passed 3；valid failed 0；invalid 0；no result 0。
- valid-run rate：3/3（100%）；verified-run success：3/3（100%）；failure category 为空。
- provider 请求总数：26；SDK retry 0；Pico retry 0。
- tool steps：6、11、9，mean 8.67，median 9。repeated reads：1、2、1，总数 4，mean 1.33，median 1。
- Runtime elapsed time：64,417、71,252、50,217 ms，mean 61,962 ms，median 64,417 ms。
- Pilot finalizer `--verify-only` 通过，G0 为 passed，报告 JSON 可确定性重算，Markdown 可逐字节重建。
- 使用实际 locator 与 credential 共 2 个敏感值扫描 `public/` 38 个文件和 `reports/` 2 个文件，命中 0。
- 报告入口：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\pilot-v4\6460508c688383102f9dc205d8a04a5681b078dd\reports\pilot-report.md`。

### 阶段停止

P3 在此关闭。`pilot-v4` 表明 Evaluation prompt 入口修复后，三任务 Pilot 的测量与产品验证均通过；不自动进入 P4A。

## P4 正式基线前置冻结（已完成，未启动 P4A）

### 阶段结论

- 已将 Pilot 中通用的 audit append、row facts 和指标提取拆为共享 coding-report 层，并新增只处理 `baseline-v1` 的纯离线 finalizer；它输出当前阶段与 27-row cohort 的确定性摘要，不提前生成 P5 总报告。
- P4 冻结命令统一携带 `--resume-missing`。首次运行选择阶段全部 9 条 row；若计划允许的 measurement defect 纯离线修复后由用户明确继续，同一命令只执行 private/public 目录均不存在的 missing rows，不能覆盖或重跑既有 row。
- `validate_live_start` 的五项封闭阻断条件和职责没有改变；Pilot 配置、报告及历史 Artifact 保持兼容。
- P4 source 包含 `6460508c688383102f9dc205d8a04a5681b078dd` 的 prompt 入口规范化修复。九份任务文档即使保留末尾换行，也会在 live client 调用 Runtime 前按标准用户入口语义裁剪。
- P2 source `b51b4a1a38b76da6cfa8403366ffec54990cfefa` 下的 Baseline 配置绑定修复前 client SHA-256 `f7adf7167effe015a9b59e5f7ed41d6760c6cd555ce29f52b442673d3cfd3bf0`，现明确禁止用于 P4。

### 起始、实现与冻结身份

- 前置冻结起始 commit：`604924e74e46f912048c9e74f1506bf8431b4cf6`。
- frozen source commit：`542f97a023218ee04c00225de994f152bfed748e`；tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`。
- frozen source 的 live client SHA-256：`fdc7aafd1128d0471d880d1a8e06244cf499de1ae2c2474ed92b728a17b9c1cf`。
- fresh clone：`/home/papewhit/pico-eval-clones/p4-542f97a023218`；tracked 状态 clean。
- Baseline 配置：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\baseline-v1\542f97a023218ee04c00225de994f152bfed748e\public\run-config.json`。
- run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`。
- profile：`dashscope-o`；profile ID：`sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`；model：`qwen3.6-plus`；wire dialect：OpenAI Responses；SDK：OpenAI `2.46.0`。
- 前置冻结结束：承载本状态条目的 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。

### 实际修改文件和 diff stat

- 新增 `pico/evaluation/coding_report.py`、`pico/evaluation/baseline_summary.py`、`scripts/finalize_evaluation_v2_baseline.py` 和 `tests/test_evaluation_v2_baseline_summary.py`。
- 更新 P4 schedule、local coding runner、Pilot report、live-start/evidence tests 和 user guide。
- 实现 commit 汇总：10 files changed, 1203 insertions(+), 235 deletions(-)。
- 本状态记录只更新 `evaluation-v2-status.md`，不改变 frozen source、run config 或 Artifact。

### 执行过的命令与测试

- Windows `uv run` 因仓库 `.venv/lib64` 权限问题在测试启动前退出；按 `docs/annoying-uv-codex.md` 改用 WSL，重建本地 `.venv` 后继续。该故障没有运行测试、provider 或 P4 row。
- 当前工作区首轮新增 baseline tests 为 5 passed；Baseline 与 Pilot report 合并回归为 17 passed；最终定向组为 81 passed，scoped Ruff 和两个 CLI `--help` 检查通过。
- 在 fresh clone 中使用 CPython 3.12.13 和 OpenAI SDK 2.46.0 复跑同一 81 项定向测试，结果为 81 passed；scoped Ruff 通过。
- fresh clone 的 source/tree、prompt 修复祖先关系、client 哈希和 clean tracked 状态均已复核。
- run-config `--verify-only` 通过；Baseline finalizer `--verify-only --stage P4A` 得到 stage `no result=9`、cohort `no result=27`、G1 `pending`。
- 独立重算配置 SHA-256 与旁路哈希一致；使用当前实际 locator 与 credential 值扫描配置，命中 0。Artifact 目录只有 `run-config.json` 和 `run-config.sha256`。

### 冻结命令

P4A：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4A --repo tinyconfig --repetitions 3 --resume-missing
```

P4B：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4B --repo miniqueue --repetitions 3 --resume-missing
```

P4C：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4C --repo logslice --repetitions 3 --resume-missing
```

### 新增 rows 与 metrics

- 新增正式 Baseline rows：0；provider HTTP：0。
- 计划身份：27；`valid + passed` 0；`valid + failed` 0；`invalid` 0；`no result` 27。
- valid-run rate 与 verified-run success 均无分母，不可计算；stable task status 九项均为 `insufficient-evidence`；G1 为 `pending`。

### 有效产品失败与 invalid rows

- 有效产品失败：0。
- invalid rows：0。

### 当前 blocker 与下一阶段的精确第一步

- 当前没有实现或配置 blocker。P4A 尚未获得单独的阶段启动指令。
- 用户明确要求开始 P4A 后，在 frozen clone 中只执行上述 `p4a` 命令一次；该指令覆盖计划内 9 条 row 的 provider HTTP 范围。完成 row 审计、部分指标、status 与阶段提交后停止，不自动进入 P4B。

## P4A tinyconfig 正式基线（已完成）

### 阶段结论

- 已按冻结配置执行 tinyconfig 的 T01–T03，每个任务 3 次独立重复，共 9 条主评测行；冻结 live 命令只启动一次，没有 retry、replacement row、语义重跑或额外 live 命令。
- 9 条 row 均为完整有效测量：8 条 `valid + passed`，1 条 `valid + failed / model_behavior`，0 条 `invalid`、`pending audit`、`pending decision` 或 `no result`。
- 唯一失败是 `baseline-v1-T02-r1`。Runtime 正常完成，精确记录 12 次 provider 请求；hidden verifier 确认实现未让 malformed database section 抛出 `ConfigError`，因此归类为模型实现遗漏，不是 Runtime、provider、协议或测量失败。
- live 命令因包含有效任务失败而按设计返回 exit 1；它仍完成了全部 9 条 row，不构成基础设施或阶段中止。
- P4A 在此关闭，不自动进入 P4B。

### 起始、结束与冻结身份

- P4A 控制面起始 commit：`6235aaa220ab8723f7c12356f6ab8e74815e2bcb`。
- P4A 结束：承载本状态条目的 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- frozen source commit：`542f97a023218ee04c00225de994f152bfed748e`；tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`。
- fresh clone：`/home/papewhit/pico-eval-clones/p4-542f97a023218`；运行前后 tracked 状态 clean。
- run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`。
- 执行窗口：`2026-07-28T20:51:11.905233+08:00` 至 `2026-07-28T21:01:27.349885+08:00`。

### 实际修改文件和 diff stat

- `M docs/evaluation/evaluation-v2-status.md`
- 汇总：1 file changed, 66 insertions(+), 4 deletions(-)。
- 阶段提交只更新本状态文档；row、审计和 checksums 位于仓库外的正式 Artifact，不进入 Git diff。
- user guide 无变化：本阶段没有新增或改变评测入口、参数、前置条件、调用范围、Artifact 结构或结果解释。

### 执行过的命令与复核

- 启动前确认控制仓库与 frozen clone clean，HEAD/tree、run config SHA-256 和旁路哈希均与冻结值一致；P4A row 目录为空，provider locator 存在且指向文件，未发现已运行的 P4A 进程。
- 在 frozen clone 中原样执行一次 P4A 冻结命令：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4A --repo tinyconfig --repetitions 3 --resume-missing
```

- Codex 逐行审计 `run-record.json`、`evidence-view.json`、verifier 结果和失败 stderr；9 份审计均通过 schema 与确定性分类校验，追加后重新封存 checksums，无需用户裁决。
- 独立执行 Baseline finalizer `--verify-only --stage P4A`，结果为 exit 0；9/9 final classified，checksums、审计和部分指标均可确定性重算。
- 实际 locator 与 credential 共 2 个敏感值扫描 `public/` 110 个文件和 `reports/` 0 个文件，命中 0。
- 9 条 row 的 measurement error、protocol error、SDK retry 和 Pico retry 均为 0；provider 请求计数全部为 exact。

### 新增 rows 与部分 metrics

- 新增正式 Baseline rows：9；cohort 当前 final classified 9/27，剩余 18 条为 `no result`，G1 为 `pending`。
- valid-run rate：9/9（100%）。
- verified-run success：8/9（88.89%）。
- stable task status：T01 `stable-pass`；T02 `mixed-valid`；T03 `stable-pass`。
- failure category：`model_behavior` 1。
- provider 请求：9/9 样本 complete，合计 77。
- tool steps：mean 9.67，median 9。
- repeated reads：总数 6，mean 0.67，median 1。
- Runtime elapsed time：mean 62,534.22 ms，median 41,896 ms。

### 有效失败与 invalid rows

- 有效失败：1 条，即 `baseline-v1-T02-r1`，分类为 `valid + failed / model_behavior`。
- invalid rows：0。

### 当前 blocker 与下一阶段的精确第一步

- 当前没有实现、配置或测量 blocker；G1 尚未通过仅因为 P4B/P4C 的 18 条计划 row 尚未启动。
- 只有用户明确要求开始 P4B 后，才复核同一 frozen source/tree、run config 哈希和 P4B row 缺失状态，并在 frozen clone 中原样执行一次 `p4b` 命令。完成 P4B 审计、部分指标、status 与阶段提交后停止，不自动进入 P4C。

## P4B miniqueue 正式基线（已完成）

### 阶段结论

- 已按冻结配置执行 miniqueue 的 T04–T06，每个任务 3 次独立重复，共 9 条主评测行；冻结 live 命令只启动一次，没有 retry、replacement row、语义重跑或额外 live 命令。
- 9 条 row 均为 `valid + passed`，0 条 `valid + failed`、`invalid`、`pending audit`、`pending decision` 或 `no result`；T04、T05、T06 均为 `stable-pass`。
- live 命令完成全部 9 条 row 并返回 exit 0。Runtime、provider、协议、测量和 deterministic verifier 均未出现失败。
- 9 份 Codex audit 追加并重新封存后，用户要求暂停；所有已启动进程正常结束。恢复时只执行纯离线复核、敏感值扫描、status 更新与阶段提交，没有再次调用 provider。
- P4B 在此关闭，不自动进入 P4C。

### 起始、结束与冻结身份

- P4B 控制面起始 commit：`a38208e6b65a124392074e3eaba5bced8608ba11`。
- P4B 结束：承载本状态条目的 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- frozen source commit：`542f97a023218ee04c00225de994f152bfed748e`；tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`。
- fresh clone：`/home/papewhit/pico-eval-clones/p4-542f97a023218`；运行前、暂停后与恢复复核时 tracked 状态 clean。
- run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`。
- live 执行窗口：`2026-07-28T21:33:01.726098+08:00` 至 `2026-07-28T21:43:01.527087+08:00`。

### 实际修改文件和 diff stat

- `M docs/evaluation/evaluation-v2-status.md`
- 汇总：1 file changed, 66 insertions(+), 4 deletions(-)。
- 阶段提交只更新本状态文档；row、审计和 checksums 位于仓库外的正式 Artifact，不进入 Git diff。
- user guide 无变化：本阶段没有新增或改变评测入口、参数、前置条件、调用范围、Artifact 结构或结果解释。

### 执行过的命令与复核

- 启动前确认控制仓库与 frozen clone clean，HEAD/tree、run config SHA-256 和旁路哈希均与冻结值一致；P4B 的 9 条 public/private row 均不存在，provider locator 存在且指向文件，未发现已运行的 P4B 进程。
- 在 frozen clone 中原样执行一次 P4B 冻结命令：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4B --repo miniqueue --repetitions 3 --resume-missing
```

- Codex 逐行审计 `run-record.json`、`evidence-view.json` 和 verifier 结果；9 份审计均通过 schema 与确定性分类校验，追加后重新封存 checksums，无需用户裁决。
- 独立执行 Baseline finalizer `--verify-only --stage P4B`，结果为 exit 0；9/9 final classified，checksums、审计、阶段指标和当前 cohort 指标均可确定性重算。
- 实际 locator 与 credential 共 2 个敏感值扫描 `public/` 218 个文件和 `reports/` 0 个文件，命中 0。
- 9 条 row 的 measurement error、protocol error、SDK retry 和 Pico retry 均为 0；provider 请求计数全部为 exact，native tool call/result ID 一一对应。

### 新增 rows 与部分 metrics

- 新增正式 Baseline rows：9；cohort 当前 final classified 18/27，剩余 9 条为 `no result`，G1 为 `pending`。
- P4B valid-run rate：9/9（100%）；verified-run success：9/9（100%）。
- P4B stable task status：T04、T05、T06 均为 `stable-pass`；failure category 为空。
- P4B provider 请求：9/9 样本 complete，合计 101。
- P4B tool steps：mean 12.33，median 10。
- P4B repeated reads：总数 10，mean 1.11，median 1。
- P4B Runtime elapsed time：mean 59,850.33 ms，median 57,545 ms。
- 当前 cohort valid-run rate：18/18（100%）；verified-run success：17/18（94.44%）；provider 请求合计 178。

### 有效失败与 invalid rows

- P4B 有效失败：0。
- P4B invalid rows：0。
- 当前 cohort 仍保留 P4A 的 `baseline-v1-T02-r1` 一条 `valid + failed / model_behavior`，没有重新分类。

### 当前 blocker 与下一阶段的精确第一步

- 当前没有实现、配置或测量 blocker；G1 尚未通过仅因为 P4C 的 9 条计划 row 尚未启动。
- 只有用户明确要求开始 P4C 后，才复核同一 frozen source/tree、run config 哈希和 P4C row 缺失状态，并在 frozen clone 中原样执行一次 `p4c` 命令。完成 P4C 审计、指标、G1 结论、status 与阶段提交后停止，不自动进入 P5。

## P4C logslice 正式基线（已完成）

### 阶段结论

- 已按冻结配置执行 logslice 的 T07–T09，每个任务 3 次独立重复，共 9 条主评测行；冻结 live 命令只启动一次，没有 retry、replacement row、语义重跑或额外 live 命令。
- 9 条 row 均为 `valid + passed`，0 条 `valid + failed`、`invalid`、`pending audit`、`pending decision` 或 `no result`；T07、T08、T09 均为 `stable-pass`。
- live 命令完成全部 9 条 row 并返回 exit 0。Runtime、provider、协议、测量和 deterministic verifier 均未出现失败。
- 完整 `baseline-v1` 的 27 条主评测行全部最终分类，G1 通过。P4A 的一条模型行为失败按原分类保留，其余 26 条通过。
- P4C 在此关闭，不自动进入 P5；本阶段没有生成 P5 报告。

### 起始、结束与冻结身份

- P4C 控制面起始 commit：`5d4a4afc25154d85c3ca5d7aa411346cbb777467`。
- P4C 结束：承载本状态条目的 docs commit；完整 SHA 在提交后的交付消息中报告，不为回填而 amend。
- frozen source commit：`542f97a023218ee04c00225de994f152bfed748e`；tree：`34e75ea5ff6340948493c93ba449b8980c2a8f85`。
- fresh clone：`/home/papewhit/pico-eval-clones/p4-542f97a023218`；运行前后 tracked 状态 clean。
- run config SHA-256：`79435b0c961e775e7de0ad68eee950f322c7094ddd10da4aba17ab728040faff`。
- live 执行窗口：`2026-07-28T22:24:47.152225+08:00` 至 `2026-07-28T22:33:35.342524+08:00`。

### 实际修改文件和 diff stat

- `M docs/evaluation/evaluation-v2-status.md`
- 汇总：1 file changed, 70 insertions(+), 4 deletions(-)。
- 阶段提交只更新本状态文档；row、审计和 checksums 位于仓库外的正式 Artifact，不进入 Git diff。
- user guide 无变化：本阶段没有新增或改变评测入口、参数、前置条件、调用范围、Artifact 结构或结果解释。

### 执行过的命令与复核

- 启动前确认控制仓库与 frozen clone clean，HEAD/tree、run config SHA-256 和旁路哈希均与冻结值一致；P4C 的 9 条 public/private row 均不存在，provider locator 存在且指向文件，未发现已运行的 P4C 进程。
- 在 frozen clone 中原样执行一次 P4C 冻结命令：

```text
uv run --frozen --extra providers --python 3.12 python scripts/run_local_coding_tasks.py --run-config /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/baseline-v1/542f97a023218ee04c00225de994f152bfed748e/public/run-config.json --cohort-id baseline-v1 --stage P4C --repo logslice --repetitions 3 --resume-missing
```

- Codex 逐行审计 `run-record.json`、`evidence-view.json` 和 verifier 结果；9 份审计均通过 schema 与确定性分类校验，追加后重新封存 checksums，无需用户裁决。
- 独立执行 Baseline finalizer `--verify-only --stage P4C`，结果为 exit 0；P4C 9/9、cohort 27/27 final classified，checksums、审计、阶段指标、完整 cohort 指标和 G1 结论均可确定性重算。
- 实际 locator 与 credential 共 2 个敏感值扫描 `public/` 326 个文件和 `reports/` 0 个文件，命中 0。
- 9 条 P4C row 的 measurement error、protocol error、SDK retry 和 Pico retry 均为 0；provider 请求计数全部为 exact，native tool call/result ID 一一对应。

### 新增 rows、完整 metrics 与 G1

- 新增正式 Baseline rows：9；cohort final classified 27/27，`no result`、`pending audit` 和 `pending decision` 均为 0，G1 为 `passed`。
- P4C valid-run rate：9/9（100%）；verified-run success：9/9（100%）。
- P4C stable task status：T07、T08、T09 均为 `stable-pass`；failure category 为空。
- P4C provider 请求：9/9 样本 complete，合计 106。
- P4C tool steps：mean 13.33，median 11。
- P4C repeated reads：总数 5，mean 0.56，median 1。
- P4C Runtime elapsed time：mean 52,366.89 ms，median 44,830 ms。
- 完整 cohort valid-run rate：27/27（100%）；verified-run success：26/27（96.30%）。
- 完整 cohort stable task status：除 T02 为 `mixed-valid` 外，T01、T03–T09 均为 `stable-pass`。
- 完整 cohort failure category：`model_behavior` 1；provider 请求合计 284。
- 完整 cohort tool steps：mean 11.78，median 10；repeated reads 总数 21，mean 0.78，median 1；Runtime elapsed time mean 58,250.48 ms，median 54,892 ms。

### 有效失败与 invalid rows

- P4C 有效失败：0。
- P4C invalid rows：0。
- 完整 cohort 有效失败：1 条，即 P4A 的 `baseline-v1-T02-r1`，分类保持为 `valid + failed / model_behavior`。
- 完整 cohort invalid rows：0。

### 当前 blocker 与下一阶段的精确第一步

- 当前没有实现、配置、测量或 G1 blocker；P4 的 27 条主评测行已全部关闭。
- 等待用户明确要求开始 P5。P5 的精确第一步是只读验证已封存的模块基线与 `baseline-v1` Artifact，然后从这些事实生成项目评测基线报告；不得调用 provider，不得修改任何 P4 row、审计或分类。

## P5 首份项目评测基线报告（已完成）

### 阶段结论

- 已从固定的 P1 `module-baseline-v1/dcd8ea1...` 与 P4 `baseline-v1/542f97a...` Artifact 生成唯一正式报告 JSON、外部 Markdown 和字节一致的仓库 Markdown 镜像。
- 正式结果子树在加入边界观察前冻结，SHA-256 为 `2e086a112940358eaea8b86831c13c430c6984839650c05c3fb9fb7ef9631908`；加入 `prompt-normalization-scope` 后该哈希不变。
- 最终公开候选使用实际 locator 与 API key 完整值扫描 413 个文件，命中 0；扫描 coverage SHA-256 为 `838834cd88c1a94daba4c2c1a2de1cc72649cdeb43c9fa0acbe0be18f524e3a6`。
- 独立只读 verifier 重算证据、正式聚合、Pilot 引用、JSON 和 Markdown，结果为 `g2_deterministic=passed`。随后一次只读 claims-to-evidence review 返回“无未解决 Finding”，因此 G2 最终为 `passed`。
- 全过程没有调用 provider、运行或修改 coding row、改变审计/历史分类、修复 Runtime 或创建补充批次。

### 起始、实现与结束

- P5 clean 起始 commit：`2545f113ad4160b4a99717d8e3aaebdb87a196f3`；tree：`e01789d7dfad5ffba6b0017b3092456496fdc85d`。
- 报告门实现 commit：`79032005cbc29d4a79fd9f96a23fb96db4cb9ca4`。
- P5 结束：承载最终 renderer 措辞、正式报告镜像和本状态条目的 docs commit；完整 SHA 在提交后的交付消息中报告。

### 实际修改与产物

- 实现提交修改 `pico/evaluation/baseline_summary.py`、`docs/evaluation/evaluation-v2-user-guide.md`，新增 `pico/evaluation/evaluation_report.py`、两个 P5 CLI 和 `tests/test_evaluation_v2_report.py`。
- 发布提交修改 `pico/evaluation/evaluation_report.py`、`docs/evaluation/evaluation-report-v2.md` 和本状态文档。
- 外部报告 JSON：`F:\dev\llm\pico-eval-artifacts\evaluation-v2\baseline-v1\542f97a023218ee04c00225de994f152bfed748e\reports\evaluation-report.json`，102345 bytes，SHA-256 `2a79b30b69db65c0e2a1a6ccd2aeedd0f67415f287dd3229fbb2ccb364a499b4`。
- 外部报告 Markdown 与仓库镜像均为 20999 bytes，SHA-256 `1ac86d95a099c6d2f65b5df9d6ea28035b7ca498ab6dd90663f446c03f3ec2c0`。

### 执行过的命令、测试与复核

- 从 clean HEAD 记录起始 commit/tree；只读运行 P1 module verifier 与 P4C Baseline finalizer，前者确认 5 个 JSON、checksum 与 Markdown 重建，后者确认 G1 为 27/27 passed。
- targeted aggregation tests 最终为 19 passed；renderer 措辞修正后报告专项测试为 13 passed。scoped Ruff 通过，两个 CLI 的实际 `--help` 均显示 `--run-config`、`--module-root` 和 `--publish-doc`。
- 构建器先验证 27 条 public/private row checksum、audit/decision、原件路径、运行时扫描覆盖与 P1 module checksum，再冻结正式结果，最后只读验证 `pilot-v3`、`pilot-v4` 并加入边界观察。
- 使用实际 locator/API key 执行最终公开扫描并生成报告；独立 `scripts/verify_evaluation_v2_report.py` 不读取 credential、不写文件、不调用 provider，复核结果为 27 planned/final、26 passed、1 failed、0 invalid、Markdown rebuilt、仓库镜像一致。
- 发布前唯一一次全仓命令 `uv run --frozen --extra providers --python 3.12 pytest tests -q` 得到 654 passed、2 skipped、6 warnings，用时 232.24 秒。warnings 均来自既有 `datetime.utcnow()` deprecation。
- 只读 claims-to-evidence review 核对 27 行、repo/task/failure 聚合、284 次请求、成本指标、P1 模块指标、三项改进机会、简历映射和 Prompt 双边界措辞；结论为“无未解决 Finding”。

### 正式指标与改进机会

- valid-run rate：27/27（100%）；verified-run success：26/27（96.30%）；invalid：0。
- failure category：`model_behavior` 1；provider requests：284；T02 为 `mixed-valid`，T01、T03–T09 均为 `stable-pass`。
- tool steps mean 11.78、median 10；repeated reads 总数 21、mean 0.78、median 1；Runtime elapsed mean 58,250.48 ms、median 54,892 ms。
- 三项正式改进机会保持为 T02 边界正确性、T09 执行成本和 miniqueue 重复读取；Prompt 边界观察没有进入排序。
- P1 module 指标保持独立分母：harness 12/12；context 平均压缩率 10.66%、current request 保留率 100%；memory_on repeated reads 0、correct rate 100%；resume_enabled success 90%、workspace drift detection 100%、false accept 0。

### Prompt 边界观察

- `pilot-v3` 的 3 条 `runtime/pre_request` 有效失败与 `pilot-v4` 规范化入口后的 3 条通过均按原分类保留；两个 Pilot source/bridge 不同，不构成严格 A/B，也不进入 `baseline-v1` 分母。
- 以标准 one-shot、REPL、TUI 和正式 Evaluation bridge 组成的完整 Pico 产品为边界，入口 `strip()` 消解该路径，因此不是正式基线产品失败。
- 以 Runtime/Pico API 为可独立调用模块，原始 request metadata 与整体 `strip()` 后 prompt 可能不一致，形成未明确声明或内部统一执行规范化的接口契约缺口，可条件式视为 Runtime bug。
- 本阶段只报告该观察，不新增 Runtime characterization test、不修改产品，也不改变正式结果、前三项改进机会或简历结论。

### 有效失败、invalid rows、blocker 与下一动作

- 正式有效失败仍只有 `baseline-v1-T02-r1` 一条，分类保持 `valid + failed / model_behavior`。
- invalid rows：0。
- 当前 blocker：无；G1 与 G2 均已通过。
- P5 与 Evaluation v2 正式基线交付关闭。任何 Runtime 修复、Auto-dream、Native Resume、补充或 post-fix cohort 都必须作为独立工作获得用户授权。
