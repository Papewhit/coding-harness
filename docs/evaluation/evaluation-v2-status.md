# Pico Evaluation v2 状态

## 文档角色

本文记录 Evaluation v2 当前阶段和人类可读进度。规范性阶段、Gate 和授权边界见
[`evaluation-v2-plan.md`](evaluation-v2-plan.md)，证据与结果分类规则见
[`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。
本文不创建新的阶段、Gate 或评测规则。

## 当前状态

- 当前阶段：P1——确定性模块基线。
- 阶段结论：进行中。模块 runner、结构化报告和确定性复核已实现并通过 targeted
  tests；尚未创建或运行正式 `module-baseline-v1` Artifact。
- 历史控制 checkpoint：
  `2876cd53e17fd2b6eb089dbfaf14cd67615498fc`。
- 计划中的 P0 起点：
  `44677cd7f6a9535c1a74e8628078e9d4967594b5`。
- 实际 P0 起始 commit：
  `758eeaf7360f09296bc8a87567b021e68ca097d7`。该提交只解除 Evaluation v2
  启动暂停并更新文档状态；P0 在检查其 diff 后从该 clean commit 开始。
- P0 结束 commit：`747feb384dbcdbe1b4d3b9e04e9590111970254f`。
- P1 起始 commit：`57eb0d4f15621ebfe01c6e1cda66ab6f145e160d`。
- P1 待确认 source commit：承载本状态条目的实现提交；完整 SHA 在提交后的交付消息
  中展示，用户接受前不得运行模块基线。
- 当前 blocker：无技术 blocker；当前停点是 source SHA 用户确认。
- 下一动作：用户接受 P1 source SHA 后，在 WSL2/Python 3.12 fresh clone 中运行
  固定模块命令并执行 `--verify-only`。

## 历史无效测量

R-01、R-02、R-03 都是 W6R5 的历史无效测量尝试，不是 Evaluation v2 评测行，也不
进入任何产品成功率、稳定性、耗时或工具使用指标。

R-03 的主要结论是测量装置缺陷：HSMOKE-V4-A 实际完成了
`read_file -> patch_file -> read_file`，但旧检查要求整句英文逐字包含，因而把语义
等价的结果误判为失败。这一记录不能作为 Pico 产品效果结论，也不得通过重新解释而
并入 Evaluation v2 基线。

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

- 起点保护检查确认工作区 clean、历史 checkpoint 是 HEAD 的祖先；计划 HEAD 已前移，
  因而先停止执行并检查 `44677cd..758eeaf` 的完整 diff。
- 漂移检查确认 `758eeaf` 只解除启动暂停和更新文档状态，随后将其记录为实际起点。
- 三个退役路径的存在性检查通过，活动源码、脚本和测试中的残留引用搜索为 0。
- plan、evidence protocol、status、metrics 和 report 共 5 份文档的相对链接检查
  通过，taskset 与 `taskset.lock.json` 目标存在。
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
- 历史无效测量：R-01、R-02、R-03，共 3 次；全部排除在 Evaluation v2 产品指标
  之外。

### 当前 blocker

无。P1 仍是纯离线阶段，不需要 provider HTTP 授权。

### 下一阶段的精确第一步

从 P0 结束 commit 启动新的 P1 顶层任务，只实现并运行
`scripts/run_evaluation_v2_modules.py` 所编排的确定性模块基线；输出到
`module-baseline-v1/<source-sha>`，不得发起 provider HTTP。

## P1 阶段记录（进行中）

### 阶段结论

- 已新增薄模块 runner，固定编排 harness、context、memory 和 recovery evaluator。
- 已将报告收敛为结构化 JSON 单一数据源，并由确定性 renderer 生成 Markdown。
- 已实现五个事实 JSON 的 SHA-256/字节数清单、不可覆盖目录检查和 `--verify-only`。
- 尚未运行正式模块基线，没有创建外部 Artifact，也没有发起 provider HTTP。

### 起始与结束 commit

- 起始：`57eb0d4f15621ebfe01c6e1cda66ab6f145e160d`。
- 待确认 source：承载本状态条目的 P1 实现提交；完整 SHA 见提交后交付消息。
- 结束：P1 尚未完成。

### 实际修改文件和 diff stat

- `M docs/evaluation/evaluation-v2-status.md`
- `M pico/evaluation/metrics.py`
- `A scripts/run_evaluation_v2_modules.py`
- `A tests/test_evaluation_v2_modules.py`
- `M tests/test_metrics.py`
- 精确 diff stat 在实现提交前复核并在 P1 完成记录中更新。

### 执行过的命令与测试

- WSL2 使用 CPython 3.12.13；`uv run --frozen --python 3.12 ruff check` 对上述
  Python 文件执行 scoped lint，结果通过。
- 第一次 targeted pytest 运行得到 `7 passed, 3 failed`；失败只涉及 canonical
  JSON 排序后公式字段顺序变化，导致 Markdown 字节重建不一致。
- 固定 renderer 的公式排序后，重新运行
  `tests/test_metrics.py tests/test_evaluation_v2_modules.py -q`，结果为
  `11 passed`。六条 `datetime.utcnow()` deprecation warning 来自既有时间戳实现，
  不影响本阶段结果。
- 测试只使用 scripted/fake evaluator；未读取 provider locator，未发起 provider
  HTTP。

### 新增 rows 与 metrics

- 新增 Evaluation v2 rows：0。
- 新增正式实测 metrics：0。
- 当前只有实现测试数据，不属于 `module-baseline-v1` 结果。

### 有效产品失败

0。正式模块基线尚未运行。

### invalid rows

0。P1 模块阶段不创建 Evaluation v2 编码评测行，正式模块基线也尚未运行。

### 当前 blocker

无技术 blocker。按照 Artifact 冻结规则，必须先提交实现并由用户接受完整 source
SHA，之后才能在对应的全新目录中运行模块基线。

### 下一阶段的精确第一步

提交 P1 实现并展示完整 source SHA、精确 Artifact 路径与离线命令；用户接受后，
从该 SHA 建立 WSL2/Python 3.12 fresh clone，运行模块基线和 `--verify-only`。
