# Thread Handoff

```json
{
  "ticket_id": "<id>",
  "status": "complete|blocked|failed",
  "base_sha": "<sha>",
  "head_sha": "<sha>",
  "dependency_commits": [],
  "own_commits": ["<sha>"],
  "files_changed": [],
  "commands_run": [],
  "tests": [{"command": "...", "result": "passed|failed", "details": "..."}],
  "outputs": [],
  "frozen_hashes": {
    "native_contract": null,
    "tool_schema": null,
    "sdk_transport_decision": null,
    "provider_selection": null,
    "native_resume_gate": null
  },
  "native_protocol_observations": {
    "text_envelope_seen_count": 0,
    "implicit_sdk_retry_seen": false,
    "call_id_result_mismatch_count": 0,
    "unknown_block_loss_count": 0,
    "safety_chain_bypass_count": 0
  },
  "defects": [],
  "risks": [],
  "status_proposal": null,
  "freeze_proposal": null,
  "ownership_change_request": null,
  "ready_for_integration": true
}
```

聊天总结不能代替 handoff。失败同样必须记录 base/head、已产生文件、失败命令、原始证据位置和下一步最小修复建议。不得把 opaque reasoning/thinking 内容写入 handoff。
