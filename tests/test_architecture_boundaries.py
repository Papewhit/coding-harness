from pathlib import Path


def test_core_modules_stay_below_growth_tripwires():
    root = Path(__file__).resolve().parents[1]
    tripwires = {
        "coda/core/runtime.py": 1000,
        "coda/core/runtime_events.py": 90,
        "coda/core/runtime_consumers.py": 90,
        "coda/core/artifacts.py": 130,
        "coda/core/task_state.py": 160,
        "coda/core/todo_ledger.py": 130,
        "coda/core/worker_manager.py": 280,
        "coda/core/context_manager.py": 510,
        "coda/core/context_usage.py": 120,
        "coda/core/compact.py": 190,
        "coda/core/engine.py": 500,
        "coda/core/model_errors.py": 140,
        "coda/core/permissions.py": 140,
        "coda/core/tool_policy.py": 100,
        "coda/core/plan_mode.py": 140,
        "coda/core/tool_executor.py": 220,
        "coda/core/tool_profiles.py": 80,
        "coda/core/turn_history.py": 250,
        "coda/features/skills.py": 240,
        "coda/features/skills_bundled.py": 120,
        "coda/features/skills_runtime.py": 140,
        "coda/tools/registry.py": 360,
        "coda/tools/todos.py": 90,
        "coda/tools/agents.py": 90,
    }

    violations = []
    for relative_path, max_lines in tripwires.items():
        line_count = len((root / relative_path).read_text(encoding="utf-8").splitlines())
        if line_count > max_lines:
            violations.append(
                f"{relative_path} has {line_count} lines, growth tripwire is {max_lines}"
            )

    assert not violations, "Core module growth tripwire violations:\n- " + "\n- ".join(
        violations
    )
