"""Tests for the versioned Common Document Object and shared utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

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
)


CHECKSUM = "A" * 64


def _location(source_format: SourceFormat) -> SourceLocation:
    if source_format is SourceFormat.PDF:
        return SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        )
    if source_format is SourceFormat.PPTX:
        return SourceLocation(
            location_type=LocationType.SLIDE,
            location_value="1",
            slide_number=1,
            element_index=1,
        )
    return SourceLocation(
        location_type=LocationType.EMAIL_BODY,
        location_value="body",
        message_id="<message@example.invalid>",
    )


def _document(source_format: SourceFormat = SourceFormat.PDF) -> ParsedDocument:
    block_type = {
        SourceFormat.PDF: BlockType.PAGE_TEXT,
        SourceFormat.PPTX: BlockType.SHAPE_TEXT,
        SourceFormat.EML: BlockType.EMAIL_BODY,
    }[source_format]
    return ParsedDocument(
        document_id="DOC-S001",
        source_id="S001",
        source_format=source_format,
        filename=f"fixture.{source_format.value.lower()}",
        checksum_sha256=CHECKSUM,
        blocks=[
            DocumentBlock(
                block_id="DOC-S001-B0001",
                sequence=1,
                block_type=block_type,
                text="Example text",
                location=_location(source_format),
            )
        ],
        parse_status=ParseStatus.SUCCESS,
    )


@pytest.mark.parametrize(
    "source_format",
    [SourceFormat.PDF, SourceFormat.PPTX, SourceFormat.EML],
)
def test_valid_parsed_documents(source_format: SourceFormat) -> None:
    document = _document(source_format)

    assert document.source_format is source_format
    assert document.schema_version == "0.1"
    assert document.block_count == 1


def test_json_serialisation_round_trip() -> None:
    document = _document()

    revalidated = ParsedDocument.model_validate_json(document.model_dump_json())

    assert revalidated == document


def test_unknown_fields_are_rejected() -> None:
    payload = _document().model_dump()
    payload["unexpected"] = "rejected"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ParsedDocument.model_validate(payload)


@pytest.mark.parametrize(
    "checksum",
    ["a" * 64, "A" * 63, "G" * 64],
)
def test_invalid_sha256_values_are_rejected(checksum: str) -> None:
    payload = _document().model_dump()
    payload["checksum_sha256"] = checksum

    with pytest.raises(ValidationError):
        ParsedDocument.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"location_type": "page", "location_value": "1"},
        {
            "location_type": "page",
            "location_value": "1",
            "page_number": 1,
            "slide_number": 1,
        },
        {"location_type": "slide", "location_value": "1"},
        {
            "location_type": "slide",
            "location_value": "1",
            "slide_number": 0,
        },
    ],
)
def test_invalid_page_and_slide_locators_are_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SourceLocation.model_validate(payload)


def test_email_location_without_message_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="require message_id"):
        SourceLocation(
            location_type=LocationType.EMAIL_BODY,
            location_value="body",
        )


def test_incompatible_source_format_location_is_rejected() -> None:
    payload = _document(SourceFormat.PDF).model_dump()
    payload["blocks"][0]["location"] = _location(SourceFormat.PPTX).model_dump()

    with pytest.raises(ValidationError, match="incompatible block locations"):
        ParsedDocument.model_validate(payload)


def test_duplicate_block_ids_are_rejected() -> None:
    payload = _document().model_dump()
    payload["blocks"].append(
        DocumentBlock(
            block_id="DOC-S001-B0001",
            sequence=2,
            block_type=BlockType.PAGE_TEXT,
            text="Second page",
            location=SourceLocation(
                location_type=LocationType.PAGE,
                location_value="2",
                page_number=2,
            ),
        ).model_dump()
    )

    with pytest.raises(ValidationError, match="block IDs must be unique"):
        ParsedDocument.model_validate(payload)


def test_non_contiguous_block_sequences_are_rejected() -> None:
    payload = _document().model_dump()
    payload["blocks"][0]["sequence"] = 2

    with pytest.raises(ValidationError, match="exactly 1..N"):
        ParsedDocument.model_validate(payload)


def test_success_with_document_warnings_is_rejected() -> None:
    payload = _document().model_dump()
    payload["warnings"] = ["Unexpected warning"]

    with pytest.raises(ValidationError, match="SUCCESS cannot"):
        ParsedDocument.model_validate(payload)


def test_success_with_block_warnings_is_rejected() -> None:
    payload = _document().model_dump()
    payload["blocks"][0]["warnings"] = ["Block warning"]

    with pytest.raises(ValidationError, match="SUCCESS cannot"):
        ParsedDocument.model_validate(payload)


def test_success_with_warnings_requires_a_warning() -> None:
    payload = _document().model_dump()
    payload["parse_status"] = ParseStatus.SUCCESS_WITH_WARNINGS

    with pytest.raises(ValidationError, match="requires a document or block warning"):
        ParsedDocument.model_validate(payload)


def test_parent_block_cannot_reference_itself() -> None:
    with pytest.raises(ValidationError, match="cannot equal block_id"):
        DocumentBlock(
            block_id="DOC-S001-B0001",
            sequence=1,
            block_type=BlockType.PAGE_TEXT,
            text="Example",
            location=_location(SourceFormat.PDF),
            parent_block_id="DOC-S001-B0001",
        )


def test_blank_page_block_requires_warning() -> None:
    with pytest.raises(ValidationError, match="blank page-text blocks"):
        DocumentBlock(
            block_id="DOC-S001-B0001",
            sequence=1,
            block_type=BlockType.PAGE_TEXT,
            text="",
            location=_location(SourceFormat.PDF),
        )


def test_normalize_text_preserves_internal_line_breaks() -> None:
    assert normalize_text("\r\nFirst  \r\nSecond\t \r\n\r\n") == "First\nSecond"


def test_hash_and_identifier_helpers_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "fixture.bin"
    path.write_bytes(b"common document object")
    expected = hashlib.sha256(path.read_bytes()).hexdigest().upper()

    assert calculate_sha256(path) == expected
    assert make_document_id("S010", expected) == "DOC-S010"
    assert make_document_id(None, expected) == f"DOC-{expected[:12]}"
    assert make_block_id("DOC-S010", 1) == "DOC-S010-B0001"
