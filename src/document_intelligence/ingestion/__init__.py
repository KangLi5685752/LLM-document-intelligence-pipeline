"""Versioned, provenance-preserving document ingestion interfaces."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from document_intelligence.ingestion.batch import (
        BatchIngestionItem,
        BatchIngestionReport,
        BatchItemStatus,
        ingest_corpus,
        load_active_source_specs,
    )
    from document_intelligence.ingestion.dispatcher import parse_document
    from document_intelligence.ingestion.eml_parser import parse_eml
    from document_intelligence.ingestion.exceptions import (
        DocumentIngestionError,
        DocumentParseError,
        UnsupportedDocumentFormatError,
    )
    from document_intelligence.ingestion.models import (
        BlockType,
        DocumentBlock,
        LocationType,
        ParseStatus,
        ParsedDocument,
        SourceFormat,
        SourceLocation,
    )
    from document_intelligence.ingestion.pdf_parser import parse_pdf
    from document_intelligence.ingestion.pptx_parser import parse_pptx


__all__ = [
    "ParsedDocument",
    "DocumentBlock",
    "SourceLocation",
    "SourceFormat",
    "ParseStatus",
    "BlockType",
    "LocationType",
    "DocumentIngestionError",
    "UnsupportedDocumentFormatError",
    "DocumentParseError",
    "parse_document",
    "parse_pdf",
    "parse_pptx",
    "parse_eml",
    "BatchItemStatus",
    "BatchIngestionItem",
    "BatchIngestionReport",
    "ingest_corpus",
    "load_active_source_specs",
]


_EXPORT_MODULES = {
    "ParsedDocument": "document_intelligence.ingestion.models",
    "DocumentBlock": "document_intelligence.ingestion.models",
    "SourceLocation": "document_intelligence.ingestion.models",
    "SourceFormat": "document_intelligence.ingestion.models",
    "ParseStatus": "document_intelligence.ingestion.models",
    "BlockType": "document_intelligence.ingestion.models",
    "LocationType": "document_intelligence.ingestion.models",
    "DocumentIngestionError": "document_intelligence.ingestion.exceptions",
    "UnsupportedDocumentFormatError": "document_intelligence.ingestion.exceptions",
    "DocumentParseError": "document_intelligence.ingestion.exceptions",
    "parse_document": "document_intelligence.ingestion.dispatcher",
    "parse_pdf": "document_intelligence.ingestion.pdf_parser",
    "parse_pptx": "document_intelligence.ingestion.pptx_parser",
    "parse_eml": "document_intelligence.ingestion.eml_parser",
    "BatchItemStatus": "document_intelligence.ingestion.batch",
    "BatchIngestionItem": "document_intelligence.ingestion.batch",
    "BatchIngestionReport": "document_intelligence.ingestion.batch",
    "ingest_corpus": "document_intelligence.ingestion.batch",
    "load_active_source_specs": "document_intelligence.ingestion.batch",
}


def __getattr__(name: str) -> Any:
    """Load public ingestion attributes only when requested."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
