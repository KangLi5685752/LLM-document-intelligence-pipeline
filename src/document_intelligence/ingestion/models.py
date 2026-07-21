"""Versioned Common Document Object for local document ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


INGESTION_SCHEMA_VERSION: Literal["0.1"] = "0.1"

MetadataValue: TypeAlias = str | int | float | bool | None | list[str]


class SourceFormat(str, Enum):
    """Supported source-document formats."""

    PDF = "PDF"
    PPTX = "PPTX"
    EML = "EML"


class ParseStatus(str, Enum):
    """Successful parse outcomes; failures are represented by exceptions."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"


class LocationType(str, Enum):
    """Supported provenance-locator categories."""

    PAGE = "page"
    SLIDE = "slide"
    EMAIL_HEADER = "email_header"
    EMAIL_BODY = "email_body"
    QUOTED_HISTORY = "quoted_history"
    DOCUMENT_METADATA = "document_metadata"


class BlockType(str, Enum):
    """Supported Common Document Object block categories."""

    PAGE_TEXT = "page_text"
    SLIDE_TITLE = "slide_title"
    SHAPE_TEXT = "shape_text"
    TABLE = "table"
    EMAIL_HEADER = "email_header"
    EMAIL_BODY = "email_body"
    QUOTED_HISTORY = "quoted_history"
    METADATA = "metadata"


class SourceLocation(BaseModel):
    """Format-neutral provenance for a document block."""

    model_config = ConfigDict(extra="forbid")

    location_type: LocationType
    location_value: str
    page_number: int | None = Field(default=None, gt=0)
    slide_number: int | None = Field(default=None, gt=0)
    message_id: str | None = None
    element_index: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_locator(self) -> SourceLocation:
        """Require the identifiers appropriate to each locator type."""
        if not self.location_value.strip():
            raise ValueError("location_value must not be empty")

        if self.location_type is LocationType.PAGE:
            if self.page_number is None:
                raise ValueError("PAGE locations require page_number")
            if self.slide_number is not None:
                raise ValueError("PAGE locations forbid slide_number")
        elif self.location_type is LocationType.SLIDE:
            if self.slide_number is None:
                raise ValueError("SLIDE locations require slide_number")
            if self.page_number is not None:
                raise ValueError("SLIDE locations forbid page_number")
        elif self.location_type in {
            LocationType.EMAIL_HEADER,
            LocationType.EMAIL_BODY,
            LocationType.QUOTED_HISTORY,
        }:
            if self.message_id is None or not self.message_id.strip():
                raise ValueError(
                    f"{self.location_type.value} locations require message_id"
                )
        return self


class DocumentBlock(BaseModel):
    """One ordered text-bearing unit with explicit source provenance."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    sequence: int = Field(gt=0)
    block_type: BlockType
    text: str
    location: SourceLocation
    parent_block_id: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_block(self) -> DocumentBlock:
        """Enforce stable identifiers and explicit blank-page warnings."""
        if not self.block_id.strip():
            raise ValueError("block_id must not be blank")
        if self.block_id != self.block_id.strip():
            raise ValueError("block_id must not contain surrounding whitespace")
        if self.parent_block_id == self.block_id:
            raise ValueError("parent_block_id cannot equal block_id")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must not contain empty strings")
        if self.block_type is BlockType.PAGE_TEXT and not self.text:
            if not self.warnings:
                raise ValueError("blank page-text blocks require a warning")
        return self


class ParsedDocument(BaseModel):
    """Strict, versioned output of one format-specific parser."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"] = INGESTION_SCHEMA_VERSION
    document_id: str
    source_id: str | None = None
    source_format: SourceFormat
    filename: str
    checksum_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    title: str | None = None
    document_date: datetime | None = None
    authors_or_senders: list[str] = Field(default_factory=list)
    blocks: list[DocumentBlock]
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    parse_status: ParseStatus

    @model_validator(mode="after")
    def validate_document(self) -> ParsedDocument:
        """Enforce block identity, ordering, warning, and format invariants."""
        if not self.document_id.strip():
            raise ValueError("document_id must not be blank")
        if not self.filename.strip():
            raise ValueError("filename must not be blank")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must not contain empty strings")

        block_ids = [block.block_id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("block IDs must be unique")

        sequences = [block.sequence for block in self.blocks]
        if sorted(sequences) != list(range(1, len(self.blocks) + 1)):
            raise ValueError("block sequences must be unique and exactly 1..N")

        has_block_warnings = any(block.warnings for block in self.blocks)
        if self.parse_status is ParseStatus.SUCCESS and (
            self.warnings or has_block_warnings
        ):
            raise ValueError("SUCCESS cannot contain document or block warnings")
        if (
            self.parse_status is ParseStatus.SUCCESS_WITH_WARNINGS
            and not self.warnings
            and not has_block_warnings
        ):
            raise ValueError(
                "SUCCESS_WITH_WARNINGS requires a document or block warning"
            )

        allowed_locations = {
            SourceFormat.PDF: {
                LocationType.PAGE,
                LocationType.DOCUMENT_METADATA,
            },
            SourceFormat.PPTX: {
                LocationType.SLIDE,
                LocationType.DOCUMENT_METADATA,
            },
            SourceFormat.EML: {
                LocationType.EMAIL_HEADER,
                LocationType.EMAIL_BODY,
                LocationType.QUOTED_HISTORY,
                LocationType.DOCUMENT_METADATA,
            },
        }
        invalid = [
            block.location.location_type.value
            for block in self.blocks
            if block.location.location_type not in allowed_locations[self.source_format]
        ]
        if invalid:
            raise ValueError(
                f"{self.source_format.value} has incompatible block locations: "
                + ", ".join(invalid)
            )
        return self

    @property
    def block_count(self) -> int:
        """Return the number of blocks without adding a serialised field."""
        return len(self.blocks)
