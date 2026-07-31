"""CLI for recording and validating the supplied v0.4 owner assessment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from document_intelligence.extraction.owner_assessment_v0_4 import (
    OwnerAssessmentV04Error,
    record_completed_owner_assessment_v0_4,
    validate_completed_owner_assessment_v0_4,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the record-and-validate-only command contract."""
    parser = argparse.ArgumentParser(
        description="Record and validate human-supplied v0.4 owner decisions."
    )
    operations = parser.add_subparsers(dest="operation", required=True)
    record = operations.add_parser("record", help="Record supplied owner decisions.")
    record.add_argument("--repository-root", required=True, type=Path)
    record.add_argument("--decision-file", required=True, type=Path)
    record.add_argument("--output-file", required=True, type=Path)
    record.add_argument("--validation-report", required=True, type=Path)
    record.add_argument("--force", action="store_true")
    validate = operations.add_parser(
        "validate", help="Independently validate a completed owner assessment."
    )
    validate.add_argument("--repository-root", required=True, type=Path)
    validate.add_argument("--completed-assessment", required=True, type=Path)
    validate.add_argument("--validation-report", required=True, type=Path)
    validate.add_argument("--force", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested bounded owner-assessment operation."""
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.operation == "record":
            completed, report = record_completed_owner_assessment_v0_4(
                repository_root=arguments.repository_root,
                decision_file=arguments.decision_file,
                output_file=arguments.output_file,
                validation_report=arguments.validation_report,
                force=arguments.force,
            )
            print(
                f"recorded={len(completed.assessments)} "
                f"validation={report.validation_status} passed={report.passed_count}"
            )
        else:
            report = validate_completed_owner_assessment_v0_4(
                repository_root=arguments.repository_root,
                completed_assessment=arguments.completed_assessment,
                validation_report=arguments.validation_report,
                force=arguments.force,
            )
            print(
                f"validation={report.validation_status} passed={report.passed_count} "
                f"failed={report.failed_count} pending={report.pending_count}"
            )
    except (OwnerAssessmentV04Error, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
