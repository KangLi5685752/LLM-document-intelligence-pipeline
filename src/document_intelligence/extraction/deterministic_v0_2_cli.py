"""Single-document CLI for deterministic-baseline-v0.2 extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_v0_2 import (
    DETERMINISTIC_BASELINE_VERSION,
    DeterministicExtractionV02Error,
    canonical_candidate_result_json_v0_2,
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.ingestion.models import ParsedDocument


def build_parser() -> argparse.ArgumentParser:
    """Build the bounded single-document v0.2 command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract one ParsedDocument with deterministic-baseline-v0.2; "
            "no evaluation or gold data is loaded."
        )
    )
    parser.add_argument("--version", action="version", version=DETERMINISTIC_BASELINE_VERSION)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to one ParsedDocument JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path; canonical CandidateExtractionResult JSON is printed if omitted.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of an existing output file.",
    )
    return parser


def _load_document(path: Path) -> ParsedDocument:
    if not path.is_file():
        raise ValueError(f"input is not a file: {path}")
    return ParsedDocument.model_validate_json(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Validate one input, run only v0.2 extraction, and emit canonical JSON."""

    args = build_parser().parse_args(argv)
    if args.overwrite and args.output is None:
        print("error: --overwrite requires --output", file=sys.stderr)
        return 2
    if args.output is not None and args.output.exists() and not args.overwrite:
        print(f"error: output already exists: {args.output}", file=sys.stderr)
        return 2

    try:
        document = _load_document(args.input)
        result = extract_deterministic_candidates_v0_2(document)
        rendered = canonical_candidate_result_json_v0_2(result)
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (
        DeterministicExtractionV02Error,
        OSError,
        UnicodeError,
        ValidationError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
