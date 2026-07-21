"""Tests for plain-text EML ingestion and quoted-history separation."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from document_intelligence.ingestion.eml_parser import parse_eml
from document_intelligence.ingestion.exceptions import DocumentParseError
from document_intelligence.ingestion.models import (
    BlockType,
    ParsedDocument,
    SourceFormat,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EMAIL_ROOT = REPOSITORY_ROOT / "data" / "synthetic" / "email"


def _message(body: str, *, subject: str = "Résumé status") -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "Project Analyst <analyst@example.com>"
    message["To"] = "Delivery Team <delivery@example.com>"
    message["Cc"] = "Reviewer <reviewer@example.com>"
    message["Date"] = "Tue, 21 Jul 2026 09:30:00 +0000"
    message["Message-ID"] = "<current@example.com>"
    message["In-Reply-To"] = "<previous@example.com>"
    message["References"] = "<first@example.com> <previous@example.com>"
    message.set_content(body)
    return message


def _write_message(path: Path, message: EmailMessage) -> None:
    path.write_bytes(message.as_bytes())


def _blocks(document: ParsedDocument, block_type: BlockType) -> list[str]:
    return [block.text for block in document.blocks if block.block_type is block_type]


def test_parse_plain_text_eml_preserves_decoded_headers_and_thread_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "message.eml"
    _write_message(path, _message("Current message body."))

    document = parse_eml(path, "S-TEMP-EML")

    assert document.source_format is SourceFormat.EML
    assert document.title == "Résumé status"
    assert document.authors_or_senders == ["Project Analyst <analyst@example.com>"]
    assert document.document_date is not None
    assert document.document_date.isoformat() == "2026-07-21T09:30:00+00:00"
    assert document.metadata["message_id"] == "<current@example.com>"
    assert document.metadata["in_reply_to"] == "<previous@example.com>"
    assert document.metadata["references"] == [
        "<first@example.com>",
        "<previous@example.com>",
    ]
    assert document.metadata["to_recipients"] == [
        "Delivery Team <delivery@example.com>"
    ]
    assert document.metadata["cc_recipients"] == [
        "Reviewer <reviewer@example.com>"
    ]
    assert _blocks(document, BlockType.EMAIL_BODY) == ["Current message body."]
    assert not _blocks(document, BlockType.QUOTED_HISTORY)


def test_parse_eml_creates_supported_header_blocks(tmp_path: Path) -> None:
    path = tmp_path / "headers.eml"
    _write_message(path, _message("Body"))

    document = parse_eml(path, "S-HEADERS")
    header_blocks = [
        block for block in document.blocks if block.block_type is BlockType.EMAIL_HEADER
    ]

    assert len(header_blocks) == 8
    assert [block.metadata["header_name"] for block in header_blocks] == [
        "Subject",
        "From",
        "To",
        "Cc",
        "Date",
        "Message-ID",
        "In-Reply-To",
        "References",
    ]
    assert all(
        block.location.message_id == "<current@example.com>"
        for block in header_blocks
    )


@pytest.mark.parametrize(
    "separator",
    [
        "----- Original Message -----",
        "---------- Forwarded message ----------",
        "Selected quoted history:",
        "Selected quoted and forwarded history:",
        "On Mon, 20 Jul 2026, Previous Sender wrote:",
    ],
)
def test_parse_eml_separates_recognized_history_markers(
    tmp_path: Path,
    separator: str,
) -> None:
    path = tmp_path / "history.eml"
    body = f"Latest assertion: Green\n\n{separator}\nOld assertion: Amber"
    _write_message(path, _message(body))

    document = parse_eml(path, "S-HISTORY")
    current = _blocks(document, BlockType.EMAIL_BODY)
    history = _blocks(document, BlockType.QUOTED_HISTORY)

    assert current == ["Latest assertion: Green"]
    assert len(history) == 1
    assert separator in history[0]
    assert "Old assertion: Amber" in history[0]
    assert "Old assertion: Amber" not in current[0]


def test_parse_eml_keeps_greater_than_quotes_in_history(tmp_path: Path) -> None:
    path = tmp_path / "greater-than.eml"
    _write_message(path, _message("Current value\n> Old value\n> More history"))

    document = parse_eml(path, "S-QUOTED")

    assert _blocks(document, BlockType.EMAIL_BODY) == ["Current value"]
    assert _blocks(document, BlockType.QUOTED_HISTORY) == [
        "> Old value\n> More history"
    ]


def test_parse_multipart_eml_concatenates_plain_parts_in_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiple-parts.eml"
    message = _message("placeholder")
    message.clear_content()
    message.make_mixed()
    first = EmailMessage()
    first.set_content("First plain part")
    second = EmailMessage()
    second.set_content("Second plain part")
    message.attach(first)
    message.attach(second)
    _write_message(path, message)

    document = parse_eml(path, "S-MULTIPART")

    assert _blocks(document, BlockType.EMAIL_BODY) == [
        "First plain part\n\n--- text/plain part ---\n\nSecond plain part"
    ]


def test_parse_eml_skips_attachment_and_records_warning(tmp_path: Path) -> None:
    path = tmp_path / "attachment.eml"
    message = _message("Readable body")
    message.add_attachment(
        b"attachment bytes",
        maintype="application",
        subtype="octet-stream",
        filename="evidence.bin",
    )
    _write_message(path, message)

    document = parse_eml(path, "S-ATTACHMENT")

    assert _blocks(document, BlockType.EMAIL_BODY) == ["Readable body"]
    assert document.metadata["attachment_count"] == 1
    assert document.metadata["attachment_filenames"] == ["evidence.bin"]
    assert document.warnings == ["Skipped 1 email attachment(s)"]


def test_parse_html_only_eml_raises_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "html-only.eml"
    message = _message("placeholder")
    message.clear_content()
    message.set_content("<p>HTML only</p>", subtype="html")
    _write_message(path, message)

    with pytest.raises(DocumentParseError, match="no readable text/plain body"):
        parse_eml(path)


@pytest.mark.parametrize(
    ("source_id", "filename", "history_expected", "references"),
    [
        ("S012", "S012_atlas_migration_01.eml", False, []),
        (
            "S013",
            "S013_atlas_migration_02.eml",
            True,
            ["<atlas-001@example.com>"],
        ),
        (
            "S014",
            "S014_atlas_migration_03.eml",
            True,
            ["<atlas-001@example.com>", "<atlas-002@example.com>"],
        ),
    ],
)
def test_parse_committed_atlas_development_messages(
    source_id: str,
    filename: str,
    history_expected: bool,
    references: list[str],
) -> None:
    document = parse_eml(EMAIL_ROOT / filename, source_id)
    history = _blocks(document, BlockType.QUOTED_HISTORY)

    assert bool(history) is history_expected
    assert document.metadata["references"] == references
    assert document.metadata["message_id"]
    if source_id == "S013":
        assert "initial fictional Atlas migration update" not in _blocks(
            document, BlockType.EMAIL_BODY
        )[0]
        assert "initial fictional Atlas migration update" in history[0]
    if source_id == "S014":
        assert "Initial update: status Amber" not in _blocks(
            document, BlockType.EMAIL_BODY
        )[0]
        assert "Initial update: status Amber" in history[0]
    ParsedDocument.model_validate_json(document.model_dump_json())
