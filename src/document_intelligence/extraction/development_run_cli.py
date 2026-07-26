"""CLI for Stage 3B.4B prepare and finalize checkpoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.extraction.baseline_freeze import BaselineFreezeError
from document_intelligence.extraction.development_run import (
    DevelopmentRunError,
    finalize_development_baseline_run,
    prepare_development_baseline_run,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or finalize deterministic-baseline-v0.1 development evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="Run extraction twice and create the first observation lock.",
    )
    prepare.add_argument("--repository-root", type=Path, required=True)
    prepare.add_argument("--parsed-root", type=Path, required=True)
    prepare.add_argument("--ingestion-report", type=Path, required=True)
    prepare.add_argument("--working-output-root", type=Path, required=True)
    prepare.add_argument("--publish-output-root", type=Path, required=True)
    prepare.add_argument("--force", action="store_true")

    finalize = subparsers.add_parser(
        "finalize",
        help="Create the reviewed report and freeze after owner assessments.",
    )
    finalize.add_argument("--repository-root", type=Path, required=True)
    finalize.add_argument("--prepared-root", type=Path, required=True)
    finalize.add_argument("--owner-assessments", type=Path, required=True)
    finalize.add_argument("--force", action="store_true")
    return parser


def _safe_message(error: Exception) -> str:
    return (" ".join(str(error).split()) or type(error).__name__)[:300]


def main(argv: list[str] | None = None) -> int:
    """Execute one explicit workflow mode with stable operational exit codes."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            prepared = prepare_development_baseline_run(
                repository_root=args.repository_root,
                parsed_root=args.parsed_root,
                ingestion_report=args.ingestion_report,
                working_output_root=args.working_output_root,
                publish_output_root=args.publish_output_root,
                force=args.force,
            )
            lock = prepared.observation_lock
            print(
                "prepared=5 "
                f"candidates={prepared.manifest.primary_candidate_total} "
                f"tp={lock.true_positive} fp={lock.false_positive} "
                f"fn={lock.false_negative} owner_review=pending"
            )
            failed_attempts = sum(
                item.status == "failed"
                for item in (
                    *prepared.manifest.primary_attempt_records,
                    *prepared.manifest.repeat_attempt_records,
                )
            )
            if failed_attempts or not prepared.manifest.all_outputs_byte_identical:
                print(
                    "error: preparation recorded failed or non-identical attempts",
                    file=sys.stderr,
                )
                return 1
        else:
            finalized = finalize_development_baseline_run(
                repository_root=args.repository_root,
                prepared_root=args.prepared_root,
                owner_assessments=args.owner_assessments,
                force=args.force,
            )
            report = finalized.evaluation_report
            print(
                "finalized=1 "
                f"tp={report.true_positive} fp={report.false_positive} "
                f"fn={report.false_negative} held_out=blocked"
            )
    except (
        BaselineFreezeError,
        DevelopmentRunError,
        OSError,
        ValidationError,
        ValueError,
    ) as error:
        print(f"error: {_safe_message(error)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
