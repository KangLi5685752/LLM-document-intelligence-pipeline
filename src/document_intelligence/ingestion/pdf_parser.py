"""Page-level PDF ingestion with deterministic provenance."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from document_intelligence.ingestion.exceptions import DocumentParseError
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
    SourceLocation,
)
from document_intelligence.ingestion.utils import (
    calculate_sha256,
    make_block_id,
    make_document_id,
    normalize_text,
    validate_input_file,
)


def _metadata_value(metadata: Any, attribute: str) -> str | None:
    """Read one PDF metadata value without leaking parser-specific objects."""
    try:
        value = getattr(metadata, attribute, None)
    except Exception:
        return None
    if value is None:
        return None
    normalized = normalize_text(str(value))
    return normalized or None


def _metadata_datetime(metadata: Any, attribute: str) -> datetime | None:
    """Read one parsed PDF date when pypdf exposes it as a datetime."""
    try:
        value = getattr(metadata, attribute, None)
    except Exception:
        return None
    return value if isinstance(value, datetime) else None


def parse_pdf(path: Path, source_id: str | None = None) -> ParsedDocument:
    """Parse one readable PDF into one page-text block per page."""
    resolved_path = validate_input_file(Path(path))

    try:
        checksum = calculate_sha256(resolved_path)
        document_id = make_document_id(source_id, checksum)
        reader = PdfReader(resolved_path, strict=False)
        is_encrypted = bool(reader.is_encrypted)
        if is_encrypted and reader.decrypt("") == 0:
            raise DocumentParseError(
                "encrypted PDF cannot be read without credentials",
                path=resolved_path,
                source_format=SourceFormat.PDF,
            )

        raw_metadata = reader.metadata
        title = _metadata_value(raw_metadata, "title")
        author = _metadata_value(raw_metadata, "author")
        document_date = _metadata_datetime(raw_metadata, "creation_date")

        blocks: list[DocumentBlock] = []
        blank_pages: list[int] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            block_warnings: list[str] = []
            if not text:
                blank_pages.append(page_number)
                block_warnings.append("No text was extracted from this PDF page")
            blocks.append(
                DocumentBlock(
                    block_id=make_block_id(document_id, page_number),
                    sequence=page_number,
                    block_type=BlockType.PAGE_TEXT,
                    text=text,
                    location=SourceLocation(
                        location_type=LocationType.PAGE,
                        location_value=str(page_number),
                        page_number=page_number,
                    ),
                    metadata={"character_count": len(text)},
                    warnings=block_warnings,
                )
            )

        warnings: list[str] = []
        if blank_pages:
            warnings.append(
                "Pages with no extracted text: "
                + ", ".join(str(page) for page in blank_pages)
            )

        metadata: dict[str, str | int | float | bool | None | list[str]] = {
            "page_count": len(reader.pages),
            "is_encrypted": is_encrypted,
        }
        for key, attribute in (
            ("pdf_title", "title"),
            ("pdf_author", "author"),
            ("pdf_subject", "subject"),
            ("pdf_creator", "creator"),
            ("pdf_producer", "producer"),
        ):
            value = _metadata_value(raw_metadata, attribute)
            if value is not None:
                metadata[key] = value
        for key, attribute in (
            ("pdf_creation_date", "creation_date"),
            ("pdf_modification_date", "modification_date"),
        ):
            value = _metadata_datetime(raw_metadata, attribute)
            if value is not None:
                metadata[key] = value.isoformat()

        return ParsedDocument(
            document_id=document_id,
            source_id=source_id,
            source_format=SourceFormat.PDF,
            filename=resolved_path.name,
            checksum_sha256=checksum,
            title=title,
            document_date=document_date,
            authors_or_senders=[author] if author else [],
            blocks=blocks,
            metadata=metadata,
            warnings=warnings,
            parse_status=(
                ParseStatus.SUCCESS_WITH_WARNINGS
                if warnings
                else ParseStatus.SUCCESS
            ),
        )
    except DocumentParseError:
        raise
    except Exception as error:
        raise DocumentParseError(
            "unable to parse PDF",
            path=resolved_path,
            source_format=SourceFormat.PDF,
        ) from error
