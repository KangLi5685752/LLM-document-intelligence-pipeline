"""Strict contracts for the two-checkpoint Stage 3B.4B workflow."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.evaluation_models import (
    MetricFraction,
    PredicateCounts,
)
from document_intelligence.extraction.models import (
    CandidateReviewStatus,
    NormalizedValue,
    QualifierValue,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType, SourceFormat


DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
SHA256_PATTERN = r"^[0-9A-F]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:^|\s)(?:[A-Za-z]:[\\/]|\\\\|/)|file://",
    re.IGNORECASE,
)
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


def _require_frozen_mapping_order(values: dict[str, object], label: str) -> None:
    if tuple(values) != DEVELOPMENT_SOURCE_IDS:
        raise ValueError(f"{label} must use the frozen development source order")


class DevelopmentInputRecord(BaseModel):
    """Path-free provenance for one scored ParsedDocument input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    document_family: str = Field(min_length=1)
    source_format: Literal[SourceFormat.PDF]
    source_checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_json_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_document_id: str = Field(min_length=1)
    parsed_block_count: int = Field(ge=0)
    parse_status: Literal["success", "success_with_warnings"]

    @model_validator(mode="after")
    def validate_text(self) -> DevelopmentInputRecord:
        """Reject path-bearing or whitespace-padded identifiers."""
        for field_name in ("document_family", "parsed_document_id"):
            value = getattr(self, field_name)
            if value != value.strip():
                raise ValueError(f"{field_name} must be trimmed")
            if ABSOLUTE_PATH_PATTERN.search(value):
                raise ValueError(f"{field_name} must not contain an absolute path")
        return self


class DevelopmentRunAttemptRecord(BaseModel):
    """Safe summary of one primary or repeat extraction attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    run_label: Literal["primary", "repeat"]
    status: Literal["success", "failed"]
    candidate_output_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    candidate_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    warning_codes: tuple[str, ...] = ()
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> DevelopmentRunAttemptRecord:
        """Keep successful and failed attempt summaries mutually exclusive."""
        _require_sorted_unique(self.warning_codes, "warning_codes")
        if any(not SNAKE_CASE_PATTERN.fullmatch(code) for code in self.warning_codes):
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


class DevelopmentRunManifest(BaseModel):
    """Complete preparation record before owner challenge assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    run_date: Literal["2026-07-26"] = "2026-07-26"
    preparation_code_commit: str = Field(pattern=COMMIT_PATTERN)
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"]
    source_inventory: tuple[str, ...]
    input_records: tuple[DevelopmentInputRecord, ...]
    primary_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    repeat_attempt_records: tuple[DevelopmentRunAttemptRecord, ...]
    all_outputs_byte_identical: bool
    primary_candidate_total: int = Field(ge=0)
    review_required_total: int = Field(ge=0)
    immutable_file_hashes: dict[str, str]
    observation_status: Literal["first_development_result_observed"]

    @model_validator(mode="after")
    def validate_manifest(self) -> DevelopmentRunManifest:
        """Reconcile source order, attempts, hashes, and aggregate counts."""
        if self.source_inventory != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("source_inventory must match the frozen order")
        inventories = (
            tuple(item.source_id for item in self.input_records),
            tuple(item.source_id for item in self.primary_attempt_records),
            tuple(item.source_id for item in self.repeat_attempt_records),
        )
        if any(inventory != DEVELOPMENT_SOURCE_IDS for inventory in inventories):
            raise ValueError("input and attempt records must use frozen source order")
        if any(
            item.run_label != "primary" for item in self.primary_attempt_records
        ) or any(
            item.run_label != "repeat" for item in self.repeat_attempt_records
        ):
            raise ValueError("attempt records use an incorrect run label")
        expected_identical = all(
            primary.status == "success"
            and repeat.status == "success"
            and primary.candidate_output_sha256
            == repeat.candidate_output_sha256
            for primary, repeat in zip(
                self.primary_attempt_records,
                self.repeat_attempt_records,
            )
        )
        if self.all_outputs_byte_identical != expected_identical:
            raise ValueError("all_outputs_byte_identical does not reconcile")
        if self.primary_candidate_total != sum(
            item.candidate_count for item in self.primary_attempt_records
        ):
            raise ValueError("primary_candidate_total does not reconcile")
        if self.review_required_total != sum(
            item.review_required_count for item in self.primary_attempt_records
        ):
            raise ValueError("review_required_total does not reconcile")
        if not self.immutable_file_hashes:
            raise ValueError("immutable_file_hashes must not be empty")
        if tuple(self.immutable_file_hashes) != tuple(
            sorted(self.immutable_file_hashes)
        ):
            raise ValueError("immutable_file_hashes must use sorted paths")
        if any(
            not re.fullmatch(SHA256_PATTERN, value)
            for value in self.immutable_file_hashes.values()
        ):
            raise ValueError("immutable_file_hashes contains an invalid SHA-256")
        return self


class DevelopmentObservationLock(BaseModel):
    """Immutable first-score evidence created before qualitative review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    observation_date: Literal["2026-07-26"] = "2026-07-26"
    observation_status: Literal["first_development_result_observed"]
    preparation_code_commit: str = Field(pattern=COMMIT_PATTERN)
    immutable_file_hashes: dict[str, str]
    source_ids: tuple[str, ...]
    primary_output_hashes: dict[str, str | None]
    repeat_output_hashes: dict[str, str | None]
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    fact_precision: MetricFraction
    fact_recall: MetricFraction
    fact_f1: MetricFraction
    per_predicate_counts: tuple[PredicateCounts, ...]
    duplicate_candidate_count: int = Field(ge=0)
    qualifier_over_specification_count: int = Field(ge=0)
    unmatched_candidate_ids: tuple[str, ...]
    unmatched_annotation_ids: tuple[str, ...]
    challenge_review_status: Literal["pending_owner_review"]
    minimum_f1_gate_applies: Literal[False] = False
    semantic_tuning_policy: Literal[
        "further semantic tuning requires deterministic-baseline-v0.2"
    ] = "further semantic tuning requires deterministic-baseline-v0.2"

    @model_validator(mode="after")
    def validate_lock(self) -> DevelopmentObservationLock:
        """Make the first observed counts and fractions self-reconciling."""
        if self.source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("source_ids must match the frozen development order")
        _require_frozen_mapping_order(
            self.primary_output_hashes,
            "primary_output_hashes",
        )
        _require_frozen_mapping_order(
            self.repeat_output_hashes,
            "repeat_output_hashes",
        )
        for output_hashes in (
            self.primary_output_hashes,
            self.repeat_output_hashes,
        ):
            if any(
                value is not None and not re.fullmatch(SHA256_PATTERN, value)
                for value in output_hashes.values()
            ):
                raise ValueError("output hashes contain an invalid SHA-256")
        if tuple(self.immutable_file_hashes) != tuple(
            sorted(self.immutable_file_hashes)
        ):
            raise ValueError("immutable_file_hashes must use sorted paths")
        if not self.immutable_file_hashes or any(
            not re.fullmatch(SHA256_PATTERN, value)
            for value in self.immutable_file_hashes.values()
        ):
            raise ValueError("immutable_file_hashes contains an invalid SHA-256")
        if self.true_positive + self.false_positive != sum(
            item.true_positive + item.false_positive
            for item in self.per_predicate_counts
        ):
            raise ValueError("candidate counts do not reconcile by predicate")
        if self.true_positive + self.false_negative != sum(
            item.true_positive + item.false_negative
            for item in self.per_predicate_counts
        ):
            raise ValueError("gold counts do not reconcile by predicate")
        if self.true_positive + self.false_negative != 25:
            raise ValueError("the frozen development gold denominator must be 25")
        if len(self.unmatched_candidate_ids) != self.false_positive:
            raise ValueError("unmatched candidate count does not reconcile")
        if len(self.unmatched_annotation_ids) != self.false_negative:
            raise ValueError("unmatched annotation count does not reconcile")
        _require_sorted_unique(
            self.unmatched_candidate_ids,
            "unmatched_candidate_ids",
        )
        _require_sorted_unique(
            self.unmatched_annotation_ids,
            "unmatched_annotation_ids",
        )
        predicates = tuple(item.predicate for item in self.per_predicate_counts)
        _require_sorted_unique(predicates, "per_predicate_counts predicates")
        expected = {
            "fact_precision": MetricFraction.from_counts(
                self.true_positive,
                self.true_positive + self.false_positive,
            ),
            "fact_recall": MetricFraction.from_counts(
                self.true_positive,
                self.true_positive + self.false_negative,
            ),
            "fact_f1": (
                MetricFraction.from_counts(0, 0)
                if self.true_positive == 0
                else MetricFraction.from_counts(
                    2 * self.true_positive,
                    2 * self.true_positive
                    + self.false_positive
                    + self.false_negative,
                )
            ),
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"{field_name} does not reconcile")
        return self


class OwnerChallengeEvidenceSummary(BaseModel):
    """Bounded candidate evidence included in the owner-review packet."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    location_type: LocationType
    location_value: str = Field(min_length=1)
    text_excerpt: str = Field(min_length=1, max_length=240)


class OwnerChallengeCandidateSummary(BaseModel):
    """A bounded emitted-candidate view for one challenge case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: str = Field(min_length=1)
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    subject_text: str = Field(min_length=1)
    subject_type: SubjectType
    raw_value: str
    normalized_value: NormalizedValue
    value_type: ValueType
    qualifiers: dict[str, QualifierValue]
    confidence: float = Field(ge=0, le=1)
    review_status: CandidateReviewStatus
    warning_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence: tuple[OwnerChallengeEvidenceSummary, ...]
    references_challenge_evidence_block: bool

    @model_validator(mode="after")
    def validate_summary(self) -> OwnerChallengeCandidateSummary:
        """Keep candidate packet collections deterministic and internally linked."""
        _require_sorted_unique(self.warning_codes, "warning_codes")
        _require_sorted_unique(self.evidence_ids, "evidence_ids")
        if tuple(item.evidence_id for item in self.evidence) != self.evidence_ids:
            raise ValueError("evidence summaries must match evidence_ids")
        return self


class OwnerChallengeReviewCase(BaseModel):
    """One owner-review question and the bounded observed evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    case_type: Literal["ambiguous", "unsupported", "missing_expected_value"]
    expected_behavior: Literal[
        "route_to_review",
        "do_not_extract",
        "preserve_missing",
    ]
    description: str = Field(min_length=1)
    evidence_block_ids: tuple[str, ...]
    evidence_location_values: tuple[str, ...]
    observed_candidates: tuple[OwnerChallengeCandidateSummary, ...]
    relevant_result_warning_codes: tuple[str, ...]
    relevant_candidate_warning_codes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_case(self) -> OwnerChallengeReviewCase:
        """Require exact, deterministic development challenge evidence."""
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("challenge case source must be development-only")
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("challenge case source and ID disagree")
        if len(self.evidence_block_ids) != len(self.evidence_location_values):
            raise ValueError("challenge evidence block and location counts differ")
        if not self.evidence_block_ids:
            raise ValueError("challenge evidence must not be empty")
        _require_sorted_unique(
            tuple(item.candidate_id for item in self.observed_candidates),
            "observed candidate IDs",
        )
        _require_sorted_unique(
            self.relevant_result_warning_codes,
            "relevant_result_warning_codes",
        )
        _require_sorted_unique(
            self.relevant_candidate_warning_codes,
            "relevant_candidate_warning_codes",
        )
        return self


class OwnerChallengeReviewPacket(BaseModel):
    """Development-only evidence packet awaiting project-owner outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    review_status: Literal["pending_owner_review"] = "pending_owner_review"
    cases: tuple[OwnerChallengeReviewCase, ...]

    @model_validator(mode="after")
    def validate_packet(self) -> OwnerChallengeReviewPacket:
        """Exclude held-out or substituted challenge cases."""
        if tuple(item.case_id for item in self.cases) != DEVELOPMENT_CASE_IDS:
            raise ValueError("packet must contain the three development cases")
        return self


class OwnerChallengeAssessmentEntry(BaseModel):
    """One intentionally incomplete or owner-completed challenge assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    expected_behavior: Literal[
        "route_to_review",
        "do_not_extract",
        "preserve_missing",
    ]
    outcome: Literal["passed", "failed"] | None = None
    related_candidate_ids: tuple[str, ...] = ()
    related_warning_codes: tuple[str, ...] = ()
    rationale: str | None = None

    @model_validator(mode="after")
    def validate_entry(self) -> OwnerChallengeAssessmentEntry:
        """Require owner outcome and rationale to be supplied together."""
        _require_sorted_unique(self.related_candidate_ids, "related_candidate_ids")
        _require_sorted_unique(self.related_warning_codes, "related_warning_codes")
        if any(
            not SNAKE_CASE_PATTERN.fullmatch(code)
            for code in self.related_warning_codes
        ):
            raise ValueError("related_warning_codes must use lowercase snake_case")
        if (self.outcome is None) != (self.rationale is None):
            raise ValueError("outcome and rationale must both be null or both be present")
        if self.rationale is not None:
            if self.rationale != self.rationale.strip() or not self.rationale:
                raise ValueError("rationale must be non-blank and trimmed")
            if len(self.rationale) > 500:
                raise ValueError("rationale must be concise")
            if ABSOLUTE_PATH_PATTERN.search(self.rationale):
                raise ValueError("rationale must not contain an absolute path")
        return self


class OwnerChallengeAssessmentTemplate(BaseModel):
    """Owner-editable challenge assessment file produced by prepare."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    assessment_method: Literal["owner_review"] = "owner_review"
    assessments: tuple[OwnerChallengeAssessmentEntry, ...]

    @model_validator(mode="after")
    def validate_template(self) -> OwnerChallengeAssessmentTemplate:
        """Require the exact three development cases in stable order."""
        if tuple(item.case_id for item in self.assessments) != DEVELOPMENT_CASE_IDS:
            raise ValueError("assessments must contain the three development cases")
        return self


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
    """Structural review hints for one unmatched development annotation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    annotation_id: str = Field(pattern=r"^PG-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    closest_candidate_ids: tuple[str, ...]
    reason_codes: tuple[DiagnosticReasonCode, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> UnmatchedAnnotationDiagnostic:
        _require_sorted_unique(self.closest_candidate_ids, "closest_candidate_ids")
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        return self


class UnmatchedCandidateDiagnostic(BaseModel):
    """Structural review hints for one unmatched emitted candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: str = Field(min_length=1)
    source_id: str = Field(pattern=r"^S\d{3}$")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    closest_annotation_ids: tuple[str, ...]
    reason_codes: tuple[DiagnosticReasonCode, ...]

    @model_validator(mode="after")
    def validate_diagnostic(self) -> UnmatchedCandidateDiagnostic:
        _require_sorted_unique(self.closest_annotation_ids, "closest_annotation_ids")
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        return self


class UnmatchedReviewInventory(BaseModel):
    """Deterministic structural inventory for owner-led failure analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    analysis_status: Literal["structural_review_inventory_only"] = (
        "structural_review_inventory_only"
    )
    unmatched_annotations: tuple[UnmatchedAnnotationDiagnostic, ...]
    unmatched_candidates: tuple[UnmatchedCandidateDiagnostic, ...]

    @model_validator(mode="after")
    def validate_inventory(self) -> UnmatchedReviewInventory:
        """Require deterministic ID ordering and development-only sources."""
        annotation_ids = tuple(
            item.annotation_id for item in self.unmatched_annotations
        )
        candidate_ids = tuple(item.candidate_id for item in self.unmatched_candidates)
        _require_sorted_unique(annotation_ids, "unmatched annotation IDs")
        _require_sorted_unique(candidate_ids, "unmatched candidate IDs")
        if any(
            item.source_id not in DEVELOPMENT_SOURCE_IDS
            for item in (*self.unmatched_annotations, *self.unmatched_candidates)
        ):
            raise ValueError("unmatched inventory contains a non-development source")
        return self


__all__ = [
    "DEVELOPMENT_SOURCE_IDS",
    "DEVELOPMENT_CASE_IDS",
    "DevelopmentInputRecord",
    "DevelopmentRunAttemptRecord",
    "DevelopmentRunManifest",
    "DevelopmentObservationLock",
    "OwnerChallengeEvidenceSummary",
    "OwnerChallengeCandidateSummary",
    "OwnerChallengeReviewCase",
    "OwnerChallengeReviewPacket",
    "OwnerChallengeAssessmentEntry",
    "OwnerChallengeAssessmentTemplate",
    "UnmatchedAnnotationDiagnostic",
    "UnmatchedCandidateDiagnostic",
    "UnmatchedReviewInventory",
]
