# Ticket Handoff（eval-control-v4）

每个 Ticket 只有一个 handoff 路径。一个 `run_shard` Ticket 的多个 Processes 合并为一份 handoff；`remediate` 更新同一路径并递增 `revision`。`not_applicable` Ticket 不生成 handoff。

```json
{
  "schema_version": "pico-eval-ticket-handoff-v4",
  "control_revision": "eval-control-v4",
  "ticket_id": "<TICKET_ID>",
  "execution_mode": "model_thread|local_process|current_integrator",
  "process_ids": [],
  "state_proposal": "accepted|needs_remediation|blocked",
  "revision": 1,
  "supersedes_handoff_sha256": null,
  "finding_ids": [],
  "base_sha": "<SHA>",
  "head_sha": "<SHA_OR_SAME_AS_BASE_FOR_NO_GIT_TRACKED_CHANGE>",
  "candidate_sha": "<EXACT_SHA_REVIEWED_OR_RUN>",
  "dependency_commits": [],
  "own_commits": [],
  "files_changed": [],
  "tests": [
    {
      "command": "...",
      "exit_code": 0,
      "summary": "<passed/failed/skipped counts>",
      "log_path": "<PATH>",
      "log_sha256": "<SHA256>"
    }
  ],
  "processes": [
    {
      "process_id": "<PROCESS_ID>",
      "command": "...",
      "exit_code": 0,
      "artifact_root": "<PATH>",
      "manifest_sha256": "<SHA256>",
      "row_count": 0,
      "http_attempt_count": 0,
      "failure_classification": "evaluation_failure|measurement_defect|null"
    }
  ],
  "outputs": [
    {"path": "<PATH>", "sha256": "<SHA256>"}
  ],
  "frozen_hashes": {},
  "native_protocol_observations": {
    "text_envelope_seen_count": 0,
    "implicit_sdk_retry_seen": false,
    "call_id_result_mismatch_count": 0,
    "unknown_block_loss_count": 0,
    "safety_chain_bypass_count": 0
  },
  "findings": [
    {
      "id": "<FINDING_ID>",
      "type": "implementation_defect|measurement_defect|evaluation_failure|change_request",
      "candidate_or_artifact": "<SHA_OR_PATH>",
      "rule_or_basis": "<EXACT_RULE_OR_BASIS>",
      "evidence": "<PATH_OR_CONCISE_FACT>",
      "responsible_ticket": "<TICKET_ID_OR_NULL>",
      "required_action": "<ONE_ACTION>"
    }
  ],
  "freeze_proposal": null,
  "human_review": {
    "base_sha": "<SHA>",
    "candidate_sha": "<SHA>",
    "changed_files": [],
    "summary": "<SHORT_SEMANTIC_SUMMARY>"
  },
  "next_action": "<ONE_EXACT_ACTION>"
}
```

不适用的数组保持为空，不得填入 opaque reasoning/thinking。失败或 `blocked` 同样必须记录精确 base/head、已产生输出、失败命令、原始证据路径和唯一下一动作。
