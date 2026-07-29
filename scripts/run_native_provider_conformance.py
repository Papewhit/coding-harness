#!/usr/bin/env python3
"""Run the versioned native-provider conformance harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coda.config import resolve_provider_config  # noqa: E402
from coda.evaluation.native_provider import (  # noqa: E402
    FROZEN_INPUT_HASHES,
    load_case_set,
    preflight_failure_artifact,
    run_native_provider_conformance,
    write_native_provider_bundle,
)
from coda.evaluation.native_provider_live import (  # noqa: E402
    NativeProviderLiveRunner,
)
from coda.evaluation.native_provider_profiles import (  # noqa: E402
    assert_provider_profile_matches,
    canonical_profile_json,
    load_public_provider_profile,
)


NATIVE_GATE_SHA256 = (
    "2fc1ebbe4d64c5be80e7fe063584915f12aabf3a8f8c08796d2cf009e94849a5"
)
CONFIG_LOCATOR_SCHEMA_VERSION = "coda-native-provider-config-locator-v1"
CONFIG_LOCATOR_ENV = "CODA_NATIVE_PROVIDER_CONFIG"


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run frozen native-provider conformance cases."
    )
    parser.add_argument("--case-set", required=True, help="Frozen cases JSON.")
    parser.add_argument("--provider", required=True, help="Local Coda profile name.")
    parser.add_argument(
        "--expected-profile",
        required=True,
        help="Frozen sanitized public profile JSON.",
    )
    parser.add_argument(
        "--repetitions",
        required=True,
        type=_positive_integer,
        help="Positive repetitions per case.",
    )
    parser.add_argument(
        "--artifact-dir",
        required=True,
        help="New exclusive shard artifact directory.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Diagnostic case ID selection; do not use for formal shards.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    case_path = Path(args.case_set)
    profile_path = Path(args.expected_profile)
    bindings = _input_bindings(case_path, profile_path)

    try:
        case_set = load_case_set(case_path)
        profile = load_public_provider_profile(profile_path)
        config_path = _resolve_config_path()
        config = resolve_provider_config(
            args.provider,
            start=Path.cwd(),
            config_path=str(config_path),
        )
        assert_provider_profile_matches(config, profile)
        runner = NativeProviderLiveRunner(
            provider=args.provider,
            start=Path.cwd(),
            config_path=str(config_path),
        )
        artifact = run_native_provider_conformance(
            case_set=case_set,
            profile=profile,
            runner=runner,
            case_ids=args.case_ids,
            repetitions=args.repetitions,
            bindings=bindings,
        )
        write_native_provider_bundle(args.artifact_dir, artifact)
    except Exception as exc:
        artifact = preflight_failure_artifact(bindings=bindings, error=exc)
        try:
            write_native_provider_bundle(args.artifact_dir, artifact)
        except Exception as write_exc:
            print(
                f"native provider conformance artifact failure: "
                f"{type(write_exc).__name__}",
                file=sys.stderr,
            )
            return 2
        print(
            json.dumps(
                {
                    "computability": "not_computable",
                    "preflight_failure": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(artifact["summary"], sort_keys=True))
    summary = artifact["summary"]
    return (
        0
        if summary["failed"] == 0
        and summary["infrastructure_failure"] == 0
        and summary["excluded"] == 0
        else 1
    )


def _input_bindings(case_path: Path, profile_path: Path) -> dict[str, Any]:
    return {
        "source_sha": _source_sha(),
        "evaluator_sha256": _file_sha256(
            ROOT / "coda" / "evaluation" / "native_provider.py"
        ),
        "cases_sha256": _optional_file_sha256(case_path),
        "cases_git_blob_oid": _git_blob_oid(case_path),
        "live_runner_sha256": _file_sha256(
            ROOT / "coda" / "evaluation" / "native_provider_live.py"
        ),
        "public_profile_sha256": _profile_sha256(profile_path),
        "public_profile_id": _profile_id(profile_path),
        "native_gate_sha256": NATIVE_GATE_SHA256,
        "sdk_transport_decision_sha256": FROZEN_INPUT_HASHES[
            "sdk_transport_decision"
        ],
        "config_locator": {
            "schema_version": CONFIG_LOCATOR_SCHEMA_VERSION,
            "environment_variable": CONFIG_LOCATOR_ENV,
        },
    }


def _source_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _resolve_config_path() -> Path:
    value = os.environ.get(CONFIG_LOCATOR_ENV)
    if not value:
        raise ValueError(
            f"{CONFIG_LOCATOR_ENV} must identify the audited provider config"
        )
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{CONFIG_LOCATOR_ENV} must identify a regular file")
    return path


def _git_blob_oid(path: Path) -> str:
    if not path.is_file():
        return ""
    completed = subprocess.run(
        ["git", "hash-object", "--", str(path.resolve())],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _profile_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        profile = load_public_provider_profile(path)
    except Exception:
        return ""
    return hashlib.sha256(canonical_profile_json(profile).encode("utf-8")).hexdigest()


def _profile_id(path: Path) -> str:
    try:
        profile = load_public_provider_profile(path)
    except Exception:
        return ""
    return str(profile["profile_id"])


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _optional_file_sha256(path: Path) -> str:
    return _file_sha256(path) if path.is_file() else ""


if __name__ == "__main__":
    raise SystemExit(main())
