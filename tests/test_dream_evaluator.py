from __future__ import annotations

import json
from pathlib import Path

import pytest

from coda.evaluation.dream_eval import (
    ARTIFACT_SCHEMA_VERSION,
    CASES_SCHEMA_VERSION,
    build_semantic_snapshot,
    evaluate_case_output,
    load_cases,
    merge_shard_artifacts,
    run_dream_evaluation,
    select_cases,
    semantic_snapshots_equal,
    validate_cases,
)


def _case(case_id: str = "D01") -> dict:
    return {
        "id": case_id,
        "description": "Atomic fact behavior",
        "fixture": {"memory": f"fixtures/{case_id}/memory"},
        "oracle": {
            "facts": [
                {
                    "id": "stable-name",
                    "disposition": "must_keep",
                    "anchors": ["prefers Ada"],
                    "topics": ["user.md"],
                },
                {
                    "id": "timezone",
                    "disposition": "replace",
                    "anchors": ["UTC+9"],
                    "old_anchors": ["UTC+8"],
                    "topics": ["user.md"],
                },
                {
                    "id": "transient-blocker",
                    "disposition": "drop",
                    "anchors": ["blocked until lunch"],
                },
            ],
            "topics": [{"path": "user.md", "facts": ["stable-name", "timezone"]}],
            "index": {"path": "MEMORY.md", "must_link": ["user.md"], "max_lines": 20},
            "frontmatter": {
                "required": ["name", "description", "type"],
                "allowed_types": ["user", "feedback", "project", "reference"],
            },
            "allowed_write_scope": ".coda/memory",
            "snapshot": {"ignore_frontmatter_fields": ["updated_at"]},
        },
    }


def _write_passing_memory(root: Path, *, updated_at: str = "2026-07-21T10:00:00Z") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "MEMORY.md").write_text("# Memory\n\n- [User profile](user.md)\n", encoding="utf-8")
    (root / "user.md").write_text(
        "---\n"
        "name: User profile\n"
        "description: Stable collaboration preferences\n"
        "type: user\n"
        f"updated_at: {updated_at}\n"
        "---\n\n"
        "The user prefers Ada and now works in UTC+9.\n",
        encoding="utf-8",
    )


def test_schema_and_loader_validate_atomic_oracle(tmp_path):
    manifest = {"schema_version": CASES_SCHEMA_VERSION, "cases": [_case()]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    assert load_cases(path) == manifest
    schema = json.loads(Path("benchmarks/v3/auto-dream/schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == CASES_SCHEMA_VERSION
    assert schema["$defs"]["fact"]["properties"]["disposition"]["enum"] == [
        "must_keep",
        "replace",
        "drop",
    ]


def test_validation_rejects_duplicate_facts_and_incomplete_replacement():
    manifest = {"schema_version": CASES_SCHEMA_VERSION, "cases": [_case()]}
    duplicate = dict(manifest["cases"][0]["oracle"]["facts"][0])
    manifest["cases"][0]["oracle"]["facts"].append(duplicate)

    with pytest.raises(ValueError, match="duplicate fact id"):
        validate_cases(manifest)

    replacement = _case()
    replacement["oracle"]["facts"][1].pop("old_anchors")
    with pytest.raises(ValueError, match="needs old_anchors"):
        validate_cases({"schema_version": CASES_SCHEMA_VERSION, "cases": [replacement]})


def test_atomic_oracle_checks_keep_replace_drop_topics_index_and_frontmatter(tmp_path):
    _write_passing_memory(tmp_path)

    row = evaluate_case_output(
        _case(),
        tmp_path,
        changed_paths=[".coda/memory/MEMORY.md", ".coda/memory/user.md"],
    )

    assert row["status"] == "pass"
    assert {item["disposition"]: item["passed"] for item in row["facts"]} == {
        "must_keep": True,
        "replace": True,
        "drop": True,
    }
    assert row["topics"] == [
        {"path": "user.md", "exists": True, "passed": True, "facts": ["stable-name", "timezone"]}
    ]
    assert row["index"]["passed"] is True
    assert row["frontmatter"]["passed"] is True
    assert all(gate["passed"] for gate in row["hard_gates"].values())


@pytest.mark.parametrize(
    ("mutation", "changed_paths", "failed_gate"),
    [
        ("secret", [".coda/memory/user.md"], "secret"),
        ("dangling", [".coda/memory/MEMORY.md"], "dangling_link"),
        ("none", ["README.md"], "scope"),
    ],
)
def test_secret_scope_and_dangling_link_are_hard_gates(tmp_path, mutation, changed_paths, failed_gate):
    _write_passing_memory(tmp_path)
    if mutation == "secret":
        with (tmp_path / "user.md").open("a", encoding="utf-8") as stream:
            stream.write("Synthetic credential sk-abcdefghijklmnop must not persist.\n")
    elif mutation == "dangling":
        with (tmp_path / "MEMORY.md").open("a", encoding="utf-8") as stream:
            stream.write("- [Missing](missing.md)\n")

    row = evaluate_case_output(_case(), tmp_path, changed_paths=changed_paths)

    assert row["passed"] is False
    assert row["hard_gates"][failed_gate]["passed"] is False
    assert f"hard_gate:{failed_gate}" in row["failures"]


def test_semantic_snapshot_ignores_only_allowed_frontmatter_time_fields(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_passing_memory(first, updated_at="2026-07-21T10:00:00Z")
    _write_passing_memory(second, updated_at="2026-07-21T11:00:00Z")

    first_snapshot = build_semantic_snapshot(first, ignored_frontmatter_fields=["updated_at"])
    second_snapshot = build_semantic_snapshot(second, ignored_frontmatter_fields=["updated_at"])

    assert semantic_snapshots_equal(first_snapshot, second_snapshot)
    with (second / "user.md").open("a", encoding="utf-8") as stream:
        stream.write("A new semantic fact.\n")
    changed = build_semantic_snapshot(second, ignored_frontmatter_fields=["updated_at"])
    assert not semantic_snapshots_equal(first_snapshot, changed)


def test_case_evaluation_reports_idempotency_from_second_output(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_passing_memory(first, updated_at="2026-07-21T10:00:00Z")
    _write_passing_memory(second, updated_at="2026-07-21T11:00:00Z")

    row = evaluate_case_output(
        _case(),
        first,
        changed_paths=[".coda/memory/MEMORY.md", ".coda/memory/user.md"],
        second_memory_root=second,
    )

    assert row["passed"] is True
    assert row["idempotency"]["passed"] is True
    assert row["idempotency"]["first_sha256"] == row["idempotency"]["second_sha256"]


def test_runner_filters_cases_and_persists_independent_shard(tmp_path):
    cases = [_case("D01"), _case("D02")]
    manifest_path = tmp_path / "cases.json"
    manifest_path.write_text(
        json.dumps({"schema_version": CASES_SCHEMA_VERSION, "cases": cases}), encoding="utf-8"
    )
    _write_passing_memory(tmp_path / "outputs" / "D02")
    artifact_path = tmp_path / "artifacts" / "shard-b.json"

    artifact = run_dream_evaluation(
        manifest_path,
        tmp_path / "outputs",
        artifact_path=artifact_path,
        case_ids=["D02"],
        changed_paths_by_case={
            "D02": [".coda/memory/MEMORY.md", ".coda/memory/user.md"]
        },
        shard_id="dream-b",
        repetition=3,
    )

    assert artifact_path.exists()
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == artifact
    assert artifact["selected_case_ids"] == ["D02"]
    assert [(row["case_id"], row["repetition"]) for row in artifact["rows"]] == [("D02", 3)]
    assert artifact["summary"]["pass_rate"] == 1.0
    with pytest.raises(ValueError, match="unknown case ids"):
        select_cases(cases, ["D99"])


def test_missing_changed_path_evidence_fails_scope_gate_closed(tmp_path):
    _write_passing_memory(tmp_path)

    row = evaluate_case_output(_case(), tmp_path)

    assert row["passed"] is False
    assert row["hard_gates"]["scope"] == {
        "passed": False,
        "violations": ["changed_path_evidence_missing"],
        "evidence": "missing",
    }


def test_merge_shards_is_deterministic_and_rejects_duplicate_case_repetitions():
    def artifact(shard_id: str, case_id: str, repetition: int, passed: bool = True) -> dict:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "shard_id": shard_id,
            "rows": [
                {
                    "case_id": case_id,
                    "repetition": repetition,
                    "passed": passed,
                    "failures": [] if passed else ["fact:missing"],
                }
            ],
        }

    merged = merge_shard_artifacts(
        [artifact("b", "D02", 1, False), artifact("a", "D01", 1)]
    )

    assert merged["shard_ids"] == ["a", "b"]
    assert [(row["case_id"], row["repetition"]) for row in merged["rows"]] == [
        ("D01", 1),
        ("D02", 1),
    ]
    assert merged["summary"] == {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "pass_rate": 0.5,
        "failure_counts": {"fact:missing": 1},
    }
    with pytest.raises(ValueError, match="duplicate case repetition"):
        merge_shard_artifacts([artifact("a", "D01", 1), artifact("b", "D01", 1)])
