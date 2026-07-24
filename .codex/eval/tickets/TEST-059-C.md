# TEST-059-C — Responses Stateless Transcript Red Tests

**Thread type:** `implementer`
**Wave:** `W6R3`

## Start conditions

- `EVAL-059-O`

## Goal

只提交测试，稳定复现 OpenAI Responses 在 `store=false`、无 `previous_response_id` 时丢失原始 Runtime prompt 和累计 transcript 的缺陷。先证明测试在未修复 source 上按预期失败，再交给 `TOOL-059-O`。

## Allowed write paths

- `tests/test_openai_responses_tools.py`
- `tests/test_native_runtime_integration.py`
- `tests/test_native_stateless_transcript.py`
- `.codex/eval/handoffs/TEST-059-C.json`

## Forbidden write paths

- `pico/**`
- frozen cases/evaluator/metrics
- 正式 `STATUS.json`、`FREEZE.json`

## Acceptance checklist

- [ ] 第二轮 wire input 同时包含原始 prompt、原 tool call 与匹配 result
- [ ] 三轮 `read_file → patch_file → read_file` 保持任务目标
- [ ] 多轮累计全部必要 transcript，不只保留最近一轮
- [ ] 每个 function output 恰好出现一次并保留原 call ID
- [ ] 测试不依赖 live provider、provider cache 或 server-side storage
- [ ] 记录未修复 snapshot 的精确 expected failures

## Stop rule

提交 red tests 与 handoff 后停止；测试失败是本 ticket 的预期 baseline，不得顺手修改产品代码。

## Review-return revision

`AUDIT-059-A-P1-002` 退回本 ticket 的原 worker thread。Revision 2 在现有 allowed paths 内补充：

- 两个 unresolved calls 只有一个 result 时，必须在 transport 前拒绝；
- extra、unknown 或 duplicate result ID 必须在 transport 前拒绝；
- 重排的合法 results 应按原 call order 规范化，不机械误拒绝；
- 历史已闭合 calls 不得误算为当前 batch。

先在 W6R3 remediation candidate 上记录精确 red baseline，再更新同一路径 handoff。Handoff 必须包含 `revision=2`、`supersedes_handoff_sha256`、finding ID、candidate SHA、新 commits 与 tests；不得创建新的 ticket handoff。
