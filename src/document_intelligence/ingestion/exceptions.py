"""Structured exceptions for local document ingestion."""

from __future__ import annotations

from pathlib import Path

from document_intelligence.ingestion.models import SourceFormat


class DocumentIngestionError(Exception):
    """Base error carrying a concise message and optional parse context."""

    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        source_format: SourceFormat | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.source_format = source_format

    def __str__(self) -> str:
        """Return only the user-facing message, without traceback details."""
        return self.message


class UnsupportedDocumentFormatError(DocumentIngestionError, ValueError):
    """Raised when a path suffix is absent or unsupported."""


class DocumentParseError(DocumentIngestionError):
    """Raised when a supported document cannot be parsed."""
