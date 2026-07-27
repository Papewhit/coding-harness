"""Deterministic file and trace helpers shared by live-task evaluators."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from pico.evaluation.contracts import sanitize_public_artifact


def workspace_manifest(root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def compare_manifests(
    before: Mapping[str, str], after: Mapping[str, str]
) -> dict[str, list[str]]:
    before_paths = set(before)
    after_paths = set(after)
    return {
        "created": sorted(after_paths - before_paths),
        "modified": sorted(
            path for path in before_paths & after_paths if before[path] != after[path]
        ),
        "deleted": sorted(before_paths - after_paths),
    }


def sanitize_trace(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove opaque contents and secrets while preserving evidence shape."""

    sanitized = []
    for event in events:
        public = dict(event)
        for key in tuple(public):
            if key.lower() in {
                "thinking",
                "reasoning",
                "continuation",
                "opaque_continuation",
            }:
                public[key] = _opaque_shape(public[key])
        sanitized.append(sanitize_public_artifact(public))
    return sanitized


def _opaque_shape(value: Any) -> dict[str, Any]:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    except (TypeError, ValueError):
        encoded = repr(type(value).__name__).encode()
    count = len(value) if isinstance(value, (list, tuple, dict)) else int(value is not None)
    return {
        "hash": hashlib.sha256(encoded).hexdigest(),
        "type": type(value).__name__,
        "count": count,
    }


__all__ = ["compare_manifests", "sanitize_trace", "workspace_manifest"]
