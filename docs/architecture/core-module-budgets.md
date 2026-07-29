# Core 模块增长 tripwire

`tests/test_architecture_boundaries.py` 中的行数检查是粗粒度异常增长 tripwire，目的是让评审者
注意模块是否发生了值得复核的显著扩张。它不是严格的模块规模预算，也不表示低于门限的模块
天然内聚，或超过门限的模块必须机械拆分。行数只是一项架构复核信号；职责、依赖方向和安全
边界仍需单独判断。

## W5R2 重校准

ARCH-046-T 以 W5R canonical `0c87dca9c823c98237cb50baf4cf7f2494cb69ef`
中的 Git blob 为审计来源，保留全部 24 个 tracked modules。`runtime.py` 的 tripwire 按用户
决定精确设为 1000；ticket 指定的另外 11 项按 canonical 实际规模重校准，其余 12 项维持
原值，未降低任何门限。产品源码 blob 未因本次重校准而改变。

完整的 `actual / old / new / margin`、canonical blob OID 和 wave-base blob 对照保存在
`F:/dev/llm/pico-eval-artifacts/w5r2-architecture-tripwire/W5R2-ARCH-046-T-01/core-module-tripwire-audit.json`。
其中 `margin = new - actual`，代表触发告警前剩余的粗粒度行数余量。

测试会先检查全部 24 个模块，再用一次断言同时列出所有超限项，避免首个失败遮蔽后续问题。
tripwire 被触发时，应审查增长原因与模块职责；只有在有明确架构依据时才调整门限或拆分模块。
