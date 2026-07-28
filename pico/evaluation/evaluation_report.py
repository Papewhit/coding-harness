"""Build and verify the final Evaluation v2 baseline report."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from pico.evaluation.baseline_summary import (
    build_baseline_summary,
    summarize_coding_rows,
    verified_baseline_config,
)
from pico.evaluation.coding_report import cohort_root, verify_coding_rows
from pico.evaluation.evaluation_v2_config import canonical_json
from pico.evaluation.evaluation_v2_evidence import (
    sha256_file,
    verify_checksums,
)
from pico.evaluation.module_baseline import (
    CHECKSUMS_PATH as MODULE_CHECKSUMS,
    REPORT_JSON_PATH as MODULE_REPORT_JSON,
    verify_module_baseline,
)
from pico.evaluation.pilot_audit import load_object
from pico.evaluation.pilot_report import (
    REPORT_JSON as PILOT_REPORT_JSON,
    verify_pilot,
)


REPORT_SCHEMA = "pico-evaluation-v2-report-v1"
REPORT_JSON = Path("reports/evaluation-report.json")
REPORT_MARKDOWN = Path("reports/evaluation-report.md")
PILOT_SOURCES = {
    "pilot-v3": "e1c5652592588464bc808504188169053445d007",
    "pilot-v4": "6460508c688383102f9dc205d8a04a5681b078dd",
}


def build_evaluation_report(
    run_config_path: Path,
    module_root: Path,
) -> dict[str, Any]:
    """Build the report from immutable coding, module, and Pilot evidence."""

    config = verified_baseline_config(run_config_path)
    root = cohort_root(run_config_path)
    verify_coding_rows(root, config)
    _verify_row_evidence(root, config)
    module_root = module_root.resolve()
    verify_module_baseline(module_root)

    formal_results = _formal_results(run_config_path, module_root)
    formal_hash = _digest_object(formal_results)
    boundary_observations = _boundary_observations(root)
    if _digest_object(formal_results) != formal_hash:
        raise ValueError("boundary observations changed the formal result subtree")

    return {
        "schema_version": REPORT_SCHEMA,
        "artifact_type": "pico-evaluation-v2-baseline-report",
        "formal_results_sha256": formal_hash,
        "formal_results": formal_results,
        "improvement_opportunities": _improvement_opportunities(formal_results),
        "resume_claims": _resume_claims(formal_results),
        "boundary_observations": boundary_observations,
        "limitations": [
            "baseline-v1 covers nine fixed Python tasks in three local mini repositories "
            "with one model, provider profile, and parameter set.",
            "P1 context, memory, recovery, and harness results are deterministic module "
            "evidence and do not enter the end-to-end coding success denominator.",
            "Pilot cohorts, W6R5 history, future supplemental cohorts, and post-fix "
            "cohorts do not enter baseline-v1 metrics.",
        ],
    }


def verify_evaluation_report(
    run_config_path: Path,
    module_root: Path,
    published_report: Path,
) -> dict[str, Any]:
    """Read and deterministically verify a completed P5 report."""

    root = cohort_root(run_config_path)
    report_path = root / REPORT_JSON
    markdown_path = root / REPORT_MARKDOWN
    actual = load_object(report_path)
    expected = build_evaluation_report(run_config_path, module_root)
    if report_path.read_bytes() != canonical_json(actual):
        raise ValueError("evaluation report JSON is not canonical")
    if canonical_json(actual) != canonical_json(expected):
        raise ValueError("evaluation report JSON cannot be rebuilt from evidence")
    expected_markdown = render_evaluation_report(actual)
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise ValueError("evaluation report Markdown cannot be rebuilt from JSON")
    if published_report.read_bytes() != markdown_path.read_bytes():
        raise ValueError("published repository report differs from the Artifact report")
    counts = actual["formal_results"]["coding"]["counts"]
    return {
        "g2_deterministic": "passed",
        "cohort_id": "baseline-v1",
        "formal_results_sha256": actual["formal_results_sha256"],
        "rows": {
            "planned": counts["planned"],
            "final_classified": counts["final_classified"],
            "valid_passed": counts["valid_passed"],
            "valid_failed": counts["valid_failed"],
            "invalid": counts["invalid"],
        },
        "markdown_rebuilt": True,
        "published_report_matches": True,
        "boundary_observations": len(actual["boundary_observations"]),
    }


def write_evaluation_report(
    run_config_path: Path,
    module_root: Path,
    published_report: Path,
    *,
    sensitive_values: Sequence[str],
) -> dict[str, Any]:
    """Scan exact candidate bytes, publish them, and verify the result."""

    root = cohort_root(run_config_path)
    report = build_evaluation_report(run_config_path, module_root)
    json_bytes = canonical_json(report)
    markdown_bytes = render_evaluation_report(report).encode("utf-8")
    candidates = {
        (root / REPORT_JSON).resolve(): json_bytes,
        (root / REPORT_MARKDOWN).resolve(): markdown_bytes,
        published_report.resolve(): markdown_bytes,
    }
    scan = _scan_public_export(
        root,
        module_root.resolve(),
        candidates,
        sensitive_values,
    )
    if not scan["passed"]:
        raise ValueError(
            "known sensitive value found in final public export candidates: "
            + ", ".join(scan["hit_paths"])
        )
    for path, content in candidates.items():
        _write_bytes_atomic(path, content)
    verified = verify_evaluation_report(
        run_config_path,
        module_root,
        published_report,
    )
    labels = {
        (root / REPORT_JSON).resolve(): "artifact-json",
        (root / REPORT_MARKDOWN).resolve(): "artifact-markdown",
        published_report.resolve(): "published-markdown",
    }
    return {
        **verified,
        "public_export_scan": scan,
        "report_files": {
            labels[path]: {
                "path": path.as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for path, content in sorted(
                candidates.items(),
                key=lambda item: item[0].as_posix(),
            )
        },
    }


def render_evaluation_report(report: Mapping[str, Any]) -> str:
    """Render the canonical human-readable report from report JSON."""

    formal = report["formal_results"]
    coding = formal["coding"]
    counts = coding["counts"]
    metrics = coding["metrics"]
    lines = [
        "# Pico Evaluation v2 基线报告",
        "",
        "## 文档状态",
        "",
        "这是 Evaluation v2 的正式基线报告。机器可读单一数据源为同目录的 "
        "`evaluation-report.json`；本文及仓库镜像均由该 JSON 确定性生成。",
        "",
        "仓库镜像中的 Artifact 相对链接以外部 canonical 报告所在目录为基准。",
        "",
        "## Suite 与批次",
        "",
        f"- 正式 coding cohort：`{formal['cohort']['id']}`",
        f"- Coding source：`{formal['cohort']['source']['commit']}`",
        f"- Module cohort：`{formal['modules']['cohort_id']}`",
        f"- Module source：`{formal['modules']['source_sha']}`",
        f"- 模型：`{formal['cohort']['profile']['model']}`",
        f"- Provider profile：`{formal['cohort']['profile']['provider']}` / "
        f"`{formal['cohort']['profile']['profile_id']}`",
        "",
        "P1 模块结果与 `baseline-v1` 真实编码结果分开报告，不共享分母。",
        "",
        "## 正式编码结果",
        "",
        f"- Final classified：{counts['final_classified']}/{counts['planned']}",
        f"- Valid passed / failed / invalid：{counts['valid_passed']} / "
        f"{counts['valid_failed']} / {counts['invalid']}",
        f"- Valid-run rate：{_format_ratio(metrics['valid_run_rate'])}",
        f"- Verified-run success：{_format_ratio(metrics['verified_run_success'])}",
        f"- Provider requests：{metrics['provider_requests']['total']}",
        f"- Tool steps：{_format_numeric(metrics['tool_steps'])}",
        f"- Repeated reads：{_format_numeric(metrics['repeated_reads'])}",
        f"- Runtime elapsed：{_format_numeric(metrics['elapsed_time_ms'], ' ms')}",
        "",
        "### 27 条正式编码评测行",
        "",
        "| Row | Repo | Task | 分类 | 一句话结果 | 原因与证据 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in coding["rows"]:
        evidence = row["evidence"]
        reason = _cell(row["reason"])
        lines.append(
            f"| `{row['row_id']}` | `{row['repo_id']}` | {row['task_id']} | "
            f"{row['final_classification']} | {_cell(row['result_summary'])} | "
            f"{reason} "
            f"([record](../{evidence['run_record']}), "
            f"[view](../{evidence['evidence_view']}), "
            f"[audit](../{evidence['codex_audit']})) |"
        )
    lines.extend(
        [
            "",
            "## 按 repo、task 与 failure category 分解",
            "",
            "### Repository",
            "",
            "| Repo | Passed | Failed | Invalid | Verified success | "
            "Requests | Mean tool steps | Repeated reads |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for repo_id, scope in coding["by_repository"].items():
        lines.append(_scope_table_row(repo_id, scope))
    lines.extend(
        [
            "",
            "### Task",
            "",
            "| Task | Repo | Stability | Passed | Failed | Invalid | "
            "Requests | Mean tool steps | Repeated reads |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for task_id, scope in coding["by_task"].items():
        task_metrics = scope["metrics"]
        task_counts = scope["counts"]
        lines.append(
            f"| {task_id} | `{scope['repository']}` | "
            f"{task_metrics['stable_task_status'][task_id]} | "
            f"{task_counts['valid_passed']} | {task_counts['valid_failed']} | "
            f"{task_counts['invalid']} | "
            f"{task_metrics['provider_requests']['total']} | "
            f"{_number(task_metrics['tool_steps']['mean'])} | "
            f"{task_metrics['repeated_reads']['total']} |"
        )
    lines.extend(
        [
            "",
            f"- Failure categories：`{json.dumps(metrics['failure_category_counts'], sort_keys=True)}`",
            "",
            "## Measurement quality 与 invalid rows",
            "",
        ]
    )
    quality = formal["measurement_quality"]
    lines.extend(
        [
            f"- Runtime evidence valid：{quality['valid_rows']}/{quality['planned_rows']}",
            f"- Invalid rows：{len(quality['invalid_rows'])}",
            f"- Exact provider request counts：{quality['exact_provider_request_rows']}/"
            f"{quality['planned_rows']}",
            f"- Runtime credential scans passed：{quality['credential_scan_passed_rows']}/"
            f"{quality['planned_rows']}",
            f"- SDK retries / Pico retries：{quality['sdk_retry_total']} / "
            f"{quality['pico_retry_total']}",
            f"- Protocol-error rows：{len(quality['protocol_error_rows'])}",
            "",
            "Measurement quality 不进入 verified-run success 分子；invalid 行会单独列出，"
            "当前批次没有 invalid 行。",
            "",
            "## Context、memory、recovery 与 harness 模块指标",
            "",
        ]
    )
    lines.extend(_render_modules(formal["modules"]))
    lines.extend(
        [
            "",
            "## 三个最重要的已观察改进机会",
            "",
        ]
    )
    for index, item in enumerate(report["improvement_opportunities"], start=1):
        lines.extend(
            [
                f"{index}. **{item['title']}**",
                f"   - 观察：{item['observation']}",
                f"   - 下一步：{item['next_step']}",
                f"   - 限制：{item['limitation']}",
            ]
        )
    lines.extend(
        [
            "",
            "## 简历结论—证据映射",
            "",
            "| 结论 | Cohort | 样本 | 公式 | 证据 | 限制 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for claim in report["resume_claims"]:
        lines.append(
            f"| {_cell(claim['claim'])} | `{claim['cohort']}` | "
            f"{_cell(claim['sample'])} | {_cell(claim['formula'])} | "
            f"{_cell('; '.join(claim['evidence']))} | "
            f"{_cell(claim['limitation'])} |"
        )
    lines.extend(
        [
            "",
            "## 测试边界观察",
            "",
        ]
    )
    for item in report["boundary_observations"]:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                item["observation"],
                "",
                f"- 完整 Pico 产品边界：{item['product_boundary']}",
                f"- 独立 Runtime 边界：{item['runtime_boundary']}",
                f"- 指标影响：{item['metric_impact']}",
                f"- 证据：{'; '.join(item['evidence'])}",
                f"- 限制：{item['limitation']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 限制与待决定事项",
            "",
            *[f"- {item}" for item in report["limitations"]],
            "",
            "本报告不自动授权或启动产品修复、补充批次、Auto-dream 或 Native Resume。",
            "",
        ]
    )
    return "\n".join(lines)


def _formal_results(run_config_path: Path, module_root: Path) -> dict[str, Any]:
    config = verified_baseline_config(run_config_path)
    root = cohort_root(run_config_path)
    summary = build_baseline_summary(run_config_path, stage="P4C")
    if summary["g1"]["status"] != "passed":
        raise ValueError("P5 report requires G1 passed")
    rows = [_enrich_row(root, row) for row in summary["cohort"]["rows"]]
    by_task = {}
    for task_id in sorted({str(row["task_id"]) for row in rows}):
        scoped = summarize_coding_rows(
            [row for row in rows if row["task_id"] == task_id]
        )
        by_task[task_id] = {
            "repository": next(
                row["repo_id"] for row in rows if row["task_id"] == task_id
            ),
            **_without_rows(scoped),
        }
    by_repository = {}
    for repo_id in sorted({str(row["repo_id"]) for row in rows}):
        scoped = summarize_coding_rows(
            [row for row in rows if row["repo_id"] == repo_id]
        )
        by_repository[repo_id] = _without_rows(scoped)
    coding = {
        **_without_rows(summary["cohort"]),
        "by_repository": by_repository,
        "by_task": by_task,
        "rows": rows,
    }
    return {
        "cohort": {
            "id": "baseline-v1",
            "source": dict(config["source"]),
            "run_config": {
                "path": "public/run-config.json",
                "sha256": run_config_path.with_name("run-config.sha256")
                .read_text(encoding="ascii")
                .strip(),
            },
            "profile": dict(config["profile"]["public_profile"]),
            "taskset": dict(config["taskset"]),
        },
        "coding": coding,
        "measurement_quality": _measurement_quality(root, rows),
        "modules": _module_results(module_root),
    }


def _enrich_row(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    row_id = str(row["row_id"])
    public_row = root / "public" / "rows" / row_id
    record = load_object(public_row / "run-record.json")
    identity = record.get("row", {})
    if (
        identity.get("row_id") != row_id
        or identity.get("task_id") != row["task_id"]
        or identity.get("repetition") != row["repetition"]
    ):
        raise ValueError(f"coding row identity drift: {row_id}")
    repo_id = str(identity.get("repo_id", ""))
    if not repo_id:
        raise ValueError(f"coding row is missing repo identity: {row_id}")
    classification = str(row["final_classification"])
    result_summary = (
        "隐藏检查通过，测量有效。"
        if classification == "valid + passed"
        else "隐藏检查失败，测量有效。"
        if classification == "valid + failed"
        else "测量无效，不形成产品通过或失败结论。"
    )
    public_originals = [
        f"public/rows/{row_id}/original/{path}"
        for path in record.get("evidence", {}).get("public_originals", [])
    ]
    private_originals = [
        f"private/rows/{row_id}/original/{path}"
        for path in record.get("evidence", {}).get("private_originals", [])
    ]
    evidence = {
        **dict(row["evidence"]),
        "public_checksums": f"public/rows/{row_id}/checksums.json",
        "private_checksums": f"private/rows/{row_id}/checksums.json",
        "verifier_result": f"public/rows/{row_id}/verifier/result.json",
        "public_originals": public_originals,
        "private_originals": private_originals,
    }
    decision = public_row / "user-decision.json"
    if decision.is_file():
        evidence["user_decision"] = f"public/rows/{row_id}/user-decision.json"
    return {
        **dict(row),
        "repo_id": repo_id,
        "result_summary": result_summary,
        "evidence": evidence,
    }


def _measurement_quality(
    root: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    exact = 0
    scan_passed = 0
    sdk_retries = 0
    pico_retries = 0
    protocol_errors = []
    for row in rows:
        row_id = str(row["row_id"])
        public_row = root / "public" / "rows" / row_id
        record = load_object(public_row / "run-record.json")
        view = load_object(public_row / "evidence-view.json")
        provider = record.get("provider_requests", {})
        if provider.get("exact") is True and type(provider.get("count")) is int:
            exact += 1
        credential = record.get("credential_scan", {})
        if all(
            credential.get(name, {}).get("passed") is True
            for name in ("source_originals", "persisted_artifacts")
        ):
            scan_passed += 1
        sdk_retries += int(record.get("client_result", {}).get("sdk_retry_count", 0))
        pico_retries += int(record.get("client_result", {}).get("pico_retry_count", 0))
        if view.get("protocol_errors"):
            protocol_errors.append(row_id)
    return {
        "planned_rows": len(rows),
        "valid_rows": sum(
            str(row["final_classification"]).startswith("valid +") for row in rows
        ),
        "invalid_rows": [
            row["row_id"]
            for row in rows
            if row["final_classification"] == "invalid"
        ],
        "exact_provider_request_rows": exact,
        "credential_scan_passed_rows": scan_passed,
        "sdk_retry_total": sdk_retries,
        "pico_retry_total": pico_retries,
        "protocol_error_rows": protocol_errors,
    }


def _module_results(module_root: Path) -> dict[str, Any]:
    report = load_object(module_root / MODULE_REPORT_JSON)
    manifest = load_object(module_root / MODULE_CHECKSUMS)
    return {
        "cohort_id": report["cohort_id"],
        "source_sha": report["source_sha"],
        "scope": dict(report["scope"]),
        "modules": dict(report["modules"]),
        "evidence": {
            "report": MODULE_REPORT_JSON.as_posix(),
            "checksums": MODULE_CHECKSUMS.as_posix(),
            "files": dict(manifest["files"]),
        },
    }


def _boundary_observations(baseline_root: Path) -> list[dict[str, Any]]:
    evaluation_root = baseline_root.parents[1]
    reports = {}
    for cohort_id, source in PILOT_SOURCES.items():
        pilot_root = evaluation_root / cohort_id / source
        run_config = pilot_root / "public" / "run-config.json"
        verify_pilot(run_config)
        report_path = pilot_root / PILOT_REPORT_JSON
        reports[cohort_id] = {
            "path": (
                f"{cohort_id}/{source}/{PILOT_REPORT_JSON.as_posix()}"
            ),
            "sha256": sha256_file(report_path),
            "report": load_object(report_path),
        }
    v3 = reports["pilot-v3"]["report"]
    v4 = reports["pilot-v4"]["report"]
    if (
        v3["counts"]["valid_failed"] != 3
        or v3["metrics"]["provider_requests"]["total"] != 0
        or v4["counts"]["valid_passed"] != 3
    ):
        raise ValueError("Prompt boundary Pilot facts differ from the accepted record")
    return [
        {
            "id": "prompt-normalization-scope",
            "title": "Prompt 规范化与测试边界",
            "kind": "execution-observation",
            "observation": (
                "Runtime 接收的 user_message 未先统一裁剪；ContextManager 在装配"
                "完整 prompt 时对整体执行 strip()，metadata 则保留原始请求。"
                "request context 随后要求最终 prompt 精确保留 metadata 中的"
                " current request，因此直接注入带外层空白的 prompt 可能在首次"
                " provider 请求前触发 ValueError。"
            ),
            "product_boundary": (
                "one-shot、REPL、TUI 和正式 Evaluation bridge 都在进入 Runtime "
                "前裁剪输入；以这些标准入口组成的完整 Pico 产品为边界时，"
                "baseline-v1 不暴露该路径，不能把它计为正式基线失败。"
            ),
            "runtime_boundary": (
                "如果 Runtime/Pico API 被视为可独立调用的模块，该接口既未统一"
                "规范化输入，也未明确要求调用者先规范化，形成内部 prompt 与"
                " metadata 不一致，可视为 Runtime 接口契约缺口。"
            ),
            "metric_impact": (
                "无；pilot-v3、pilot-v4 不进入 baseline-v1 分母，不改变正式"
                "结果子树、前三项改进机会或简历结论。"
            ),
            "evidence": [
                f"{reports['pilot-v3']['path']}#sha256={reports['pilot-v3']['sha256']}",
                f"{reports['pilot-v4']['path']}#sha256={reports['pilot-v4']['sha256']}",
                "pico/core/context_manager.py#ContextManager._assemble_prompt",
                "pico/core/context_manager.py#ContextManager._metadata",
                "pico/core/request_context.py#build_request_context",
                "pico/cli.py#main",
                "pico/tui/app.py#PicoApp.action_submit_input",
                "scripts/run_pico_live_task_client.py#run_live_task",
                "commit:6460508c688383102f9dc205d8a04a5681b078dd",
            ],
            "limitation": (
                "pilot-v3 与 pilot-v4 使用不同 source 和 bridge，不能解释为严格"
                " A/B 效果；两批历史分类保持原样。本观察是条件式接口判断，"
                "不是新的正式评测行或 Runtime 修复。"
            ),
        }
    ]


def _improvement_opportunities(
    formal: Mapping[str, Any],
) -> list[dict[str, Any]]:
    coding = formal["coding"]
    t02 = coding["by_task"]["T02"]
    t09 = coding["by_task"]["T09"]
    queue = coding["by_repository"]["miniqueue"]
    return [
        {
            "id": "t02-boundary-correctness",
            "title": "提高 T02 嵌套配置边界行为的稳定性",
            "observation": (
                f"T02 为 {t02['metrics']['stable_task_status']['T02']}，"
                f"三次运行中 {t02['counts']['valid_failed']} 次有效失败；"
                "失败行遗漏 malformed database section 的 ConfigError。"
            ),
            "next_step": (
                "后续独立计划应检查模型在提交前是否系统覆盖 malformed nested "
                "section，不得回写 baseline-v1。"
            ),
            "limitation": "当前失败分类为 model_behavior，未证明 Pico Runtime 根因。",
        },
        {
            "id": "t09-execution-cost",
            "title": "降低 T09 的请求与工具步骤成本",
            "observation": (
                f"T09 三次共 {t09['metrics']['provider_requests']['total']} 次请求，"
                f"平均 {t09['metrics']['tool_steps']['mean']:.2f} 个工具步骤。"
            ),
            "next_step": "在独立可比 cohort 中调查规划和验证步骤的长尾。",
            "limitation": "三条样本只能定位观察点，不能建立成本根因。",
        },
        {
            "id": "miniqueue-repeated-reads",
            "title": "减少 miniqueue 任务中的重复读取",
            "observation": (
                "miniqueue 的九条 valid 行累计 "
                f"{queue['metrics']['repeated_reads']['total']} 次重复读取。"
            ),
            "next_step": (
                "结合 working-memory 模块证据，在独立实验中检查真实 coding "
                "路径的记忆命中与重复读取关系。"
            ),
            "limitation": "现有基线只记录重复读取次数，不证明 working memory 是根因。",
        },
    ]


def _resume_claims(formal: Mapping[str, Any]) -> list[dict[str, Any]]:
    coding = formal["coding"]
    modules = formal["modules"]["modules"]
    counts = coding["counts"]
    context = modules["context_ablation"]
    memory = modules["working_memory_ablation"]
    recovery = modules["recovery_ablation"]
    return [
        {
            "claim": (
                f"在固定的 9-task × 3-repeat 本地编码基线中，"
                f"{counts['valid_passed']}/{counts['valid_passed'] + counts['valid_failed']} "
                "条有效运行通过隐藏检查。"
            ),
            "cohort": "baseline-v1",
            "sample": "27 条正式 coding rows",
            "formula": "valid + passed / 全部 valid rows",
            "evidence": [
                "public/run-config.json",
                "public/rows/<row-id>/codex-audit.json",
            ],
            "limitation": "一个模型、provider profile 和固定 mini-repo taskset。",
        },
        {
            "claim": (
                f"{counts['final_classified']}/{counts['planned']} 条正式行最终分类，"
                f"invalid={counts['invalid']}。"
            ),
            "cohort": "baseline-v1",
            "sample": "27 条正式 coding rows",
            "formula": "valid rows / final-classified rows；invalid 单列",
            "evidence": ["public/rows/<row-id>/checksums.json"],
            "limitation": "实际凭据扫描只检查本次进程已知的精确敏感值。",
        },
        {
            "claim": (
                "确定性 context ablation 的平均 prompt 压缩率为 "
                f"{context['metrics']['avg_prompt_compression_ratio']:.2%}，"
                "最新请求保留率为 "
                f"{context['metrics']['current_request_preserved_rate']:.2%}。"
            ),
            "cohort": "module-baseline-v1",
            "sample": "12 configs × 5 repetitions",
            "formula": context["formulas"]["avg_prompt_compression_ratio"],
            "evidence": [context["artifact_path"]],
            "limitation": "模块级确定性证据，不是端到端 provider 结果。",
        },
        {
            "claim": (
                "working-memory ablation 中 memory_on 的 repeated_reads=0，"
                "correct_rate=100%。"
            ),
            "cohort": "module-baseline-v1",
            "sample": "12 tasks × 5 repetitions for memory_on",
            "formula": memory["formulas"]["repeated_reads"],
            "evidence": [memory["artifact_path"]],
            "limitation": "scripted 模块任务，不直接推出真实 coding 路径收益。",
        },
        {
            "claim": (
                "recovery ablation 中 resume_enabled 的 resume success rate 为 "
                f"{recovery['metrics']['resume_enabled']['resume_success_rate']:.2%}，"
                "workspace drift detection rate 为 "
                f"{recovery['metrics']['resume_enabled']['workspace_drift_detection_rate']:.2%}。"
            ),
            "cohort": "module-baseline-v1",
            "sample": "10 tasks × 3 repetitions for resume_enabled",
            "formula": recovery["formulas"]["resume_success_rate"],
            "evidence": [recovery["artifact_path"]],
            "limitation": "模块级恢复实验，不代表尚未实现的 Native Resume。",
        },
    ]


def _verify_row_evidence(root: Path, config: Mapping[str, Any]) -> None:
    for allowed in config["allowed_rows"]:
        row_id = str(allowed["row_id"])
        public_row = root / "public" / "rows" / row_id
        private_row = root / "private" / "rows" / row_id
        if not public_row.is_dir() or not private_row.is_dir():
            raise ValueError(f"P5 requires public and private row evidence: {row_id}")
        verify_checksums(public_row / "checksums.json", public_row)
        verify_checksums(private_row / "checksums.json", private_row)
        record = load_object(public_row / "run-record.json")
        _verify_original_paths(public_row, private_row, record)
        _verify_runtime_credential_scan(public_row, private_row, record)


def _verify_original_paths(
    public_row: Path,
    private_row: Path,
    record: Mapping[str, Any],
) -> None:
    evidence = record.get("evidence", {})
    for label, row_root in (
        ("public_originals", public_row),
        ("private_originals", private_row),
    ):
        paths = evidence.get(label)
        if not isinstance(paths, list) or not paths:
            raise ValueError(f"row evidence is missing {label}")
        for value in paths:
            relative = _safe_relative_path(value)
            if not (row_root / "original" / relative).exists():
                raise ValueError(f"row original evidence is missing: {value}")


def _verify_runtime_credential_scan(
    public_row: Path,
    private_row: Path,
    record: Mapping[str, Any],
) -> None:
    credential = record.get("credential_scan", {})
    source = credential.get("source_originals", {})
    persisted = credential.get("persisted_artifacts", {})
    for name, value in (("source_originals", source), ("persisted_artifacts", persisted)):
        if (
            value.get("passed") is not True
            or value.get("hit_paths") != []
            or type(value.get("files_scanned")) is not int
        ):
            raise ValueError(f"runtime credential scan is not valid: {name}")
    workspace_after = record.get("workspace_manifest", {}).get("after", {})
    source_files = [
        path for path in workspace_after if str(path).startswith(".pico/")
    ]
    if source["files_scanned"] != len(source_files):
        raise ValueError("source credential scan coverage count drift")
    private_files = [
        path
        for path in private_row.rglob("*")
        if path.is_file() and path.name != "checksums.json"
    ]
    public_files = [
        path
        for path in public_row.rglob("*")
        if path.is_file()
        and path.name
        not in {"checksums.json", "codex-audit.json", "user-decision.json"}
    ]
    if persisted["files_scanned"] != len(private_files) + len(public_files):
        raise ValueError("persisted credential scan coverage count drift")


def _scan_public_export(
    baseline_root: Path,
    module_root: Path,
    candidates: Mapping[Path, bytes],
    sensitive_values: Sequence[str],
) -> dict[str, Any]:
    values = [value.encode("utf-8") for value in sensitive_values if value]
    files: dict[str, bytes] = {}
    roots = {
        "baseline": baseline_root / "public",
        "module-public": module_root / "public",
        "module-reports": module_root / "reports",
    }
    evaluation_root = baseline_root.parents[1]
    for cohort_id, source in PILOT_SOURCES.items():
        pilot_root = evaluation_root / cohort_id / source
        roots[f"{cohort_id}-public"] = pilot_root / "public"
        roots[f"{cohort_id}-reports"] = pilot_root / "reports"
    for label, root in roots.items():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files[f"{label}/{path.relative_to(root).as_posix()}"] = path.read_bytes()
    for index, (path, content) in enumerate(
        sorted(candidates.items(), key=lambda item: item[0].as_posix())
    ):
        files[f"candidate/{index}-{path.name}"] = content
    hits = [
        path
        for path, content in files.items()
        if any(value in content for value in values)
    ]
    inventory = [
        {
            "path": path,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for path, content in sorted(files.items())
    ]
    return {
        "passed": not hits,
        "files_scanned": len(files),
        "hit_paths": hits,
        "coverage_sha256": _digest_object(inventory),
    }


def _render_modules(modules: Mapping[str, Any]) -> list[str]:
    items = modules["modules"]
    context = items["context_ablation"]
    memory = items["working_memory_ablation"]
    recovery = items["recovery_ablation"]
    harness = items["harness_regression"]
    return [
        f"- Harness：{harness['metrics']['passed']}/{harness['metrics']['total_tasks']} "
        "passed，verifier pass rate "
        f"{harness['metrics']['verifier_pass_rate']:.2%}。",
        "- Context："
        f"{context['sample_counts']['configs']} configs × "
        f"{context['sample_counts']['repetitions_per_config']} repetitions，平均压缩率 "
        f"{context['metrics']['avg_prompt_compression_ratio']:.2%}，当前请求保留率 "
        f"{context['metrics']['current_request_preserved_rate']:.2%}。",
        "- Working memory：memory_on repeated_reads="
        f"{memory['metrics']['memory_on']['repeated_reads']}、correct_rate="
        f"{memory['metrics']['memory_on']['correct_rate']:.2%}；memory_off "
        f"repeated_reads={memory['metrics']['memory_off']['repeated_reads']}。",
        "- Recovery：resume_enabled success="
        f"{recovery['metrics']['resume_enabled']['resume_success_rate']:.2%}、"
        "workspace drift detection="
        f"{recovery['metrics']['resume_enabled']['workspace_drift_detection_rate']:.2%}、"
        "false accept="
        f"{recovery['metrics']['resume_enabled']['resume_false_accept_rate']:.2%}。",
        f"- P1 checksum manifest：`{modules['evidence']['checksums']}`。",
    ]


def _scope_table_row(label: str, scope: Mapping[str, Any]) -> str:
    counts = scope["counts"]
    metrics = scope["metrics"]
    return (
        f"| `{label}` | {counts['valid_passed']} | {counts['valid_failed']} | "
        f"{counts['invalid']} | {_format_ratio(metrics['verified_run_success'])} | "
        f"{metrics['provider_requests']['total']} | "
        f"{_number(metrics['tool_steps']['mean'])} | "
        f"{metrics['repeated_reads']['total']} |"
    )


def _without_rows(scope: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in scope.items() if key != "rows"}


def _format_ratio(value: Mapping[str, Any]) -> str:
    ratio = value.get("value")
    if ratio is None:
        return f"不可计算 ({value['numerator']}/{value['denominator']})"
    return f"{value['numerator']}/{value['denominator']} ({ratio:.2%})"


def _format_numeric(value: Mapping[str, Any], suffix: str = "") -> str:
    if value.get("mean") is None:
        return f"不可计算 (0/{value['valid_samples']} samples)"
    total = f", total={value['total']}{suffix}" if "total" in value else ""
    return (
        f"mean={value['mean']:.2f}{suffix}, median={value['median']:.2f}{suffix}"
        f"{total} ({value['available_samples']}/{value['valid_samples']} samples)"
    )


def _number(value: Any) -> str:
    return "—" if value is None else f"{float(value):.2f}"


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _digest_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _safe_relative_path(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("evidence path is not a safe relative POSIX path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"unsafe evidence path: {value}")
    return Path(*pure.parts)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


__all__ = [
    "REPORT_JSON",
    "REPORT_MARKDOWN",
    "REPORT_SCHEMA",
    "build_evaluation_report",
    "render_evaluation_report",
    "verify_evaluation_report",
    "write_evaluation_report",
]
