# W6R3 — Oracle v2 与 Responses 多轮上下文恢复

W6R3 从 W6R2 handoff 与两次 human smoke 的新事实恢复。W6R2 Gate N1 selection 保留为历史 evidence，但 `dashscope-o` human smoke 已证明 OpenAI Responses 在 `store=false` 且无 server-side continuation 时丢失原始 prompt 与累计 transcript；W7 因此保持 blocked。补充 `dashscope-a` smoke 的 `read_file → patch_file → read_file` 语义通过，原 verifier 因遗漏 Markdown 反引号产生 false negative。

分发前的 Wave open control overlay 必须引用 `CONTROL.md` 的 canonical-history 规则，并绑定 `.codex/eval/state/W6R3-commit-map.json`、`<ARTIFACT_ROOT>/wave-bundles/W6R3-workers.bundle` 与 annotated tag `eval-v3/w6r3-canonical`。不得复制一份容易漂移的规则正文。

本 Wave 先执行 `EVAL-059-O`，版本化并冻结 Oracle v2。Oracle 将安全链定义为 Runtime snapshot 级不变量，将 Runtime 前拒绝排除出执行分母，并遵循 Runtime 对 `execute=completed` 与结构化工具结果的既有语义。W6R2 cases、rows、selection、human-smoke 原始产物与 hashes 不得覆盖。

随后 `TEST-059-C` 先提交可稳定复现 Responses 上下文丢失的 red tests；`TOOL-059-O` 只能在这些测试与 Oracle v2 上修复客户端管理的完整无状态 transcript。`EVAL-059-H` 建立单一 scenario manifest 驱动的 human-smoke v2 runner/verifier，`TOOL-059-R` 独立修复路径别名绕过 repetition fingerprint。完成后由 `AUDIT-059-A` 只读复审责任边界、双 dialect 对称性、call/result 唯一性和证据闭环。

`TOOL-059-G` 只在 Ubuntu WSL2/Python 3.12 fresh clone 运行 deterministic、protected、full suite、Ruff 与 PLAN 校验；不得发 provider HTTP。Gate 通过后冻结新的 immutable recovery snapshot，验证 commit map、worker bundle 与 canonical tag，提出 W6R4 ready set 并停止。不得重新选择 profile、执行新的 human smoke 或启动 W7。

## Remediation cycle 1

`AUDIT-059-A` 的三个 finding 以及 plan-level 复审补充的 human-smoke harness 问题，都可由既有 native call/result、双 dialect 对称性和 semantic smoke 约定唯一决定，不构成真正 blocked。W6R3 按新的同 Wave remediation 规则继续：

1. `TEST-059-A-R1` 冻结 Anthropic 三轮 stateless transcript red baseline；`TOOL-059-A-R1` 在其后修复完整累计 transcript。
2. `TEST-059-O-R1` 冻结 Responses 未闭合 call/result batch red baseline；`TOOL-059-O-R1` 在 transport 前强制精确一一对应。
3. `EVAL-059-H-R1` 发布 human-smoke v3，不修改已冻结 v2；修复 live call ID 绑定、semantic tool ordering、场景 B 命令缺失、programmatic live fail-closed 与 artifact provenance。
4. `AUDIT-059-A-R1` 只读复审所有 remediation。只有它通过后，现有 `TOOL-059-G` 才可执行。

前三个 red-test/fixture tickets 可从同一 immutable remediation candidate 并行启动；两个产品修复分别等待自己的 red baseline。不得发 live HTTP、执行 human smoke、重新 selection 或启动 W6R4/W7。

旧流程已经生成的 `W6R3-wave-handoff.json`、`W6R3-workers.bundle` 与 `eval-v3/w6r3-canonical` 保持不变，作为采用 remediation 规则前的历史 blocked attempt。恢复时不得移动或覆盖这些对象。W6R3 最终通过或真正 blocked 后，使用 `W6R3-wave-handoff-r1.json`、`W6R3-r1-commit-map.json`、`W6R3-r1-workers.bundle` 与 `eval-v3/w6r3-canonical-r1` 记录最终结果；修复过程不生成其他 Wave 级 handoff、bundle 或 tag。
