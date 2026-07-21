"""Single-document command-line interface for JSON ingestion output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from document_intelligence.ingestion.dispatcher import parse_document
from document_intelligence.ingestion.exceptions import (
    DocumentParseError,
    UnsupportedDocumentFormatError,
)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse one PDF, PPTX, or EML into provenance-preserving JSON."
        )
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--indent", type=int, default=2)
    return parser


def _warning_count(document: object) -> int:
    document_warnings = getattr(document, "warnings")
    blocks = getattr(document, "blocks")
    return len(document_warnings) + sum(len(block.warnings) for block in blocks)


def main(argv: list[str] | None = None) -> int:
    """Parse one document, write JSON, and return a stable process exit code."""
    args = _build_argument_parser().parse_args(argv)
    if args.indent < 0:
        print("error: --indent must not be negative", file=sys.stderr)
        return 2
    if not args.input_file.exists():
        print("error: input file does not exist", file=sys.stderr)
        return 2
    if not args.input_file.is_file():
        print("error: input path is not a file", file=sys.stderr)
        return 2

    try:
        document = parse_document(args.input_file, args.source_id)
    except UnsupportedDocumentFormatError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except DocumentParseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    json_output = document.model_dump_json(indent=args.indent)
    if args.output is None:
        print(json_output)
        return 0

    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_output + "\n", encoding="utf-8")
    except OSError as error:
        print(f"error: unable to write output: {type(error).__name__}", file=sys.stderr)
        return 1

    identifier = document.source_id or document.document_id
    print(
        f"source={identifier} format={document.source_format.value} "
        f"blocks={document.block_count} warnings={_warning_count(document)} "
        f"output={args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
