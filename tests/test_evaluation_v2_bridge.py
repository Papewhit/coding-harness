from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from pico.evaluation.evaluation_v2_config import CONFIG_LOCATOR_ENV, canonical_json
from pico.evaluation.live_tasks import (
    InfrastructureFailure,
    LocalLiveTaskRunner,
    load_task_specs,
)
from scripts.run_local_coding_tasks import CommandClient
from tests.evaluation_v2_helpers import (
    TASKSET,
    request as evaluation_request,
    write_config,
)


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_CLIENT = ROOT / "tests" / "evaluation_v2_bridge_client.py"


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bwrap") is None,
    reason="production bridge requires Linux bubblewrap",
)
def test_production_bridge_normalizes_user_prompt_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CONFIG_LOCATOR_ENV, raising=False)
    config_path, cohort_root = write_config(tmp_path, monkeypatch)
    client = CommandClient(
        [sys.executable, str(BRIDGE_CLIENT)],
        timeout_seconds=30,
    )

    evidence = LocalLiveTaskRunner(cohort_root).run(
        load_task_specs(TASKSET)[0],
        evaluation_request(config_path),
        client,
    )

    record = evidence.artifact
    assert evidence.failure_category == "task"
    assert record["measurement_status"] == "complete"
    assert record["provider_requests"] == {"count": 1, "exact": True}
    assert record["client_result"]["failure_category"] == "none"
    assert record["client_result"]["failure_origin"] == "none"
    assert record["client_result"]["failure_stage"] == "none"
    assert record["client_result"]["error_type"] == ""
    assert record["client_result"]["error"] == ""
    assert len(record["client_result"]["http_attempts"]) == 1
    assert record["client_result"]["http_attempts_exact"] is True
    assert record["client_result"]["exit_code"] == 0
    assert (
        record["client_result"]["final_answer"]
        == "Normalized prompt reached transport."
    )
    assert record["failure"] == {
        "category": "task",
        "error_type": "VerifierFailure",
        "exit_code": 1,
        "origin": "verifier",
        "provider_request_count": 1,
        "provider_request_count_exact": True,
        "stage": "verifier",
    }


def test_command_client_rejects_lost_original_failure(
    tmp_path: Path,
) -> None:
    child = tmp_path / "lost_failure.py"
    child.write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from pathlib import Path",
                "path = Path(os.environ['PICO_LIVE_EVIDENCE_PATH'])",
                "path.write_text(json.dumps({",
                "    'failure_category': 'none',",
                "    'http_attempts': [],",
                "    'http_attempts_exact': True,",
                "    'error': 'original exception was lost',",
                "}), encoding='utf-8')",
                "raise SystemExit(1)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    evidence_path = tmp_path / "client-evidence.json"

    with pytest.raises(InfrastructureFailure, match="invalid original failure"):
        CommandClient(
            [sys.executable, str(child)],
            timeout_seconds=10,
        ).run(
            tmp_path,
            "prompt",
            evidence_path=evidence_path,
        )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["error"] == "original exception was lost"
    assert payload["failure_category"] == "none"
    assert payload["exit_code"] == 1
    assert evidence_path.read_bytes() == canonical_json(payload)


def test_command_client_start_failure_has_no_product_result(
    tmp_path: Path,
) -> None:
    with pytest.raises(InfrastructureFailure, match="could not run"):
        CommandClient(
            [str(tmp_path / "missing-client-executable")],
            timeout_seconds=10,
        ).run(
            tmp_path,
            "prompt",
            evidence_path=tmp_path / "client-evidence.json",
        )
