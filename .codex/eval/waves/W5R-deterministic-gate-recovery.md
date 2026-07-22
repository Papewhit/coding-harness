# W5R — Blocked W5 Remediation 与 Deterministic Gate Recovery

W5 的 blocked canonical snapshot、tag、handoff、失败 artifact 与无效 Context hash 声明必须原样保留。W5R 从 W5 metadata HEAD 创建新的 control overlay 和 immutable `wave_base_sha`，不得重写 W5 历史。

第一批可并行分发 `TOOL-043-R`、`TOOL-044-F`、`ARCH-045-B` 与 `CHORE-045-L`，写路径必须完全分离。Integrator 在接纳 retry 修复前，先验证 fixture-only snapshot 仍能捕获 W5 blocked snapshot 的 retry-after-read 回归。

上述修复全部验收后分发 `EVAL-032-F`，以 canonical Git blob bytes 发布 versioned Context binding 并重新生成 artifact。最后分发 `TOOL-042-G-R1`，从 Ubuntu WSL2 用户 `papewhit` 的 `~/dev/` fresh clone 运行完整 Gate。

WSL Gate 固定 Python 3.12、committed `uv.lock` 和用户级 `uv`。禁止使用 `sudo`；如必须安装系统级依赖，立即停止并请求用户处理。所有规定命令必须真实 exit 0，不得 skip、xfail、重分类或通过 monkey patch 改变 protected tests 的依赖边界。

Exit Gate：protected tests 使用显式 native fixtures；retry-after-read 与真正重复 mutation 语义正确；repository Ruff、架构、安全、权限和策略 Gate 全通过；Context binding 可从 fresh clone 的 Git blob 重建；新的 run snapshot 与 evidence hash 冻结。通过后才允许 W6 ready。
