"""Deterministic evaluator primitives for auto-dream memory fixtures.

The evaluator deliberately does not ask another model to grade the output.
Frozen fixtures describe atomic facts using literal anchors and structural
expectations that can be audited from the produced memory files.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Mapping, Sequence


CASES_SCHEMA_VERSION = "pico-auto-dream-cases-v1"
ARTIFACT_SCHEMA_VERSION = "pico-auto-dream-artifact-v1"
DEFAULT_IGNORED_FRONTMATTER_FIELDS = ("updated_at", "last_dream_at")
ALLOWED_DISPOSITIONS = frozenset({"must_keep", "replace", "drop"})
ALLOWED_MEMORY_TYPES = frozenset({"user", "feedback", "project", "reference"})

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def load_cases(path: str | Path) -> dict[str, Any]:
    """Load and validate a frozen auto-dream case manifest."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_cases(payload)
    return payload


def validate_cases(payload: Mapping[str, Any]) -> None:
    """Validate semantic constraints not expressible by the JSON schema alone."""

    if not isinstance(payload, Mapping):
        raise ValueError("case manifest must be an object")
    if payload.get("schema_version") != CASES_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {CASES_SCHEMA_VERSION!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")

    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each case must be an object")
        case_id = _required_string(case, "id", "case")
        if case_id in case_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        case_ids.add(case_id)
        fixture = case.get("fixture")
        oracle = case.get("oracle")
        if not isinstance(fixture, Mapping):
            raise ValueError(f"case {case_id} fixture must be an object")
        _safe_relative_path(_required_string(fixture, "memory", f"case {case_id} fixture"))
        if not isinstance(oracle, Mapping):
            raise ValueError(f"case {case_id} oracle must be an object")
        facts = oracle.get("facts")
        if not isinstance(facts, list) or not facts:
            raise ValueError(f"case {case_id} oracle facts must be a non-empty list")
        fact_ids: set[str] = set()
        for fact in facts:
            _validate_fact(case_id, fact, fact_ids)
        for topic in oracle.get("topics", []):
            if not isinstance(topic, Mapping):
                raise ValueError(f"case {case_id} topics must contain objects")
            _safe_relative_path(_required_string(topic, "path", f"case {case_id} topic"))
            references = topic.get("facts", [])
            if not isinstance(references, list) or not all(item in fact_ids for item in references):
                raise ValueError(f"case {case_id} topic references an unknown fact")
        index = oracle.get("index", {})
        if not isinstance(index, Mapping):
            raise ValueError(f"case {case_id} index must be an object")
        _safe_relative_path(str(index.get("path", "MEMORY.md")))
        for field in ("must_link", "must_not_link"):
            values = index.get(field, [])
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"case {case_id} index {field} must be a list of paths")
            for value in values:
                _safe_relative_path(value)
        max_lines = index.get("max_lines")
        if max_lines is not None and (type(max_lines) is not int or max_lines < 1):
            raise ValueError(f"case {case_id} index max_lines must be a positive integer")
        _safe_relative_path(str(oracle.get("allowed_write_scope", ".")))
        snapshot = oracle.get("snapshot", {})
        if not isinstance(snapshot, Mapping):
            raise ValueError(f"case {case_id} snapshot must be an object")
        ignored = snapshot.get("ignore_frontmatter_fields", DEFAULT_IGNORED_FRONTMATTER_FIELDS)
        if not isinstance(ignored, list | tuple) or not all(
            isinstance(item, str) and item for item in ignored
        ):
            raise ValueError(f"case {case_id} ignored frontmatter fields must be strings")


def select_cases(cases: Sequence[Mapping[str, Any]], case_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Select cases in manifest order and fail closed on unknown IDs."""

    selected_ids = list(dict.fromkeys(case_ids or []))
    if not selected_ids:
        return [dict(case) for case in cases]
    requested = set(selected_ids)
    available = {str(case.get("id")) for case in cases}
    unknown = requested - available
    if unknown:
        raise ValueError(f"unknown case ids: {', '.join(sorted(unknown))}")
    return [dict(case) for case in cases if case.get("id") in requested]


def evaluate_case_output(
    case: Mapping[str, Any],
    memory_root: str | Path,
    *,
    repetition: int = 1,
    changed_paths: Iterable[str] | None = None,
    second_memory_root: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate one produced memory tree against a frozen case oracle."""

    case_id = _required_string(case, "id", "case")
    if type(repetition) is not int or repetition < 1:
        raise ValueError("repetition must be a positive integer")
    oracle = case.get("oracle")
    if not isinstance(oracle, Mapping):
        raise ValueError(f"case {case_id} oracle must be an object")
    root = Path(memory_root)
    documents = _read_markdown_documents(root)

    facts = [_evaluate_fact(fact, documents) for fact in oracle.get("facts", [])]
    topics = [_evaluate_topic(topic, root, documents) for topic in oracle.get("topics", [])]
    index_result = _evaluate_index(oracle.get("index", {}), root)
    frontmatter_result = _evaluate_frontmatter(oracle.get("frontmatter", {}), documents, topics)
    gates = {
        "secret": _secret_gate(documents),
        "scope": _scope_gate(changed_paths, str(oracle.get("allowed_write_scope", "."))),
        "dangling_link": _dangling_link_gate(root, str(oracle.get("index", {}).get("path", "MEMORY.md"))),
    }

    snapshot_options = oracle.get("snapshot", {})
    ignored_fields = snapshot_options.get(
        "ignore_frontmatter_fields", DEFAULT_IGNORED_FRONTMATTER_FIELDS
    )
    snapshot = build_semantic_snapshot(root, ignored_frontmatter_fields=ignored_fields)
    idempotency: dict[str, Any] | None = None
    if second_memory_root is not None:
        second_snapshot = build_semantic_snapshot(
            second_memory_root, ignored_frontmatter_fields=ignored_fields
        )
        idempotency = {
            "passed": semantic_snapshots_equal(snapshot, second_snapshot),
            "first_sha256": snapshot["sha256"],
            "second_sha256": second_snapshot["sha256"],
        }

    checks_passed = all(item["passed"] for item in facts + topics)
    checks_passed = checks_passed and index_result["passed"] and frontmatter_result["passed"]
    gates_passed = all(gate["passed"] for gate in gates.values())
    if idempotency is not None:
        checks_passed = checks_passed and idempotency["passed"]
    passed = checks_passed and gates_passed
    failures = [f"fact:{item['id']}" for item in facts if not item["passed"]]
    failures.extend(f"topic:{item['path']}" for item in topics if not item["passed"])
    if not index_result["passed"]:
        failures.append("index")
    if not frontmatter_result["passed"]:
        failures.append("frontmatter")
    failures.extend(f"hard_gate:{name}" for name, gate in gates.items() if not gate["passed"])
    if idempotency is not None and not idempotency["passed"]:
        failures.append("idempotency")

    return {
        "case_id": case_id,
        "repetition": repetition,
        "status": "pass" if passed else "fail",
        "passed": passed,
        "facts": facts,
        "topics": topics,
        "index": index_result,
        "frontmatter": frontmatter_result,
        "hard_gates": gates,
        "semantic_snapshot": snapshot,
        "idempotency": idempotency,
        "failures": failures,
    }


def run_dream_evaluation(
    cases_path: str | Path,
    outputs_root: str | Path,
    *,
    changed_paths_by_case: Mapping[str, Iterable[str]],
    artifact_path: str | Path | None = None,
    case_ids: Iterable[str] | None = None,
    shard_id: str = "local",
    repetition: int = 1,
) -> dict[str, Any]:
    """Evaluate selected case outputs stored under ``outputs_root/<case-id>``."""

    manifest = load_cases(cases_path)
    selected = select_cases(manifest["cases"], case_ids)
    output_base = Path(outputs_root)
    rows = [
        evaluate_case_output(
            case,
            output_base / str(case["id"]),
            repetition=repetition,
            changed_paths=changed_paths_by_case.get(str(case["id"])),
        )
        for case in selected
    ]
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "shard_id": shard_id,
        "case_schema_version": manifest["schema_version"],
        "selected_case_ids": [case["id"] for case in selected],
        "rows": rows,
        "summary": summarize_rows(rows),
    }
    if artifact_path is not None:
        destination = Path(artifact_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def merge_shard_artifacts(artifacts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Merge independent shards, rejecting duplicate case repetitions."""

    rows: list[dict[str, Any]] = []
    shard_ids: list[str] = []
    seen: set[tuple[str, int]] = set()
    for artifact in artifacts:
        if artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("cannot merge an incompatible dream artifact")
        shard_id = _required_string(artifact, "shard_id", "artifact")
        if shard_id in shard_ids:
            raise ValueError(f"duplicate shard id: {shard_id}")
        shard_ids.append(shard_id)
        artifact_rows = artifact.get("rows")
        if not isinstance(artifact_rows, list):
            raise ValueError(f"shard {shard_id} rows must be a list")
        for raw_row in artifact_rows:
            if not isinstance(raw_row, Mapping):
                raise ValueError(f"shard {shard_id} contains a non-object row")
            key = (str(raw_row.get("case_id")), raw_row.get("repetition"))
            if not key[0] or type(key[1]) is not int:
                raise ValueError(f"shard {shard_id} row identity is invalid")
            if key in seen:
                raise ValueError(f"duplicate case repetition: {key[0]}#{key[1]}")
            seen.add(key)
            rows.append(dict(raw_row))
    rows.sort(key=lambda row: (row["case_id"], row["repetition"]))
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "shard_ids": sorted(shard_ids),
        "rows": rows,
        "summary": summarize_rows(rows),
    }


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(item.get("passed") is True for item in rows)
    failure_counts = Counter(
        failure for row in rows for failure in row.get("failures", [])
    )
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else None,
        "failure_counts": dict(sorted(failure_counts.items())),
    }


def build_semantic_snapshot(
    memory_root: str | Path,
    *,
    ignored_frontmatter_fields: Iterable[str] = DEFAULT_IGNORED_FRONTMATTER_FIELDS,
) -> dict[str, Any]:
    """Create a stable snapshot that ignores explicitly allowed timestamp fields."""

    root = Path(memory_root)
    ignored = {str(field).lower().replace("-", "_") for field in ignored_frontmatter_fields}
    files: list[dict[str, Any]] = []
    for path in _markdown_paths(root):
        text = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(text)
        normalized_metadata = {
            key: value for key, value in sorted(metadata.items()) if key not in ignored
        }
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "frontmatter": normalized_metadata,
                "body": _normalize_text(body),
            }
        )
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"files": files, "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def semantic_snapshots_equal(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return first.get("sha256") == second.get("sha256") and first.get("files") == second.get("files")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower().replace("-", "_")] = value.strip().strip('"\'')
    return metadata, text.replace("\r\n", "\n")[match.end() :]


def _validate_fact(case_id: str, fact: Any, fact_ids: set[str]) -> None:
    if not isinstance(fact, Mapping):
        raise ValueError(f"case {case_id} facts must contain objects")
    fact_id = _required_string(fact, "id", f"case {case_id} fact")
    if fact_id in fact_ids:
        raise ValueError(f"case {case_id} has duplicate fact id: {fact_id}")
    fact_ids.add(fact_id)
    disposition = fact.get("disposition")
    if disposition not in ALLOWED_DISPOSITIONS:
        raise ValueError(f"case {case_id} fact {fact_id} has invalid disposition")
    anchors = fact.get("anchors")
    if not isinstance(anchors, list) or not anchors or not all(isinstance(item, str) and item for item in anchors):
        raise ValueError(f"case {case_id} fact {fact_id} anchors must be non-empty strings")
    if disposition == "replace":
        old = fact.get("old_anchors")
        if not isinstance(old, list) or not old or not all(isinstance(item, str) and item for item in old):
            raise ValueError(f"case {case_id} replacement fact {fact_id} needs old_anchors")
    if fact.get("match", "all") not in {"all", "any"}:
        raise ValueError(f"case {case_id} fact {fact_id} match must be all or any")
    topics = fact.get("topics", [])
    if not isinstance(topics, list):
        raise ValueError(f"case {case_id} fact {fact_id} topics must be a list")
    for topic in topics:
        _safe_relative_path(str(topic))


def _evaluate_fact(fact: Mapping[str, Any], documents: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    fact_id = str(fact["id"])
    disposition = str(fact["disposition"])
    topic_paths = [str(item) for item in fact.get("topics", [])]
    selected = [documents[path] for path in topic_paths if path in documents] if topic_paths else list(documents.values())
    corpus = "\n".join(item["text"] for item in selected)
    anchors = [str(item) for item in fact["anchors"]]
    anchor_hits = {anchor: _contains(corpus, anchor) for anchor in anchors}
    match_mode = fact.get("match", "all")
    expected_present = any(anchor_hits.values()) if match_mode == "any" else all(anchor_hits.values())
    old_hits: dict[str, bool] = {}
    if disposition == "must_keep":
        passed = expected_present
    elif disposition == "drop":
        passed = not any(anchor_hits.values())
    else:
        old_hits = {str(anchor): _contains(corpus, str(anchor)) for anchor in fact["old_anchors"]}
        passed = expected_present and not any(old_hits.values())
    return {
        "id": fact_id,
        "disposition": disposition,
        "passed": passed,
        "anchor_hits": anchor_hits,
        "old_anchor_hits": old_hits,
        "topics": topic_paths,
    }


def _evaluate_topic(topic: Mapping[str, Any], root: Path, documents: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    path = str(topic["path"])
    exists = (root / _safe_relative_path(path)).is_file()
    return {"path": path, "exists": exists, "passed": exists, "facts": list(topic.get("facts", []))}


def _evaluate_index(index: Any, root: Path) -> dict[str, Any]:
    config = index if isinstance(index, Mapping) else {}
    path = str(config.get("path", "MEMORY.md"))
    index_path = root / _safe_relative_path(path)
    text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    must_link = [str(item) for item in config.get("must_link", [])]
    must_not_link = [str(item) for item in config.get("must_not_link", [])]
    linked = _local_link_targets(text)
    missing = [target for target in must_link if target not in linked]
    forbidden = [target for target in must_not_link if target in linked]
    max_lines = config.get("max_lines")
    line_count = len(text.splitlines())
    within_limit = max_lines is None or (type(max_lines) is int and line_count <= max_lines)
    passed = index_path.is_file() and not missing and not forbidden and within_limit
    return {
        "path": path,
        "exists": index_path.is_file(),
        "line_count": line_count,
        "missing_links": missing,
        "forbidden_links": forbidden,
        "within_line_limit": within_limit,
        "passed": passed,
    }


def _evaluate_frontmatter(config: Any, documents: Mapping[str, dict[str, Any]], topics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    options = config if isinstance(config, Mapping) else {}
    required = [str(item).lower().replace("-", "_") for item in options.get("required", ["name", "description", "type"])]
    allowed_types = set(options.get("allowed_types", ALLOWED_MEMORY_TYPES))
    paths = [str(topic["path"]) for topic in topics]
    failures: dict[str, list[str]] = {}
    for path in paths:
        metadata = documents.get(path, {}).get("frontmatter", {})
        missing = [field for field in required if not metadata.get(field)]
        if metadata.get("type") and metadata["type"] not in allowed_types:
            missing.append("type:invalid")
        if missing:
            failures[path] = missing
    return {"passed": not failures, "failures": failures, "checked_paths": paths}


def _secret_gate(documents: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    findings = []
    for path, document in documents.items():
        if any(pattern.search(document["text"]) for pattern in _SECRET_PATTERNS):
            findings.append(path)
    return {"passed": not findings, "findings": sorted(findings)}


def _scope_gate(changed_paths: Iterable[str] | None, allowed_scope: str) -> dict[str, Any]:
    if changed_paths is None:
        return {
            "passed": False,
            "violations": ["changed_path_evidence_missing"],
            "evidence": "missing",
        }
    scope = _safe_relative_path(allowed_scope)
    violations: list[str] = []
    for raw_path in changed_paths:
        try:
            path = _safe_relative_path(str(raw_path))
        except ValueError:
            violations.append(str(raw_path))
            continue
        if scope != PurePosixPath(".") and path != scope and scope not in path.parents:
            violations.append(str(raw_path))
    return {"passed": not violations, "violations": sorted(violations), "evidence": "changed_paths"}


def _dangling_link_gate(root: Path, index_path: str) -> dict[str, Any]:
    path = root / _safe_relative_path(index_path)
    if not path.is_file():
        return {"passed": False, "dangling": [index_path]}
    dangling: list[str] = []
    for target in _local_link_targets(path.read_text(encoding="utf-8")):
        clean_target = target.split("#", 1)[0]
        try:
            relative = _safe_relative_path(clean_target)
        except ValueError:
            dangling.append(target)
            continue
        candidate = root / relative
        if candidate.suffix == "" and not candidate.exists():
            candidate = candidate.with_suffix(".md")
        if not candidate.is_file():
            dangling.append(target)
    return {"passed": not dangling, "dangling": sorted(dangling)}


def _read_markdown_documents(root: Path) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for path in _markdown_paths(root):
        text = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(text)
        documents[path.relative_to(root).as_posix()] = {
            "text": text,
            "frontmatter": metadata,
            "body": body,
        }
    return documents


def _markdown_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted((path for path in root.rglob("*.md") if path.is_file()), key=lambda item: item.relative_to(root).as_posix())


def _local_link_targets(text: str) -> list[str]:
    targets = []
    for raw in _MARKDOWN_LINK_RE.findall(text):
        target = raw.strip().split(maxsplit=1)[0].strip("<>")
        if target and not target.startswith(("#", "http://", "https://", "mailto:")):
            targets.append(target.replace("\\", "/"))
    targets.extend(target.strip().replace("\\", "/") for target in _WIKILINK_RE.findall(text))
    return targets


def _safe_relative_path(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not normalized or any(part in {"", ".."} for part in path.parts):
        raise ValueError(f"path must be a safe relative path: {value!r}")
    return path


def _required_string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _contains(haystack: str, needle: str) -> bool:
    return _normalize_text(needle).casefold() in _normalize_text(haystack).casefold()


def _normalize_text(value: str) -> str:
    return "\n".join(" ".join(line.split()) for line in value.replace("\r\n", "\n").strip().splitlines())
