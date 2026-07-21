"""Command-line interface for deterministic frozen-corpus batch ingestion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.ingestion.batch import (
    BatchManifestError,
    ingest_corpus,
)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a frozen-corpus split into validated JSON documents."
    )
    parser.add_argument(
        "--source-register",
        type=Path,
        default=Path("data/manifests/source_register.csv"),
    )
    parser.add_argument(
        "--corpus-split",
        type=Path,
        default=Path("data/manifests/corpus_split.csv"),
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--synthetic-root",
        type=Path,
        default=Path("data/synthetic"),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=("development", "held_out", "all"),
        default="all",
    )
    parser.add_argument("--parser-commit", required=True)
    parser.add_argument(
        "--run-type",
        choices=("held_out_first_run", "full_corpus_validation"),
        required=True,
    )
    parser.add_argument("--report", type=Path, required=True)
    return parser


def _validate_inputs(args: argparse.Namespace) -> str | None:
    for label, path in (
        ("source register", args.source_register),
        ("corpus split", args.corpus_split),
    ):
        if not path.is_file():
            return f"{label} does not exist or is not a file"
    for label, path in (
        ("raw root", args.raw_root),
        ("synthetic root", args.synthetic_root),
    ):
        if not path.is_dir():
            return f"{label} does not exist or is not a directory"
    return None


def main(argv: list[str] | None = None) -> int:
    """Run one deterministic batch and return a stable process exit code."""
    args = _build_argument_parser().parse_args(argv)
    input_error = _validate_inputs(args)
    if input_error is not None:
        print(f"error: {input_error}", file=sys.stderr)
        return 2

    try:
        report = ingest_corpus(
            source_register_path=args.source_register,
            corpus_split_path=args.corpus_split,
            raw_root=args.raw_root,
            synthetic_root=args.synthetic_root,
            output_root=args.output_root,
            split=None if args.split == "all" else args.split,
            parser_commit=args.parser_commit,
            run_type=args.run_type,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    except (BatchManifestError, ValidationError, OSError, ValueError) as error:
        message = " ".join(str(error).split()) or type(error).__name__
        print(f"error: {message[:300]}", file=sys.stderr)
        return 2

    print(
        f"sources={report.source_count} successful={report.success_count} "
        f"warning_sources={report.warning_source_count} "
        f"failed={report.failure_count} report={args.report.resolve()}"
    )
    return 1 if report.failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
