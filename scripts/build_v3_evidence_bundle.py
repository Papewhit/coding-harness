from __future__ import annotations

import argparse
import json

from pico.evaluation.evidence_bundle import build_evidence_bundle_file, validate_claim_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Pico v3 evidence bundle and claim registry.")
    parser.add_argument("--manifest", required=True, help="Evidence bundle manifest JSON path.")
    parser.add_argument("--output", required=True, help="Destination bundle JSON path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    bundle = build_evidence_bundle_file(args.manifest, args.output)
    validate_claim_registry(bundle)
    print(
        json.dumps(
            {
                "sources": len(bundle["sources"]),
                "claims": len(bundle["claim_registry"]["claims"]),
                "output": args.output,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
