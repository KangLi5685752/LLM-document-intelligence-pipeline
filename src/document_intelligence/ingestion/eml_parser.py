"""Plain-text EML ingestion with current-body and history separation."""

from __future__ import annotations

import re
from datetime import datetime
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

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


SUPPORTED_HEADERS = (
    "Subject",
    "From",
    "To",
    "Cc",
    "Date",
    "Message-ID",
    "In-Reply-To",
    "References",
)

_HISTORY_PATTERNS = (
    re.compile(r"^-{5,}\s*Original Message\s*-{5,}$", re.IGNORECASE),
    re.compile(r"^-{5,}\s*Forwarded message\s*-{5,}$", re.IGNORECASE),
    re.compile(r"^Selected quoted history:$", re.IGNORECASE),
    re.compile(r"^Selected quoted and forwarded history:$", re.IGNORECASE),
    re.compile(r"^On .+ wrote:$", re.IGNORECASE),
)


def _header_value(message: Message, header_name: str) -> str | None:
    value = message.get(header_name)
    if value is None:
        return None
    normalized = normalize_text(str(value))
    return normalized or None


def _message_ids(value: str | None) -> list[str]:
    """Extract message identifiers in their deterministic header order."""
    if not value:
        return []
    bracketed = re.findall(r"<[^<>]+>", value)
    if bracketed:
        return bracketed
    return [part for part in value.split() if part]


def _addresses(message: Message, header_name: str) -> list[str]:
    values = [str(value) for value in message.get_all(header_name, [])]
    return [
        f"{name} <{address}>" if name and address else name or address
        for name, address in getaddresses(values)
        if name or address
    ]


def _part_text(part: Message) -> str:
    content = part.get_content()
    if isinstance(content, str):
        return content
    charset = part.get_content_charset() or "utf-8"
    return content.decode(charset, errors="replace")


def _plain_text_parts(
    message: Message,
) -> tuple[list[str], list[str], list[str]]:
    """Return body parts, attachment filenames, and attachment content types."""
    body_parts: list[str] = []
    attachment_filenames: list[str] = []
    attachment_content_types: list[str] = []

    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.is_multipart():
            continue
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "attachment" or filename is not None:
            attachment_filenames.append(filename or "unnamed")
            attachment_content_types.append(part.get_content_type())
            continue
        if part.get_content_type() == "text/plain":
            body_parts.append(_part_text(part))
    return body_parts, attachment_filenames, attachment_content_types


def _split_quoted_history(text: str) -> tuple[str, str | None, str | None]:
    """Split current content from the first recognized quoted-history marker."""
    lines = text.split("\n")
    split_index: int | None = None
    separator: str | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in _HISTORY_PATTERNS):
            split_index = index
            separator = stripped
            break
        if stripped.startswith(">"):
            split_index = index
            separator = "quoted lines"
            break

    if split_index is None:
        return normalize_text(text), None, None
    current_body = normalize_text("\n".join(lines[:split_index]))
    quoted_history = normalize_text("\n".join(lines[split_index:]))
    return current_body, quoted_history or None, separator


def parse_eml(path: Path, source_id: str | None = None) -> ParsedDocument:
    """Parse one plain-text EML with explicit header and history blocks."""
    resolved_path = validate_input_file(Path(path))

    try:
        checksum = calculate_sha256(resolved_path)
        document_id = make_document_id(source_id, checksum)
        message = BytesParser(policy=default).parsebytes(resolved_path.read_bytes())
        raw_message_id = _header_value(message, "Message-ID")
        message_id = raw_message_id or f"<{document_id.lower()}@local.invalid>"

        body_parts, attachment_filenames, attachment_content_types = (
            _plain_text_parts(message)
        )
        normalized_parts = [normalize_text(part) for part in body_parts]
        readable_parts = [part for part in normalized_parts if part]
        if not readable_parts:
            raise DocumentParseError(
                "EML contains no readable text/plain body",
                path=resolved_path,
                source_format=SourceFormat.EML,
            )
        combined_body = "\n\n--- text/plain part ---\n\n".join(readable_parts)
        current_body, quoted_history, history_separator = _split_quoted_history(
            combined_body
        )
        if not current_body:
            raise DocumentParseError(
                "EML contains no readable current message body",
                path=resolved_path,
                source_format=SourceFormat.EML,
            )

        raw_date = _header_value(message, "Date")
        document_date: datetime | None = None
        if raw_date:
            try:
                document_date = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError, OverflowError):
                document_date = None

        in_reply_to = _header_value(message, "In-Reply-To")
        references = _message_ids(_header_value(message, "References"))
        senders = _addresses(message, "From")
        to_recipients = _addresses(message, "To")
        cc_recipients = _addresses(message, "Cc")

        blocks: list[DocumentBlock] = []
        for header_name in SUPPORTED_HEADERS:
            value = _header_value(message, header_name)
            if value is None:
                continue
            sequence = len(blocks) + 1
            blocks.append(
                DocumentBlock(
                    block_id=make_block_id(document_id, sequence),
                    sequence=sequence,
                    block_type=BlockType.EMAIL_HEADER,
                    text=f"{header_name}: {value}",
                    location=SourceLocation(
                        location_type=LocationType.EMAIL_HEADER,
                        location_value=header_name,
                        message_id=message_id,
                    ),
                    metadata={"header_name": header_name},
                )
            )

        body_sequence = len(blocks) + 1
        blocks.append(
            DocumentBlock(
                block_id=make_block_id(document_id, body_sequence),
                sequence=body_sequence,
                block_type=BlockType.EMAIL_BODY,
                text=current_body,
                location=SourceLocation(
                    location_type=LocationType.EMAIL_BODY,
                    location_value="body",
                    message_id=message_id,
                ),
                metadata={"plain_text_part_count": len(readable_parts)},
            )
        )
        if quoted_history is not None:
            history_sequence = len(blocks) + 1
            history_metadata: dict[
                str, str | int | float | bool | None | list[str]
            ] = {}
            if history_separator is not None:
                history_metadata["separator"] = history_separator
            blocks.append(
                DocumentBlock(
                    block_id=make_block_id(document_id, history_sequence),
                    sequence=history_sequence,
                    block_type=BlockType.QUOTED_HISTORY,
                    text=quoted_history,
                    location=SourceLocation(
                        location_type=LocationType.QUOTED_HISTORY,
                        location_value="quoted_history",
                        message_id=message_id,
                    ),
                    metadata=history_metadata,
                )
            )

        warnings: list[str] = []
        if raw_message_id is None:
            warnings.append("Message-ID header missing; deterministic local ID used")
        if attachment_filenames:
            warnings.append(
                f"Skipped {len(attachment_filenames)} email attachment(s)"
            )

        metadata: dict[str, str | int | float | bool | None | list[str]] = {
            "message_id": message_id,
            "references": references,
            "from_senders": senders,
            "to_recipients": to_recipients,
            "cc_recipients": cc_recipients,
            "content_type": message.get_content_type(),
            "attachment_count": len(attachment_filenames),
            "attachment_filenames": attachment_filenames,
            "attachment_content_types": attachment_content_types,
        }
        if in_reply_to is not None:
            metadata["in_reply_to"] = in_reply_to
        subject = _header_value(message, "Subject")
        if subject is not None:
            metadata["subject"] = subject
        if raw_date is not None:
            metadata["raw_date"] = raw_date
        if history_separator is not None:
            metadata["quoted_history_separator"] = history_separator

        return ParsedDocument(
            document_id=document_id,
            source_id=source_id,
            source_format=SourceFormat.EML,
            filename=resolved_path.name,
            checksum_sha256=checksum,
            title=subject,
            document_date=document_date,
            authors_or_senders=senders,
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
            "unable to parse EML",
            path=resolved_path,
            source_format=SourceFormat.EML,
        ) from error
