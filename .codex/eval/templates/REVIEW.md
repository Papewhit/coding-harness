# Review Output（eval-control-v4）

`reviewer` 必须绑定精确 `base_sha`、`candidate_sha`、Artifact 路径/hash 和检查命令。输出 verdict 只有：

- `accepted`：没有 open Finding；
- `findings`：至少一个按下列四类填写的 Finding。

```json
{
  "schema_version": "pico-eval-review-v4",
  "ticket_id": "<REVIEW_TICKET_ID>",
  "base_sha": "<SHA>",
  "candidate_sha": "<SHA>",
  "artifact_bindings": [],
  "verdict": "accepted|findings",
  "findings": [
    {
      "id": "<FINDING_ID>",
      "type": "implementation_defect|measurement_defect|evaluation_failure|change_request",
      "candidate_or_artifact": "<SHA_OR_PATH>",
      "rule_or_basis": "<EXACT_RULE_OR_BASIS>",
      "evidence": "<FILE:LINE, COMMAND LOG, ROW ID, OR HASH>",
      "responsible_ticket": "<TICKET_ID_OR_NULL>",
      "required_action": "<ONE_ACTION>"
    }
  ],
  "checks": [
    {"command": "...", "exit_code": 0, "summary": "...", "log_path": "...", "log_sha256": "..."}
  ]
}
```

分类规则：

- 违反现有 contract/Freeze/Ticket 验收：`implementation_defect`；
- evaluator/runner/evidence/Artifact 绑定关系使结果不可信：`measurement_defect`；
- 测量有效但任务、provider 或产品表现失败：`evaluation_failure`；
- 需要改变 frozen 语义、范围、所有权或既有行为：`change_request`。

`reviewer` 不设置 Wave 状态，不修改实现，不要求“另开 repair Wave”。`evaluation_failure` 的 required action 必须是保留结果并继续，而不是修复到成功。
