"""Single-document CLI for deterministic-baseline-v0.4 extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_v0_4 import (
    DETERMINISTIC_BASELINE_VERSION,
    DeterministicExtractionV04Error,
    canonical_candidate_result_json_v0_4,
    extract_deterministic_candidates_v0_4,
)
from document_intelligence.ingestion.models import ParsedDocument


def build_parser() -> argparse.ArgumentParser:
    """Build the bounded single-document v0.4 command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract one ParsedDocument with deterministic-baseline-v0.4; "
            "no evaluation or gold data is loaded."
        )
    )
    parser.add_argument("--version", action="version", version=DETERMINISTIC_BASELINE_VERSION)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate one input, run v0.4, and emit canonical JSON."""

    args = build_parser().parse_args(argv)
    if args.overwrite and args.output is None:
        print("error: --overwrite requires --output", file=sys.stderr)
        return 2
    if args.output is not None and args.output.exists() and not args.overwrite:
        print(f"error: output already exists: {args.output}", file=sys.stderr)
        return 2
    try:
        if not args.input.is_file():
            raise ValueError(f"input is not a file: {args.input}")
        document = ParsedDocument.model_validate_json(
            args.input.read_text(encoding="utf-8")
        )
        rendered = canonical_candidate_result_json_v0_4(
            extract_deterministic_candidates_v0_4(document)
        )
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (
        DeterministicExtractionV04Error,
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
