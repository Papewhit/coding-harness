# Pico Evaluation v2 状态

## 文档角色

本文记录 Evaluation v2 当前阶段和人类可读进度。规范性阶段、Gate 和授权边界见
[`evaluation-v2-plan.md`](evaluation-v2-plan.md)，证据与结果分类规则见
[`evaluation-v2-evidence-protocol.md`](evaluation-v2-evidence-protocol.md)。
本文不创建新的阶段、Gate 或评测规则。

## 当前状态

- 当前阶段：P0——停止旧控制面并恢复可见性。
- 阶段结论：已完成。W6R5 专用活动入口已退役，Evaluation v2 文档入口已建立。
- 历史控制 checkpoint：
  `2876cd53e17fd2b6eb089dbfaf14cd67615498fc`。
- 计划中的 P0 起点：
  `44677cd7f6a9535c1a74e8628078e9d4967594b5`。
- 实际 P0 起始 commit：
  `758eeaf7360f09296bc8a87567b021e68ca097d7`。该提交只解除 Evaluation v2
  启动暂停并更新文档状态；P0 在检查其 diff 后从该 clean commit 开始。
- P0 结束 commit：承载本状态条目的提交。完整 SHA 在 P0 提交后的交付消息中记录，
  并由 P1 第一次更新状态页时回填为字面 SHA。
- 当前 blocker：无。
- 下一阶段：P1——确定性模块基线。

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
- 结束：承载本状态条目的 P0 commit；完整 SHA 见提交后交付记录。

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
