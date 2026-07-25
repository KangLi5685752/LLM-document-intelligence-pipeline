"""CLI for deterministic ParsedDocument-to-candidate extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from document_intelligence.extraction.deterministic import (
    DeterministicExtractionError,
    canonical_candidate_result_json,
    extract_deterministic_candidates,
)
from document_intelligence.ingestion.models import ParsedDocument


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract deterministic candidate facts from one ParsedDocument JSON file."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Existing JSON file containing exactly one ParsedDocument.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional candidate-result JSON path; stdout is used when omitted.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow deterministic replacement of an existing output file.",
    )
    return parser


def _load_document(path: Path) -> ParsedDocument:
    if not path.is_file():
        raise DeterministicExtractionError("input must be an existing JSON file")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise DeterministicExtractionError("input JSON could not be read") from error
    try:
        return ParsedDocument.model_validate_json(content)
    except ValidationError as error:
        raise DeterministicExtractionError(
            "input JSON is not a valid ParsedDocument"
        ) from error


def _write_output(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise DeterministicExtractionError(
            "output already exists; use --force to overwrite it"
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as error:
        raise DeterministicExtractionError("output JSON could not be written") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run deterministic extraction with concise path-free failures."""
    args = _build_parser().parse_args(argv)
    try:
        document = _load_document(args.input)
        result = extract_deterministic_candidates(document)
        content = canonical_candidate_result_json(result)
        if args.output is None:
            sys.stdout.write(content)
        else:
            _write_output(args.output, content, force=args.force)
    except (DeterministicExtractionError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
