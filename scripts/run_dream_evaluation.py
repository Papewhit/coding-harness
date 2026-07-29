from __future__ import annotations

import argparse
import json
from pathlib import Path

from pico.evaluation.dream_eval import run_dream_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate frozen auto-dream output directories.")
    parser.add_argument("--cases", required=True, help="Path to the frozen cases manifest.")
    parser.add_argument("--outputs-root", required=True, help="Directory containing one output tree per case ID.")
    parser.add_argument("--artifact", required=True, help="Destination JSON artifact path.")
    parser.add_argument(
        "--changes",
        required=True,
        help="JSON object mapping each case ID to workspace-relative changed paths.",
    )
    parser.add_argument("--case", action="append", dest="case_ids", help="Case ID to run; repeat to select a shard.")
    parser.add_argument("--shard-id", default="local")
    parser.add_argument("--repetition", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    changed_paths_by_case = json.loads(Path(args.changes).read_text(encoding="utf-8"))
    if not isinstance(changed_paths_by_case, dict):
        raise ValueError("changes file must contain an object keyed by case ID")
    artifact = run_dream_evaluation(
        args.cases,
        args.outputs_root,
        artifact_path=args.artifact,
        case_ids=args.case_ids,
        changed_paths_by_case=changed_paths_by_case,
        shard_id=args.shard_id,
        repetition=args.repetition,
    )
    print(json.dumps(artifact["summary"], sort_keys=True))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
