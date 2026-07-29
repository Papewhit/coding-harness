# W3 — SDK 依赖锁、Native Adapters 与 Profile Model

`TOOL-019-D` 是 pyproject/uv.lock 唯一 owner，先按决策建立 optional/lazy SDK 依赖与 transport wrapper。随后 OpenAI Responses、Anthropic Messages adapters 并行实现；Provider profile/capability 线程独立处理配置与 CLI validation。

Exit Gate：两个 adapter contract tests 通过；Core 未 import SDK；无 Tool/Agent Runner。
