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
