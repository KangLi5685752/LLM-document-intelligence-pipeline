"""Strict additive run-artifact contracts for deterministic-baseline-v0.2."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from document_intelligence.extraction.evaluation_models_v0_2 import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    PreliminaryDevelopmentEvaluationReport,
)
from document_intelligence.ingestion.models import LocationType, SourceFormat


EXPERIMENT_ID = "deterministic-baseline-v0.2"
PLANNING_MERGE_COMMIT = "f224c4e385fab5c4e0348bcf251015630cea9af8"
PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
CORPUS_VERSION = "stage1-corpus-v1.0"
PUBLIC_GOLD_VERSION = "public-gold-v0.1"
PUBLIC_GOLD_FACTS_SHA256 = (
    "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
)
PUBLIC_GOLD_CASES_SHA256 = (
    "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
)
CANDIDATE_SCHEMA_VERSION = "0.1"
PREDICATE_VOCABULARY_VERSION = "0.1"
MATCHING_PROTOCOL_VERSION = "0.1"
HELD_OUT_ACCESS = (
    "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
)
SHA256_PATTERN = r"^[0-9A-F]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
DIAGNOSTIC_REASON_CODES = {
    "additional_candidate_duplicate",
    "no_candidate_same_source_predicate",
    "no_strict_match",
    "normalized_value_mismatch",
    "qualifier_mismatch",
    "qualifier_missing",
    "subject_text_mismatch",
    "subject_type_mismatch",
    "value_type_mismatch",
}


def _require_sorted_unique(values: tuple[str, ...], label: str) -> None:
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be sorted")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} must not contain blank values")


def _validate_relative_path(value: str, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-blank and trimmed")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{label} must be repository-relative")
    if ".." in posix.parts or ".." in windows.parts:
        raise ValueError(f"{label} must not contain parent traversal")
    if "\\" in value or value != posix.as_posix():
        raise ValueError(f"{label} must use repository-relative POSIX syntax")
    return value


def _require_hash_mapping(values: dict[str, str], label: str) -> None:
    if not values:
        raise ValueError(f"{label} must not be empty")
    if tuple(values) != tuple(sorted(values)):
        raise ValueError(f"{label} paths must be sorted")
    for path, value in values.items():
        _validate_relative_path(path, f"{label} path")
        if not re.fullmatch(SHA256_PATTERN, value):
            raise ValueError(f"{label} contains an invalid SHA-256")


class DevelopmentInputRecord(BaseModel):
    """Path-safe provenance for one validated ParsedDocument."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    source_id: str = Field(pattern=r"^S\d{3}$")
    document_family: str = Field(min_length=1)
    source_format: Literal[SourceFormat.PDF]
    source_filename: str = Field(min_length=1)
    source_checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_relative_path: str = Field(min_length=1)
    parsed_json_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_document_id: str = Field(min_length=1)
    parsed_block_count: int = Field(ge=0)
    parse_status: Literal["success", "success_with_warnings"]

    @field_validator("parsed_relative_path")
    @classmethod
    def validate_parsed_path(cls, value: str) -> str:
        return _validate_relative_path(value, "parsed_relative_path")

    @field_validator("source_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        _validate_relative_path(value, "source_filename")
        if "/" in value or "\\" in value:
            raise ValueError("source_filename must contain a filename only")
        return value

    @model_validator(mode="after")
    def validate_text(self) -> DevelopmentInputRecord:
        for name in ("document_family", "parsed_document_id"):
            value = getattr(self, name)
            if value != value.strip():
                raise ValueError(f"{name} must be trimmed")
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("input record contains a non-development source")
        parsed_path = PurePosixPath(self.parsed_relative_path)
        if parsed_path.name != f"{self.source_id}.json":
            raise ValueError("parsed_relative_path must use the canonical source name")
        return self


ParsedInputRecord = DevelopmentInputRecord


class DevelopmentRunAttemptRecord(BaseModel):
    """Safe primary or repeat extraction-attempt summary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    source_id: str = Field(pattern=r"^S\d{3}$")
    run_label: Literal["primary", "repeat"]
    status: Literal["success", "failed"]
    candidate_output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    candidate_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    warning_codes: tuple[str, ...] = ()
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> DevelopmentRunAttemptRecord:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("attempt contains a non-development source")
        _require_sorted_unique(self.warning_codes, "warning_codes")
        if any(not SNAKE_CASE_PATTERN.fullmatch(item) for item in self.warning_codes):
            raise ValueError("warning_codes must use lowercase snake_case")
        if self.review_required_count > self.candidate_count:
            raise ValueError("review_required_count exceeds candidate_count")
        if self.status == "success":
            if self.candidate_output_sha256 is None or self.error_code is not None:
                raise ValueError("successful attempts require a hash and no error")
        else:
            if self.candidate_output_sha256 is not None:
                raise ValueError("failed attempts must not contain an output hash")
            if any(
                value != 0
                for value in (
                    self.candidate_count,
                    self.evidence_count,
                    self.review_required_count,
                )
            ):
                raise ValueError("failed attempt counts must be zero")
            if self.warning_codes:
                raise ValueError("failed attempts must not contain output warnings")
            if self.error_code is None or not SNAKE_CASE_PATTERN.fullmatch(
                self.error_code
            ):
                raise ValueError("failed attempts require a snake-case error_code")
        return self


SourceExecutionAttempt = DevelopmentRunAttemptRecord


class CandidateOutputRecord(BaseModel):
    """One canonical primary or repeat candidate-output reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    source_id: str = Field(pattern=r"^S\d{3}$")
    run_label: Literal["primary", "repeat"]
    relative_path: str
    canonical_output_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_schema_version: Literal["0.1"] = CANDIDATE_SCHEMA_VERSION

    @field_validator("relative_path")
    @classmethod
    def validate_output_path(cls, value: str) -> str:
        return _validate_relative_path(value, "relative_path")

    @model_validator(mode="after")
    def validate_record(self) -> CandidateOutputRecord:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("output contains a non-development source")
        expected = f"{self.run_label}/{self.source_id}.json"
        if self.relative_path != expected:
            raise ValueError("candidate output path is not canonical")
        return self


class SourceReproducibilityRecord(BaseModel):
    """One source-level reproducibility outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    source_id: str = Field(pattern=r"^S\d{3}$")
    primary_output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    repeat_output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    byte_identical: bool | None
    status: Literal["passed", "failed", "unavailable"]

    @model_validator(mode="after")
    def validate_record(self) -> SourceReproducibilityRecord:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("reproducibility record contains a non-development source")
        first = self.primary_output_sha256
        second = self.repeat_output_sha256
        if self.status == "passed":
            if first is None or second is None or first != second:
                raise ValueError("passed requires equal primary and repeat hashes")
            if self.byte_identical is not True:
                raise ValueError("passed requires byte_identical=true")
        elif self.status == "failed":
            if first is None or second is None or first == second:
                raise ValueError("failed requires different primary and repeat hashes")
            if self.byte_identical is not False:
                raise ValueError("failed requires byte_identical=false")
        else:
            if first is not None and second is not None:
                raise ValueError("unavailable requires at least one absent hash")
            if self.byte_identical is not None:
                raise ValueError("unavailable requires byte_identical=null")
        return self


ReproducibilityRecord = SourceReproducibilityRecord


class DevelopmentPreparationManifest(BaseModel):
    """Preparation boundary and exact input/output inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    planning_merge_commit: Literal[
        "f224c4e385fab5c4e0348bcf251015630cea9af8"
    ] = PLANNING_MERGE_COMMIT
    config_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"] = (
        PARSER_COMMIT
    )
    corpus_version: Literal["stage1-corpus-v1.0"] = CORPUS_VERSION
    public_gold_version: Literal["public-gold-v0.1"] = PUBLIC_GOLD_VERSION
    public_gold_facts_sha256: Literal[
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ] = PUBLIC_GOLD_FACTS_SHA256
    public_gold_cases_sha256: Literal[
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ] = PUBLIC_GOLD_CASES_SHA256
    candidate_schema_version: Literal["0.1"] = CANDIDATE_SCHEMA_VERSION
    predicate_vocabulary_version: Literal["0.1"] = PREDICATE_VOCABULARY_VERSION
    matching_protocol_version: Literal["0.1"] = MATCHING_PROTOCOL_VERSION
    source_inventory: tuple[str, ...]
    input_records: tuple[DevelopmentInputRecord, ...]
    primary_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    repeat_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    primary_output_records: tuple[CandidateOutputRecord, ...]
    repeat_output_records: tuple[CandidateOutputRecord, ...]
    reproducibility_records: tuple[SourceReproducibilityRecord, ...]
    aggregate_reproducibility: bool
    preliminary_evaluation: PreliminaryDevelopmentEvaluationReport
    structural_unmatched_reason_code_counts: dict[str, int]
    plan_validator_passed: Literal[True]
    implementation_commit_verified_before_observation: Literal[True]
    protected_planning_hashes: dict[str, str]
    protected_v0_1_hashes_valid: Literal[True]
    d1_implementation_hashes: dict[str, str]
    observation_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    structural_inventory_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_review_packet_sha256: str | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    owner_assessment_template_sha256: str | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    owner_review_authorized: bool
    held_out_access: Literal[
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    ] = HELD_OUT_ACCESS

    @model_validator(mode="after")
    def validate_manifest(self) -> DevelopmentPreparationManifest:
        if self.source_inventory != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("source_inventory must match frozen development order")
        for values, label in (
            (self.input_records, "input_records"),
            (self.primary_attempt_records, "primary_attempt_records"),
            (self.repeat_attempt_records, "repeat_attempt_records"),
            (self.reproducibility_records, "reproducibility_records"),
        ):
            if tuple(item.source_id for item in values) != DEVELOPMENT_SOURCE_IDS:
                raise ValueError(f"{label} must use frozen development order")
        if any(item.run_label != "primary" for item in self.primary_attempt_records):
            raise ValueError("primary attempt records use the wrong run label")
        if any(item.run_label != "repeat" for item in self.repeat_attempt_records):
            raise ValueError("repeat attempt records use the wrong run label")
        successful_primary = tuple(
            item.source_id
            for item in self.primary_attempt_records
            if item.status == "success"
        )
        successful_repeat = tuple(
            item.source_id
            for item in self.repeat_attempt_records
            if item.status == "success"
        )
        if tuple(item.source_id for item in self.primary_output_records) != (
            successful_primary
        ):
            raise ValueError("primary output records do not reconcile with attempts")
        if tuple(item.source_id for item in self.repeat_output_records) != (
            successful_repeat
        ):
            raise ValueError("repeat output records do not reconcile with attempts")
        expected_aggregate = all(
            item.status == "passed" for item in self.reproducibility_records
        )
        if self.aggregate_reproducibility != expected_aggregate:
            raise ValueError("aggregate_reproducibility does not reconcile")
        if self.preliminary_evaluation.source_ids != self.source_inventory:
            raise ValueError("preliminary evaluation source inventory differs")
        if self.preliminary_evaluation.all_outputs_byte_identical != (
            self.aggregate_reproducibility
        ):
            raise ValueError("preliminary evaluation reproducibility differs")
        if tuple(self.structural_unmatched_reason_code_counts) != tuple(
            sorted(self.structural_unmatched_reason_code_counts)
        ):
            raise ValueError("reason-code counts must use sorted keys")
        if any(
            key not in DIAGNOSTIC_REASON_CODES or value < 0
            for key, value in self.structural_unmatched_reason_code_counts.items()
        ):
            raise ValueError("reason-code counts contain an invalid entry")
        expected_owner = (
            expected_aggregate
            and len(successful_primary) == 5
            and len(successful_repeat) == 5
        )
        if self.owner_review_authorized != expected_owner:
            raise ValueError("owner_review_authorized does not reconcile")
        if self.owner_review_authorized:
            if self.owner_review_packet_sha256 is None or (
                self.owner_assessment_template_sha256 is None
            ):
                raise ValueError("authorized owner review requires packet hashes")
        elif self.owner_review_packet_sha256 is not None or (
            self.owner_assessment_template_sha256 is not None
        ):
            raise ValueError("ineligible runs must not record owner packet hashes")
        _require_hash_mapping(
            self.protected_planning_hashes, "protected_planning_hashes"
        )
        _require_hash_mapping(
            self.d1_implementation_hashes, "d1_implementation_hashes"
        )
        return self


PreparationManifest = DevelopmentPreparationManifest


class DevelopmentObservationLock(BaseModel):
    """Immutable first-observation evidence written before owner review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    observation_status: Literal["first_development_observation_locked"] = (
        "first_development_observation_locked"
    )
    metrics_status: Literal["preliminary_until_finalization"] = (
        "preliminary_until_finalization"
    )
    implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    planning_merge_commit: Literal[
        "f224c4e385fab5c4e0348bcf251015630cea9af8"
    ] = PLANNING_MERGE_COMMIT
    config_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"] = (
        PARSER_COMMIT
    )
    corpus_version: Literal["stage1-corpus-v1.0"] = CORPUS_VERSION
    public_gold_version: Literal["public-gold-v0.1"] = PUBLIC_GOLD_VERSION
    public_gold_facts_sha256: Literal[
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ] = PUBLIC_GOLD_FACTS_SHA256
    public_gold_cases_sha256: Literal[
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ] = PUBLIC_GOLD_CASES_SHA256
    candidate_schema_version: Literal["0.1"] = CANDIDATE_SCHEMA_VERSION
    predicate_vocabulary_version: Literal["0.1"] = PREDICATE_VOCABULARY_VERSION
    matching_protocol_version: Literal["0.1"] = MATCHING_PROTOCOL_VERSION
    source_ids: tuple[str, ...]
    input_records: tuple[DevelopmentInputRecord, ...]
    primary_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    repeat_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    primary_output_records: tuple[CandidateOutputRecord, ...]
    repeat_output_records: tuple[CandidateOutputRecord, ...]
    reproducibility_records: tuple[SourceReproducibilityRecord, ...]
    aggregate_reproducibility: bool
    preliminary_evaluation: PreliminaryDevelopmentEvaluationReport
    structural_unmatched_reason_code_counts: dict[str, int]
    implementation_commit_verified_before_observation: Literal[True]
    held_out_semantic_content_loaded: Literal[False]
    held_out_access: Literal[
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    ] = HELD_OUT_ACCESS

    @model_validator(mode="after")
    def validate_lock(self) -> DevelopmentObservationLock:
        if self.source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("source_ids must match frozen development order")
        for values, label in (
            (self.input_records, "input_records"),
            (self.primary_attempt_records, "primary_attempt_records"),
            (self.repeat_attempt_records, "repeat_attempt_records"),
            (self.reproducibility_records, "reproducibility_records"),
        ):
            if tuple(item.source_id for item in values) != DEVELOPMENT_SOURCE_IDS:
                raise ValueError(f"{label} must use frozen development order")
        if self.preliminary_evaluation.source_ids != self.source_ids:
            raise ValueError("preliminary evaluation source inventory differs")
        expected_aggregate = all(
            item.status == "passed" for item in self.reproducibility_records
        )
        if self.aggregate_reproducibility != expected_aggregate:
            raise ValueError("aggregate reproducibility does not reconcile")
        if self.preliminary_evaluation.all_outputs_byte_identical != (
            self.aggregate_reproducibility
        ):
            raise ValueError("evaluation reproducibility differs from lock")
        if tuple(self.structural_unmatched_reason_code_counts) != tuple(
            sorted(self.structural_unmatched_reason_code_counts)
        ):
            raise ValueError("reason-code counts must use sorted keys")
        if any(
            key not in DIAGNOSTIC_REASON_CODES or value < 0
            for key, value in self.structural_unmatched_reason_code_counts.items()
        ):
            raise ValueError("reason-code counts contain an invalid entry")
        return self


ObservationLock = DevelopmentObservationLock


DiagnosticReasonCode = Literal[
    "additional_candidate_duplicate",
    "no_candidate_same_source_predicate",
    "no_strict_match",
    "normalized_value_mismatch",
    "qualifier_mismatch",
    "qualifier_missing",
    "subject_text_mismatch",
    "subject_type_mismatch",
    "value_type_mismatch",
]


class UnmatchedAnnotationDiagnostic(BaseModel):
    """Structural closest-pair hints for one unmatched annotation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    annotation_id: str = Field(pattern=r"^PG-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    closest_candidate_ids: tuple[str, ...]
    reason_codes: tuple[DiagnosticReasonCode, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> UnmatchedAnnotationDiagnostic:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("diagnostic contains a non-development source")
        _require_sorted_unique(self.closest_candidate_ids, "closest_candidate_ids")
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        return self


class UnmatchedCandidateDiagnostic(BaseModel):
    """Structural closest-pair hints for one unmatched candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    candidate_id: str = Field(min_length=1)
    source_id: str = Field(pattern=r"^S\d{3}$")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    closest_annotation_ids: tuple[str, ...]
    reason_codes: tuple[DiagnosticReasonCode, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> UnmatchedCandidateDiagnostic:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("diagnostic contains a non-development source")
        _require_sorted_unique(self.closest_annotation_ids, "closest_annotation_ids")
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        return self


class SourcePredicateDiagnosticSummary(BaseModel):
    """Bounded source/predicate structural summary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    source_id: str = Field(pattern=r"^S\d{3}$")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    unmatched_candidate_count: int = Field(ge=0)
    unmatched_annotation_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    semantic_duplicate_count: int = Field(ge=0)


class StructuralUnmatchedInventory(BaseModel):
    """Deterministic structural inventory without semantic judgments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    analysis_status: Literal["structural_review_inventory_only"] = (
        "structural_review_inventory_only"
    )
    unmatched_annotations: tuple[UnmatchedAnnotationDiagnostic, ...]
    unmatched_candidates: tuple[UnmatchedCandidateDiagnostic, ...]
    source_predicate_summaries: tuple[SourcePredicateDiagnosticSummary, ...]
    reason_code_counts: dict[str, int]
    duplicate_candidate_count: int = Field(ge=0)
    review_required_candidate_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_inventory(self) -> StructuralUnmatchedInventory:
        annotation_ids = tuple(item.annotation_id for item in self.unmatched_annotations)
        candidate_ids = tuple(item.candidate_id for item in self.unmatched_candidates)
        _require_sorted_unique(annotation_ids, "unmatched annotation IDs")
        _require_sorted_unique(candidate_ids, "unmatched candidate IDs")
        expected_summaries = tuple(
            sorted(
                self.source_predicate_summaries,
                key=lambda item: (item.source_id, item.predicate),
            )
        )
        if self.source_predicate_summaries != expected_summaries:
            raise ValueError("source_predicate_summaries must be sorted")
        if len(
            {(item.source_id, item.predicate) for item in self.source_predicate_summaries}
        ) != len(self.source_predicate_summaries):
            raise ValueError("source_predicate_summaries must be unique")
        if tuple(self.reason_code_counts) != tuple(sorted(self.reason_code_counts)):
            raise ValueError("reason_code_counts must use sorted keys")
        observed = {
            code: sum(
                code in item.reason_codes
                for item in (*self.unmatched_annotations, *self.unmatched_candidates)
            )
            for code in sorted(
                {
                    code
                    for item in (*self.unmatched_annotations, *self.unmatched_candidates)
                    for code in item.reason_codes
                }
            )
        }
        if self.reason_code_counts != observed:
            raise ValueError("reason_code_counts do not reconcile")
        return self


UnmatchedReviewInventory = StructuralUnmatchedInventory


class OwnerChallengeEvidenceSummary(BaseModel):
    """Bounded candidate evidence for owner challenge review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    evidence_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    location_type: LocationType
    location_value: str = Field(min_length=1)
    text_excerpt: str = Field(min_length=1, max_length=240)


class OwnerChallengeCandidateSummary(BaseModel):
    """Bounded candidate and evidence references for one challenge case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    candidate_id: str = Field(min_length=1)
    warning_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence: tuple[OwnerChallengeEvidenceSummary, ...]

    @model_validator(mode="after")
    def validate_summary(self) -> OwnerChallengeCandidateSummary:
        _require_sorted_unique(self.warning_codes, "warning_codes")
        _require_sorted_unique(self.evidence_ids, "evidence_ids")
        if tuple(item.evidence_id for item in self.evidence) != self.evidence_ids:
            raise ValueError("evidence summaries must match evidence_ids")
        return self


class OwnerChallengeReviewCase(BaseModel):
    """One bounded development challenge question and observed evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    expected_behavior: Literal[
        "route_to_review", "do_not_extract", "preserve_missing"
    ]
    candidate_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warning_codes: tuple[str, ...]
    observed_candidates: tuple[OwnerChallengeCandidateSummary, ...]

    @model_validator(mode="after")
    def validate_case(self) -> OwnerChallengeReviewCase:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("challenge case contains a non-development source")
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("challenge case ID and source disagree")
        _require_sorted_unique(self.candidate_ids, "candidate_ids")
        _require_sorted_unique(self.evidence_ids, "evidence_ids")
        _require_sorted_unique(self.warning_codes, "warning_codes")
        if tuple(item.candidate_id for item in self.observed_candidates) != (
            self.candidate_ids
        ):
            raise ValueError("observed candidates must match candidate_ids")
        return self


class OwnerChallengeReviewPacket(BaseModel):
    """Evidence packet created only after complete reproducibility."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    review_status: Literal["authorized_pending_owner_review"] = (
        "authorized_pending_owner_review"
    )
    cases: tuple[OwnerChallengeReviewCase, ...]

    @model_validator(mode="after")
    def validate_packet(self) -> OwnerChallengeReviewPacket:
        if tuple(item.case_id for item in self.cases) != DEVELOPMENT_CASE_IDS:
            raise ValueError("packet must contain exact development challenge cases")
        return self


class BlankOwnerAssessmentEntry(BaseModel):
    """A deliberately judgment-free owner-assessment placeholder."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    expected_behavior: Literal[
        "route_to_review", "do_not_extract", "preserve_missing"
    ]
    outcome: None = None
    related_candidate_ids: tuple[str, ...] = ()
    related_warning_codes: tuple[str, ...] = ()
    rationale: None = None


class OwnerChallengeAssessmentTemplate(BaseModel):
    """Blank owner-editable assessment template."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    assessment_method: Literal["owner_review"] = "owner_review"
    assessments: tuple[BlankOwnerAssessmentEntry, ...]

    @model_validator(mode="after")
    def validate_template(self) -> OwnerChallengeAssessmentTemplate:
        if tuple(item.case_id for item in self.assessments) != DEVELOPMENT_CASE_IDS:
            raise ValueError("template must contain exact development challenge cases")
        return self


class CompletedOwnerAssessmentEntry(BaseModel):
    """One explicit owner-completed challenge assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    expected_behavior: Literal[
        "route_to_review", "do_not_extract", "preserve_missing"
    ]
    outcome: Literal["passed", "failed"]
    related_candidate_ids: tuple[str, ...] = ()
    related_warning_codes: tuple[str, ...] = ()
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_entry(self) -> CompletedOwnerAssessmentEntry:
        _require_sorted_unique(self.related_candidate_ids, "related_candidate_ids")
        _require_sorted_unique(self.related_warning_codes, "related_warning_codes")
        if any(
            not SNAKE_CASE_PATTERN.fullmatch(item)
            for item in self.related_warning_codes
        ):
            raise ValueError("related_warning_codes must use snake_case")
        if self.rationale != self.rationale.strip():
            raise ValueError("rationale must be trimmed")
        if re.search(r"(?:[A-Za-z]:[\\/]|\\\\|file://)", self.rationale):
            raise ValueError("rationale must not contain an absolute path")
        return self


class CompletedOwnerAssessmentArtifact(BaseModel):
    """Complete explicit owner outcomes required by finalization."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    assessment_method: Literal["owner_review"] = "owner_review"
    assessment_status: Literal["complete"] = "complete"
    assessments: tuple[CompletedOwnerAssessmentEntry, ...]

    @model_validator(mode="after")
    def validate_artifact(self) -> CompletedOwnerAssessmentArtifact:
        if tuple(item.case_id for item in self.assessments) != DEVELOPMENT_CASE_IDS:
            raise ValueError("completed assessments must contain exact challenge cases")
        return self


class BaselineFreezeReferences(BaseModel):
    """Repository-relative references used by finalization and freeze."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    preparation_manifest_path: str
    preparation_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    observation_lock_path: str
    observation_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    structural_inventory_path: str
    structural_inventory_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_review_packet_path: str
    owner_review_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_assessment_path: str
    owner_assessment_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_report_path: str
    evaluation_report_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator(
        "preparation_manifest_path",
        "observation_lock_path",
        "structural_inventory_path",
        "owner_review_packet_path",
        "owner_assessment_path",
        "evaluation_report_path",
    )
    @classmethod
    def validate_paths(cls, value: str) -> str:
        return _validate_relative_path(value, "artifact path")


class FinalizationRecord(BaseModel):
    """Finalization identity and evidence-link record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    finalization_status: Literal["complete_process_gates_passed"] = (
        "complete_process_gates_passed"
    )
    implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    planning_merge_commit: Literal[
        "f224c4e385fab5c4e0348bcf251015630cea9af8"
    ] = PLANNING_MERGE_COMMIT
    evidence_references: BaselineFreezeReferences
    all_source_attempts_successful: Literal[True]
    all_outputs_byte_identical: Literal[True]
    owner_assessments_complete: Literal[True]
    held_out_semantic_content_loaded: Literal[False]
    held_out_access: Literal[
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    ] = HELD_OUT_ACCESS


__all__ = [
    "EXPERIMENT_ID",
    "PLANNING_MERGE_COMMIT",
    "PARSER_COMMIT",
    "CORPUS_VERSION",
    "PUBLIC_GOLD_VERSION",
    "PUBLIC_GOLD_FACTS_SHA256",
    "PUBLIC_GOLD_CASES_SHA256",
    "CANDIDATE_SCHEMA_VERSION",
    "PREDICATE_VOCABULARY_VERSION",
    "MATCHING_PROTOCOL_VERSION",
    "HELD_OUT_ACCESS",
    "DEVELOPMENT_SOURCE_IDS",
    "DEVELOPMENT_CASE_IDS",
    "DevelopmentInputRecord",
    "ParsedInputRecord",
    "DevelopmentRunAttemptRecord",
    "SourceExecutionAttempt",
    "CandidateOutputRecord",
    "SourceReproducibilityRecord",
    "ReproducibilityRecord",
    "DevelopmentPreparationManifest",
    "PreparationManifest",
    "DevelopmentObservationLock",
    "ObservationLock",
    "UnmatchedAnnotationDiagnostic",
    "UnmatchedCandidateDiagnostic",
    "SourcePredicateDiagnosticSummary",
    "StructuralUnmatchedInventory",
    "UnmatchedReviewInventory",
    "OwnerChallengeEvidenceSummary",
    "OwnerChallengeCandidateSummary",
    "OwnerChallengeReviewCase",
    "OwnerChallengeReviewPacket",
    "BlankOwnerAssessmentEntry",
    "OwnerChallengeAssessmentTemplate",
    "CompletedOwnerAssessmentEntry",
    "CompletedOwnerAssessmentArtifact",
    "BaselineFreezeReferences",
    "FinalizationRecord",
]
