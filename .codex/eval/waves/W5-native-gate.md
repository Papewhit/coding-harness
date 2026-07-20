# W5 — Runtime Wiring、文本协议删除与 Deterministic Gate

按依赖推进：`TOOL-040-I → TOOL-041-M`；之后 `TOOL-049-I` 与 `EVAL-031-G` 可并行，最后 `TOOL-042-G`。

Exit Gate：Runtime/online evaluator 无 `<tool>/<final>` 可执行路径；call ID/result、batch、error result、安全链和 structured context tests 通过。此 Gate 仍不是 live provider selection。
