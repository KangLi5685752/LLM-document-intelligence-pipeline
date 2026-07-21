"""Deterministic shared utilities for document ingestion."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from document_intelligence.ingestion.exceptions import DocumentParseError


def validate_input_file(path: Path) -> Path:
    """Resolve and validate a local input file for a format-specific parser."""
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise DocumentParseError("input file does not exist", path=resolved_path)
    if not resolved_path.is_file():
        raise DocumentParseError("input path is not a file", path=resolved_path)
    return resolved_path


def calculate_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate an uppercase SHA-256 digest using chunked file reads."""
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"file does not exist: {resolved_path}")
    if not resolved_path.is_file():
        raise ValueError(f"path is not a file: {resolved_path}")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    digest = hashlib.sha256()
    with resolved_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_text(text: str) -> str:
    """Normalize line endings and trailing space while preserving line structure."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def make_document_id(source_id: str | None, checksum_sha256: str) -> str:
    """Build a stable identifier from a source ID or checksum prefix."""
    if source_id is not None:
        normalized_source_id = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            source_id.strip(),
        ).strip("-")
        if not normalized_source_id:
            raise ValueError("source_id must contain an identifier character")
        return f"DOC-{normalized_source_id.upper()}"

    if not re.fullmatch(r"[0-9A-Fa-f]{64}", checksum_sha256):
        raise ValueError("checksum_sha256 must contain 64 hexadecimal characters")
    return f"DOC-{checksum_sha256[:12].upper()}"


def make_block_id(document_id: str, sequence: int) -> str:
    """Build a deterministic block identifier for a positive sequence."""
    if not document_id.strip():
        raise ValueError("document_id must not be blank")
    if sequence <= 0:
        raise ValueError("sequence must be positive")
    return f"{document_id}-B{sequence:04d}"
