# Pico Evaluation v2 状态

## 文档角色

本文记录 Evaluation v2 当前阶段和人类可读进度。规范性阶段、Gate 和授权边界见 [`evaluation-v2-plan.md`](evaluation-v2-plan.md)，证据与结果分类规则见 [`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。 本文不创建新的阶段、Gate 或评测规则。

## 当前状态

- 当前阶段：P2——最小真实编码桥接。
- 阶段结论：实现候选和本地离线验证已完成，正等待在候选 source 的 WSL fresh clone 中完成最终复核并冻结 `pilot-v1`、`baseline-v1` 两份 run config。P2 尚未关闭，配置尚未获得用户接受，没有发起 provider HTTP，也没有进入 P3。
- 历史控制 checkpoint： `2876cd53e17fd2b6eb089dbfaf14cd67615498fc`。
- 计划中的 P0 起点： `44677cd7f6a9535c1a74e8628078e9d4967594b5`。
- 实际 P0 起始 commit： `758eeaf7360f09296bc8a87567b021e68ca097d7`。该提交只解除 Evaluation v2 启动暂停并更新文档状态；P0 在检查其 diff 后从该 clean commit 开始。
- P0 结束 commit：`747feb384dbcdbe1b4d3b9e04e9590111970254f`。
- P1 起始 commit：`57eb0d4f15621ebfe01c6e1cda66ab6f145e160d`。
- 原 P1 候选 source commit：`2abc0c30badd619151b99f01abdab82331482824`； user guide 计划更新和 verifier revision 后已失效，未作为批次 source 接受，也未 运行 Artifact。
- P1 已接受 source commit： `dcd8ea110c6c4dad5c09943fab26b8197142ae29`。
- P1 结束 commit：承载本状态条目的 commit；完整 SHA 在提交后的交付消息中报告， 不为回填而 amend。
- P1 实际结束 commit：`91a578d74439bd643b0dcb693a3b55a806b71f34`。
- P2 实际起始 commit：`4a70016101ffab6f777e53f938c472b5fe1e405d`；它相对 P1 结束 commit 只重排 Markdown 和补充对应文档规则，不改变 Evaluation v2 语义。
- P2 实现候选 source：承载本状态条目的 commit；完整 SHA 和 tree 在提交后的交付消息中报告，不为回填而 amend。
- 正式 Artifact： `F:\dev\llm\pico-eval-artifacts\evaluation-v2\module-baseline-v1\dcd8ea110c6c4dad5c09943fab26b8197142ae29`。
- wrapper revision 使用量：`0/1`。`dcd8ea1` 是正式测量前由总体方案和 user guide 交付要求驱动的实现对齐，不是测量 wrapper 缺陷修订。
- 当前 blocker：候选提交后的 WSL fresh-clone 复核、两份 run config 冻结以及用户对其内容和哈希的明确接受尚未完成。
- 下一动作：提交 P2 实现候选，在其 detached WSL fresh clone 中使用 providers extra 复跑定向测试和 scoped Ruff；全部通过后，以该提交为 source 创建并只读验证两份 run config，展示全文、哈希、source/tree 和 scoped diff，随后停止等待用户接受。

## 历史无效测量

R-01、R-02、R-03 都是 W6R5 的历史无效测量尝试，不是 Evaluation v2 评测行，也不 进入任何产品成功率、稳定性、耗时或工具使用指标。

R-03 的主要结论是测量装置缺陷：HSMOKE-V4-A 实际完成了 `read_file -> patch_file -> read_file`，但旧检查要求整句英文逐字包含，因而把语义 等价的结果误判为失败。这一记录不能作为 Pico 产品效果结论，也不得通过重新解释而 并入 Evaluation v2 基线。

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

- 起点保护检查确认工作区 clean、历史 checkpoint 是 HEAD 的祖先；计划 HEAD 已前移， 因而先停止执行并检查 `44677cd..758eeaf` 的完整 diff。
- 漂移检查确认 `758eeaf` 只解除启动暂停和更新文档状态，随后将其记录为实际起点。
- 三个退役路径的存在性检查通过，活动源码、脚本和测试中的残留引用搜索为 0。
- plan、evidence protocol、status、metrics 和 report 共 5 份文档的相对链接检查 通过，taskset 与 `taskset.lock.json` 目标存在。
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
- 历史无效测量：R-01、R-02、R-03，共 3 次；全部排除在 Evaluation v2 产品指标 之外。

### 当前 blocker

无。P1 仍是纯离线阶段，不需要 provider HTTP 授权。

### 下一阶段的精确第一步

从 P0 结束 commit 启动新的 P1 顶层任务，只实现并运行 `scripts/run_evaluation_v2_modules.py` 所编排的确定性模块基线；输出到 `module-baseline-v1/<source-sha>`，不得发起 provider HTTP。

## P1 阶段记录（已完成）

### 阶段结论

- 已新增薄模块 runner，固定编排 harness、context、memory 和 recovery evaluator。
- 已将报告收敛为结构化 JSON 单一数据源，并由确定性 renderer 生成 Markdown。
- 已将五个事实 JSON、报告合同和 Markdown 的复核逻辑抽为 P5/G2 可组合调用的纯 verifier；`--verify-only` 不再依赖当前 checkout 或 HEAD。
- 已创建当前版本的 `evaluation-v2-user-guide.md`，并核对 CLI `--help`、测试和 文档中的参数、前置条件、调用范围、产物入口与结果边界。
- 用户接受完整 source `dcd8ea110c6c4dad5c09943fab26b8197142ae29` 后，已在 WSL2、CPython 3.12.13 fresh clone 中生成正式 `module-baseline-v1` Artifact。
- 独立 `--verify-only` 已验证固定五个事实 JSON 的精确清单、字节数和 SHA-256， 并由报告 JSON 逐字节重建 Markdown。Artifact 边界记录 provider HTTP 请求数为 0，且明确不是端到端编码结果。

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
- wrapper revision 使用量为 `0/1`。`dcd8ea1` 同时承载了已批准总体方案新增的 living user guide 要求和测量前 verifier 边界调整；它发生在 source 接受和首次正式测量 之前，不计为测量 wrapper 缺陷修订。

### 执行过的命令与测试

- WSL2 使用 CPython 3.12.13；`uv run --frozen --python 3.12 ruff check` 对上述 revision Python 文件执行 scoped lint，结果通过。
- 第一次 targeted pytest 运行得到 `7 passed, 3 failed`；失败只涉及 canonical JSON 排序后公式字段顺序变化，导致 Markdown 字节重建不一致。
- 固定 renderer 的公式排序后，重新运行 `tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`，初始实现结果为 `11 passed`。
- 本次 revision 首次测试为 `17 passed, 1 failed`；唯一失败是 user guide 将 `provider HTTP` 跨行拆分，导致精确文档边界检查未匹配。修正文档后重新运行为 `18 passed`。六条 `datetime.utcnow()` deprecation warning 来自既有时间戳实现， 不影响本阶段结果。
- 实际 CLI `--help` 只包含 `--output-root` 和 `--verify-only`，与 user guide 和 targeted tests 一致。
- source 接受后，在 `/home/papewhit/pico-eval-clones/p1-dcd8ea110c6c4dad` 建立 detached fresh clone，确认 HEAD 为已接受 source、tree 为上述 tree、checkout clean、Python 为 3.12.13。
- fresh clone 中显式运行 `uv sync --frozen --python 3.12`；随后运行 `uv run --frozen --python 3.12 pytest tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`，结果为 `18 passed`，并出现上述 6 条既有 deprecation warning。
- fresh clone 中对 `pico/evaluation/module_baseline.py`、 `scripts/run_evaluation_v2_modules.py`、两个对应测试文件和 `pico/evaluation/metrics.py` 执行 scoped Ruff，结果通过；再次执行实际 CLI `--help`，仍只包含 user guide 已记录的两个参数。
- 正式运行命令为 `uv run --frozen --python 3.12 python scripts/run_evaluation_v2_modules.py --output-root /mnt/f/dev/llm/pico-eval-artifacts/evaluation-v2/module-baseline-v1/dcd8ea110c6c4dad5c09943fab26b8197142ae29`， 运行前再次确认 checkout clean、HEAD 正确且目标目录不存在。
- 独立复核命令为同一命令追加 `--verify-only`；结果为 source 和 cohort 一致、 `verified_json_files=5`、`markdown_rebuilt=true`。
- 正式 Artifact 包含 4 个模块 JSON、`public/modules/checksums.json`、报告 JSON 和 报告 Markdown。manifest 精确覆盖 5 个事实 JSON，没有额外项；所有哈希为 64 位 SHA-256，所有字节数重算一致。
- 首次选择的 `/tmp` fresh clone 在后续 WSL 调用前被环境清理；随后对 `/mnt/f` fresh clone 的创建命令在宿主等待 120 秒后超时。两次都没有启动 evaluator 或 创建 Artifact；最终使用上述 WSL 用户目录 fresh clone 完成正式运行。
- 完成实际运行后再次核对 user guide；CLI、前置条件、调用范围、Artifact 结构和 结果解释均未变化，因此本次结束提交中 user guide 无变化。
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
- 其他三个 ablation evaluator 输出指标而不作开放语义 passed/failed 分类，因此 verifier 不把它们自动转成产品失败。特别是 recovery 中 3 个 `schema_mismatch_missing` 重复按 fixture 得到 `no-checkpoint`，使 `resume_enabled` 的聚合 resume success rate 为 90%；其 false accept 均为 0。 本记录保留该事实，不替用户作额外语义判分。

### invalid rows

0。P1 不创建 Evaluation v2 编码评测行；所有正式模块 Artifact 均完整并通过独立 复核。前述两次环境准备中断发生在 evaluator 启动前，不是测量行，也不产生 `invalid`。

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
