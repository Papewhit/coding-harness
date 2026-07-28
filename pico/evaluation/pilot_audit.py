"""Validation contracts for Evaluation v2 Pilot audits and decisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from pico.evaluation.evaluation_v2_config import canonical_json


AUDIT_SCHEMA = "pico-evaluation-v2-codex-audit-v1"
DECISION_SCHEMA = "pico-evaluation-v2-user-decision-v1"
FINAL_CLASSIFICATIONS = {"valid + passed", "valid + failed", "invalid"}
FAILURE_CATEGORIES = {
    "none",
    "product_behavior",
    "model_behavior",
    "provider",
    "protocol",
    "infrastructure",
    "measurement",
}
AUDIT_FIELDS = {
    "schema_version",
    "row_id",
    "auditor",
    "evidence_sufficient",
    "measurement_result",
    "product_result",
    "final_classification",
    "failure_category",
    "reason",
    "evidence_refs",
    "user_decision",
}
DECISION_FIELDS = {
    "schema_version",
    "row_id",
    "decided_by",
    "final_classification",
    "failure_category",
    "reason",
}


def validate_audit(public_row: Path, audit: Mapping[str, Any]) -> None:
    if set(audit) != AUDIT_FIELDS or audit.get("schema_version") != AUDIT_SCHEMA:
        raise ValueError("Codex audit schema or fields are invalid")
    row_id = public_row.name
    if audit.get("row_id") != row_id or audit.get("auditor") != "Codex":
        raise ValueError("Codex audit identity is invalid")
    record = load_object(public_row / "run-record.json")
    view = optional_object(public_row / "evidence-view.json")
    mechanical_measurement_valid = is_measurement_valid(record, view)
    measurement_result = audit.get("measurement_result")
    if measurement_result not in {"valid", "invalid"}:
        raise ValueError("audit measurement result is invalid")
    if measurement_result == "valid" and not mechanical_measurement_valid:
        raise ValueError("audit cannot promote mechanically invalid evidence to valid")
    sufficient = audit.get("evidence_sufficient")
    if type(sufficient) is not bool or sufficient is not (measurement_result == "valid"):
        raise ValueError("audit evidence_sufficient contradicts its measurement result")
    if audit.get("failure_category") not in FAILURE_CATEGORIES:
        raise ValueError("audit failure category is invalid")
    if not isinstance(audit.get("reason"), str) or not audit["reason"].strip():
        raise ValueError("audit reason is required")
    _validate_refs(public_row, audit.get("evidence_refs"))
    user_decision = audit.get("user_decision")
    classification = audit.get("final_classification")
    product = audit.get("product_result")
    if user_decision not in {"not_required", "required"}:
        raise ValueError("audit user_decision must be not_required or required")
    if measurement_result == "invalid":
        if (
            classification != "invalid"
            or product != "not_determined"
            or audit.get("failure_category") != "measurement"
            or user_decision != "not_required"
        ):
            raise ValueError("invalid measurement classification is inconsistent")
        return
    if user_decision == "required":
        if classification != "pending decision":
            raise ValueError("an audit requiring a decision must remain pending")
        return
    if classification not in FINAL_CLASSIFICATIONS:
        raise ValueError("audit final classification is invalid")
    expected_product = deterministic_product_result(record, view)
    if product != expected_product:
        raise ValueError("audit product result contradicts deterministic evidence")
    expected_classification = f"valid + {expected_product}"
    if classification != expected_classification:
        raise ValueError("audit final classification contradicts product result")
    if expected_product == "passed" and audit.get("failure_category") != "none":
        raise ValueError("passed audit must use failure_category=none")
    if expected_product == "failed" and audit.get("failure_category") == "none":
        raise ValueError("failed audit requires a failure category")


def validate_decision(public_row: Path, decision: Mapping[str, Any]) -> None:
    if set(decision) != DECISION_FIELDS or decision.get("schema_version") != DECISION_SCHEMA:
        raise ValueError("user decision schema or fields are invalid")
    if decision.get("row_id") != public_row.name:
        raise ValueError("user decision row identity is invalid")
    if not isinstance(decision.get("decided_by"), str) or not decision["decided_by"]:
        raise ValueError("user decision actor is required")
    if decision.get("final_classification") not in FINAL_CLASSIFICATIONS:
        raise ValueError("user decision final classification is invalid")
    if decision.get("failure_category") not in FAILURE_CATEGORIES:
        raise ValueError("user decision failure category is invalid")
    if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise ValueError("user decision reason is required")


def is_measurement_valid(
    record: Mapping[str, Any], view: Mapping[str, Any]
) -> bool:
    credential = record.get("credential_scan", {})
    source_scan = credential.get("source_originals", {})
    persisted_scan = credential.get("persisted_artifacts", {})
    provider = view.get("provider_requests", record.get("provider_requests", {}))
    return bool(
        record.get("measurement_status") == "complete"
        and not record.get("measurement_errors")
        and isinstance(view, Mapping)
        and not view.get("protocol_errors")
        and provider.get("exact") is True
        and source_scan.get("passed") is True
        and persisted_scan.get("passed") is True
    )


def deterministic_product_result(
    record: Mapping[str, Any], view: Mapping[str, Any]
) -> str:
    failure = record.get("failure")
    if isinstance(failure, Mapping) and failure.get("category") not in {
        None,
        "none",
        "measurement",
    }:
        return "failed"
    verifier = view.get("verifier", {})
    if type(verifier.get("passed")) is not bool:
        raise ValueError("valid measurement has no deterministic verifier result")
    return "passed" if verifier["passed"] else "failed"


def reject_sensitive(payload: Mapping[str, Any], values: Sequence[str]) -> None:
    encoded = canonical_json(dict(payload))
    if any(value and value.encode("utf-8") in encoded for value in values):
        raise ValueError("audit input contains a known sensitive value")


def load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing JSON object: {path}")
    value = __import__("json").loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def optional_object(path: Path) -> dict[str, Any]:
    return load_object(path) if path.is_file() else {}


def _validate_refs(public_row: Path, refs: Any) -> None:
    if not isinstance(refs, list) or not refs:
        raise ValueError("audit evidence_refs must be a non-empty list")
    for ref in refs:
        if not isinstance(ref, Mapping) or set(ref) != {"path", "pointer"}:
            raise ValueError("audit evidence ref fields are invalid")
        relative = _safe_relative(ref.get("path"))
        if not (public_row / relative).is_file():
            raise ValueError(f"audit evidence ref does not exist: {relative}")
        if not isinstance(ref.get("pointer"), str):
            raise ValueError("audit evidence pointer must be a string")


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("artifact path must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact path must be a safe relative POSIX path")
    return path.as_posix()


__all__ = [
    "AUDIT_SCHEMA",
    "DECISION_SCHEMA",
    "FINAL_CLASSIFICATIONS",
    "deterministic_product_result",
    "is_measurement_valid",
    "load_object",
    "optional_object",
    "reject_sensitive",
    "validate_audit",
    "validate_decision",
]
