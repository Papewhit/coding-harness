from __future__ import annotations

import argparse
import json
from pathlib import Path

from pico.evaluation.context_eval import merge_fragments, run_context_asset_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate structured ModelRequest context captures.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cases", help="Frozen context-asset case manifest.")
    mode.add_argument(
        "--merge-fragment",
        action="append",
        dest="fragments",
        help="Fragment JSON to merge; repeat for every shard.",
    )
    parser.add_argument("--workspace-root", default=".", help="Root used to resolve artifact pointers.")
    parser.add_argument("--artifact", required=True, help="Destination fragment or merged artifact.")
    parser.add_argument("--case", action="append", dest="case_ids", help="Case ID to evaluate.")
    parser.add_argument("--shard-id", default="local")
    parser.add_argument("--repetition", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.fragments:
        if args.case_ids:
            raise ValueError("--case cannot be used while merging fragments")
        fragments = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.fragments]
        artifact = merge_fragments(fragments)
        destination = Path(args.artifact)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        artifact = run_context_asset_evaluation(
            args.cases,
            workspace_root=args.workspace_root,
            artifact_path=args.artifact,
            case_ids=args.case_ids,
            shard_id=args.shard_id,
            repetition=args.repetition,
        )
    print(json.dumps(artifact["summary"], sort_keys=True))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
