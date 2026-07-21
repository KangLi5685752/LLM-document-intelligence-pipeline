"""Manifest-driven, failure-isolated ingestion for the frozen corpus."""

from __future__ import annotations

import csv
import re
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from document_intelligence.ingestion.dispatcher import parse_document
from document_intelligence.ingestion.models import (
    ParseStatus,
    ParsedDocument,
    SourceFormat,
)
from document_intelligence.ingestion.utils import calculate_sha256


PARSER_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM_PATTERN = re.compile(r"^[0-9A-F]{64}$")
VALID_SPLITS = {"development", "held_out"}
VALID_RUN_TYPES = {"held_out_first_run", "full_corpus_validation"}


class BatchManifestError(ValueError):
    """Raised when source-control manifests are missing or inconsistent."""


class ChecksumMismatchError(ValueError):
    """Raised when exact source bytes do not match the frozen checksum."""


class BatchItemStatus(str, Enum):
    """Per-source batch outcomes."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"


def _validate_relative_path(value: str, field_name: str) -> str:
    """Reject absolute and parent-traversing paths on POSIX and Windows."""
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError(f"{field_name} must be relative")
    if ".." in posix_path.parts or ".." in windows_path.parts:
        raise ValueError(f"{field_name} must not contain parent traversal")
    return value


class SourceSpec(BaseModel):
    """Validated join of one active split row and source-register row."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    document_family: str
    split: Literal["development", "held_out"]
    source_format: SourceFormat
    local_filename: str
    expected_checksum_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")

    @field_validator("source_id", "document_family")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("local_filename")
    @classmethod
    def validate_local_filename(cls, value: str) -> str:
        _validate_relative_path(value, "local_filename")
        if "/" in value or "\\" in value:
            raise ValueError("local_filename must contain a filename only")
        return value


class BatchIngestionItem(BaseModel):
    """Machine-readable result for one frozen source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    document_family: str
    split: str
    source_format: SourceFormat
    input_filename: str
    expected_checksum_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    observed_checksum_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9A-F]{64}$",
    )
    checksum_matches: bool
    status: BatchItemStatus
    document_id: str | None = None
    block_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    page_count: int | None = Field(default=None, gt=0)
    slide_count: int | None = Field(default=None, gt=0)
    message_id: str | None = None
    output_json: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    @field_validator("source_id", "document_family", "split")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("input_filename")
    @classmethod
    def validate_input_filename(cls, value: str) -> str:
        return _validate_relative_path(value, "input_filename")

    @field_validator("output_json")
    @classmethod
    def validate_output_json(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_relative_path(value, "output_json")

    @model_validator(mode="after")
    def validate_outcome(self) -> BatchIngestionItem:
        successful = self.status in {
            BatchItemStatus.SUCCESS,
            BatchItemStatus.SUCCESS_WITH_WARNINGS,
        }
        if successful:
            if self.document_id is None or not self.document_id.strip():
                raise ValueError("successful items require document_id")
            if self.observed_checksum_sha256 is None:
                raise ValueError("successful items require observed checksum")
            if not self.checksum_matches:
                raise ValueError("successful items require matching checksum")
            if self.output_json is None:
                raise ValueError("successful items require output_json")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("successful items cannot contain errors")
        if self.status is BatchItemStatus.FAILED:
            if not self.error_type or not self.error_message:
                raise ValueError("failed items require error_type and error_message")
        if self.status is BatchItemStatus.SUCCESS and self.warning_count != 0:
            raise ValueError("success items cannot contain warnings")
        if (
            self.status is BatchItemStatus.SUCCESS_WITH_WARNINGS
            and self.warning_count == 0
        ):
            raise ValueError("success_with_warnings items require warnings")
        return self


class BatchIngestionReport(BaseModel):
    """Deterministic report for one manifest-driven ingestion run."""

    model_config = ConfigDict(extra="forbid")

    report_schema_version: Literal["0.1"] = "0.1"
    corpus_version: Literal["stage1-corpus-v1.0"] = "stage1-corpus-v1.0"
    parser_commit: str
    run_type: Literal["held_out_first_run", "full_corpus_validation"]
    source_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    warning_source_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    checksum_match_count: int = Field(ge=0)
    items: list[BatchIngestionItem]

    @field_validator("parser_commit")
    @classmethod
    def validate_parser_commit(cls, value: str) -> str:
        if not PARSER_COMMIT_PATTERN.fullmatch(value):
            raise ValueError(
                "parser_commit must be a 40-character lowercase hexadecimal commit"
            )
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> BatchIngestionReport:
        source_ids = [item.source_id for item in self.items]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("batch item source IDs must be unique")
        expected = {
            "source_count": len(self.items),
            "success_count": sum(
                item.status is not BatchItemStatus.FAILED for item in self.items
            ),
            "warning_source_count": sum(
                item.warning_count > 0 for item in self.items
            ),
            "failure_count": sum(
                item.status is BatchItemStatus.FAILED for item in self.items
            ),
            "checksum_match_count": sum(
                item.checksum_matches for item in self.items
            ),
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(
                    f"{field_name} does not reconcile with batch items"
                )
        return self


def _read_csv_rows(path: Path, label: str) -> list[dict[str, str]]:
    if not path.exists():
        raise BatchManifestError(f"{label} does not exist")
    if not path.is_file():
        raise BatchManifestError(f"{label} is not a file")
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise BatchManifestError(f"{label} has no CSV header")
            return [dict(row) for row in reader]
    except UnicodeError as error:
        raise BatchManifestError(f"{label} is not valid UTF-8 CSV") from error


def _index_unique_rows(
    rows: list[dict[str, str]],
    label: str,
) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        source_id = (row.get("source_id") or "").strip()
        if not source_id:
            raise BatchManifestError(f"{label} contains a blank source_id")
        if source_id in indexed:
            raise BatchManifestError(
                f"{label} contains duplicate source_id {source_id}"
            )
        indexed[source_id] = row
    return indexed


def load_active_source_specs(
    source_register_path: Path,
    corpus_split_path: Path,
) -> list[SourceSpec]:
    """Join and validate active source specifications in split-manifest order."""
    register_rows = _read_csv_rows(Path(source_register_path), "source register")
    split_rows = _read_csv_rows(Path(corpus_split_path), "corpus split")
    register_by_id = _index_unique_rows(register_rows, "source register")
    _index_unique_rows(split_rows, "corpus split")

    specs: list[SourceSpec] = []
    for split_row in split_rows:
        source_id = (split_row.get("source_id") or "").strip()
        register_row = register_by_id.get(source_id)
        if register_row is None:
            raise BatchManifestError(
                f"corpus split source {source_id} is missing from source register"
            )

        corpus_status = (register_row.get("corpus_status") or "").strip().lower()
        if corpus_status != "approved":
            raise BatchManifestError(
                f"source {source_id} is not approved: {corpus_status or 'blank'}"
            )

        register_format = (register_row.get("source_format") or "").strip().upper()
        split_format = (split_row.get("source_format") or "").strip().upper()
        if register_format != split_format:
            raise BatchManifestError(
                f"source format mismatch for {source_id}: "
                f"register={register_format or 'blank'} split={split_format or 'blank'}"
            )
        try:
            source_format = SourceFormat(split_format)
        except ValueError as error:
            raise BatchManifestError(
                f"unsupported source format for {source_id}: {split_format or 'blank'}"
            ) from error

        checksum = (register_row.get("sha256") or "").strip()
        if not CHECKSUM_PATTERN.fullmatch(checksum):
            raise BatchManifestError(
                f"source {source_id} has an invalid uppercase SHA-256"
            )

        try:
            specs.append(
                SourceSpec(
                    source_id=source_id,
                    document_family=(
                        split_row.get("document_family") or ""
                    ).strip(),
                    split=(split_row.get("split") or "").strip(),
                    source_format=source_format,
                    local_filename=(
                        register_row.get("local_filename") or ""
                    ).strip(),
                    expected_checksum_sha256=checksum,
                )
            )
        except ValueError as error:
            raise BatchManifestError(
                f"invalid source specification for {source_id}: {error}"
            ) from error
    return specs


def _resolve_source_path(
    spec: SourceSpec,
    raw_root: Path,
    synthetic_root: Path,
) -> Path:
    if spec.source_format is SourceFormat.PDF:
        return raw_root / spec.local_filename
    if spec.source_format is SourceFormat.PPTX:
        return synthetic_root / "pptx" / spec.local_filename
    return synthetic_root / "email" / spec.local_filename


def _safe_error_message(
    error: Exception,
    input_path: Path,
    output_path: Path,
) -> str:
    message = " ".join(str(error).split()) or type(error).__name__
    path_replacements: dict[str, str] = {}
    for path in (input_path, output_path):
        for path_value in {
            str(path),
            str(path.resolve()),
            path.as_posix(),
            path.resolve().as_posix(),
        }:
            path_replacements[path_value] = path.name
    for path_value in sorted(path_replacements, key=len, reverse=True):
        message = message.replace(path_value, path_replacements[path_value])
    return message[:300]


def _metadata_positive_int(
    document: ParsedDocument,
    key: str,
) -> int | None:
    value = document.metadata.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def ingest_corpus(
    *,
    source_register_path: Path,
    corpus_split_path: Path,
    raw_root: Path,
    synthetic_root: Path,
    output_root: Path,
    split: str | None,
    parser_commit: str,
    run_type: str,
) -> BatchIngestionReport:
    """Ingest a selected frozen-corpus split while isolating source failures."""
    if split is not None and split not in VALID_SPLITS:
        raise BatchManifestError(f"invalid split: {split}")
    if run_type not in VALID_RUN_TYPES:
        raise BatchManifestError(f"invalid run_type: {run_type}")
    if not PARSER_COMMIT_PATTERN.fullmatch(parser_commit):
        raise BatchManifestError(
            "parser_commit must be a 40-character lowercase hexadecimal commit"
        )

    specs = load_active_source_specs(source_register_path, corpus_split_path)
    selected_specs = [spec for spec in specs if split is None or spec.split == split]
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    raw_root = Path(raw_root)
    synthetic_root = Path(synthetic_root)

    items: list[BatchIngestionItem] = []
    for spec in selected_specs:
        input_path = _resolve_source_path(spec, raw_root, synthetic_root)
        output_path = output_root / f"{spec.source_id}.json"
        observed_checksum: str | None = None
        checksum_matches = False
        try:
            if not input_path.exists():
                raise FileNotFoundError("input file does not exist")
            if not input_path.is_file():
                raise ValueError("input path is not a file")
            observed_checksum = calculate_sha256(input_path)
            checksum_matches = observed_checksum == spec.expected_checksum_sha256
            if not checksum_matches:
                raise ChecksumMismatchError(
                    "observed source checksum does not match frozen manifest"
                )

            document = parse_document(input_path, spec.source_id)
            checksum_matches = (
                document.checksum_sha256 == spec.expected_checksum_sha256
                and observed_checksum == spec.expected_checksum_sha256
            )
            if not checksum_matches:
                raise ChecksumMismatchError(
                    "parsed document checksum does not match frozen manifest"
                )
            if document.source_format is not spec.source_format:
                raise ValueError("parsed document source format does not match manifest")

            json_output = document.model_dump_json(indent=2) + "\n"
            output_path.write_text(json_output, encoding="utf-8")
            revalidated = ParsedDocument.model_validate_json(
                output_path.read_text(encoding="utf-8")
            )
            warning_count = len(revalidated.warnings) + sum(
                len(block.warnings) for block in revalidated.blocks
            )
            status = (
                BatchItemStatus.SUCCESS_WITH_WARNINGS
                if revalidated.parse_status is ParseStatus.SUCCESS_WITH_WARNINGS
                else BatchItemStatus.SUCCESS
            )
            message_id = revalidated.metadata.get("message_id")
            items.append(
                BatchIngestionItem(
                    source_id=spec.source_id,
                    document_family=spec.document_family,
                    split=spec.split,
                    source_format=spec.source_format,
                    input_filename=spec.local_filename,
                    expected_checksum_sha256=spec.expected_checksum_sha256,
                    observed_checksum_sha256=observed_checksum,
                    checksum_matches=True,
                    status=status,
                    document_id=revalidated.document_id,
                    block_count=revalidated.block_count,
                    warning_count=warning_count,
                    page_count=_metadata_positive_int(revalidated, "page_count"),
                    slide_count=_metadata_positive_int(revalidated, "slide_count"),
                    message_id=(message_id if isinstance(message_id, str) else None),
                    output_json=output_path.relative_to(output_root).as_posix(),
                )
            )
        except Exception as error:  # One source must not abort the batch.
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            items.append(
                BatchIngestionItem(
                    source_id=spec.source_id,
                    document_family=spec.document_family,
                    split=spec.split,
                    source_format=spec.source_format,
                    input_filename=spec.local_filename,
                    expected_checksum_sha256=spec.expected_checksum_sha256,
                    observed_checksum_sha256=observed_checksum,
                    checksum_matches=checksum_matches,
                    status=BatchItemStatus.FAILED,
                    block_count=0,
                    warning_count=0,
                    error_type=type(error).__name__,
                    error_message=_safe_error_message(
                        error,
                        input_path,
                        output_path,
                    ),
                )
            )

    return BatchIngestionReport(
        parser_commit=parser_commit,
        run_type=run_type,
        source_count=len(items),
        success_count=sum(item.status is not BatchItemStatus.FAILED for item in items),
        warning_source_count=sum(item.warning_count > 0 for item in items),
        failure_count=sum(item.status is BatchItemStatus.FAILED for item in items),
        checksum_match_count=sum(item.checksum_matches for item in items),
        items=items,
    )
