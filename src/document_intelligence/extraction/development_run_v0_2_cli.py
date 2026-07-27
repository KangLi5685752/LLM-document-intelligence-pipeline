"""Prepare/finalize CLI for deterministic-baseline-v0.2 development evidence."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.extraction.baseline_freeze_v0_2 import (
    BaselineFreezeError,
)
from document_intelligence.extraction.development_run_v0_2 import (
    DevelopmentRunError,
    finalize_development_baseline_run,
    prepare_development_baseline_run,
)


EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 2
EXIT_INCOMPLETE_PREPARATION = 3


def build_parser() -> argparse.ArgumentParser:
    """Build the two-command parser; no single-source or overwrite bypass exists."""
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or finalize deterministic-baseline-v0.2 development evidence."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser(
        "prepare", help="Run exact five-source primary/repeat preparation."
    )
    prepare.add_argument("--repository-root", type=Path, required=True)
    prepare.add_argument("--parsed-root", type=Path, required=True)
    prepare.add_argument("--ingestion-report", type=Path, required=True)
    prepare.add_argument("--implementation-commit", required=True)
    prepare.add_argument("--output-root", type=Path, required=True)

    finalize = subparsers.add_parser(
        "finalize", help="Finalize existing evidence after explicit owner review."
    )
    finalize.add_argument("--repository-root", type=Path, required=True)
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--owner-assessments", type=Path, required=True)
    finalize.add_argument("--freeze-date")
    return parser


def _safe_message(error: Exception) -> str:
    message = " ".join(str(error).split()) or type(error).__name__
    message = re.sub(r"[A-Za-z]:[\\/][^\s,;]+", "[local-path]", message)
    message = re.sub(r"file://[^\s,;]+", "[local-path]", message)
    return message[:300]


def main(argv: list[str] | None = None) -> int:
    """Execute one bounded workflow mode with stable exit codes."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            prepared = prepare_development_baseline_run(
                repository_root=args.repository_root,
                parsed_root=args.parsed_root,
                ingestion_report=args.ingestion_report,
                implementation_commit=args.implementation_commit,
                output_root=args.output_root,
            )
            report = prepared.observation_lock.preliminary_evaluation
            print(
                "prepared=5 "
                f"successful={report.schema_valid_source_count} "
                f"failed={report.failed_source_count} "
                f"tp={report.true_positive} fp={report.false_positive} "
                f"fn={report.false_negative} "
                f"owner_review_authorized={str(prepared.manifest.owner_review_authorized).lower()}"
            )
            if not prepared.manifest.owner_review_authorized:
                print(
                    "error: observation preserved; owner review is not authorized",
                    file=sys.stderr,
                )
                return EXIT_INCOMPLETE_PREPARATION
        else:
            finalized = finalize_development_baseline_run(
                repository_root=args.repository_root,
                output_root=args.output_root,
                owner_assessments=args.owner_assessments,
                freeze_date=args.freeze_date,
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
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXIT_SUCCESS",
    "EXIT_VALIDATION_ERROR",
    "EXIT_INCOMPLETE_PREPARATION",
    "build_parser",
    "main",
]
