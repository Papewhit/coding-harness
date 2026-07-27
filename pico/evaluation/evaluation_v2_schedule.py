"""Frozen row identities and stage commands for Evaluation v2."""

from __future__ import annotations

import shlex
from typing import Any


def allowed_rows(cohort_id: str) -> list[dict[str, Any]]:
    task_ids = (
        ["T01", "T04", "T07"]
        if cohort_id == "pilot-v1"
        else [f"T{number:02d}" for number in range(1, 10)]
    )
    repetitions = 1 if cohort_id == "pilot-v1" else 3
    return [
        {
            "row_id": f"{cohort_id}-{task_id}-r{repetition}",
            "task_id": task_id,
            "repetition": repetition,
        }
        for repetition in range(1, repetitions + 1)
        for task_id in task_ids
    ]


def launch_commands(
    *, source_root: str, run_config: str, cohort_id: str
) -> dict[str, Any]:
    base = [
        "uv",
        "run",
        "--frozen",
        "--extra",
        "providers",
        "--python",
        "3.12",
        "python",
        "scripts/run_local_coding_tasks.py",
        "--run-config",
        run_config,
        "--cohort-id",
        cohort_id,
    ]
    stages = (
        {
            "p3_g0": [
                *base,
                "--stage",
                "P3-G0",
                "--task",
                "T01",
                "--repo",
                "tinyconfig",
                "--repetitions",
                "1",
            ],
            "p3_remainder": [
                *base,
                "--stage",
                "P3-remainder",
                "--task",
                "T04",
                "--task",
                "T07",
                "--repetitions",
                "1",
            ],
        }
        if cohort_id == "pilot-v1"
        else {
            "p4a": [
                *base,
                "--stage",
                "P4A",
                "--repo",
                "tinyconfig",
                "--repetitions",
                "3",
            ],
            "p4b": [
                *base,
                "--stage",
                "P4B",
                "--repo",
                "miniqueue",
                "--repetitions",
                "3",
            ],
            "p4c": [
                *base,
                "--stage",
                "P4C",
                "--repo",
                "logslice",
                "--repetitions",
                "3",
            ],
        }
    )
    return {
        name: {
            "cwd": source_root,
            "argv": argv,
            "display": shlex.join(argv),
        }
        for name, argv in stages.items()
    }


__all__ = ["allowed_rows", "launch_commands"]
