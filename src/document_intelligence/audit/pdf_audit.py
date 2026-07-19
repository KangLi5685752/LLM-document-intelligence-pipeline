"""Deterministic, local-only technical checks for PDF corpus candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pypdf import PdfReader


AUDIT_CSV_FIELDS: Final[list[str]] = [
    "filename",
    "file_path",
    "audit_status",
    "error_message",
    "sha256",
    "file_size_bytes",
    "page_count",
    "is_encrypted",
    "total_text_chars",
    "minimum_page_text_chars",
    "maximum_page_text_chars",
    "mean_page_text_chars",
    "pages_with_no_text",
    "near_empty_pages",
    "sample_pages",
    "probable_scanned_page_risk",
    "warning_count",
    "warnings",
]


@dataclass(frozen=True)
class PdfAuditResult:
    """Result of deterministic technical checks for one PDF file."""

    filename: str
    file_path: str
    audit_status: str
    error_message: str
    sha256: str
    file_size_bytes: int
    page_count: int
    is_encrypted: bool
    total_text_chars: int
    minimum_page_text_chars: int
    maximum_page_text_chars: int
    mean_page_text_chars: float
    pages_with_no_text: list[int]
    near_empty_pages: list[int]
    sample_pages: list[int]
    probable_scanned_page_risk: str
    warning_count: int
    warnings: list[str]


def calculate_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate an uppercase SHA-256 digest by reading a file in chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def classify_scanned_page_risk(page_text_counts: list[int]) -> str:
    """Screen for scan risk using zero-text pages, not definitive scan detection."""
    if not page_text_counts:
        return "unknown"

    zero_text_ratio = page_text_counts.count(0) / len(page_text_counts)
    if zero_text_ratio == 0:
        return "none_observed"
    if zero_text_ratio <= 0.10:
        return "low"
    if zero_text_ratio <= 0.40:
        return "medium"
    return "high"


def choose_sample_pages(page_count: int) -> list[int]:
    """Choose unique 1-based first, lower-middle, and final page numbers."""
    if page_count <= 0:
        return []

    middle_page = (page_count + 1) // 2
    return sorted({1, middle_page, page_count})


def _concise_error(error: Exception) -> str:
    message = " ".join(str(error).split())
    if message:
        return f"{type(error).__name__}: {message}"[:300]
    return type(error).__name__


def _failed_result(
    path: Path,
    error_message: str,
    *,
    sha256: str = "",
    file_size_bytes: int = 0,
    is_encrypted: bool = False,
    warnings: list[str] | None = None,
) -> PdfAuditResult:
    failure_warnings = list(warnings or [])
    failure_warnings.append(f"Failed PDF read: {error_message}")
    return PdfAuditResult(
        filename=path.name,
        file_path=str(path),
        audit_status="failed",
        error_message=error_message,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        page_count=0,
        is_encrypted=is_encrypted,
        total_text_chars=0,
        minimum_page_text_chars=0,
        maximum_page_text_chars=0,
        mean_page_text_chars=0.0,
        pages_with_no_text=[],
        near_empty_pages=[],
        sample_pages=[],
        probable_scanned_page_risk="unknown",
        warning_count=len(failure_warnings),
        warnings=failure_warnings,
    )


def audit_pdf(path: Path, near_empty_threshold: int = 50) -> PdfAuditResult:
    """Audit one PDF without saving extracted text or making network calls."""
    if near_empty_threshold < 0:
        raise ValueError("near_empty_threshold must not be negative")

    resolved_path = path.expanduser().resolve()
    file_size_bytes = 0
    sha256 = ""
    is_encrypted = False
    warnings: list[str] = []

    try:
        file_size_bytes = resolved_path.stat().st_size
        sha256 = calculate_sha256(resolved_path)
        reader = PdfReader(resolved_path, strict=False)
        is_encrypted = bool(reader.is_encrypted)

        if is_encrypted:
            warnings.append("Encrypted document")
            if not reader.decrypt(""):
                raise ValueError("encrypted PDF cannot be read without credentials")

        page_count = len(reader.pages)
        page_text_counts: list[int] = []
        for page in reader.pages:
            text = page.extract_text()
            page_text_counts.append(len((text or "").strip()))
    except Exception as error:  # Failure isolation is required for batch audits.
        return _failed_result(
            resolved_path,
            _concise_error(error),
            sha256=sha256,
            file_size_bytes=file_size_bytes,
            is_encrypted=is_encrypted,
            warnings=warnings,
        )

    pages_with_no_text = [
        page_number
        for page_number, character_count in enumerate(page_text_counts, start=1)
        if character_count == 0
    ]
    near_empty_pages = [
        page_number
        for page_number, character_count in enumerate(page_text_counts, start=1)
        if character_count < near_empty_threshold
    ]

    if page_count == 0:
        warnings.append("Zero-page document")
    if pages_with_no_text:
        warnings.append(
            "Pages with zero extracted text: "
            + _format_page_numbers(pages_with_no_text)
        )
    if near_empty_pages:
        warnings.append(
            f"Near-empty pages (<{near_empty_threshold} chars): "
            + _format_page_numbers(near_empty_pages)
        )

    total_text_chars = sum(page_text_counts)
    minimum_page_text_chars = min(page_text_counts, default=0)
    maximum_page_text_chars = max(page_text_counts, default=0)
    mean_page_text_chars = (
        float(statistics.mean(page_text_counts)) if page_text_counts else 0.0
    )

    return PdfAuditResult(
        filename=resolved_path.name,
        file_path=str(resolved_path),
        audit_status="completed",
        error_message="",
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        page_count=page_count,
        is_encrypted=is_encrypted,
        total_text_chars=total_text_chars,
        minimum_page_text_chars=minimum_page_text_chars,
        maximum_page_text_chars=maximum_page_text_chars,
        mean_page_text_chars=mean_page_text_chars,
        pages_with_no_text=pages_with_no_text,
        near_empty_pages=near_empty_pages,
        sample_pages=choose_sample_pages(page_count),
        probable_scanned_page_risk=classify_scanned_page_risk(page_text_counts),
        warning_count=len(warnings),
        warnings=warnings,
    )


def audit_directory(
    input_dir: Path,
    pattern: str = "*.pdf",
    near_empty_threshold: int = 50,
) -> list[PdfAuditResult]:
    """Audit matching local PDFs and return results sorted by filename."""
    if near_empty_threshold < 0:
        raise ValueError("near_empty_threshold must not be negative")

    paths = sorted(
        (path for path in input_dir.glob(pattern) if path.is_file()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    results = [
        audit_pdf(path, near_empty_threshold=near_empty_threshold) for path in paths
    ]
    return sorted(
        results,
        key=lambda result: (result.filename.casefold(), result.filename),
    )


def _format_page_numbers(page_numbers: list[int]) -> str:
    return ";".join(str(page_number) for page_number in page_numbers)


def _result_to_csv_row(result: PdfAuditResult) -> dict[str, object]:
    return {
        "filename": result.filename,
        "file_path": result.file_path,
        "audit_status": result.audit_status,
        "error_message": result.error_message,
        "sha256": result.sha256,
        "file_size_bytes": result.file_size_bytes,
        "page_count": result.page_count,
        "is_encrypted": str(result.is_encrypted).lower(),
        "total_text_chars": result.total_text_chars,
        "minimum_page_text_chars": result.minimum_page_text_chars,
        "maximum_page_text_chars": result.maximum_page_text_chars,
        "mean_page_text_chars": f"{result.mean_page_text_chars:.2f}",
        "pages_with_no_text": _format_page_numbers(result.pages_with_no_text),
        "near_empty_pages": _format_page_numbers(result.near_empty_pages),
        "sample_pages": _format_page_numbers(result.sample_pages),
        "probable_scanned_page_risk": result.probable_scanned_page_risk,
        "warning_count": result.warning_count,
        "warnings": "; ".join(result.warnings),
    }


def write_audit_csv(
    results: list[PdfAuditResult],
    output_path: Path,
) -> None:
    """Write deterministic UTF-8 CSV output without extracted page text."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_results = sorted(
        results,
        key=lambda result: (result.filename.casefold(), result.filename),
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=AUDIT_CSV_FIELDS,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(_result_to_csv_row(result) for result in sorted_results)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic technical checks over local PDF files.",
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/audits/pdf_audit.csv"),
    )
    parser.add_argument("--pattern", default="*.pdf")
    parser.add_argument("--near-empty-threshold", type=int, default=50)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line PDF audit and return a process exit code."""
    args = _build_argument_parser().parse_args(argv)

    if args.near_empty_threshold < 0:
        print("error: --near-empty-threshold must not be negative", file=sys.stderr)
        return 2
    if not args.input_dir.is_dir():
        print(f"error: input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 2

    try:
        results = audit_directory(
            args.input_dir,
            pattern=args.pattern,
            near_empty_threshold=args.near_empty_threshold,
        )
    except (OSError, ValueError) as error:
        print(f"error: {_concise_error(error)}", file=sys.stderr)
        return 2

    if not results:
        print(
            f"error: no files matched {args.pattern!r} in {args.input_dir}",
            file=sys.stderr,
        )
        return 2

    write_audit_csv(results, args.output)
    failed_count = sum(result.audit_status == "failed" for result in results)
    successful_count = len(results) - failed_count
    print(
        f"audited={len(results)} successful={successful_count} "
        f"failed={failed_count} output={args.output.resolve()}"
    )
    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
