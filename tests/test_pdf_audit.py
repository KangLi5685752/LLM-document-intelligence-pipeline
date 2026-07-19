"""Tests for the deterministic local PDF audit utility."""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter

from document_intelligence.audit.pdf_audit import (
    AUDIT_CSV_FIELDS,
    audit_directory,
    audit_pdf,
    calculate_sha256,
    choose_sample_pages,
    classify_scanned_page_risk,
    main,
    write_audit_csv,
)


def _write_blank_pdf(path: Path, page_count: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)


def test_package_import_does_not_preload_pdf_audit_module() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import document_intelligence.audit\n"
                "print('document_intelligence.audit.pdf_audit' in sys.modules)\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "False\n"
    assert "RuntimeWarning" not in result.stderr


def test_module_cli_does_not_emit_runpy_warning_for_empty_directory(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "empty"
    output_path = tmp_path / "audit.csv"
    input_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.audit.pdf_audit",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "error: no files matched '*.pdf' in" in result.stderr
    assert "RuntimeWarning" not in result.stderr
    assert "found in sys.modules" not in result.stderr
    assert "prior to execution" not in result.stderr
    assert not output_path.exists()


def test_package_level_lazy_exports_match_pdf_audit_module() -> None:
    from document_intelligence.audit import (
        PdfAuditResult as exported_result,
        audit_directory as exported_directory,
        audit_pdf as exported_pdf,
    )
    from document_intelligence.audit import pdf_audit

    assert exported_result is pdf_audit.PdfAuditResult
    assert exported_directory is pdf_audit.audit_directory
    assert exported_pdf is pdf_audit.audit_pdf


def test_calculate_sha256_returns_uppercase_known_digest(tmp_path: Path) -> None:
    path = tmp_path / "known.bin"
    content = b"deterministic audit fixture"
    path.write_bytes(content)

    assert calculate_sha256(path) == hashlib.sha256(content).hexdigest().upper()


@pytest.mark.parametrize(
    ("page_count", "expected"),
    [
        (0, []),
        (1, [1]),
        (2, [1, 2]),
        (5, [1, 3, 5]),
        (6, [1, 3, 6]),
    ],
)
def test_choose_sample_pages(page_count: int, expected: list[int]) -> None:
    assert choose_sample_pages(page_count) == expected


@pytest.mark.parametrize(
    ("page_text_counts", "expected"),
    [
        ([10, 20], "none_observed"),
        ([0, 1, 1, 1, 1, 1, 1, 1, 1, 1], "low"),
        ([0, 0, 1, 1, 1, 1, 1, 1, 1, 1], "medium"),
        ([0, 0, 0, 1], "high"),
        ([], "unknown"),
    ],
)
def test_classify_scanned_page_risk(
    page_text_counts: list[int],
    expected: str,
) -> None:
    assert classify_scanned_page_risk(page_text_counts) == expected


def test_audit_pdf_handles_temporary_blank_pdf(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    _write_blank_pdf(path, page_count=2)

    result = audit_pdf(path)

    assert result.audit_status == "completed"
    assert result.page_count == 2
    assert result.pages_with_no_text == [1, 2]
    assert result.near_empty_pages == [1, 2]
    assert result.probable_scanned_page_risk == "high"
    assert result.warning_count == len(result.warnings)


def test_audit_directory_sorts_files_by_filename(tmp_path: Path) -> None:
    _write_blank_pdf(tmp_path / "zeta.pdf")
    _write_blank_pdf(tmp_path / "alpha.pdf")

    results = audit_directory(tmp_path)

    assert [result.filename for result in results] == ["alpha.pdf", "zeta.pdf"]


def test_unreadable_pdf_does_not_stop_valid_pdf(tmp_path: Path) -> None:
    (tmp_path / "broken.pdf").write_bytes(b"not a PDF")
    _write_blank_pdf(tmp_path / "valid.pdf")

    results = audit_directory(tmp_path)
    by_filename = {result.filename: result for result in results}

    assert len(results) == 2
    assert by_filename["broken.pdf"].audit_status == "failed"
    assert by_filename["broken.pdf"].error_message
    assert by_filename["valid.pdf"].audit_status == "completed"


def test_write_audit_csv_preserves_header_and_field_count(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    output_path = tmp_path / "audit.csv"
    _write_blank_pdf(pdf_path, page_count=2)

    write_audit_csv([audit_pdf(pdf_path)], output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == AUDIT_CSV_FIELDS
    assert all(len(row) == 18 for row in rows)
    row = dict(zip(rows[0], rows[1]))
    assert row["mean_page_text_chars"] == "0.00"
    assert row["pages_with_no_text"] == "1;2"
    assert "extracted_text" not in rows[0]
    assert "page_text" not in rows[0]


def test_write_audit_csv_writes_header_for_empty_results(tmp_path: Path) -> None:
    output_path = tmp_path / "empty.csv"

    write_audit_csv([], output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows == [AUDIT_CSV_FIELDS]


def test_cli_returns_two_for_missing_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.csv"

    exit_code = main(
        [
            "--input-dir",
            str(tmp_path / "missing"),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    assert not output_path.exists()


def test_cli_returns_two_when_no_pdfs_match(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.csv"

    exit_code = main(
        [
            "--input-dir",
            str(tmp_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 2
    assert not output_path.exists()


def test_cli_rejects_negative_near_empty_threshold(tmp_path: Path) -> None:
    output_path = tmp_path / "audit.csv"

    exit_code = main(
        [
            "--input-dir",
            str(tmp_path),
            "--output",
            str(output_path),
            "--near-empty-threshold",
            "-1",
        ]
    )

    assert exit_code == 2
    assert not output_path.exists()
