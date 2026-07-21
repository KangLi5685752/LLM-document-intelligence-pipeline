"""Tests for deterministic manifest-driven frozen-corpus ingestion."""

from __future__ import annotations

import csv
import hashlib
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import document_intelligence.ingestion.batch as batch_module
import document_intelligence.ingestion.batch_cli as batch_cli_module
from document_intelligence.ingestion.batch import (
    BatchIngestionItem,
    BatchIngestionReport,
    BatchItemStatus,
    BatchManifestError,
    ingest_corpus,
    load_active_source_specs,
)
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


PARSER_COMMIT = "a" * 40
REGISTER_FIELDS = [
    "source_id",
    "source_format",
    "local_filename",
    "sha256",
    "corpus_status",
]
SPLIT_FIELDS = ["source_id", "document_family", "source_format", "split"]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _manifest_rows(
    source_id: str,
    source_format: SourceFormat,
    *,
    split: str = "development",
    content: bytes = b"source bytes",
    corpus_status: str = "approved",
    checksum: str | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    extension = source_format.value.lower()
    register = {
        "source_id": source_id,
        "source_format": source_format.value,
        "local_filename": f"{source_id}.{extension}",
        "sha256": checksum if checksum is not None else _sha256(content),
        "corpus_status": corpus_status,
    }
    split_row = {
        "source_id": source_id,
        "document_family": f"F-{source_id}",
        "source_format": source_format.value,
        "split": split,
    }
    return register, split_row


def _environment(
    tmp_path: Path,
    definitions: list[tuple[str, SourceFormat, str, bytes]],
) -> dict[str, Any]:
    raw_root = tmp_path / "raw"
    synthetic_root = tmp_path / "synthetic"
    (synthetic_root / "pptx").mkdir(parents=True)
    (synthetic_root / "email").mkdir(parents=True)
    raw_root.mkdir()

    register_rows: list[dict[str, str]] = []
    split_rows: list[dict[str, str]] = []
    for source_id, source_format, split, content in definitions:
        register, split_row = _manifest_rows(
            source_id,
            source_format,
            split=split,
            content=content,
        )
        register_rows.append(register)
        split_rows.append(split_row)
        if source_format is SourceFormat.PDF:
            source_path = raw_root / register["local_filename"]
        elif source_format is SourceFormat.PPTX:
            source_path = synthetic_root / "pptx" / register["local_filename"]
        else:
            source_path = synthetic_root / "email" / register["local_filename"]
        source_path.write_bytes(content)

    register_path = tmp_path / "source_register.csv"
    split_path = tmp_path / "corpus_split.csv"
    _write_csv(register_path, REGISTER_FIELDS, register_rows)
    _write_csv(split_path, SPLIT_FIELDS, split_rows)
    return {
        "register_path": register_path,
        "split_path": split_path,
        "raw_root": raw_root,
        "synthetic_root": synthetic_root,
        "output_root": tmp_path / "output",
        "register_rows": register_rows,
        "split_rows": split_rows,
    }


def _parsed_document(
    source_id: str,
    source_format: SourceFormat,
    checksum: str,
    *,
    with_warning: bool = False,
) -> ParsedDocument:
    if source_format is SourceFormat.PDF:
        block_type = BlockType.PAGE_TEXT
        location = SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        )
        metadata: dict[str, Any] = {"page_count": 1}
    elif source_format is SourceFormat.PPTX:
        block_type = BlockType.SHAPE_TEXT
        location = SourceLocation(
            location_type=LocationType.SLIDE,
            location_value="1",
            slide_number=1,
            element_index=1,
        )
        metadata = {"slide_count": 1}
    else:
        block_type = BlockType.EMAIL_BODY
        location = SourceLocation(
            location_type=LocationType.EMAIL_BODY,
            location_value="body",
            message_id=f"<{source_id.lower()}@example.invalid>",
        )
        metadata = {"message_id": f"<{source_id.lower()}@example.invalid>"}

    warnings = ["Format-general warning"] if with_warning else []
    return ParsedDocument(
        document_id=f"DOC-{source_id}",
        source_id=source_id,
        source_format=source_format,
        filename=f"{source_id}.{source_format.value.lower()}",
        checksum_sha256=checksum,
        blocks=[
            DocumentBlock(
                block_id=f"DOC-{source_id}-B0001",
                sequence=1,
                block_type=block_type,
                text="Temporary parser output",
                location=location,
            )
        ],
        metadata=metadata,
        warnings=warnings,
        parse_status=(
            ParseStatus.SUCCESS_WITH_WARNINGS
            if with_warning
            else ParseStatus.SUCCESS
        ),
    )


def _fake_parser(path: Path, source_id: str | None) -> ParsedDocument:
    assert source_id is not None
    source_format = SourceFormat(path.suffix[1:].upper())
    return _parsed_document(source_id, source_format, _sha256(path.read_bytes()))


def _run_batch(
    environment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    split: str | None = None,
) -> BatchIngestionReport:
    monkeypatch.setattr(batch_module, "parse_document", _fake_parser)
    return ingest_corpus(
        source_register_path=environment["register_path"],
        corpus_split_path=environment["split_path"],
        raw_root=environment["raw_root"],
        synthetic_root=environment["synthetic_root"],
        output_root=environment["output_root"],
        split=split,
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
    )


def test_load_active_source_specs_joins_valid_manifests(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"pdf")],
    )

    specs = load_active_source_specs(
        environment["register_path"], environment["split_path"]
    )

    assert len(specs) == 1
    assert specs[0].source_id == "T001"
    assert specs[0].document_family == "F-T001"
    assert specs[0].source_format is SourceFormat.PDF


def test_package_level_batch_exports_are_available() -> None:
    from document_intelligence.ingestion import (
        BatchIngestionItem as exported_item,
        BatchIngestionReport as exported_report,
        BatchItemStatus as exported_status,
        ingest_corpus as exported_ingest,
        load_active_source_specs as exported_loader,
    )

    assert exported_item is BatchIngestionItem
    assert exported_report is BatchIngestionReport
    assert exported_status is BatchItemStatus
    assert exported_ingest is ingest_corpus
    assert exported_loader is load_active_source_specs


@pytest.mark.parametrize("manifest_name", ["register", "split"])
def test_duplicate_source_ids_are_rejected(
    tmp_path: Path,
    manifest_name: str,
) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"pdf")],
    )
    key = "register_rows" if manifest_name == "register" else "split_rows"
    path_key = "register_path" if manifest_name == "register" else "split_path"
    fields = REGISTER_FIELDS if manifest_name == "register" else SPLIT_FIELDS
    rows = environment[key]
    _write_csv(environment[path_key], fields, [rows[0], rows[0]])

    with pytest.raises(BatchManifestError, match="duplicate source_id"):
        load_active_source_specs(
            environment["register_path"], environment["split_path"]
        )


def test_missing_source_register_row_is_rejected(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"pdf")],
    )
    extra = _manifest_rows("T002", SourceFormat.EML)[1]
    _write_csv(environment["split_path"], SPLIT_FIELDS, [extra])

    with pytest.raises(BatchManifestError, match="missing from source register"):
        load_active_source_specs(
            environment["register_path"], environment["split_path"]
        )


@pytest.mark.parametrize("corpus_status", ["deferred", "candidate"])
def test_deferred_or_unapproved_sources_are_rejected(
    tmp_path: Path,
    corpus_status: str,
) -> None:
    register, split_row = _manifest_rows(
        "T001",
        SourceFormat.PDF,
        corpus_status=corpus_status,
    )
    register_path = tmp_path / "register.csv"
    split_path = tmp_path / "split.csv"
    _write_csv(register_path, REGISTER_FIELDS, [register])
    _write_csv(split_path, SPLIT_FIELDS, [split_row])

    with pytest.raises(BatchManifestError, match="is not approved"):
        load_active_source_specs(register_path, split_path)


def test_source_format_mismatch_is_rejected(tmp_path: Path) -> None:
    register, split_row = _manifest_rows("T001", SourceFormat.PDF)
    split_row["source_format"] = "EML"
    register_path = tmp_path / "register.csv"
    split_path = tmp_path / "split.csv"
    _write_csv(register_path, REGISTER_FIELDS, [register])
    _write_csv(split_path, SPLIT_FIELDS, [split_row])

    with pytest.raises(BatchManifestError, match="source format mismatch"):
        load_active_source_specs(register_path, split_path)


@pytest.mark.parametrize("checksum", ["a" * 64, "A" * 63, "G" * 64])
def test_invalid_manifest_checksum_is_rejected(
    tmp_path: Path,
    checksum: str,
) -> None:
    register, split_row = _manifest_rows(
        "T001", SourceFormat.PDF, checksum=checksum
    )
    register_path = tmp_path / "register.csv"
    split_path = tmp_path / "split.csv"
    _write_csv(register_path, REGISTER_FIELDS, [register])
    _write_csv(split_path, SPLIT_FIELDS, [split_row])

    with pytest.raises(BatchManifestError, match="invalid uppercase SHA-256"):
        load_active_source_specs(register_path, split_path)


def test_split_filtering_selects_only_requested_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [
            ("T001", SourceFormat.PDF, "development", b"dev"),
            ("T002", SourceFormat.EML, "held_out", b"held"),
        ],
    )

    report = _run_batch(environment, monkeypatch, split="held_out")

    assert [item.source_id for item in report.items] == ["T002"]


def test_manifest_order_is_retained(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        [
            ("T003", SourceFormat.EML, "held_out", b"third"),
            ("T001", SourceFormat.PDF, "development", b"first"),
            ("T002", SourceFormat.PPTX, "development", b"second"),
        ],
    )

    specs = load_active_source_specs(
        environment["register_path"], environment["split_path"]
    )

    assert [spec.source_id for spec in specs] == ["T003", "T001", "T002"]


def test_paths_are_resolved_by_format_without_source_specific_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [
            ("PX", SourceFormat.PDF, "development", b"pdf"),
            ("PP", SourceFormat.PPTX, "development", b"pptx"),
            ("PE", SourceFormat.EML, "development", b"eml"),
        ],
    )
    observed_paths: list[Path] = []

    def capture(path: Path, source_id: str | None) -> ParsedDocument:
        observed_paths.append(path)
        return _fake_parser(path, source_id)

    monkeypatch.setattr(batch_module, "parse_document", capture)
    report = ingest_corpus(
        source_register_path=environment["register_path"],
        corpus_split_path=environment["split_path"],
        raw_root=environment["raw_root"],
        synthetic_root=environment["synthetic_root"],
        output_root=environment["output_root"],
        split=None,
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
    )

    assert report.failure_count == 0
    assert observed_paths == [
        environment["raw_root"] / "PX.pdf",
        environment["synthetic_root"] / "pptx" / "PP.pptx",
        environment["synthetic_root"] / "email" / "PE.eml",
    ]


def test_one_parser_failure_does_not_abort_remaining_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [
            ("T001", SourceFormat.PDF, "development", b"bad"),
            ("T002", SourceFormat.PDF, "development", b"good"),
        ],
    )

    def fail_first(path: Path, source_id: str | None) -> ParsedDocument:
        if source_id == "T001":
            raise DocumentParseError("temporary parser failure")
        return _fake_parser(path, source_id)

    monkeypatch.setattr(batch_module, "parse_document", fail_first)
    report = ingest_corpus(
        source_register_path=environment["register_path"],
        corpus_split_path=environment["split_path"],
        raw_root=environment["raw_root"],
        synthetic_root=environment["synthetic_root"],
        output_root=environment["output_root"],
        split=None,
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
    )

    assert report.failure_count == 1
    assert [item.status for item in report.items] == [
        BatchItemStatus.FAILED,
        BatchItemStatus.SUCCESS,
    ]
    assert (environment["output_root"] / "T002.json").is_file()


def test_successful_json_is_written_and_revalidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.EML, "development", b"email")],
    )

    report = _run_batch(environment, monkeypatch)
    output_path = environment["output_root"] / report.items[0].output_json

    document = ParsedDocument.model_validate_json(output_path.read_text("utf-8"))
    assert document.source_id == "T001"
    assert report.items[0].output_json == "T001.json"


def test_checksum_mismatch_creates_failed_item_without_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"original")],
    )
    source_path = environment["raw_root"] / "T001.pdf"
    source_path.write_bytes(b"changed after manifest")

    def must_not_parse(path: Path, source_id: str | None) -> ParsedDocument:
        raise AssertionError("parser must not run after checksum mismatch")

    monkeypatch.setattr(batch_module, "parse_document", must_not_parse)
    report = ingest_corpus(
        source_register_path=environment["register_path"],
        corpus_split_path=environment["split_path"],
        raw_root=environment["raw_root"],
        synthetic_root=environment["synthetic_root"],
        output_root=environment["output_root"],
        split=None,
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
    )

    item = report.items[0]
    assert item.status is BatchItemStatus.FAILED
    assert item.error_type == "ChecksumMismatchError"
    assert item.observed_checksum_sha256 is not None
    assert not item.checksum_matches
    assert not (environment["output_root"] / "T001.json").exists()


def test_report_counts_must_reconcile() -> None:
    item = _successful_item()

    with pytest.raises(ValidationError, match="success_count does not reconcile"):
        BatchIngestionReport(
            parser_commit=PARSER_COMMIT,
            run_type="full_corpus_validation",
            source_count=1,
            success_count=0,
            warning_source_count=0,
            failure_count=1,
            checksum_match_count=1,
            items=[item],
        )


@pytest.mark.parametrize("parser_commit", ["A" * 40, "a" * 39, "g" * 40])
def test_report_rejects_invalid_parser_commit(parser_commit: str) -> None:
    with pytest.raises(ValidationError, match="40-character lowercase"):
        BatchIngestionReport(
            parser_commit=parser_commit,
            run_type="full_corpus_validation",
            source_count=1,
            success_count=1,
            warning_source_count=0,
            failure_count=0,
            checksum_match_count=1,
            items=[_successful_item()],
        )


@pytest.mark.parametrize("path_field", ["input_filename", "output_json"])
def test_absolute_paths_are_rejected_from_batch_items(
    tmp_path: Path,
    path_field: str,
) -> None:
    payload = _successful_item().model_dump()
    payload[path_field] = str((tmp_path / "absolute.json").resolve())

    with pytest.raises(ValidationError, match="must be relative"):
        BatchIngestionItem.model_validate(payload)


def _successful_item() -> BatchIngestionItem:
    return BatchIngestionItem(
        source_id="T001",
        document_family="F-T001",
        split="development",
        source_format=SourceFormat.PDF,
        input_filename="T001.pdf",
        expected_checksum_sha256="A" * 64,
        observed_checksum_sha256="A" * 64,
        checksum_matches=True,
        status=BatchItemStatus.SUCCESS,
        document_id="DOC-T001",
        block_count=1,
        warning_count=0,
        page_count=1,
        output_json="T001.json",
    )


def _cli_report(*, failed: bool = False) -> BatchIngestionReport:
    if failed:
        item = BatchIngestionItem(
            source_id="T001",
            document_family="F-T001",
            split="development",
            source_format=SourceFormat.PDF,
            input_filename="T001.pdf",
            expected_checksum_sha256="A" * 64,
            observed_checksum_sha256="A" * 64,
            checksum_matches=True,
            status=BatchItemStatus.FAILED,
            block_count=0,
            warning_count=0,
            error_type="DocumentParseError",
            error_message="temporary parse failure",
        )
    else:
        item = _successful_item()
    return BatchIngestionReport(
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
        source_count=1,
        success_count=0 if failed else 1,
        warning_source_count=0,
        failure_count=1 if failed else 0,
        checksum_match_count=1,
        items=[item],
    )


def _cli_args(tmp_path: Path) -> list[str]:
    register = tmp_path / "register.csv"
    split = tmp_path / "split.csv"
    raw = tmp_path / "raw"
    synthetic = tmp_path / "synthetic"
    register.write_text("source_id\n", encoding="utf-8")
    split.write_text("source_id\n", encoding="utf-8")
    raw.mkdir()
    synthetic.mkdir()
    return [
        "--source-register",
        str(register),
        "--corpus-split",
        str(split),
        "--raw-root",
        str(raw),
        "--synthetic-root",
        str(synthetic),
        "--output-root",
        str(tmp_path / "output"),
        "--parser-commit",
        PARSER_COMMIT,
        "--run-type",
        "full_corpus_validation",
        "--report",
        str(tmp_path / "reports" / "report.json"),
    ]


def test_batch_cli_returns_zero_for_full_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(batch_cli_module, "ingest_corpus", lambda **_: _cli_report())
    args = _cli_args(tmp_path)

    assert batch_cli_module.main(args) == 0
    captured = capsys.readouterr()
    assert "sources=1 successful=1" in captured.out
    report_path = tmp_path / "reports" / "report.json"
    BatchIngestionReport.model_validate_json(report_path.read_text("utf-8"))


def test_batch_cli_returns_one_for_partial_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        batch_cli_module,
        "ingest_corpus",
        lambda **_: _cli_report(failed=True),
    )

    assert batch_cli_module.main(_cli_args(tmp_path)) == 1


def test_batch_cli_returns_two_for_missing_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = tmp_path / "raw"
    synthetic = tmp_path / "synthetic"
    raw.mkdir()
    synthetic.mkdir()
    exit_code = batch_cli_module.main(
        [
            "--source-register",
            str(tmp_path / "missing.csv"),
            "--corpus-split",
            str(tmp_path / "also-missing.csv"),
            "--raw-root",
            str(raw),
            "--synthetic-root",
            str(synthetic),
            "--output-root",
            str(tmp_path / "output"),
            "--parser-commit",
            PARSER_COMMIT,
            "--run-type",
            "full_corpus_validation",
            "--report",
            str(tmp_path / "report.json"),
        ]
    )

    assert exit_code == 2
    assert "source register" in capsys.readouterr().err


def test_batch_cli_help_has_no_runtime_warning() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.ingestion.batch_cli",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "RuntimeWarning" not in result.stderr
    assert "found in sys.modules" not in result.stderr
    assert "prior to execution" not in result.stderr


def test_manifest_loading_does_not_read_ground_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"pdf")],
    )
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "synthetic_ground_truth.jsonl":
            raise AssertionError("ground truth must not be read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    assert load_active_source_specs(
        environment["register_path"], environment["split_path"]
    )


def test_batch_ingestion_makes_no_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = _environment(
        tmp_path,
        [("T001", SourceFormat.PDF, "development", b"pdf")],
    )

    def reject_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", reject_network)
    report = _run_batch(environment, monkeypatch)

    assert report.failure_count == 0
