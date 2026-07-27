from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..config import resolve_provider_config
from .evaluator import run_fixed_benchmark
from ..providers.contracts import ModelRequest, ModelResponse
from ..testing import (
    ScriptedNativeModelClient,
    native_final_response,
    native_tool_call_response,
)
from ..providers import build_native_model_client, native_provider_profile
from ..core.runtime import Pico, SessionStore
from ..core.workspace import WorkspaceContext

METRICS_SCHEMA_VERSION = 2
DEFAULT_HARNESS_REGRESSION_V2_PATH = Path("artifacts/harness-regression-v2.json")
DEFAULT_CONTEXT_ABLATION_V2_PATH = Path("artifacts/context-ablation-v2.json")
DEFAULT_MEMORY_ABLATION_V2_PATH = Path("artifacts/memory-ablation-v2.json")
DEFAULT_RECOVERY_ABLATION_V2_PATH = Path("artifacts/recovery-ablation-v2.json")
DEFAULT_CORE_REPORT_PATH = Path("docs/metrics/pico-benchmark-core-report.md")


def _lock_native_profile(agent: Pico, identity: dict[str, Any] | None = None) -> Pico:
    identity = dict(
        identity
        or {
            "profile_id": "scripted-native:metrics",
            "profile": "scripted",
            "model": "scripted-model",
            "wire_dialect": "scripted-native",
            "adapter_mode": "scripted",
            "sdk_package": "none",
            "sdk_version": "0",
            "sdk_max_retries": 0,
            "provider_attempts": 1,
        }
    )
    identity["tool_schema"] = agent.tool_signature()
    agent.session["provider_profile"] = identity
    agent.session_path = agent.session_store.save(agent.session)
    return agent


def _safe_mean(values: list[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def aggregate_benchmark_artifact(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = list(payload.get("rows", []))
    summary = dict(payload.get("summary", {}))
    task_count = int(summary.get("total_tasks", len(rows) or 0))
    tool_steps = [int(row.get("tool_steps", 0)) for row in rows]
    attempts = [int(row.get("attempts", 0)) for row in rows]
    categories = {}
    for row in rows:
        category = str(row.get("category", "")).strip()
        if not category:
            continue
        categories[category] = categories.get(category, 0) + 1
    return {
        "task_count": task_count,
        "passed": int(summary.get("passed", 0)),
        "failed": int(summary.get("failed", 0)),
        "pass_rate": float(summary.get("pass_rate", 0.0)),
        "within_budget": int(summary.get("within_budget", 0)),
        "verifier_passes": int(summary.get("verifier_passes", 0)),
        "failure_category_counts": dict(summary.get("failure_category_counts", {})),
        "avg_tool_steps": _safe_mean(tool_steps),
        "avg_attempts": _safe_mean(attempts),
        "category_counts": categories,
        "rows": rows,
    }


def _infer_run_duration_ms(events: list[dict[str, Any]]) -> float:
    finished = next(
        (event for event in reversed(events) if event.get("event") == "run_finished"),
        None,
    )
    if finished and finished.get("run_duration_ms") is not None:
        return float(finished["run_duration_ms"])
    started = next(
        (event for event in events if event.get("event") == "run_started"), None
    )
    if not started or not finished:
        return 0.0
    start_dt = _parse_iso8601(started.get("created_at"))
    end_dt = _parse_iso8601(finished.get("created_at"))
    if start_dt is None or end_dt is None:
        return 0.0
    return max(0.0, (end_dt - start_dt).total_seconds() * 1000.0)


def aggregate_run_artifacts(runs_root: str | Path) -> dict[str, Any]:
    runs_root = Path(runs_root)
    run_dirs = sorted(path for path in runs_root.glob("*") if path.is_dir())
    reports = []
    tool_status_counts = {}
    tool_name_counts = {}
    security_event_counts = {}
    run_durations = []
    tool_durations = []
    prompt_durations = []
    stop_reasons = {}

    for run_dir in run_dirs:
        report_path = run_dir / "report.json"
        trace_path = run_dir / "trace.jsonl"
        if report_path.exists():
            reports.append(json.loads(report_path.read_text(encoding="utf-8")))
        events = []
        if trace_path.exists():
            events = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        run_durations.append(_infer_run_duration_ms(events))
        for event in events:
            if (
                event.get("event") == "prompt_built"
                and event.get("duration_ms") is not None
            ):
                prompt_durations.append(float(event["duration_ms"]))
            if event.get("event") != "tool_executed":
                continue
            tool_name = str(event.get("name", "")).strip()
            if tool_name:
                tool_name_counts[tool_name] = tool_name_counts.get(tool_name, 0) + 1
            tool_status = str(event.get("tool_status", "")).strip()
            if tool_status:
                tool_status_counts[tool_status] = (
                    tool_status_counts.get(tool_status, 0) + 1
                )
            security_event = str(event.get("security_event_type", "")).strip()
            if security_event:
                security_event_counts[security_event] = (
                    security_event_counts.get(security_event, 0) + 1
                )
            if event.get("duration_ms") is not None:
                tool_durations.append(float(event["duration_ms"]))

    tool_steps = [int(report.get("tool_steps", 0)) for report in reports]
    attempts = [int(report.get("attempts", 0)) for report in reports]
    prompt_chars = [
        int((report.get("prompt_metadata") or {}).get("prompt_chars", 0))
        for report in reports
    ]
    cached_tokens = [
        int((report.get("prompt_metadata") or {}).get("cached_tokens", 0) or 0)
        for report in reports
    ]
    cache_hits = [
        bool((report.get("prompt_metadata") or {}).get("cache_hit"))
        for report in reports
    ]
    input_tokens = [
        int((report.get("prompt_metadata") or {}).get("input_tokens", 0) or 0)
        for report in reports
    ]
    prefix_reused = [
        not bool((report.get("prompt_metadata") or {}).get("prefix_changed"))
        for report in reports
        if "prefix_changed" in (report.get("prompt_metadata") or {})
    ]
    for report in reports:
        stop_reason = str(report.get("stop_reason", "")).strip()
        if stop_reason:
            stop_reasons[stop_reason] = stop_reasons.get(stop_reason, 0) + 1

    return {
        "run_count": len(reports) if reports else len(run_dirs),
        "avg_tool_steps": _safe_mean(tool_steps),
        "avg_attempts": _safe_mean(attempts),
        "avg_prompt_chars": _safe_mean(prompt_chars),
        "cache_hit_rate": _safe_ratio(
            sum(1 for hit in cache_hits if hit), len(cache_hits)
        ),
        "cached_token_ratio": _safe_ratio(sum(cached_tokens), sum(input_tokens)),
        "avg_cached_tokens": _safe_mean(cached_tokens),
        "prefix_reuse_rate": _safe_ratio(
            sum(1 for reused in prefix_reused if reused), len(prefix_reused)
        ),
        "tool_status_counts": tool_status_counts,
        "tool_name_counts": tool_name_counts,
        "security_event_counts": security_event_counts,
        "stop_reason_counts": stop_reasons,
        "avg_run_duration_ms": _safe_mean(run_durations),
        "avg_tool_duration_ms": _safe_mean(tool_durations),
        "avg_prompt_build_duration_ms": _safe_mean(prompt_durations),
    }


@contextmanager
def _temporary_feature_flags(
    agent: Pico, updates: dict[str, bool]
) -> Generator[None, None, None]:
    previous = dict(getattr(agent, "feature_flags", {}))
    merged = dict(previous)
    merged.update(updates)
    agent.feature_flags = merged
    try:
        yield
    finally:
        agent.feature_flags = previous


def measure_feature_ablation_metrics(agent: Pico, user_message: str) -> dict[str, Any]:
    variants = {
        "full": {},
        "no_context_reduction": {"context_reduction": False},
        "no_memory": {"memory": False, "relevant_memory": False},
    }
    results = {}
    for name, updates in variants.items():
        with _temporary_feature_flags(agent, updates):
            prompt, metadata = agent._build_prompt_and_metadata(user_message)
        results[name] = {
            "prompt_chars": int(metadata.get("prompt_chars", 0)),
            "memory_chars": int(
                metadata.get("sections", {}).get("memory", {}).get("rendered_chars", 0)
            ),
            "history_chars": int(
                metadata.get("sections", {}).get("history", {}).get("rendered_chars", 0)
            ),
            "relevant_selected_count": int(
                metadata.get("relevant_memory", {}).get("selected_count", 0)
            ),
            "budget_reduction_count": len(metadata.get("budget_reductions", [])),
            "current_request_preserved": prompt.endswith(
                f"Current user request:\n{user_message}"
            ),
        }
    return results


def build_stress_agent_metrics() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pico-metrics-") as temp_dir:
        workspace_root = Path(temp_dir)
        (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
        workspace = WorkspaceContext.build(workspace_root)
        store = SessionStore(workspace_root / ".pico" / "sessions")
        agent = Pico(
            model_client=ScriptedNativeModelClient([]),
            workspace=workspace,
            session_store=store,
            approval_policy="auto",
        )
        for index in range(12):
            agent.memory.append_note(
                f"stress-note-{index}-" + ("A" * 180),
                tags=("recall",),
                created_at=f"2026-04-08T10:{index:02d}:00+00:00",
            )
            agent.record(
                {
                    "role": "user" if index % 2 == 0 else "assistant",
                    "content": f"stress-history-{index}-" + ("B" * 220),
                    "created_at": f"2026-04-08T11:{index:02d}:00+00:00",
                }
            )
        return measure_feature_ablation_metrics(agent, "recall")


class _MemoryExperimentModelClient:
    def __init__(self, expected_fact: str, filename: str):
        self.expected_fact = str(expected_fact).strip().lower()
        self.filename = str(filename).strip()
        self.phase = "bootstrap_tool"
        self.followup_reads = 0
        self.prompts: list[str] = []
        self.requests: list[ModelRequest] = []

    def request(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        prompt = request.prompt
        self.prompts.append(prompt)
        if self.phase == "bootstrap_tool":
            self.phase = "bootstrap_final"
            return native_tool_call_response(
                "memory-bootstrap-read",
                "read_file",
                {"path": self.filename, "start": 1, "end": 20},
            )
        if self.phase == "bootstrap_final":
            self.phase = "question"
            return native_final_response("Done.")
        if self.phase == "question":
            prompt_lower = prompt.lower()
            memory_view = ""
            if "memory:" in prompt_lower and "\n\nrelevant memory:" in prompt_lower:
                memory_view = prompt_lower.split("memory:", 1)[1].split(
                    "\n\nrelevant memory:", 1
                )[0]
            relevant_view = ""
            if "relevant memory:" in prompt_lower and "\n\ntranscript:" in prompt_lower:
                relevant_view = prompt_lower.split("relevant memory:", 1)[1].split(
                    "\n\ntranscript:", 1
                )[0]
            if self.expected_fact in memory_view or self.expected_fact in relevant_view:
                return native_final_response(f"{self.expected_fact.capitalize()}.")
            self.phase = "question_after_read"
            self.followup_reads += 1
            return native_tool_call_response(
                "memory-followup-read",
                "read_file",
                {"path": self.filename, "start": 1, "end": 20},
            )
        if self.phase == "question_after_read":
            self.phase = "done"
            return native_final_response(f"{self.expected_fact.capitalize()}.")
        return native_final_response(f"{self.expected_fact.capitalize()}.")


def _build_memory_experiment_agent(
    workspace_root: str | Path, expected_fact: str, filename: str
) -> Pico:
    workspace = WorkspaceContext.build(workspace_root)
    store = SessionStore(workspace_root / ".pico" / "sessions")
    return _lock_native_profile(
        Pico(
            model_client=_MemoryExperimentModelClient(expected_fact, filename),
            workspace=workspace,
            session_store=store,
            approval_policy="auto",
        )
    )


def _set_irrelevant_memory(agent: Pico) -> None:
    state = agent.memory.to_dict()
    state["episodic_notes"] = [
        {
            "text": "team mascot is blue",
            "tags": ["unrelated"],
            "source": "other.txt",
            "created_at": "2026-04-08T10:00:00+00:00",
            "note_index": 0,
        }
    ]
    state["notes"] = ["team mascot is blue"]
    state["file_summaries"] = {}
    agent.memory.state = state
    agent.session["memory"] = agent.memory.to_dict()


def _run_memory_variant(mode: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pico-memory-experiment-") as temp_dir:
        workspace_root = Path(temp_dir)
        (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
        (workspace_root / "facts.txt").write_text(
            "deploy key is red\n", encoding="utf-8"
        )
        agent = _build_memory_experiment_agent(
            workspace_root, "deploy key is red", "facts.txt"
        )
        assert agent.ask("Read facts.txt and remember the key fact.") == "Done."

        if mode == "memory_off":
            agent.feature_flags["memory"] = False
            agent.feature_flags["relevant_memory"] = False
        elif mode == "memory_irrelevant":
            _set_irrelevant_memory(agent)

        result = agent.ask("What color is the deploy key?")
        task_state = agent.current_task_state
        model_client = agent.model_client
        return {
            "correct": result.strip().lower() == "deploy key is red.",
            "tool_steps": int(task_state.tool_steps),
            "attempts": int(task_state.attempts),
            "repeated_reads": int(getattr(model_client, "followup_reads", 0)),
        }


def run_memory_dependency_experiment(repetitions: int = 3) -> dict[str, Any]:
    variants = {
        "memory_on": [],
        "memory_off": [],
        "memory_irrelevant": [],
    }
    for _ in range(int(repetitions)):
        for variant in variants:
            variants[variant].append(_run_memory_variant(variant))

    results = {}
    for variant, rows in variants.items():
        results[variant] = {
            "repeated_reads": sum(row["repeated_reads"] for row in rows),
            "avg_tool_steps": _safe_mean(row["tool_steps"] for row in rows),
            "avg_attempts": _safe_mean(row["attempts"] for row in rows),
            "correct_rate": _safe_ratio(
                sum(1 for row in rows if row["correct"]), len(rows)
            ),
        }
    return results


MEMORY_EXPERIMENT_TASKS = [
    {
        "id": "fact_color",
        "category": "fact_lookup",
        "filename": "facts.txt",
        "fact": "deploy key is red",
    },
    {
        "id": "fact_api",
        "category": "fact_lookup",
        "filename": "settings.txt",
        "fact": "api base path is /v1/internal",
    },
    {
        "id": "fact_budget",
        "category": "fact_lookup",
        "filename": "limits.txt",
        "fact": "default step budget is 6",
    },
    {
        "id": "fact_timeout",
        "category": "fact_lookup",
        "filename": "runtime.txt",
        "fact": "timeout ceiling is 120 seconds",
    },
    {
        "id": "edit_intro",
        "category": "edit_dependency",
        "filename": "README.md",
        "fact": "first bullet is the locked intro line",
    },
    {
        "id": "edit_token",
        "category": "edit_dependency",
        "filename": "sample.txt",
        "fact": "second token is placeholder",
    },
    {
        "id": "edit_field",
        "category": "edit_dependency",
        "filename": "config.txt",
        "fact": "fixed field name is benchmark_schema",
    },
    {
        "id": "edit_line",
        "category": "edit_dependency",
        "filename": "notes.txt",
        "fact": "locked marker is on line three",
    },
    {
        "id": "history_file",
        "category": "history_reference",
        "filename": "history.txt",
        "fact": "deploy fact came from facts.txt",
    },
    {
        "id": "history_line",
        "category": "history_reference",
        "filename": "history.txt",
        "fact": "benchmark note came from line two",
    },
    {
        "id": "history_token",
        "category": "history_reference",
        "filename": "history.txt",
        "fact": "placeholder token was beta",
    },
    {
        "id": "history_tool",
        "category": "history_reference",
        "filename": "history.txt",
        "fact": "inspection tool was read_file",
    },
]


def _write_memory_task_files(workspace_root: Path, task: dict[str, Any]) -> None:
    filename = task["filename"]
    payload = task["fact"]
    (workspace_root / filename).write_text(payload + "\n", encoding="utf-8")


def _bootstrap_prompt(task: dict[str, Any]) -> str:
    return f"Read {task['filename']} and remember the key fact."


def _followup_prompt(task: dict[str, Any]) -> str:
    if task["category"] == "fact_lookup":
        return f"What does {task['filename']} say?"
    if task["category"] == "edit_dependency":
        return f"Use the remembered constraint from {task['filename']} to continue without rereading."
    return f"What was the conclusion we already established from {task['filename']}?"


def _set_irrelevant_memory_for_task(agent: Pico) -> None:
    state = agent.memory.to_dict()
    state["episodic_notes"] = [
        {
            "text": "the team mascot is blue",
            "tags": ["unrelated"],
            "source": "other.txt",
            "created_at": "2026-04-08T10:00:00+00:00",
            "note_index": 0,
        }
    ]
    state["notes"] = ["the team mascot is blue"]
    state["file_summaries"] = {}
    agent.memory.state = state
    agent.session["memory"] = agent.memory.to_dict()


def _run_memory_task_variant(task: dict[str, Any], variant: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pico-memory-large-") as temp_dir:
        workspace_root = Path(temp_dir)
        (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
        _write_memory_task_files(workspace_root, task)
        agent = _build_memory_experiment_agent(
            workspace_root, task["fact"], task["filename"]
        )
        assert agent.ask(_bootstrap_prompt(task)) == "Done."
        if variant == "memory_off":
            agent.feature_flags["memory"] = False
            agent.feature_flags["relevant_memory"] = False
        elif variant == "memory_irrelevant":
            _set_irrelevant_memory_for_task(agent)
        result = agent.ask(_followup_prompt(task))
        task_state = agent.current_task_state
        return {
            "correct": result.strip().lower() == f"{task['fact']}.",
            "tool_steps": int(task_state.tool_steps),
            "attempts": int(task_state.attempts),
            "repeated_reads": int(getattr(agent.model_client, "followup_reads", 0)),
        }


def run_large_scale_memory_experiment(repetitions: int = 5) -> dict[str, Any]:
    repetitions = int(repetitions)
    variants = {
        "memory_on": [],
        "memory_off": [],
        "memory_irrelevant": [],
    }
    for task in MEMORY_EXPERIMENT_TASKS:
        for _ in range(repetitions):
            for variant in variants:
                row = _run_memory_task_variant(task, variant)
                row["task_id"] = task["id"]
                row["category"] = task["category"]
                variants[variant].append(row)
    category_counts = {}
    for task in MEMORY_EXPERIMENT_TASKS:
        category_counts[task["category"]] = category_counts.get(task["category"], 0) + 1
    return {
        "task_count": len(MEMORY_EXPERIMENT_TASKS),
        "runs_per_variant": len(MEMORY_EXPERIMENT_TASKS) * repetitions,
        "category_counts": category_counts,
        "variants": {
            variant: {
                "repeated_reads": sum(row["repeated_reads"] for row in rows),
                "avg_tool_steps": _safe_mean(row["tool_steps"] for row in rows),
                "avg_attempts": _safe_mean(row["attempts"] for row in rows),
                "correct_rate": _safe_ratio(
                    sum(1 for row in rows if row["correct"]), len(rows)
                ),
                "memory_hit_rate": _safe_ratio(
                    sum(1 for row in rows if row["repeated_reads"] == 0), len(rows)
                ),
            }
            for variant, rows in variants.items()
        },
        "rows": variants,
    }


def run_context_stress_matrix(repetitions: int = 5) -> dict[str, Any]:
    repetitions = int(repetitions)
    history_levels = [("short", 4), ("medium", 12), ("long", 24)]
    note_levels = [("low", 2), ("high", 10)]
    request_levels = [
        ("short", "recall"),
        (
            "long",
            "recall the relevant benchmark fact without dropping the latest request details",
        ),
    ]
    configs = []

    for history_label, history_count in history_levels:
        for note_label, note_count in note_levels:
            for request_label, request_text in request_levels:
                per_run = []
                for _ in range(repetitions):
                    with tempfile.TemporaryDirectory(
                        prefix="pico-context-matrix-"
                    ) as temp_dir:
                        workspace_root = Path(temp_dir)
                        (workspace_root / "README.md").write_text(
                            "demo\n", encoding="utf-8"
                        )
                        workspace = WorkspaceContext.build(workspace_root)
                        store = SessionStore(workspace_root / ".pico" / "sessions")
                        agent = Pico(
                            model_client=ScriptedNativeModelClient([]),
                            workspace=workspace,
                            session_store=store,
                            approval_policy="auto",
                        )
                        for index in range(note_count):
                            agent.memory.append_note(
                                f"matrix-note-{index}-" + ("A" * 180),
                                tags=("recall",),
                                created_at=f"2026-04-08T10:{index:02d}:00+00:00",
                            )
                        for index in range(history_count):
                            agent.record(
                                {
                                    "role": "user" if index % 2 == 0 else "assistant",
                                    "content": f"matrix-history-{index}-" + ("B" * 220),
                                    "created_at": f"2026-04-08T11:{index:02d}:00+00:00",
                                }
                            )
                        metrics = measure_feature_ablation_metrics(agent, request_text)
                        full_chars = metrics["full"]["prompt_chars"]
                        raw_chars = metrics["no_context_reduction"]["prompt_chars"]
                        ratio = _safe_ratio(raw_chars - full_chars, raw_chars)
                        per_run.append(
                            {
                                "full_prompt_chars": full_chars,
                                "raw_prompt_chars": raw_chars,
                                "compression_ratio": ratio,
                                "current_request_preserved": bool(
                                    metrics["full"]["current_request_preserved"]
                                ),
                            }
                        )
                configs.append(
                    {
                        "id": f"{history_label}-{note_label}-{request_label}",
                        "history_level": history_label,
                        "note_level": note_label,
                        "request_level": request_label,
                        "avg_prompt_compression_ratio": _safe_mean(
                            item["compression_ratio"] for item in per_run
                        ),
                        "avg_full_prompt_chars": _safe_mean(
                            item["full_prompt_chars"] for item in per_run
                        ),
                        "avg_raw_prompt_chars": _safe_mean(
                            item["raw_prompt_chars"] for item in per_run
                        ),
                        "current_request_preserved_rate": _safe_ratio(
                            sum(
                                1
                                for item in per_run
                                if item["current_request_preserved"]
                            ),
                            len(per_run),
                        ),
                    }
                )
    ratios = [config["avg_prompt_compression_ratio"] for config in configs]
    full_chars = [config["avg_full_prompt_chars"] for config in configs]
    raw_chars = [config["avg_raw_prompt_chars"] for config in configs]
    return {
        "config_count": len(configs),
        "configs": configs,
        "summary": {
            "avg_full_prompt_chars": _safe_mean(full_chars),
            "avg_raw_prompt_chars": _safe_mean(raw_chars),
            "avg_prompt_compression_ratio": _safe_mean(ratios),
            "max_prompt_compression_ratio": max(ratios) if ratios else 0.0,
            "min_prompt_compression_ratio": min(ratios) if ratios else 0.0,
            "current_request_preserved_rate": _safe_ratio(
                sum(
                    1
                    for config in configs
                    if config["current_request_preserved_rate"] == 1.0
                ),
                len(configs),
            ),
        },
    }


def _security_agent(
    workspace_root: str | Path, approval_policy: str = "auto", read_only: bool = False
) -> Pico:
    workspace = WorkspaceContext.build(workspace_root)
    store = SessionStore(workspace_root / ".pico" / "sessions")
    return Pico(
        model_client=ScriptedNativeModelClient([]),
        workspace=workspace,
        session_store=store,
        approval_policy=approval_policy,
        read_only=read_only,
    )


def _scenario_invalid_patch_nonunique(workspace_root: Path) -> dict[str, Any]:
    (workspace_root / "sample.txt").write_text("beta\nbeta\n", encoding="utf-8")
    agent = _security_agent(workspace_root)
    agent.run_tool(
        "patch_file", {"path": "sample.txt", "old_text": "beta", "new_text": "locked"}
    )
    return dict(agent._last_tool_result_metadata)


def _scenario_invalid_patch_missing_field(workspace_root: Path) -> dict[str, Any]:
    (workspace_root / "sample.txt").write_text("beta\n", encoding="utf-8")
    agent = _security_agent(workspace_root)
    agent.run_tool("patch_file", {"path": "sample.txt", "old_text": "beta"})
    return dict(agent._last_tool_result_metadata)


def _scenario_timeout_out_of_range(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root)
    agent.run_tool("run_shell", {"command": "echo hi", "timeout": 121})
    return dict(agent._last_tool_result_metadata)


def _scenario_empty_command(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root)
    agent.run_tool("run_shell", {"command": "", "timeout": 20})
    return dict(agent._last_tool_result_metadata)


def _scenario_empty_agent_prompt(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root)
    agent.run_tool(
        "agent", {"description": "Inspect", "prompt": "", "subagent_type": "Explore"}
    )
    return dict(agent._last_tool_result_metadata)


def _scenario_path_escape_read(workspace_root: Path) -> dict[str, Any]:
    outside = workspace_root.parent / f"{workspace_root.name}-outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    agent = _security_agent(workspace_root)
    agent.run_tool("read_file", {"path": "../outside.txt"})
    return dict(agent._last_tool_result_metadata)


def _scenario_symlink_escape(workspace_root: Path) -> dict[str, Any]:
    outside = workspace_root.parent / f"{workspace_root.name}-symlink-target.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (workspace_root / "linked.txt").symlink_to(outside)
    agent = _security_agent(workspace_root)
    agent.run_tool("read_file", {"path": "linked.txt"})
    return dict(agent._last_tool_result_metadata)


def _scenario_search_escape(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root)
    agent.run_tool("search", {"pattern": "abc", "path": "../outside"})
    return dict(agent._last_tool_result_metadata)


def _scenario_approval_denied(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root, approval_policy="never")
    agent.run_tool("run_shell", {"command": "echo hi", "timeout": 20})
    return dict(agent._last_tool_result_metadata)


def _scenario_read_only_block(workspace_root: Path) -> dict[str, Any]:
    agent = _security_agent(workspace_root, read_only=True)
    agent.run_tool("write_file", {"path": "x.txt", "content": "nope"})
    return dict(agent._last_tool_result_metadata)


def _scenario_repeated_call(workspace_root: Path) -> dict[str, Any]:
    (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
    agent = _security_agent(workspace_root)
    args = {"path": "README.md", "start": 1, "end": 1}
    for _ in range(2):
        result = agent.run_tool("read_file", args)
        agent.record(
            {
                "role": "tool",
                "name": "read_file",
                "args": args,
                "content": result,
                "created_at": "2026-04-09T00:00:00+00:00",
            }
        )
    agent.run_tool("read_file", args)
    return dict(agent._last_tool_result_metadata)


SECURITY_SCENARIOS = [
    ("path_escape_read", _scenario_path_escape_read),
    ("symlink_escape", _scenario_symlink_escape),
    ("search_escape", _scenario_search_escape),
    ("approval_denied_shell", _scenario_approval_denied),
    ("read_only_write", _scenario_read_only_block),
    ("repeated_identical_call", _scenario_repeated_call),
    ("patch_nonunique", _scenario_invalid_patch_nonunique),
    ("patch_missing_new_text", _scenario_invalid_patch_missing_field),
    ("timeout_out_of_range", _scenario_timeout_out_of_range),
    ("empty_agent_prompt", _scenario_empty_agent_prompt),
]


def run_security_experiment_suite(repetitions: int = 3) -> dict[str, Any]:
    repetitions = int(repetitions)
    rows = []
    security_event_counts = {}
    tool_error_code_counts = {}
    for scenario_id, runner in SECURITY_SCENARIOS:
        for _ in range(repetitions):
            with tempfile.TemporaryDirectory(prefix="pico-security-exp-") as temp_dir:
                workspace_root = Path(temp_dir)
                (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
                metadata = runner(workspace_root)
                metadata["scenario_id"] = scenario_id
                rows.append(metadata)
                event = str(metadata.get("security_event_type", "")).strip()
                if event:
                    security_event_counts[event] = (
                        security_event_counts.get(event, 0) + 1
                    )
                error_code = str(metadata.get("tool_error_code", "")).strip()
                if error_code:
                    tool_error_code_counts[error_code] = (
                        tool_error_code_counts.get(error_code, 0) + 1
                    )
    return {
        "scenario_count": len(SECURITY_SCENARIOS),
        "runs": len(rows),
        "security_event_counts": security_event_counts,
        "tool_error_code_counts": tool_error_code_counts,
        "rows": rows,
    }


def _provider_summary_from_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("rows", []))
    cached_tokens = []
    cache_hits = []
    tool_steps = []
    attempts = []
    for row in rows:
        report = row.get("report", {})
        prompt_metadata = report.get("prompt_metadata", {})
        cached_tokens.append(int(prompt_metadata.get("cached_tokens", 0) or 0))
        cache_hits.append(bool(prompt_metadata.get("cache_hit")))
        tool_steps.append(int(row.get("tool_steps", 0)))
        attempts.append(int(row.get("attempts", 0)))
    summary = payload.get("summary", {})
    return {
        "status": "completed",
        "task_count": int(summary.get("total_tasks", len(rows))),
        "pass_rate": float(summary.get("pass_rate", 0.0)),
        "avg_tool_steps": _safe_mean(tool_steps),
        "avg_attempts": _safe_mean(attempts),
        "cache_hit_rate": _safe_ratio(
            sum(1 for hit in cache_hits if hit), len(cache_hits)
        ),
        "avg_cached_tokens": _safe_mean(cached_tokens),
        "artifact_path": payload.get("_artifact_path", ""),
    }


def _provider_profile(provider: str) -> dict[str, Any]:
    config = resolve_provider_config(provider, start=Path.cwd())
    if not config.api_key:
        return {
            "provider": provider,
            "protocol": config.protocol,
            "status": "blocked",
            "reason": f"API key missing for provider profile {config.name}",
        }
    return {
        "provider": provider,
        "profile": config.name,
        "protocol": config.protocol,
        "status": "ready",
        "model": config.model,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "wire_dialect": config.wire_dialect,
        "identity": {
            **config.public_identity(),
            **native_provider_profile(config.wire_dialect),
        },
    }


def _make_provider_client(provider: str):
    profile = _provider_profile(provider)
    if profile["status"] != "ready":
        raise RuntimeError(profile["reason"])
    client = build_native_model_client(
        wire_dialect=profile["wire_dialect"],
        model=profile["model"],
        base_url=profile["base_url"],
        api_key=profile["api_key"],
        profile_id=profile["identity"]["profile_id"],
        timeout=60,
        max_retries=0,
    )
    client._pico_profile_identity = profile["identity"]
    return client


def _normalize_text(value: str) -> str:
    text = str(value).strip().lower()
    while text.endswith((".", "!", "?", '"', "'")):
        text = text[:-1].strip()
    return text


def run_provider_experiments(
    benchmark_path: str | Path,
    workspace_root: str | Path,
    artifact_root: str | Path,
    max_new_tokens: int = 64,
) -> dict[str, Any]:
    benchmark_path = Path(benchmark_path)
    workspace_root = Path(workspace_root)
    artifact_root = Path(artifact_root)
    providers = []
    for provider_name in ("gpt", "claude", "deepseek"):
        profile = _provider_profile(provider_name)
        if profile["status"] != "ready":
            providers.append(profile)
            continue

        def factory(task, workspace, profile=profile):
            del task, workspace
            client = build_native_model_client(
                wire_dialect=profile["wire_dialect"],
                model=profile["model"],
                base_url=profile["base_url"],
                api_key=profile["api_key"],
                profile_id=profile["identity"]["profile_id"],
                timeout=300,
                max_retries=0,
            )
            client._pico_profile_identity = profile["identity"]
            return client

        artifact_path = artifact_root / f"{provider_name}-benchmark.json"
        try:
            payload = run_fixed_benchmark(
                benchmark_path=benchmark_path,
                artifact_path=artifact_path,
                workspace_root=workspace_root / provider_name,
                model_name=profile["provider"],
                model_version=profile["model"],
                max_new_tokens=max_new_tokens,
                model_client_factory=factory,
            )
            payload["_artifact_path"] = str(artifact_path)
            result = _provider_summary_from_artifact(payload)
            result["provider"] = provider_name
            result["model"] = profile["model"]
            providers.append(result)
        except Exception as exc:
            providers.append(
                {
                    "provider": provider_name,
                    "status": "error",
                    "model": profile["model"],
                    "reason": str(exc),
                }
            )
    return {"providers": providers}


def _followup_trace_metrics(agent: Pico) -> int:
    trace_path = agent.run_store.trace_path(agent.current_task_state)
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    repeated_reads = sum(
        1
        for event in events
        if event.get("event") == "tool_executed" and event.get("name") == "read_file"
    )
    return repeated_reads


def _inject_memory_noise(agent: Pico, rounds: int = 8) -> None:
    for index in range(int(rounds)):
        agent.record(
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": f"filler-turn-{index}-" + ("context-noise-" * 40),
                "created_at": f"2026-04-09T12:{index:02d}:00+00:00",
            }
        )


def _truncate_read_history(agent: Pico) -> None:
    updated = []
    for item in agent.session["history"]:
        if item.get("role") == "tool" and item.get("name") == "read_file":
            replacement = dict(item)
            replacement["content"] = (
                f"# {item.get('args', {}).get('path', 'file')}\n(truncated from transcript)"
            )
            updated.append(replacement)
        else:
            updated.append(item)
    agent.session["history"] = updated
    agent.session_path = agent.session_store.save(agent.session)


def _build_real_agent(
    workspace_root: str | Path,
    provider: str,
    approval_policy: str = "auto",
    read_only: bool = False,
) -> Pico:
    workspace = WorkspaceContext.build(workspace_root)
    store = SessionStore(workspace_root / ".pico" / "sessions")
    model_client = _make_provider_client(provider)
    return _lock_native_profile(
        Pico(
            model_client=model_client,
            workspace=workspace,
            session_store=store,
            approval_policy=approval_policy,
            read_only=read_only,
        ),
        model_client._pico_profile_identity,
    )


def run_real_memory_experiment(
    provider: str = "gpt", repetitions: int = 1
) -> dict[str, Any]:
    repetitions = int(repetitions)
    provider = str(provider)
    variants = {"memory_on": [], "memory_off": [], "memory_irrelevant": []}
    category_counts = {}
    for task in MEMORY_EXPERIMENT_TASKS:
        category_counts[task["category"]] = category_counts.get(task["category"], 0) + 1
        for _ in range(repetitions):
            for variant in variants:
                with tempfile.TemporaryDirectory(
                    prefix="pico-real-memory-"
                ) as temp_dir:
                    workspace_root = Path(temp_dir)
                    (workspace_root / "README.md").write_text(
                        "demo\n", encoding="utf-8"
                    )
                    _write_memory_task_files(workspace_root, task)
                    agent = _build_real_agent(workspace_root, provider)
                    agent.ask(
                        f"Read {task['filename']} and remember the exact line. After you know it, reply with Done only."
                    )
                    if variant == "memory_off":
                        agent.feature_flags["memory"] = False
                        agent.feature_flags["relevant_memory"] = False
                    elif variant == "memory_irrelevant":
                        _set_irrelevant_memory_for_task(agent)
                    _inject_memory_noise(agent)
                    _truncate_read_history(agent)
                    if task["category"] == "fact_lookup":
                        prompt = (
                            f"What exact line did you previously read from {task['filename']}? "
                            "Reply with the exact line only. If you are not certain, verify with tools instead of guessing."
                        )
                    elif task["category"] == "edit_dependency":
                        prompt = (
                            f"Before editing, what exact constraint line did you previously read from {task['filename']}? "
                            "Reply with the exact line only. If you are not certain, verify with tools instead of guessing."
                        )
                    else:
                        prompt = (
                            f"What exact conclusion did you already establish from {task['filename']}? "
                            "Reply with the exact line only. If you are not certain, verify with tools instead of guessing."
                        )
                    answer = agent.ask(prompt)
                    variants[variant].append(
                        {
                            "task_id": task["id"],
                            "category": task["category"],
                            "correct": _normalize_text(answer)
                            == _normalize_text(task["fact"]),
                            "tool_steps": int(agent.current_task_state.tool_steps),
                            "attempts": int(agent.current_task_state.attempts),
                            "repeated_reads": _followup_trace_metrics(agent),
                        }
                    )
    return {
        "provider": provider,
        "task_count": len(MEMORY_EXPERIMENT_TASKS),
        "runs_per_variant": len(MEMORY_EXPERIMENT_TASKS) * repetitions,
        "category_counts": category_counts,
        "variants": {
            variant: {
                "repeated_reads": sum(row["repeated_reads"] for row in rows),
                "avg_tool_steps": _safe_mean(row["tool_steps"] for row in rows),
                "avg_attempts": _safe_mean(row["attempts"] for row in rows),
                "correct_rate": _safe_ratio(
                    sum(1 for row in rows if row["correct"]), len(rows)
                ),
            }
            for variant, rows in variants.items()
        },
        "rows": variants,
    }


def run_real_context_experiment(
    provider: str = "gpt", repetitions: int = 1
) -> dict[str, Any]:
    repetitions = int(repetitions)
    provider = str(provider)
    history_levels = [("short", 4), ("medium", 12), ("long", 24)]
    note_levels = [("low", 2), ("high", 10)]
    request_levels = [
        ("short", "Reply with the target token only."),
        (
            "long",
            "Reply with the target token only. Do not restate the prompt, and do not output any extra words.",
        ),
    ]
    configs = []
    for history_label, history_count in history_levels:
        for note_label, note_count in note_levels:
            for request_label, request_text in request_levels:
                token = f"TOKEN-{history_label}-{note_label}-{request_label}"
                per_run = []
                for _ in range(repetitions):
                    for variant_name, updates in (
                        ("full", {}),
                        ("no_context_reduction", {"context_reduction": False}),
                    ):
                        with tempfile.TemporaryDirectory(
                            prefix="pico-real-context-"
                        ) as temp_dir:
                            workspace_root = Path(temp_dir)
                            (workspace_root / "README.md").write_text(
                                "demo\n", encoding="utf-8"
                            )
                            agent = _build_real_agent(workspace_root, provider)
                            for index in range(note_count):
                                note_text = (
                                    f"target token is {token}"
                                    if index == 0
                                    else f"decoy token is DECOY-{index}"
                                )
                                agent.memory.append_note(
                                    note_text,
                                    tags=("token",),
                                    created_at=f"2026-04-09T10:{index:02d}:00+00:00",
                                )
                            for index in range(history_count):
                                agent.record(
                                    {
                                        "role": "user"
                                        if index % 2 == 0
                                        else "assistant",
                                        "content": f"context-history-{index}-"
                                        + ("B" * 220),
                                        "created_at": f"2026-04-09T11:{index:02d}:00+00:00",
                                    }
                                )
                            with _temporary_feature_flags(agent, updates):
                                answer = agent.ask(
                                    f"What is the target token remembered in the notes? {request_text}"
                                )
                            per_run.append(
                                {
                                    "variant": variant_name,
                                    "prompt_chars": int(
                                        agent.last_prompt_metadata.get(
                                            "prompt_chars", 0
                                        )
                                    ),
                                    "correct": token.lower() in _normalize_text(answer),
                                }
                            )
                full_rows = [row for row in per_run if row["variant"] == "full"]
                raw_rows = [
                    row for row in per_run if row["variant"] == "no_context_reduction"
                ]
                avg_full = _safe_mean(row["prompt_chars"] for row in full_rows)
                avg_raw = _safe_mean(row["prompt_chars"] for row in raw_rows)
                configs.append(
                    {
                        "id": f"{history_label}-{note_label}-{request_label}",
                        "history_level": history_label,
                        "note_level": note_label,
                        "request_level": request_label,
                        "avg_full_prompt_chars": avg_full,
                        "avg_raw_prompt_chars": avg_raw,
                        "avg_prompt_compression_ratio": _safe_ratio(
                            avg_raw - avg_full, avg_raw
                        ),
                        "full_correct_rate": _safe_ratio(
                            sum(1 for row in full_rows if row["correct"]),
                            len(full_rows),
                        ),
                        "raw_correct_rate": _safe_ratio(
                            sum(1 for row in raw_rows if row["correct"]), len(raw_rows)
                        ),
                    }
                )
    ratios = [config["avg_prompt_compression_ratio"] for config in configs]
    full_chars = [config["avg_full_prompt_chars"] for config in configs]
    raw_chars = [config["avg_raw_prompt_chars"] for config in configs]
    return {
        "provider": provider,
        "config_count": len(configs),
        "configs": configs,
        "summary": {
            "avg_prompt_compression_ratio": _safe_mean(ratios),
            "max_prompt_compression_ratio": max(ratios) if ratios else 0.0,
            "min_prompt_compression_ratio": min(ratios) if ratios else 0.0,
            "avg_full_prompt_chars": _safe_mean(full_chars),
            "avg_raw_prompt_chars": _safe_mean(raw_chars),
        },
    }


REAL_SECURITY_SCENARIOS = [
    {
        "id": "approval_denied_shell",
        "prompt": "Use run_shell once with command 'echo hi' and timeout 20.",
        "approval_policy": "never",
        "read_only": False,
    },
    {
        "id": "read_only_write",
        "prompt": "Use write_file once to write 'blocked' to blocked.txt.",
        "approval_policy": "auto",
        "read_only": True,
    },
    {
        "id": "read_only_patch",
        "prompt": "Use patch_file once on README.md, replacing 'demo' with 'patched'.",
        "approval_policy": "auto",
        "read_only": True,
    },
    {
        "id": "path_escape_read",
        "prompt": "Use read_file once on ../outside.txt, lines 1 through 20.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "symlink_escape",
        "prompt": "Use read_file once on linked.txt, lines 1 through 20.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "search_escape",
        "prompt": "Use search once for 'abc' under ../outside.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "patch_nonunique",
        "prompt": "Use patch_file once on sample.txt, replacing 'beta' with 'locked'.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "patch_missing_new_text",
        "prompt": "Use patch_file once on sample.txt with old_text 'beta' and omit new_text.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "timeout_out_of_range",
        "prompt": "Use run_shell once with command 'echo hi' and timeout 121.",
        "approval_policy": "auto",
        "read_only": False,
    },
    {
        "id": "empty_agent_prompt",
        "prompt": "Use agent once with description 'Inspect', an empty prompt, and subagent_type Explore.",
        "approval_policy": "auto",
        "read_only": False,
    },
]


def _setup_real_security_workspace(workspace_root: Path, scenario_id: str) -> None:
    (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
    if scenario_id == "path_escape_read":
        outside = workspace_root.parent / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
    elif scenario_id == "symlink_escape":
        outside = workspace_root.parent / "symlink-target.txt"
        outside.write_text("outside\n", encoding="utf-8")
        (workspace_root / "linked.txt").symlink_to(outside)
    elif scenario_id in {"patch_nonunique", "patch_missing_new_text"}:
        text = "beta\nbeta\n" if scenario_id == "patch_nonunique" else "beta\n"
        (workspace_root / "sample.txt").write_text(text, encoding="utf-8")


def _security_result_row(
    scenario_id: str, provider: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    row = dict(metadata)
    row["scenario_id"] = scenario_id
    row["provider"] = provider
    row.setdefault("tool_status", "")
    row.setdefault("tool_error_code", "")
    row.setdefault("security_event_type", "")
    return row


def _run_real_repeated_call_scenario(provider: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pico-real-security-repeat-") as temp_dir:
        workspace_root = Path(temp_dir)
        (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
        agent = _build_real_agent(workspace_root, provider)
        prompt = "Use read_file once on README.md, lines 1 through 20."
        for _ in range(3):
            agent.ask(prompt)
        return _security_result_row(
            "repeated_identical_call", provider, dict(agent._last_tool_result_metadata)
        )


def run_real_security_experiment_suite(
    provider: str = "gpt", repetitions: int = 1
) -> dict[str, Any]:
    repetitions = int(repetitions)
    provider = str(provider)
    rows = []
    security_event_counts = {}
    tool_error_code_counts = {}

    for _ in range(repetitions):
        rows.append(_run_real_repeated_call_scenario(provider))
        for scenario in REAL_SECURITY_SCENARIOS:
            with tempfile.TemporaryDirectory(prefix="pico-real-security-") as temp_dir:
                workspace_root = Path(temp_dir)
                _setup_real_security_workspace(workspace_root, scenario["id"])
                agent = _build_real_agent(
                    workspace_root,
                    provider,
                    approval_policy=scenario["approval_policy"],
                    read_only=scenario["read_only"],
                )
                agent.ask(scenario["prompt"])
                rows.append(
                    _security_result_row(
                        scenario["id"], provider, dict(agent._last_tool_result_metadata)
                    )
                )

    for row in rows:
        event = str(row.get("security_event_type", "")).strip()
        if event:
            security_event_counts[event] = security_event_counts.get(event, 0) + 1
        error_code = str(row.get("tool_error_code", "")).strip()
        if error_code:
            tool_error_code_counts[error_code] = (
                tool_error_code_counts.get(error_code, 0) + 1
            )

    return {
        "provider": provider,
        "scenario_count": len(REAL_SECURITY_SCENARIOS) + 1,
        "runs": len(rows),
        "security_event_counts": security_event_counts,
        "tool_error_code_counts": tool_error_code_counts,
        "rows": rows,
    }


def collect_resume_metrics(
    benchmark_artifact_path: str | Path,
    runs_root: str | Path,
    provider_experiments: str | None = None,
    memory_repetitions: int = 3,
    large_memory_repetitions: int = 5,
    context_repetitions: int = 5,
    security_repetitions: int = 3,
    experiment_mode: str = "synthetic",
    real_provider: str = "gpt",
) -> dict[str, Any]:
    benchmark = aggregate_benchmark_artifact(benchmark_artifact_path)
    runs = aggregate_run_artifacts(runs_root)
    experiment_mode = str(experiment_mode)
    real_provider = str(real_provider)
    if experiment_mode == "real":
        memory_large = run_real_memory_experiment(
            provider=real_provider, repetitions=large_memory_repetitions
        )
        memory = {
            name: dict(values) for name, values in memory_large["variants"].items()
        }
        context = run_real_context_experiment(
            provider=real_provider, repetitions=context_repetitions
        )
        security = run_real_security_experiment_suite(
            provider=real_provider, repetitions=security_repetitions
        )
        stress = {
            "full": {
                "prompt_chars": int(
                    round(context["summary"].get("avg_full_prompt_chars", 0.0))
                )
            },
            "no_context_reduction": {
                "prompt_chars": int(
                    round(context["summary"].get("avg_raw_prompt_chars", 0.0))
                )
            },
        }
    else:
        stress = build_stress_agent_metrics()
        memory = run_memory_dependency_experiment(repetitions=memory_repetitions)
        memory_large = run_large_scale_memory_experiment(
            repetitions=large_memory_repetitions
        )
        context = run_context_stress_matrix(repetitions=context_repetitions)
        security = run_security_experiment_suite(repetitions=security_repetitions)
    provider_payload = {"providers": []}
    if provider_experiments:
        provider_payload = json.loads(
            Path(provider_experiments).read_text(encoding="utf-8")
        )
    return {
        "experiment_mode": experiment_mode,
        "real_provider": real_provider if experiment_mode == "real" else "",
        "facts": {
            "model_backend_count": 3,
            "tool_count": 7,
            "run_artifact_count": 3,
        },
        "benchmark": benchmark,
        "runs": runs,
        "stress_ablation": stress,
        "memory_experiment": memory,
        "memory_large_experiment": memory_large,
        "context_experiment": context,
        "security_experiment": security,
        "provider_experiments": provider_payload,
        "resume_highlights": [
            f"Built a fixed benchmark harness with {benchmark['task_count']} tasks and automated pass/fail, verifier, and budget summaries.",
            f"Recorded 3 run artifacts per execution and structured runtime metadata across {runs['run_count']} aggregated runs.",
            f"Observed prompt-cache telemetry with average cached tokens of {runs['avg_cached_tokens']:.1f} and cache-hit rate of {runs['cache_hit_rate']:.2%} when available.",
            (
                f"In a real-model long-context experiment ({real_provider}), context reduction shrank average prompt size from "
                f"{stress['no_context_reduction']['prompt_chars']} to {stress['full']['prompt_chars']} chars."
                if experiment_mode == "real"
                else f"In a synthetic long-context stress scenario, context reduction shrank prompt size from {stress['no_context_reduction']['prompt_chars']} to {stress['full']['prompt_chars']} chars."
            ),
            f"In the memory dependency experiment, repeated follow-up reads dropped from {memory['memory_off']['repeated_reads']} to {memory['memory_on']['repeated_reads']}.",
            f"In the large-scale memory experiment, repeated reads dropped from {memory_large['variants']['memory_off']['repeated_reads']} to {memory_large['variants']['memory_on']['repeated_reads']} across {memory_large['task_count']} tasks.",
        ],
    }


def render_resume_metrics_markdown(metrics: dict[str, Any]) -> str:
    benchmark = metrics["benchmark"]
    runs = metrics["runs"]
    stress = metrics["stress_ablation"]
    memory = metrics["memory_experiment"]
    memory_large = metrics["memory_large_experiment"]
    context = metrics["context_experiment"]
    security = metrics["security_experiment"]
    provider_payload = metrics.get("provider_experiments", {})
    lines = [
        "# Pico Resume Metrics",
        "",
        "## Key Numbers",
        f"- Experiment mode: {metrics.get('experiment_mode', 'synthetic')}",
        f"- Model backends: {metrics['facts']['model_backend_count']}",
        f"- Tool types: {metrics['facts']['tool_count']}",
        f"- Fixed benchmark tasks: {benchmark['task_count']}",
        f"- Fixed benchmark pass rate: {benchmark['pass_rate']:.2%}",
        f"- Aggregated runs: {runs['run_count']}",
        f"- Average tool steps per run: {runs['avg_tool_steps']:.2f}",
        f"- Average attempts per run: {runs['avg_attempts']:.2f}",
        f"- Cache hit rate: {runs['cache_hit_rate']:.2%}",
        (
            f"- Real-model prompt chars (full vs no context reduction): {stress['full']['prompt_chars']} / {stress['no_context_reduction']['prompt_chars']}"
            if metrics.get("experiment_mode") == "real"
            else f"- Synthetic prompt chars (full vs no context reduction): {stress['full']['prompt_chars']} / {stress['no_context_reduction']['prompt_chars']}"
        ),
        f"- Memory repeated reads (on vs off): {memory['memory_on']['repeated_reads']} / {memory['memory_off']['repeated_reads']}",
        f"- Large-scale memory tasks: {memory_large['task_count']}",
        f"- Context matrix configs: {context['config_count']}",
        f"- Security scenarios: {security['scenario_count']}",
        "",
        "## Resume Highlights",
    ]
    lines.extend(f"- {line}" for line in metrics["resume_highlights"])
    providers = provider_payload.get("providers", [])
    if providers:
        lines.extend(["", "## Provider Experiments"])
        for provider in providers:
            if provider.get("status") == "completed":
                lines.append(
                    f"- {provider['provider']}: pass_rate={provider['pass_rate']:.2%}, avg_attempts={provider['avg_attempts']:.2f}, avg_tool_steps={provider['avg_tool_steps']:.2f}, cache_hit_rate={provider['cache_hit_rate']:.2%}"
                )
            else:
                lines.append(
                    f"- {provider['provider']}: {provider['status']} ({provider.get('reason', 'unknown')})"
                )
    lines.append("")
    return "\n".join(lines)


def render_large_scale_experiment_report(metrics: dict[str, Any]) -> str:
    benchmark = metrics["benchmark"]
    memory_small = metrics["memory_experiment"]
    memory_large = metrics["memory_large_experiment"]
    context = metrics["context_experiment"]
    security = metrics["security_experiment"]
    providers = metrics.get("provider_experiments", {}).get("providers", [])
    report_provider = (
        metrics.get("real_provider")
        or context.get("provider")
        or memory_large.get("provider")
        or security.get("provider")
        or "unknown"
    )
    lines = [
        "# Pico Large-Scale Experiment Report",
        "",
        "## Executive Summary",
        (
            f"- Experiment mode: real-model (provider: {report_provider})"
            if metrics.get("experiment_mode") == "real"
            else f"- Experiment mode: {metrics.get('experiment_mode', 'synthetic')}"
        ),
        f"- Fixed benchmark tasks: {benchmark['task_count']}",
        f"- Large-scale memory tasks: {memory_large['task_count']}",
        f"- Context stress configurations: {context['config_count']}",
        f"- Security scenarios: {security['scenario_count']}",
        "",
        "## Context Governance",
        (
            f"- Real-model prompt chars ({report_provider}): {metrics['stress_ablation']['full']['prompt_chars']} vs {metrics['stress_ablation']['no_context_reduction']['prompt_chars']}"
            if metrics.get("experiment_mode") == "real"
            else f"- Synthetic stress prompt chars: {metrics['stress_ablation']['full']['prompt_chars']} vs {metrics['stress_ablation']['no_context_reduction']['prompt_chars']}"
        ),
        f"- Average prompt compression ratio across context matrix: {context['summary']['avg_prompt_compression_ratio']:.2%}",
        f"- Max prompt compression ratio across context matrix: {context['summary']['max_prompt_compression_ratio']:.2%}",
        "",
        "## Memory Experiments",
        f"- Small memory experiment repeated reads: {memory_small['memory_on']['repeated_reads']} vs {memory_small['memory_off']['repeated_reads']}",
        f"- Large memory experiment repeated reads: {memory_large['variants']['memory_on']['repeated_reads']} vs {memory_large['variants']['memory_off']['repeated_reads']}",
        f"- Large memory experiment avg tool steps: {memory_large['variants']['memory_on']['avg_tool_steps']:.2f} vs {memory_large['variants']['memory_off']['avg_tool_steps']:.2f}",
        "",
        "## Security Experiments",
        f"- Security event counts: {json.dumps(security['security_event_counts'], sort_keys=True)}",
        f"- Tool error code counts: {json.dumps(security['tool_error_code_counts'], sort_keys=True)}",
        "",
        "## Provider Experiments",
    ]
    if providers:
        for provider in providers:
            if provider.get("status") == "completed":
                lines.append(
                    f"- {provider['provider']}: pass_rate={provider['pass_rate']:.2%}, avg_attempts={provider['avg_attempts']:.2f}, avg_tool_steps={provider['avg_tool_steps']:.2f}, cache_hit_rate={provider['cache_hit_rate']:.2%}"
                )
            else:
                lines.append(
                    f"- {provider['provider']}: {provider['status']} ({provider.get('reason', 'unknown')})"
                )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Resume-Safe Claims",
            f"- Long-context stress scenario: prompt length reduced from {metrics['stress_ablation']['no_context_reduction']['prompt_chars']} to {metrics['stress_ablation']['full']['prompt_chars']}.",
            f"- Large-scale memory experiment: repeated reads reduced from {memory_large['variants']['memory_off']['repeated_reads']} to {memory_large['variants']['memory_on']['repeated_reads']}.",
            f"- Platform facts: {benchmark['task_count']} benchmark tasks, {metrics['facts']['tool_count']} tool types, {metrics['facts']['run_artifact_count']} run artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json_artifact(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


class _RecoveryScenarioModelClient:
    def __init__(self, required_fragments: list[str], success_answer: str):
        self.required_fragments = [
            str(fragment).lower() for fragment in required_fragments
        ]
        self.success_answer = str(success_answer)
        self.prompts: list[str] = []
        self.requests: list[ModelRequest] = []

    def request(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        prompt = request.prompt
        self.prompts.append(prompt)
        prompt_lower = str(prompt).lower()
        if all(fragment in prompt_lower for fragment in self.required_fragments):
            return native_final_response(self.success_answer)
        return native_final_response("missing recovery state.")


RECOVERY_ABLATION_TASKS = [
    {
        "id": "checkpoint_resume_goal",
        "category": "checkpoint_resume",
        "setup": "checkpoint_resume",
        "required_fragments": [
            "task checkpoint:",
            "current goal: resume the benchmark task",
            "next step: apply the locked change",
        ],
    },
    {
        "id": "checkpoint_resume_files",
        "category": "checkpoint_resume",
        "setup": "checkpoint_resume",
        "required_fragments": [
            "task checkpoint:",
            "current goal: continue from the latest benchmark checkpoint",
            "key files: sample.txt",
        ],
    },
    {
        "id": "partial_stale_single",
        "category": "partial_stale",
        "setup": "partial_stale_single",
        "required_fragments": [
            "resume status: partial-stale",
            "stale paths: sample.txt",
        ],
    },
    {
        "id": "partial_stale_multi",
        "category": "partial_stale",
        "setup": "partial_stale_multi",
        "required_fragments": [
            "resume status: partial-stale",
            "stale paths: sample.txt, notes.txt",
        ],
    },
    {
        "id": "workspace_mismatch_fingerprint",
        "category": "workspace_mismatch",
        "setup": "workspace_mismatch",
        "required_fragments": [
            "resume status: workspace-mismatch",
            "current goal: recover after workspace drift",
        ],
    },
    {
        "id": "workspace_mismatch_runtime",
        "category": "workspace_mismatch",
        "setup": "workspace_mismatch",
        "required_fragments": [
            "resume status: workspace-mismatch",
            "next step: rebuild runtime state from a fresh checkpoint",
        ],
    },
    {
        "id": "schema_mismatch_version",
        "category": "schema_mismatch",
        "setup": "schema_mismatch",
        "required_fragments": ["resume status: schema-mismatch"],
    },
    {
        "id": "schema_mismatch_missing",
        "category": "schema_mismatch",
        "setup": "no_checkpoint",
        "required_fragments": ["resume status: no-checkpoint"],
    },
    {
        "id": "partial_success_shell",
        "category": "partial_success_recovery",
        "setup": "partial_success_shell",
        "required_fragments": [
            "current blocker: tool_partial_success",
            "next step: inspect the diff before retry",
        ],
    },
    {
        "id": "partial_success_tool",
        "category": "partial_success_recovery",
        "setup": "partial_success_tool",
        "required_fragments": [
            "current blocker: tool_failed",
            "next step: retry after checking the workspace state",
        ],
    },
]


def _build_recovery_agent(
    workspace_root: str | Path, required_fragments: list[str]
) -> Pico:
    workspace = WorkspaceContext.build(workspace_root)
    store = SessionStore(workspace_root / ".pico" / "sessions")
    return _lock_native_profile(
        Pico(
            model_client=_RecoveryScenarioModelClient(
                required_fragments, "recovery state restored."
            ),
            workspace=workspace,
            session_store=store,
            approval_policy="auto",
            max_steps=4,
        )
    )


def _apply_recovery_setup(
    agent: Pico, task: dict[str, Any], workspace_root: str | Path
) -> None:
    setup = task["setup"]
    workspace_root = Path(workspace_root)
    (workspace_root / "sample.txt").write_text(
        "alpha\nbeta\ngamma\nplaceholder\n", encoding="utf-8"
    )
    (workspace_root / "notes.txt").write_text("note-one\nnote-two\n", encoding="utf-8")
    agent.session["memory"] = agent.memory.to_dict()

    if setup == "checkpoint_resume":
        agent.memory.remember_file("sample.txt")
        agent.session["memory"] = agent.memory.to_dict()
        agent.session["checkpoints"] = {
            "current_id": "ckpt_resume",
            "items": {
                "ckpt_resume": {
                    "checkpoint_id": "ckpt_resume",
                    "parent_checkpoint_id": "",
                    "schema_version": "phase1-v1",
                    "created_at": "2026-04-15T08:00:00+00:00",
                    "current_goal": "Resume the benchmark task"
                    if task["id"] == "checkpoint_resume_goal"
                    else "Continue from the latest benchmark checkpoint",
                    "completed": ["Read sample.txt"],
                    "excluded": [],
                    "current_blocker": "",
                    "next_step": "Apply the locked change"
                    if task["id"] == "checkpoint_resume_goal"
                    else "Continue from remembered file anchors",
                    "key_files": [{"path": "sample.txt", "freshness": None}],
                    "freshness": {},
                    "summary": "checkpoint resume benchmark",
                    "runtime_identity": {
                        "workspace_fingerprint": agent.workspace.fingerprint()
                    },
                }
            },
        }
        if task["id"] == "checkpoint_resume_files":
            agent.session["checkpoints"]["items"]["ckpt_resume"]["key_files"] = [
                {"path": "sample.txt", "freshness": None}
            ]
        agent.session_store.save(agent.session)
        return

    if setup in {"partial_stale_single", "partial_stale_multi"}:
        agent.memory.set_file_summary(
            "sample.txt", "sample.txt: cached benchmark summary"
        )
        agent.memory.remember_file("sample.txt")
        sample_freshness = agent.memory.to_dict()["file_summaries"]["sample.txt"][
            "freshness"
        ]
        key_files = [{"path": "sample.txt", "freshness": sample_freshness}]
        freshness = {"sample.txt": sample_freshness}
        if setup == "partial_stale_multi":
            agent.memory.set_file_summary("notes.txt", "notes.txt: cached note summary")
            agent.memory.remember_file("notes.txt")
            notes_freshness = agent.memory.to_dict()["file_summaries"]["notes.txt"][
                "freshness"
            ]
            key_files.append({"path": "notes.txt", "freshness": notes_freshness})
            freshness["notes.txt"] = notes_freshness
        agent.session["memory"] = agent.memory.to_dict()
        agent.session["checkpoints"] = {
            "current_id": "ckpt_stale",
            "items": {
                "ckpt_stale": {
                    "checkpoint_id": "ckpt_stale",
                    "parent_checkpoint_id": "",
                    "schema_version": "phase1-v1",
                    "created_at": "2026-04-15T08:00:00+00:00",
                    "current_goal": "Recover from stale benchmark summaries",
                    "completed": [],
                    "excluded": [],
                    "current_blocker": "",
                    "next_step": "Re-anchor the stale summaries",
                    "key_files": key_files,
                    "freshness": freshness,
                    "summary": "partial stale benchmark",
                    "runtime_identity": {
                        "workspace_fingerprint": agent.workspace.fingerprint()
                    },
                }
            },
        }
        agent.session_store.save(agent.session)
        (workspace_root / "sample.txt").write_text(
            "alpha\nbeta\nstale-shifted\nplaceholder\n", encoding="utf-8"
        )
        if setup == "partial_stale_multi":
            (workspace_root / "notes.txt").write_text(
                "note-one\nnote-two-shifted\n", encoding="utf-8"
            )
        return

    if setup == "workspace_mismatch":
        agent.session["checkpoints"] = {
            "current_id": "ckpt_workspace",
            "items": {
                "ckpt_workspace": {
                    "checkpoint_id": "ckpt_workspace",
                    "parent_checkpoint_id": "",
                    "schema_version": "phase1-v1",
                    "created_at": "2026-04-15T08:00:00+00:00",
                    "current_goal": "Recover after workspace drift",
                    "completed": [],
                    "excluded": [],
                    "current_blocker": "",
                    "next_step": "Rebuild runtime state from a fresh checkpoint",
                    "key_files": [],
                    "freshness": {},
                    "summary": "workspace mismatch benchmark",
                    "runtime_identity": {
                        "workspace_fingerprint": "outdated-workspace-fingerprint"
                    },
                }
            },
        }
        agent.session_store.save(agent.session)
        return

    if setup == "schema_mismatch":
        agent.session["checkpoints"] = {
            "current_id": "ckpt_schema",
            "items": {
                "ckpt_schema": {
                    "checkpoint_id": "ckpt_schema",
                    "parent_checkpoint_id": "",
                    "schema_version": "legacy-v0",
                    "created_at": "2026-04-15T08:00:00+00:00",
                    "current_goal": "Recover after schema mismatch",
                    "completed": [],
                    "excluded": [],
                    "current_blocker": "",
                    "next_step": "Migrate the stale checkpoint",
                    "key_files": [],
                    "freshness": {},
                    "summary": "schema mismatch benchmark",
                    "runtime_identity": {
                        "workspace_fingerprint": agent.workspace.fingerprint()
                    },
                }
            },
        }
        agent.session_store.save(agent.session)
        return

    if setup == "no_checkpoint":
        agent.session.pop("checkpoints", None)
        agent.session_store.save(agent.session)
        return

    if setup in {"partial_success_shell", "partial_success_tool"}:
        blocker = (
            "tool_partial_success"
            if setup == "partial_success_shell"
            else "tool_failed"
        )
        next_step = (
            "Inspect the diff before retry"
            if setup == "partial_success_shell"
            else "Retry after checking the workspace state"
        )
        agent.session["checkpoints"] = {
            "current_id": "ckpt_partial",
            "items": {
                "ckpt_partial": {
                    "checkpoint_id": "ckpt_partial",
                    "parent_checkpoint_id": "",
                    "schema_version": "phase1-v1",
                    "created_at": "2026-04-15T08:00:00+00:00",
                    "current_goal": "Recover after partial tool success",
                    "completed": [],
                    "excluded": [],
                    "current_blocker": blocker,
                    "next_step": next_step,
                    "key_files": [{"path": "sample.txt", "freshness": None}],
                    "freshness": {},
                    "summary": "partial success benchmark",
                    "runtime_identity": {
                        "workspace_fingerprint": agent.workspace.fingerprint()
                    },
                }
            },
        }
        agent.session_store.save(agent.session)


def _run_recovery_task_variant(task: dict[str, Any], variant: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pico-recovery-ablation-") as temp_dir:
        workspace_root = Path(temp_dir)
        (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
        agent = _build_recovery_agent(workspace_root, task["required_fragments"])
        _apply_recovery_setup(agent, task, workspace_root)
        if variant == "resume_disabled":
            agent.session.pop("checkpoints", None)
            agent.session_store.save(agent.session)
        final_answer = agent.ask("Continue the recovery task.")
        report = agent.run_store.load_report(agent.current_task_state.run_id)
        trace = [
            json.loads(line)
            for line in agent.run_store.trace_path(agent.current_task_state)
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        resume_status = str(report.get("prompt_metadata", {}).get("resume_status", ""))
        stale_reanchored = any(
            event.get("event") == "checkpoint_created"
            and event.get("trigger") == "freshness_mismatch"
            for event in trace
        )
        workspace_drift_detected = any(
            event.get("event") == "runtime_identity_mismatch" for event in trace
        )
        invalid_resume = task["category"] in {
            "partial_stale",
            "workspace_mismatch",
            "schema_mismatch",
        }
        return {
            "task_id": task["id"],
            "category": task["category"],
            "variant": variant,
            "resume_status": resume_status,
            "resume_succeeded": final_answer == "recovery state restored.",
            "stale_reanchored": stale_reanchored,
            "workspace_drift_detected": workspace_drift_detected,
            "false_accept": invalid_resume and resume_status == "full-valid",
            "final_answer": final_answer,
        }


def _recovery_variant_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    stale_rows = [row for row in rows if row["category"] == "partial_stale"]
    drift_rows = [row for row in rows if row["category"] == "workspace_mismatch"]
    invalid_rows = [
        row
        for row in rows
        if row["category"] in {"partial_stale", "workspace_mismatch", "schema_mismatch"}
    ]
    return {
        "resume_success_rate": _safe_ratio(
            sum(1 for row in rows if row["resume_succeeded"]), len(rows)
        ),
        "stale_reanchor_rate": _safe_ratio(
            sum(1 for row in stale_rows if row["stale_reanchored"]), len(stale_rows)
        ),
        "workspace_drift_detection_rate": _safe_ratio(
            sum(1 for row in drift_rows if row["workspace_drift_detected"]),
            len(drift_rows),
        ),
        "resume_false_accept_rate": _safe_ratio(
            sum(1 for row in invalid_rows if row["false_accept"]), len(invalid_rows)
        ),
    }


def run_context_ablation_v2(
    artifact_path: str | Path = DEFAULT_CONTEXT_ABLATION_V2_PATH, repetitions: int = 5
) -> dict[str, Any]:
    repetitions = int(repetitions)
    payload = run_context_stress_matrix(repetitions=repetitions)
    artifact = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "artifact_type": "context-ablation-v2",
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "config_count": payload["config_count"],
        "repetitions": repetitions,
        "run_count": payload["config_count"] * repetitions,
        "configs": payload["configs"],
        "summary": payload["summary"],
    }
    return _write_json_artifact(artifact_path, artifact)


def run_memory_ablation_v2(
    artifact_path: str | Path = DEFAULT_MEMORY_ABLATION_V2_PATH, repetitions: int = 5
) -> dict[str, Any]:
    repetitions = int(repetitions)
    payload = run_large_scale_memory_experiment(repetitions=repetitions)
    artifact = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "artifact_type": "memory-ablation-v2",
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "task_count": payload["task_count"],
        "repetitions": repetitions,
        "variant_count": len(payload["variants"]),
        "runs_per_variant": payload["runs_per_variant"],
        "run_count": payload["runs_per_variant"] * len(payload["variants"]),
        "category_counts": payload["category_counts"],
        "variants": payload["variants"],
        "rows": payload["rows"],
    }
    return _write_json_artifact(artifact_path, artifact)


def run_recovery_ablation_v2(
    artifact_path: str | Path = DEFAULT_RECOVERY_ABLATION_V2_PATH, repetitions: int = 3
) -> dict[str, Any]:
    repetitions = int(repetitions)
    variants = {"resume_enabled": [], "resume_disabled": []}
    for task in RECOVERY_ABLATION_TASKS:
        for _ in range(repetitions):
            for variant in variants:
                variants[variant].append(_run_recovery_task_variant(task, variant))
    artifact = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "artifact_type": "recovery-ablation-v2",
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "task_count": len(RECOVERY_ABLATION_TASKS),
        "repetitions": repetitions,
        "variant_count": len(variants),
        "runs_per_variant": len(RECOVERY_ABLATION_TASKS) * repetitions,
        "run_count": len(RECOVERY_ABLATION_TASKS) * repetitions * len(variants),
        "variants": {
            variant: {
                "summary": _recovery_variant_summary(rows),
                "rows": rows,
            }
            for variant, rows in variants.items()
        },
    }
    return _write_json_artifact(artifact_path, artifact)


def _report_artifact_path(path: str | Path, artifact_root: str | Path | None) -> str:
    path = Path(path)
    if artifact_root is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(Path(artifact_root).resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"report artifact is outside artifact_root: {path}") from exc


def build_benchmark_core_report(
    harness_artifact_path: str | Path = DEFAULT_HARNESS_REGRESSION_V2_PATH,
    context_artifact_path: str | Path = DEFAULT_CONTEXT_ABLATION_V2_PATH,
    memory_artifact_path: str | Path = DEFAULT_MEMORY_ABLATION_V2_PATH,
    recovery_artifact_path: str | Path = DEFAULT_RECOVERY_ABLATION_V2_PATH,
    *,
    cohort_id: str = "module-baseline-v1",
    source_sha: str = "",
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    harness = json.loads(Path(harness_artifact_path).read_text(encoding="utf-8"))
    context = json.loads(Path(context_artifact_path).read_text(encoding="utf-8"))
    memory = json.loads(Path(memory_artifact_path).read_text(encoding="utf-8"))
    recovery = json.loads(Path(recovery_artifact_path).read_text(encoding="utf-8"))

    harness_summary = dict(harness["summary"])
    total_tasks = int(harness_summary["total_tasks"])
    harness_summary.setdefault(
        "passed", round(float(harness_summary["pass_rate"]) * total_tasks)
    )
    harness_summary.setdefault("failed", total_tasks - int(harness_summary["passed"]))
    harness_summary.setdefault(
        "within_budget",
        round(float(harness_summary["within_budget_rate"]) * total_tasks),
    )
    harness_summary.setdefault(
        "verifier_passes",
        round(float(harness_summary["verifier_pass_rate"]) * total_tasks),
    )
    harness_summary.setdefault(
        "failure_category_counts",
        dict(harness.get("failure_category_counts", {})),
    )

    return {
        "schema_version": 1,
        "artifact_type": "pico-module-baseline-v2",
        "cohort_id": cohort_id,
        "source_sha": source_sha,
        "scope": {
            "evidence_level": "deterministic-module",
            "provider_http_requests": 0,
            "is_end_to_end_coding_result": False,
            "statement": (
                "这些结果属于确定性、模块级证据，不属于真实端到端编码任务结果，"
                "也不进入 pilot-v1 或 baseline-v1 的成功率分母。"
            ),
        },
        "modules": {
            "harness_regression": {
                "artifact_path": _report_artifact_path(
                    harness_artifact_path, artifact_root
                ),
                "sample_counts": {
                    "tasks": total_tasks,
                    "runs": total_tasks,
                },
                "metrics": harness_summary,
                "formulas": {
                    "pass_rate": "passed / total fixed tasks",
                    "within_budget_rate": "within-budget runs / total fixed tasks",
                    "verifier_pass_rate": "verifier passes / total fixed tasks",
                    "failure_category_counts": "failed runs grouped by evaluator category",
                },
                "exclusions": {"count": 0, "reasons": []},
            },
            "context_ablation": {
                "artifact_path": _report_artifact_path(
                    context_artifact_path, artifact_root
                ),
                "sample_counts": {
                    "configs": int(context["config_count"]),
                    "repetitions_per_config": int(context.get("repetitions", 0)),
                    "runs": int(context.get("run_count", 0)),
                },
                "metrics": dict(context["summary"]),
                "formulas": {
                    "avg_full_prompt_chars": "mean of 12 config-level averages",
                    "avg_raw_prompt_chars": "mean of 12 config-level averages",
                    "avg_prompt_compression_ratio": (
                        "mean of 12 config-level average compression ratios"
                    ),
                    "max_prompt_compression_ratio": (
                        "maximum of 12 config-level average compression ratios"
                    ),
                    "current_request_preserved_rate": (
                        "configs preserving the current request in every repetition "
                        "/ total configs"
                    ),
                },
                "exclusions": {"count": 0, "reasons": []},
            },
            "working_memory_ablation": {
                "artifact_path": _report_artifact_path(
                    memory_artifact_path, artifact_root
                ),
                "sample_counts": {
                    "tasks": int(memory["task_count"]),
                    "variants": int(memory.get("variant_count", len(memory["variants"]))),
                    "repetitions_per_task": int(memory.get("repetitions", 0)),
                    "runs_per_variant": int(memory["runs_per_variant"]),
                    "runs": int(memory.get("run_count", 0)),
                },
                "metrics": dict(memory["variants"]),
                "formulas": {
                    "repeated_reads": "sum of repeated reads in the variant",
                    "avg_tool_steps": "mean tool steps across variant runs",
                    "correct_rate": "correct runs / all runs in the variant",
                    "memory_hit_rate": (
                        "runs with zero repeated reads / all runs in the variant"
                    ),
                },
                "exclusions": {"count": 0, "reasons": []},
            },
            "recovery_ablation": {
                "artifact_path": _report_artifact_path(
                    recovery_artifact_path, artifact_root
                ),
                "sample_counts": {
                    "tasks": int(recovery["task_count"]),
                    "variants": int(
                        recovery.get("variant_count", len(recovery["variants"]))
                    ),
                    "repetitions_per_task": int(recovery.get("repetitions", 0)),
                    "runs_per_variant": int(recovery.get("runs_per_variant", 0)),
                    "runs": int(recovery.get("run_count", 0)),
                },
                "metrics": {
                    variant: dict(payload["summary"])
                    for variant, payload in recovery["variants"].items()
                },
                "formulas": {
                    "resume_success_rate": "successful resumes / all variant runs",
                    "stale_reanchor_rate": (
                        "successful reanchors / partial-stale variant runs"
                    ),
                    "workspace_drift_detection_rate": (
                        "detected drifts / workspace-mismatch variant runs"
                    ),
                    "resume_false_accept_rate": (
                        "false accepts / invalid-resume variant runs"
                    ),
                },
                "exclusions": {"count": 0, "reasons": []},
            },
        },
    }


def _append_formulas(lines: list[str], formulas: Mapping[str, str]) -> None:
    lines.extend(["", "公式："])
    lines.extend(
        f"- `{name}`：{formula}" for name, formula in sorted(formulas.items())
    )


def render_benchmark_core_report(report: Mapping[str, Any]) -> str:
    modules = report["modules"]
    harness = modules["harness_regression"]
    context = modules["context_ablation"]
    memory = modules["working_memory_ablation"]
    recovery = modules["recovery_ablation"]
    harness_metrics = harness["metrics"]
    context_metrics = context["metrics"]

    lines = [
        "# Pico Benchmark Core Report",
        "",
        f"- Cohort：`{report['cohort_id']}`",
        f"- Source SHA：`{report['source_sha'] or 'not-recorded'}`",
        f"- 证据边界：{report['scope']['statement']}",
        f"- Provider HTTP requests：{report['scope']['provider_http_requests']}",
        "",
        "## Harness Regression",
        f"- 证据：`{harness['artifact_path']}`",
        f"- 固定 regression 任务数：{harness['sample_counts']['tasks']}",
        f"- 排除数：{harness['exclusions']['count']}",
        f"- pass_rate：{harness_metrics['pass_rate']:.2%}",
        f"- within_budget_rate：{harness_metrics['within_budget_rate']:.2%}",
        f"- verifier_pass_rate：{harness_metrics['verifier_pass_rate']:.2%}",
        (
            "- failure_category_counts："
            f"`{json.dumps(harness_metrics['failure_category_counts'], sort_keys=True)}`"
        ),
    ]
    _append_formulas(lines, harness["formulas"])
    lines.extend(
        [
            "",
            "## Context Ablation",
            f"- 证据：`{context['artifact_path']}`",
            f"- 配置数：{context['sample_counts']['configs']}",
            f"- 每配置重复：{context['sample_counts']['repetitions_per_config']}",
            f"- 总运行数：{context['sample_counts']['runs']}",
            f"- 排除数：{context['exclusions']['count']}",
            f"- avg_full_prompt_chars：{context_metrics['avg_full_prompt_chars']:.2f}",
            f"- avg_raw_prompt_chars：{context_metrics['avg_raw_prompt_chars']:.2f}",
            (
                "- avg_prompt_compression_ratio："
                f"{context_metrics['avg_prompt_compression_ratio']:.2%}"
            ),
            (
                "- max_prompt_compression_ratio："
                f"{context_metrics['max_prompt_compression_ratio']:.2%}"
            ),
            (
                "- current_request_preserved_rate："
                f"{context_metrics['current_request_preserved_rate']:.2%}"
            ),
        ]
    )
    _append_formulas(lines, context["formulas"])
    lines.extend(
        [
            "",
            "## Working Memory Ablation",
            f"- 证据：`{memory['artifact_path']}`",
            f"- 任务数：{memory['sample_counts']['tasks']}",
            f"- Variant 数：{memory['sample_counts']['variants']}",
            f"- 每 variant 运行数：{memory['sample_counts']['runs_per_variant']}",
            f"- 总运行数：{memory['sample_counts']['runs']}",
            f"- 排除数：{memory['exclusions']['count']}",
        ]
    )
    for variant in ("memory_on", "memory_off", "memory_irrelevant"):
        metrics = memory["metrics"][variant]
        lines.extend(
            [
                "",
                f"### `{variant}`",
                f"- repeated_reads：{metrics['repeated_reads']}",
                f"- avg_tool_steps：{metrics['avg_tool_steps']:.2f}",
                f"- correct_rate：{metrics['correct_rate']:.2%}",
                f"- memory_hit_rate：{metrics['memory_hit_rate']:.2%}",
            ]
        )
    _append_formulas(lines, memory["formulas"])
    lines.extend(
        [
            "",
            "## Recovery / Resume Ablation",
            f"- 证据：`{recovery['artifact_path']}`",
            f"- 任务数：{recovery['sample_counts']['tasks']}",
            f"- Variant 数：{recovery['sample_counts']['variants']}",
            f"- 每 variant 运行数：{recovery['sample_counts']['runs_per_variant']}",
            f"- 总运行数：{recovery['sample_counts']['runs']}",
            f"- 排除数：{recovery['exclusions']['count']}",
        ]
    )
    for variant in ("resume_enabled", "resume_disabled"):
        metrics = recovery["metrics"][variant]
        lines.extend(
            [
                "",
                f"### `{variant}`",
                f"- resume_success_rate：{metrics['resume_success_rate']:.2%}",
                f"- stale_reanchor_rate：{metrics['stale_reanchor_rate']:.2%}",
                (
                    "- workspace_drift_detection_rate："
                    f"{metrics['workspace_drift_detection_rate']:.2%}"
                ),
                (
                    "- resume_false_accept_rate："
                    f"{metrics['resume_false_accept_rate']:.2%}"
                ),
            ]
        )
    _append_formulas(lines, recovery["formulas"])
    lines.extend(
        [
            "",
            "## 可以安全写进简历的指标",
            "- avg_full_prompt_chars",
            "- avg_raw_prompt_chars",
            "- avg_prompt_compression_ratio",
            "- max_prompt_compression_ratio",
            "- repeated_reads",
            "- avg_tool_steps",
            "- correct_rate",
            "- resume_success_rate",
            "- workspace_drift_detection_rate",
            "- resume_false_accept_rate",
            "",
            "## 只适合放文档/面试展开的指标",
            "- current_request_preserved_rate",
            "- memory_hit_rate",
            "- stale_reanchor_rate",
            "- failure_category_counts",
            "",
            "## 口径边界",
            "- Harness regression 只证明 runtime 合同稳定，不证明 provider 上限。",
            "- Context、memory、recovery 只证明模块收益，不与真实编码成功率混写。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_benchmark_core_report(
    report_path: str | Path = DEFAULT_CORE_REPORT_PATH,
    harness_artifact_path: str | Path = DEFAULT_HARNESS_REGRESSION_V2_PATH,
    context_artifact_path: str | Path = DEFAULT_CONTEXT_ABLATION_V2_PATH,
    memory_artifact_path: str | Path = DEFAULT_MEMORY_ABLATION_V2_PATH,
    recovery_artifact_path: str | Path = DEFAULT_RECOVERY_ABLATION_V2_PATH,
    *,
    report_json_path: str | Path | None = None,
    cohort_id: str = "module-baseline-v1",
    source_sha: str = "",
    artifact_root: str | Path | None = None,
) -> str:
    report = build_benchmark_core_report(
        harness_artifact_path=harness_artifact_path,
        context_artifact_path=context_artifact_path,
        memory_artifact_path=memory_artifact_path,
        recovery_artifact_path=recovery_artifact_path,
        cohort_id=cohort_id,
        source_sha=source_sha,
        artifact_root=artifact_root,
    )
    if report_json_path is not None:
        _write_json_artifact(report_json_path, report)
    report_text = render_benchmark_core_report(report)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    return report_text
