# W1 — Native 与 Evaluation 并行基础

并发上限 6。优先启动 `TOOL-010`、`TOOL-011`、`TOOL-012-I`、`EVAL-020`、三个 mini repo 中的两个；空出 slot 后启动 SDK dialect plugins、Dream fixtures、Context contract、live runner。

依赖内启动允许：`TOOL-012-O/A` 等待通用 harness；`EVAL-021-A/B` 等待 Dream core；`EVAL-030` 等待 native contract/schema；`EVAL-041` 等待 native contract。

Exit Gate：接口候选和 probe harness 可用；所有 lane 无共享文件冲突。不得运行正式在线效果评测。
