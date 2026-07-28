# Pico Evaluation v2 基线报告

## 文档状态

这是 Evaluation v2 的正式基线报告。机器可读单一数据源是外部 canonical Artifact 中的 `reports/evaluation-report.json`；外部 Markdown 与本文仓库镜像均由该 JSON 确定性生成。

仓库镜像中的 Artifact 相对链接以外部 canonical 报告所在目录为基准。

## Suite 与批次

- 正式 coding cohort：`baseline-v1`
- Coding source：`542f97a023218ee04c00225de994f152bfed748e`
- Module cohort：`module-baseline-v1`
- Module source：`dcd8ea110c6c4dad5c09943fab26b8197142ae29`
- 模型：`qwen3.6-plus`
- Provider profile：`dashscope-o` / `sha256:41ebb321c6332867f0bb020621b7e1c17f8c60430374c37c3a670c916326ee70`

P1 模块结果与 `baseline-v1` 真实编码结果分开报告，不共享分母。

## 正式编码结果

- Final classified：27/27
- Valid passed / failed / invalid：26 / 1 / 0
- Valid-run rate：27/27 (100.00%)
- Verified-run success：26/27 (96.30%)
- Provider requests：284
- Tool steps：mean=11.78, median=10.00 (27/27 samples)
- Repeated reads：mean=0.78, median=1.00, total=21 (27/27 samples)
- Runtime elapsed：mean=58250.48 ms, median=54892.00 ms (27/27 samples)

### 27 条正式编码评测行

| Row | Repo | Task | 分类 | 一句话结果 | 原因与证据 |
| --- | --- | --- | --- | --- | --- |
| `baseline-v1-T01-r1` | `tinyconfig` | T01 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T01-r1/run-record.json), [view](../public/rows/baseline-v1-T01-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T01-r1/codex-audit.json)) |
| `baseline-v1-T02-r1` | `tinyconfig` | T02 | valid + failed | 隐藏检查失败，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, and both credential scans passed. The Runtime completed normally, but the deterministic verifier found that a malformed database section did not raise ConfigError, so this is a model implementation failure. ([record](../public/rows/baseline-v1-T02-r1/run-record.json), [view](../public/rows/baseline-v1-T02-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T02-r1/codex-audit.json)) |
| `baseline-v1-T03-r1` | `tinyconfig` | T03 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T03-r1/run-record.json), [view](../public/rows/baseline-v1-T03-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T03-r1/codex-audit.json)) |
| `baseline-v1-T04-r1` | `miniqueue` | T04 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T04-r1/run-record.json), [view](../public/rows/baseline-v1-T04-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T04-r1/codex-audit.json)) |
| `baseline-v1-T05-r1` | `miniqueue` | T05 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T05-r1/run-record.json), [view](../public/rows/baseline-v1-T05-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T05-r1/codex-audit.json)) |
| `baseline-v1-T06-r1` | `miniqueue` | T06 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T06-r1/run-record.json), [view](../public/rows/baseline-v1-T06-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T06-r1/codex-audit.json)) |
| `baseline-v1-T07-r1` | `logslice` | T07 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T07-r1/run-record.json), [view](../public/rows/baseline-v1-T07-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T07-r1/codex-audit.json)) |
| `baseline-v1-T08-r1` | `logslice` | T08 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T08-r1/run-record.json), [view](../public/rows/baseline-v1-T08-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T08-r1/codex-audit.json)) |
| `baseline-v1-T09-r1` | `logslice` | T09 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T09-r1/run-record.json), [view](../public/rows/baseline-v1-T09-r1/evidence-view.json), [audit](../public/rows/baseline-v1-T09-r1/codex-audit.json)) |
| `baseline-v1-T01-r2` | `tinyconfig` | T01 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T01-r2/run-record.json), [view](../public/rows/baseline-v1-T01-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T01-r2/codex-audit.json)) |
| `baseline-v1-T02-r2` | `tinyconfig` | T02 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T02-r2/run-record.json), [view](../public/rows/baseline-v1-T02-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T02-r2/codex-audit.json)) |
| `baseline-v1-T03-r2` | `tinyconfig` | T03 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T03-r2/run-record.json), [view](../public/rows/baseline-v1-T03-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T03-r2/codex-audit.json)) |
| `baseline-v1-T04-r2` | `miniqueue` | T04 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T04-r2/run-record.json), [view](../public/rows/baseline-v1-T04-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T04-r2/codex-audit.json)) |
| `baseline-v1-T05-r2` | `miniqueue` | T05 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T05-r2/run-record.json), [view](../public/rows/baseline-v1-T05-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T05-r2/codex-audit.json)) |
| `baseline-v1-T06-r2` | `miniqueue` | T06 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T06-r2/run-record.json), [view](../public/rows/baseline-v1-T06-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T06-r2/codex-audit.json)) |
| `baseline-v1-T07-r2` | `logslice` | T07 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T07-r2/run-record.json), [view](../public/rows/baseline-v1-T07-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T07-r2/codex-audit.json)) |
| `baseline-v1-T08-r2` | `logslice` | T08 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T08-r2/run-record.json), [view](../public/rows/baseline-v1-T08-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T08-r2/codex-audit.json)) |
| `baseline-v1-T09-r2` | `logslice` | T09 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T09-r2/run-record.json), [view](../public/rows/baseline-v1-T09-r2/evidence-view.json), [audit](../public/rows/baseline-v1-T09-r2/codex-audit.json)) |
| `baseline-v1-T01-r3` | `tinyconfig` | T01 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T01-r3/run-record.json), [view](../public/rows/baseline-v1-T01-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T01-r3/codex-audit.json)) |
| `baseline-v1-T02-r3` | `tinyconfig` | T02 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T02-r3/run-record.json), [view](../public/rows/baseline-v1-T02-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T02-r3/codex-audit.json)) |
| `baseline-v1-T03-r3` | `tinyconfig` | T03 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T03-r3/run-record.json), [view](../public/rows/baseline-v1-T03-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T03-r3/codex-audit.json)) |
| `baseline-v1-T04-r3` | `miniqueue` | T04 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T04-r3/run-record.json), [view](../public/rows/baseline-v1-T04-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T04-r3/codex-audit.json)) |
| `baseline-v1-T05-r3` | `miniqueue` | T05 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T05-r3/run-record.json), [view](../public/rows/baseline-v1-T05-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T05-r3/codex-audit.json)) |
| `baseline-v1-T06-r3` | `miniqueue` | T06 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T06-r3/run-record.json), [view](../public/rows/baseline-v1-T06-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T06-r3/codex-audit.json)) |
| `baseline-v1-T07-r3` | `logslice` | T07 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T07-r3/run-record.json), [view](../public/rows/baseline-v1-T07-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T07-r3/codex-audit.json)) |
| `baseline-v1-T08-r3` | `logslice` | T08 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T08-r3/run-record.json), [view](../public/rows/baseline-v1-T08-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T08-r3/codex-audit.json)) |
| `baseline-v1-T09-r3` | `logslice` | T09 | valid + passed | 隐藏检查通过，测量有效。 | Measurement completed without measurement or protocol errors, provider request counting is exact, both credential scans passed, and the deterministic verifier passed. ([record](../public/rows/baseline-v1-T09-r3/run-record.json), [view](../public/rows/baseline-v1-T09-r3/evidence-view.json), [audit](../public/rows/baseline-v1-T09-r3/codex-audit.json)) |

## 按 repo、task 与 failure category 分解

### Repository

| Repo | Passed | Failed | Invalid | Verified success | Requests | Mean tool steps | Repeated reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `logslice` | 9 | 0 | 0 | 9/9 (100.00%) | 106 | 13.33 | 5 |
| `miniqueue` | 9 | 0 | 0 | 9/9 (100.00%) | 101 | 12.33 | 10 |
| `tinyconfig` | 8 | 1 | 0 | 8/9 (88.89%) | 77 | 9.67 | 6 |

### Task

| Task | Repo | Stability | Passed | Failed | Invalid | Requests | Mean tool steps | Repeated reads |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T01 | `tinyconfig` | stable-pass | 3 | 0 | 0 | 24 | 9.00 | 2 |
| T02 | `tinyconfig` | mixed-valid | 2 | 1 | 0 | 32 | 11.67 | 2 |
| T03 | `tinyconfig` | stable-pass | 3 | 0 | 0 | 21 | 8.33 | 2 |
| T04 | `miniqueue` | stable-pass | 3 | 0 | 0 | 27 | 10.33 | 4 |
| T05 | `miniqueue` | stable-pass | 3 | 0 | 0 | 39 | 14.67 | 2 |
| T06 | `miniqueue` | stable-pass | 3 | 0 | 0 | 35 | 12.00 | 4 |
| T07 | `logslice` | stable-pass | 3 | 0 | 0 | 28 | 8.67 | 0 |
| T08 | `logslice` | stable-pass | 3 | 0 | 0 | 33 | 12.33 | 2 |
| T09 | `logslice` | stable-pass | 3 | 0 | 0 | 45 | 19.00 | 3 |

- Failure categories：`{"model_behavior": 1}`

## Measurement quality 与 invalid rows

- Runtime evidence valid：27/27
- Invalid rows：0
- Exact provider request counts：27/27
- Runtime credential scans passed：27/27
- SDK retries / Pico retries：0 / 0
- Protocol-error rows：0

Measurement quality 不进入 verified-run success 分子；invalid 行会单独列出，当前批次没有 invalid 行。

## Context、memory、recovery 与 harness 模块指标

- Harness：12/12 passed，verifier pass rate 100.00%。
- Context：12 configs × 5 repetitions，平均压缩率 10.66%，当前请求保留率 100.00%。
- Working memory：memory_on repeated_reads=0、correct_rate=100.00%；memory_off repeated_reads=60。
- Recovery：resume_enabled success=90.00%、workspace drift detection=100.00%、false accept=0.00%。
- P1 checksum manifest：`public/modules/checksums.json`。

## 三个最重要的已观察改进机会

1. **提高 T02 嵌套配置边界行为的稳定性**
   - 观察：T02 为 mixed-valid，三次运行中 1 次有效失败；失败行遗漏 malformed database section 的 ConfigError。
   - 下一步：后续独立计划应检查模型在提交前是否系统覆盖 malformed nested section，不得回写 baseline-v1。
   - 限制：当前失败分类为 model_behavior，未证明 Pico Runtime 根因。
2. **降低 T09 的请求与工具步骤成本**
   - 观察：T09 三次共 45 次请求，平均 19.00 个工具步骤。
   - 下一步：在独立可比 cohort 中调查规划和验证步骤的长尾。
   - 限制：三条样本只能定位观察点，不能建立成本根因。
3. **减少 miniqueue 任务中的重复读取**
   - 观察：miniqueue 的九条 valid 行累计 10 次重复读取。
   - 下一步：结合 working-memory 模块证据，在独立实验中检查真实 coding 路径的记忆命中与重复读取关系。
   - 限制：现有基线只记录重复读取次数，不证明 working memory 是根因。

## 简历结论—证据映射

| 结论 | Cohort | 样本 | 公式 | 证据 | 限制 |
| --- | --- | --- | --- | --- | --- |
| 在固定的 9-task × 3-repeat 本地编码基线中，26/27 条有效运行通过隐藏检查。 | `baseline-v1` | 27 条正式 coding rows | valid + passed / 全部 valid rows | public/run-config.json; public/rows/<row-id>/codex-audit.json | 一个模型、provider profile 和固定 mini-repo taskset。 |
| 27/27 条正式行最终分类，invalid=0。 | `baseline-v1` | 27 条正式 coding rows | valid rows / final-classified rows；invalid 单列 | public/rows/<row-id>/checksums.json | 实际凭据扫描只检查本次进程已知的精确敏感值。 |
| 确定性 context ablation 的平均 prompt 压缩率为 10.66%，最新请求保留率为 100.00%。 | `module-baseline-v1` | 12 configs × 5 repetitions | mean of 12 config-level average compression ratios | public/modules/context-ablation-v2.json | 模块级确定性证据，不是端到端 provider 结果。 |
| working-memory ablation 中 memory_on 的 repeated_reads=0，correct_rate=100%。 | `module-baseline-v1` | 12 tasks × 5 repetitions for memory_on | sum of repeated reads in the variant | public/modules/memory-ablation-v2.json | scripted 模块任务，不直接推出真实 coding 路径收益。 |
| recovery ablation 中 resume_enabled 的 resume success rate 为 90.00%，workspace drift detection rate 为 100.00%。 | `module-baseline-v1` | 10 tasks × 3 repetitions for resume_enabled | successful resumes / all variant runs | public/modules/recovery-ablation-v2.json | 模块级恢复实验，不代表尚未实现的 Native Resume。 |

## 测试边界观察

### Prompt 规范化与测试边界

Runtime 接收的 user_message 未先统一裁剪；ContextManager 在装配完整 prompt 时对整体执行 strip()，metadata 则保留原始请求。request context 随后要求最终 prompt 精确保留 metadata 中的 current request，因此直接注入带外层空白的 prompt 可能在首次 provider 请求前触发 ValueError。

- 完整 Pico 产品边界：one-shot、REPL、TUI 和正式 Evaluation bridge 都在进入 Runtime 前裁剪输入；以这些标准入口组成的完整 Pico 产品为边界时，baseline-v1 不暴露该路径，不能把它计为正式基线失败。
- 独立 Runtime 边界：如果 Runtime/Pico API 被视为可独立调用的模块，该接口既未统一规范化输入，也未明确要求调用者先规范化，形成内部 prompt 与 metadata 不一致，可视为 Runtime 接口契约缺口。
- 指标影响：无；pilot-v3、pilot-v4 不进入 baseline-v1 分母，不改变正式结果子树、前三项改进机会或简历结论。
- 证据：pilot-v3/e1c5652592588464bc808504188169053445d007/reports/pilot-report.json#sha256=11d39bba88b0332300431292b6a719e5aea4ff8061a9174ee67de57834dce8d2; pilot-v4/6460508c688383102f9dc205d8a04a5681b078dd/reports/pilot-report.json#sha256=f12b90a2bb974de4df4fbf9609dcf0738de0496c45c256f0849e835d44841574; pico/core/context_manager.py#ContextManager._assemble_prompt; pico/core/context_manager.py#ContextManager._metadata; pico/core/request_context.py#build_request_context; pico/cli.py#main; pico/tui/app.py#PicoApp.action_submit_input; scripts/run_pico_live_task_client.py#run_live_task; commit:6460508c688383102f9dc205d8a04a5681b078dd
- 限制：pilot-v3 与 pilot-v4 使用不同 source 和 bridge，不能解释为严格 A/B 效果；两批历史分类保持原样。本观察是条件式接口判断，不是新的正式评测行或 Runtime 修复。

## 限制与待决定事项

- baseline-v1 covers nine fixed Python tasks in three local mini repositories with one model, provider profile, and parameter set.
- P1 context, memory, recovery, and harness results are deterministic module evidence and do not enter the end-to-end coding success denominator.
- Pilot cohorts, W6R5 history, future supplemental cohorts, and post-fix cohorts do not enter baseline-v1 metrics.

本报告不自动授权或启动产品修复、补充批次、Auto-dream 或 Native Resume。
