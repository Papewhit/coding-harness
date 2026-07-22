# W5R2 — Architecture Tripwire 与 Provider Profile Gate Recovery

W5R2 从 W5R blocked handoff 恢复，不重写 W5/W5R 历史，也不晋级 W5R 中尚未通过 Gate 的 proposals。第一批并行执行 `ARCH-046-T` 与 `TEST-046-P`；前者统一校准全部 Core 模块增长警戒线并让门禁一次报告所有超限项，后者完成普通 scripted-native tests 的显式 provider profile 迁移。

`ARCH-046-T` 以 W5R canonical 行数为审计基准。除用户指定 `runtime.py=1000` 外，现有余量不足的警戒线按约 20% headroom、向上取整的原则统一调整；已有更宽门限不降低。该测试是异常增长 tripwire，不是严格的模块规模预算，但超过门限仍须显式审查，不能静默放行。

`TOOL-046-W` 与 `TEST-046-T` 等待 `TEST-046-P`。worker ticket 必须区分 fixture/profile 前置失败与真实产品回归，并保证 child session 使用与自身最终 tool schema 匹配的 profile。TUI ticket 只恢复显式 fixture，不得修改生产 TUI 或放大 timeout。

最后由 `TOOL-042-G-R2` 从 Ubuntu WSL2 用户 `papewhit` 的 `~/dev/` fresh clone 运行完整 Gate。固定 Python 3.12、committed `uv.lock` 与用户级 `uv`；禁止 `sudo`、live provider 和正式效果评测。只有 required commands 全部 exit 0，才允许 Wave Integrator 晋级 Context/Gate proposals、创建 W5R2 canonical，并开放 W6 ready set。
