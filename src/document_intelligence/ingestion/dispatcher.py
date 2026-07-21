"""Explicit extension-based dispatch for supported document formats."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from document_intelligence.ingestion.eml_parser import parse_eml
from document_intelligence.ingestion.exceptions import UnsupportedDocumentFormatError
from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.ingestion.pdf_parser import parse_pdf
from document_intelligence.ingestion.pptx_parser import parse_pptx


Parser = Callable[[Path, str | None], ParsedDocument]

PARSER_REGISTRY: dict[str, Parser] = {
    ".pdf": parse_pdf,
    ".pptx": parse_pptx,
    ".eml": parse_eml,
}


def parse_document(path: Path, source_id: str | None = None) -> ParsedDocument:
    """Dispatch one local document by its case-insensitive filename suffix."""
    document_path = Path(path)
    suffix = document_path.suffix.casefold()
    parser = PARSER_REGISTRY.get(suffix)
    if parser is None:
        label = suffix or "<missing>"
        raise UnsupportedDocumentFormatError(
            f"unsupported document extension: {label}",
            path=document_path,
        )
    return parser(document_path, source_id)
