from pathlib import Path


def test_core_modules_stay_below_growth_tripwires():
    root = Path(__file__).resolve().parents[1]
    tripwires = {
        "pico/core/runtime.py": 1000,
        "pico/core/runtime_events.py": 90,
        "pico/core/runtime_consumers.py": 90,
        "pico/core/artifacts.py": 130,
        "pico/core/task_state.py": 160,
        "pico/core/todo_ledger.py": 130,
        "pico/core/worker_manager.py": 280,
        "pico/core/context_manager.py": 510,
        "pico/core/context_usage.py": 120,
        "pico/core/compact.py": 190,
        "pico/core/engine.py": 500,
        "pico/core/model_errors.py": 140,
        "pico/core/permissions.py": 140,
        "pico/core/tool_policy.py": 100,
        "pico/core/plan_mode.py": 140,
        "pico/core/tool_executor.py": 220,
        "pico/core/tool_profiles.py": 80,
        "pico/core/turn_history.py": 250,
        "pico/features/skills.py": 240,
        "pico/features/skills_bundled.py": 120,
        "pico/features/skills_runtime.py": 140,
        "pico/tools/registry.py": 360,
        "pico/tools/todos.py": 90,
        "pico/tools/agents.py": 90,
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
