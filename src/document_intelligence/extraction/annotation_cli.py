"""CLI for deterministic validation of the public-PDF annotation draft."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from document_intelligence.extraction.annotations import (
    PublicGoldValidationReport,
    validate_public_gold_dataset,
)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate public-PDF annotations against ParsedDocument JSON."
    )
    parser.add_argument(
        "--facts",
        type=Path,
        default=Path("data/annotations/public_gold_facts_v0.1.jsonl"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/annotations/public_gold_cases_v0.1.jsonl"),
    )
    parser.add_argument(
        "--corpus-split",
        type=Path,
        default=Path("data/manifests/corpus_split.csv"),
    )
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def _validate_paths(args: argparse.Namespace) -> str | None:
    for label, path in (
        ("facts", args.facts),
        ("cases", args.cases),
        ("corpus split", args.corpus_split),
    ):
        if not path.is_file():
            return f"{label} does not exist or is not a file: {path}"
    if not args.parsed_root.is_dir():
        return f"parsed root does not exist or is not a directory: {args.parsed_root}"
    return None


def _write_report(path: Path, report: PublicGoldValidationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Validate annotations and return a stable process exit code."""
    args = _build_argument_parser().parse_args(argv)
    path_error = _validate_paths(args)
    if path_error is not None:
        print(f"error: {path_error}", file=sys.stderr)
        return 2

    try:
        report = validate_public_gold_dataset(
            fact_path=args.facts,
            case_path=args.cases,
            corpus_split_path=args.corpus_split,
            parsed_document_root=args.parsed_root,
        )
        _write_report(args.report, report)
    except (OSError, ValueError) as error:
        message = " ".join(str(error).split()) or type(error).__name__
        print(f"error: {message[:500]}", file=sys.stderr)
        return 1

    verification = "pending" if report.draft_count else "recorded"
    print(
        f"facts={report.fact_count} cases={report.challenge_case_count} "
        f"development={report.development_fact_count} "
        f"held_out={report.held_out_fact_count} drafts={report.draft_count} "
        f"owner_verification={verification} passed={str(report.passed).lower()} "
        f"report={args.report.resolve()}"
    )
    if not report.passed:
        for error in report.errors:
            print(f"error: {error[:500]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
