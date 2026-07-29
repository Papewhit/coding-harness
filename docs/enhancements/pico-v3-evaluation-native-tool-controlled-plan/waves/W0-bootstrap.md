# W0 — Bootstrap、Native 基线与 Artifact Contract

串行执行 `EVAL-000 → EVAL-001`。记录 base/branch、dirty paths、`runtime_checkpoints.py` diff hash、architecture baseline、文本协议引用清单和现有 provider/client 合同。创建 bootstrap snapshot 后再实现统一 artifact contract。

Exit Gate：`bootstrap_sha`、native baseline、artifact contract hash 已写入状态；未覆盖既有 checkpoint 修改；全新只读 controller 能仅依据持久化状态准确重建 W1 ready set。
