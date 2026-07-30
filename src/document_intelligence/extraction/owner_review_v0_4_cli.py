"""CLI for deterministic-baseline-v0.4 owner-review preparation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from document_intelligence.extraction.owner_review_v0_4 import (
    OwnerReviewPreparationError,
    prepare_owner_review_v0_4,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the preparation-only command-line contract."""
    parser = argparse.ArgumentParser(
        description="Prepare the owner-neutral deterministic-baseline-v0.4 review package."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    prepare = subparsers.add_parser(
        "prepare", description="Validate development evidence and prepare blank owner review."
    )
    prepare.add_argument("--repository-root", required=True, type=Path)
    prepare.add_argument("--parsed-root", required=True, type=Path)
    prepare.add_argument("--ingestion-report", required=True, type=Path)
    prepare.add_argument("--candidate-root", required=True, type=Path)
    prepare.add_argument("--output-root", required=True, type=Path)
    prepare.add_argument(
        "--force",
        action="store_true",
        help="Replace only an authorized dedicated v0.4 preparation output root.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the single supported prepare operation."""
    arguments = build_parser().parse_args(argv)
    try:
        manifest = prepare_owner_review_v0_4(
            repository_root=arguments.repository_root,
            parsed_root=arguments.parsed_root,
            ingestion_report=arguments.ingestion_report,
            candidate_root=arguments.candidate_root,
            output_root=arguments.output_root,
            force=arguments.force,
        )
    except (OwnerReviewPreparationError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    counts = manifest.evidence_linked_candidate_count_by_case
    print(
        "prepared=3 pending_owner_assessments=3 "
        + " ".join(f"{case_id}={counts[case_id]}" for case_id in counts)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
