"""Tests for page-level PDF ingestion."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from document_intelligence.ingestion.exceptions import DocumentParseError
from document_intelligence.ingestion.models import (
    BlockType,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
)
from document_intelligence.ingestion.pdf_parser import parse_pdf


def _add_text_page(writer: PdfWriter, text: str) -> None:
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_reference}
            )
        }
    )
    stream = DecodedStreamObject()
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(
        f"BT /F1 12 Tf 72 180 Td ({safe_text}) Tj ET".encode("ascii")
    )
    page[NameObject("/Contents")] = writer._add_object(stream)


def _write_pdf(path: Path, page_texts: list[str | None]) -> None:
    writer = PdfWriter()
    for text in page_texts:
        if text is None:
            writer.add_blank_page(width=300, height=300)
        else:
            _add_text_page(writer, text)
    writer.add_metadata({"/Title": "Temporary PDF", "/Author": "Test Author"})
    with path.open("wb") as handle:
        writer.write(handle)


def test_parse_pdf_extracts_text_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "minimal.pdf"
    _write_pdf(path, ["Extractable PDF text"])

    document = parse_pdf(path, "S-TEMP-PDF")

    assert document.source_format is SourceFormat.PDF
    assert document.parse_status is ParseStatus.SUCCESS
    assert re.fullmatch(r"[0-9A-F]{64}", document.checksum_sha256)
    assert document.title == "Temporary PDF"
    assert document.authors_or_senders == ["Test Author"]
    assert document.metadata["page_count"] == 1
    assert document.blocks[0].block_type is BlockType.PAGE_TEXT
    assert "Extractable PDF text" in document.blocks[0].text
    ParsedDocument.model_validate_json(document.model_dump_json())


def test_parse_pdf_preserves_page_order_and_one_based_locators(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiple.pdf"
    _write_pdf(path, ["First page", "Second page", "Third page"])

    document = parse_pdf(path, "S-MULTI")

    assert document.block_count == 3
    assert [block.sequence for block in document.blocks] == [1, 2, 3]
    assert [block.location.location_type for block in document.blocks] == [
        LocationType.PAGE,
        LocationType.PAGE,
        LocationType.PAGE,
    ]
    assert [block.location.page_number for block in document.blocks] == [1, 2, 3]
    assert [block.location.location_value for block in document.blocks] == [
        "1",
        "2",
        "3",
    ]


def test_parse_pdf_ids_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "deterministic.pdf"
    _write_pdf(path, ["First", "Second"])

    first = parse_pdf(path, "S-DETERMINISTIC")
    second = parse_pdf(path, "S-DETERMINISTIC")

    assert first.document_id == second.document_id == "DOC-S-DETERMINISTIC"
    assert [block.block_id for block in first.blocks] == [
        block.block_id for block in second.blocks
    ]


def test_parse_pdf_retains_blank_page_with_warnings(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    _write_pdf(path, [None])

    document = parse_pdf(path, "S-BLANK")

    assert document.block_count == 1
    assert document.blocks[0].text == ""
    assert document.blocks[0].warnings
    assert document.warnings == ["Pages with no extracted text: 1"]
    assert document.parse_status is ParseStatus.SUCCESS_WITH_WARNINGS


def test_parse_pdf_malformed_file_raises_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "malformed.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(DocumentParseError, match="unable to parse PDF"):
        parse_pdf(path)


def test_parse_pdf_missing_file_raises_structured_error(tmp_path: Path) -> None:
    with pytest.raises(DocumentParseError, match="input file does not exist"):
        parse_pdf(tmp_path / "missing.pdf")
