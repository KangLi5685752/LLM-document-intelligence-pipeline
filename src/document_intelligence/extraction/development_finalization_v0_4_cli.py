"""Bounded command-line boundary for deterministic v0.4 finalization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.extraction.development_finalization_v0_4 import (
    DevelopmentFinalizationV04Error,
    audit_finalization_readiness_v0_4,
    finalize_development_v0_4,
    validate_finalized_development_v0_4,
)


EXIT_SUCCESS = 0
EXIT_CONTRACT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    """Build the fixed audit/finalize/validate interface."""
    parser = argparse.ArgumentParser(
        description="Audit, finalize, or validate deterministic-baseline-v0.4."
    )
    operations = parser.add_subparsers(dest="operation", required=True)

    audit = operations.add_parser("audit", help="Read-only prerequisite audit.")
    audit.add_argument("--repository-root", type=Path, required=True)

    finalize = operations.add_parser(
        "finalize", help="Run the exact five-source transactional finalization."
    )
    finalize.add_argument("--repository-root", type=Path, required=True)
    finalize.add_argument("--parsed-root", type=Path, required=True)
    finalize.add_argument("--ingestion-report", type=Path, required=True)
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--freeze-date", required=True)
    finalize.add_argument(
        "--force",
        action="store_true",
        help="Replace only the fourteen fixed outputs transactionally.",
    )

    validate = operations.add_parser(
        "validate", help="Read-only validation of an installed v0.4 freeze."
    )
    validate.add_argument("--repository-root", type=Path, required=True)
    validate.add_argument("--output-root", type=Path, required=True)
    return parser


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    """Run one bounded operation and convert expected failures to exit code 2."""
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.operation == "audit":
            audit = audit_finalization_readiness_v0_4(
                repository_root=arguments.repository_root
            )
            _print_json(audit.model_dump(mode="json"))
        elif arguments.operation == "finalize":
            result = finalize_development_v0_4(
                repository_root=arguments.repository_root,
                parsed_root=arguments.parsed_root,
                ingestion_report=arguments.ingestion_report,
                output_root=arguments.output_root,
                freeze_date=arguments.freeze_date,
                force=arguments.force,
            )
            _print_json(
                {
                    "artifact_count": len(result.artifact_paths),
                    "experiment_id": result.freeze_manifest.experiment_id,
                    "freeze_date": result.freeze_manifest.freeze_date,
                    "status": "finalized",
                }
            )
        else:
            freeze = validate_finalized_development_v0_4(
                repository_root=arguments.repository_root,
                output_root=arguments.output_root,
            )
            _print_json(
                {
                    "artifact_count": 14,
                    "experiment_id": freeze.experiment_id,
                    "freeze_date": freeze.freeze_date,
                    "status": "valid",
                }
            )
    except (DevelopmentFinalizationV04Error, ValidationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_CONTRACT_ERROR
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
