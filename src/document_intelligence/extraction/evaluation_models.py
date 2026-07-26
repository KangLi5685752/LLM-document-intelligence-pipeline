"""Strict Stage 3B development-evaluation report contracts."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from document_intelligence.extraction.models import CandidateExtractionResult


_DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
_DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
_SHA256_PATTERN = r"^[0-9A-F]{64}$"
_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:^|\s)(?:[A-Za-z]:[\\/]|\\\\|/)|file://",
    re.IGNORECASE,
)
_EVALUATOR_WARNING_CODES = {
    "failed_source_attempt",
    "non_identical_repeat_output",
    "qualifier_over_specification",
    "semantic_duplicate_candidate",
}


def _require_sorted_unique(values: tuple[str, ...], label: str) -> None:
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be sorted")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} must not contain blank values")


class MetricFraction(BaseModel):
    """An exact metric numerator, denominator, and derived value."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None

    @model_validator(mode="after")
    def validate_fraction(self) -> MetricFraction:
        """Keep stored counts and the floating-point representation consistent."""
        if self.numerator > self.denominator:
            raise ValueError("numerator cannot exceed denominator")
        if self.denominator == 0:
            if self.value is not None:
                raise ValueError("zero denominator requires a null value")
            return self
        expected = self.numerator / self.denominator
        if self.value is None or not math.isclose(
            self.value,
            expected,
            rel_tol=1e-15,
            abs_tol=1e-15,
        ):
            raise ValueError("value must equal numerator / denominator")
        return self

    @classmethod
    def from_counts(cls, numerator: int, denominator: int) -> MetricFraction:
        """Construct a fraction deterministically from exact integer counts."""
        return cls(
            numerator=numerator,
            denominator=denominator,
            value=None if denominator == 0 else numerator / denominator,
        )


class DevelopmentExtractionAttempt(BaseModel):
    """One explicit successful or failed development-source extraction attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    result: CandidateExtractionResult | None = None
    error_code: str | None = None
    canonical_output_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )

    @model_validator(mode="after")
    def validate_attempt(self) -> DevelopmentExtractionAttempt:
        """Require exactly one safe, source-consistent outcome."""
        if (self.result is None) == (self.error_code is None):
            raise ValueError("exactly one of result or error_code must be present")
        if self.result is not None:
            try:
                validated_result = CandidateExtractionResult.model_validate(
                    self.result.model_dump()
                )
            except ValidationError as error:
                raise ValueError("result must satisfy the candidate schema") from error
            if validated_result != self.result:
                raise ValueError("result must satisfy the candidate schema")
            if self.result.source_ids != [self.source_id]:
                raise ValueError("result source_ids must exactly match source_id")
            if self.canonical_output_sha256 is None:
                raise ValueError("successful attempts require an output SHA-256")
        else:
            if self.canonical_output_sha256 is not None:
                raise ValueError("failed attempts must not contain an output hash")
            assert self.error_code is not None
            if not _SNAKE_CASE_PATTERN.fullmatch(self.error_code):
                raise ValueError("error_code must use lowercase snake_case")
        return self


class ReproducibilityCheck(BaseModel):
    """Source-level comparison of two canonical candidate outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    first_output_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    second_output_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    byte_identical: bool | None
    status: Literal["passed", "failed", "unavailable"]

    @model_validator(mode="after")
    def validate_status(self) -> ReproducibilityCheck:
        """Make status a lossless expression of the two available hashes."""
        first = self.first_output_sha256
        second = self.second_output_sha256
        if self.status == "passed":
            if first is None or second is None or first != second:
                raise ValueError("passed requires two equal output hashes")
            if self.byte_identical is not True:
                raise ValueError("passed requires byte_identical=true")
        elif self.status == "failed":
            if first is None or second is None or first == second:
                raise ValueError("failed requires two different output hashes")
            if self.byte_identical is not False:
                raise ValueError("failed requires byte_identical=false")
        else:
            if first is not None and second is not None:
                raise ValueError("unavailable requires at least one absent output")
            if self.byte_identical is not None:
                raise ValueError("unavailable requires byte_identical=null")
        return self


class StrictFactMatch(BaseModel):
    """Compact provenance-only record for one strict candidate/gold pairing."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    candidate_id: str = Field(min_length=1)
    annotation_id: str = Field(min_length=1)
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    qualifier_over_specification: tuple[str, ...] = ()
    evidence_source_match: bool
    evidence_location_match: bool
    evidence_excerpt_exact_match: bool

    @model_validator(mode="after")
    def validate_match(self) -> StrictFactMatch:
        """Keep the compact diagnostic keys deterministic."""
        _require_sorted_unique(
            self.qualifier_over_specification,
            "qualifier_over_specification",
        )
        return self


class ValueAlignment(BaseModel):
    """One value-agnostic candidate/gold alignment and its value outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^S\d{3}$")
    candidate_id: str = Field(min_length=1)
    annotation_id: str = Field(min_length=1)
    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    normalized_value_match: bool


class PredicateCounts(BaseModel):
    """Strict TP, FP, and FN counts for one canonical predicate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    predicate: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)


class ChallengeCaseAssessment(BaseModel):
    """Explicit owner outcome for one development challenge case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    expected_behavior: Literal[
        "route_to_review",
        "do_not_extract",
        "preserve_missing",
    ]
    outcome: Literal["passed", "failed"]
    assessment_method: Literal["owner_review"] = "owner_review"
    related_candidate_ids: tuple[str, ...] = ()
    related_warning_codes: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_assessment(self) -> ChallengeCaseAssessment:
        """Exclude nondeterministic, path-bearing, or unbounded assessment data."""
        _require_sorted_unique(self.related_candidate_ids, "related_candidate_ids")
        _require_sorted_unique(self.related_warning_codes, "related_warning_codes")
        if any(
            not _SNAKE_CASE_PATTERN.fullmatch(code)
            for code in self.related_warning_codes
        ):
            raise ValueError(
                "related_warning_codes must use lowercase snake_case"
            )
        if self.rationale != self.rationale.strip() or not self.rationale.strip():
            raise ValueError("rationale must be non-blank and trimmed")
        if _ABSOLUTE_PATH_PATTERN.search(self.rationale):
            raise ValueError("rationale must not contain an absolute path")
        if len(self.rationale) > 500:
            raise ValueError("rationale must be concise")
        return self


class DevelopmentEvaluationReport(BaseModel):
    """Complete deterministic-baseline-v0.1 development evaluation structure."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    report_schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    matching_protocol_version: Literal["0.1"] = "0.1"
    public_gold_version: Literal["public-gold-v0.1"] = "public-gold-v0.1"
    candidate_schema_version: Literal["0.1"] = "0.1"
    source_ids: tuple[str, ...]
    attempted_source_count: int = Field(ge=0)
    schema_valid_source_count: int = Field(ge=0)
    failed_source_count: int = Field(ge=0)
    total_candidate_count: int = Field(ge=0)
    candidate_counts_by_source: dict[str, int]
    review_required_candidate_count: int = Field(ge=0)
    duplicate_candidate_count: int = Field(ge=0)
    qualifier_over_specification_count: int = Field(ge=0)
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    fact_precision: MetricFraction
    fact_recall: MetricFraction
    fact_f1: MetricFraction
    normalized_value_exact_match: MetricFraction
    schema_valid_result_rate: MetricFraction
    evidence_source_accuracy: MetricFraction
    evidence_location_accuracy: MetricFraction
    evidence_excerpt_exact_match: MetricFraction
    development_challenge_case_pass_rate: MetricFraction
    per_predicate_counts: tuple[PredicateCounts, ...]
    strict_matches: tuple[StrictFactMatch, ...]
    value_alignments: tuple[ValueAlignment, ...]
    unmatched_candidate_ids: tuple[str, ...]
    unmatched_annotation_ids: tuple[str, ...]
    challenge_case_assessments: tuple[ChallengeCaseAssessment, ...]
    reproducibility_checks: tuple[ReproducibilityCheck, ...]
    all_outputs_byte_identical: bool
    warnings: tuple[str, ...]

    @model_validator(mode="after")
    def validate_report(self) -> DevelopmentEvaluationReport:
        """Reconcile every report count and deterministic collection."""
        if self.source_ids != _DEVELOPMENT_SOURCE_IDS:
            raise ValueError("source_ids must match the frozen development order")
        if self.attempted_source_count != 5:
            raise ValueError("attempted_source_count must be five")
        if self.schema_valid_source_count + self.failed_source_count != 5:
            raise ValueError("successful and failed source counts must reconcile")
        if tuple(self.candidate_counts_by_source) != self.source_ids:
            raise ValueError("candidate_counts_by_source must use frozen source order")
        if any(value < 0 for value in self.candidate_counts_by_source.values()):
            raise ValueError("candidate counts must be non-negative")
        if sum(self.candidate_counts_by_source.values()) != self.total_candidate_count:
            raise ValueError("candidate source counts must reconcile")
        if self.true_positive + self.false_positive != self.total_candidate_count:
            raise ValueError("candidate total must equal TP + FP")
        if self.true_positive + self.false_negative != 25:
            raise ValueError("gold total must equal 25")
        if self.review_required_candidate_count > self.total_candidate_count:
            raise ValueError("review-required count exceeds candidate count")
        if self.duplicate_candidate_count > self.total_candidate_count:
            raise ValueError("duplicate count exceeds candidate count")
        if len(self.strict_matches) != self.true_positive:
            raise ValueError("strict match count must equal true_positive")
        if len(self.unmatched_candidate_ids) != self.false_positive:
            raise ValueError("unmatched candidate count must equal false_positive")
        if len(self.unmatched_annotation_ids) != self.false_negative:
            raise ValueError("unmatched annotation count must equal false_negative")
        if self.qualifier_over_specification_count != sum(
            len(match.qualifier_over_specification) for match in self.strict_matches
        ):
            raise ValueError("qualifier over-specification count must reconcile")

        allowed_sources = set(_DEVELOPMENT_SOURCE_IDS)
        if any(
            match.source_id not in allowed_sources for match in self.strict_matches
        ):
            raise ValueError("strict_matches contain a non-development source")
        if any(
            alignment.source_id not in allowed_sources
            for alignment in self.value_alignments
        ):
            raise ValueError("value_alignments contain a non-development source")

        strict_candidate_ids = tuple(
            match.candidate_id for match in self.strict_matches
        )
        strict_annotation_ids = tuple(
            match.annotation_id for match in self.strict_matches
        )
        if len(strict_candidate_ids) != len(set(strict_candidate_ids)):
            raise ValueError("strict match candidate IDs must be unique")
        if len(strict_annotation_ids) != len(set(strict_annotation_ids)):
            raise ValueError("strict match annotation IDs must be unique")
        alignment_candidate_ids = tuple(
            alignment.candidate_id for alignment in self.value_alignments
        )
        alignment_annotation_ids = tuple(
            alignment.annotation_id for alignment in self.value_alignments
        )
        if len(alignment_candidate_ids) != len(set(alignment_candidate_ids)):
            raise ValueError("value alignment candidate IDs must be unique")
        if len(alignment_annotation_ids) != len(set(alignment_annotation_ids)):
            raise ValueError("value alignment annotation IDs must be unique")

        _require_sorted_unique(self.unmatched_candidate_ids, "unmatched_candidate_ids")
        _require_sorted_unique(self.unmatched_annotation_ids, "unmatched_annotation_ids")
        _require_sorted_unique(self.warnings, "warnings")
        if not set(self.warnings).issubset(_EVALUATOR_WARNING_CODES):
            raise ValueError("warnings contain an unknown evaluator warning code")

        match_order = tuple(
            sorted(
                self.strict_matches,
                key=lambda item: (item.source_id, item.candidate_id, item.annotation_id),
            )
        )
        if self.strict_matches != match_order:
            raise ValueError("strict_matches must use deterministic order")
        alignment_order = tuple(
            sorted(
                self.value_alignments,
                key=lambda item: (item.source_id, item.candidate_id, item.annotation_id),
            )
        )
        if self.value_alignments != alignment_order:
            raise ValueError("value_alignments must use deterministic order")

        predicates = tuple(item.predicate for item in self.per_predicate_counts)
        _require_sorted_unique(predicates, "per_predicate_counts predicates")
        if sum(item.true_positive for item in self.per_predicate_counts) != self.true_positive:
            raise ValueError("per-predicate true positives must reconcile")
        if sum(item.false_positive for item in self.per_predicate_counts) != self.false_positive:
            raise ValueError("per-predicate false positives must reconcile")
        if sum(item.false_negative for item in self.per_predicate_counts) != self.false_negative:
            raise ValueError("per-predicate false negatives must reconcile")

        if len(self.challenge_case_assessments) != 3:
            raise ValueError("exactly three challenge assessments are required")
        case_ids = tuple(item.case_id for item in self.challenge_case_assessments)
        _require_sorted_unique(case_ids, "challenge assessment case IDs")
        if case_ids != _DEVELOPMENT_CASE_IDS:
            raise ValueError(
                "challenge assessment case IDs must match the frozen development cases"
            )
        if len(self.reproducibility_checks) != 5:
            raise ValueError("exactly five reproducibility checks are required")
        if tuple(item.source_id for item in self.reproducibility_checks) != self.source_ids:
            raise ValueError("reproducibility checks must use frozen source order")
        expected_identical = all(
            item.status == "passed" for item in self.reproducibility_checks
        )
        if self.all_outputs_byte_identical != expected_identical:
            raise ValueError("all_outputs_byte_identical must reconcile")

        expected_fractions = {
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
                    2 * self.true_positive + self.false_positive + self.false_negative,
                )
            ),
            "normalized_value_exact_match": MetricFraction.from_counts(
                sum(item.normalized_value_match for item in self.value_alignments),
                len(self.value_alignments),
            ),
            "schema_valid_result_rate": MetricFraction.from_counts(
                self.schema_valid_source_count,
                self.attempted_source_count,
            ),
            "evidence_source_accuracy": MetricFraction.from_counts(
                sum(item.evidence_source_match for item in self.strict_matches),
                len(self.strict_matches),
            ),
            "evidence_location_accuracy": MetricFraction.from_counts(
                sum(item.evidence_location_match for item in self.strict_matches),
                len(self.strict_matches),
            ),
            "evidence_excerpt_exact_match": MetricFraction.from_counts(
                sum(item.evidence_excerpt_exact_match for item in self.strict_matches),
                len(self.strict_matches),
            ),
            "development_challenge_case_pass_rate": MetricFraction.from_counts(
                sum(
                    item.outcome == "passed"
                    for item in self.challenge_case_assessments
                ),
                3,
            ),
        }
        for field_name, expected in expected_fractions.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} does not reconcile with exact counts")
        return self


__all__ = [
    "MetricFraction",
    "DevelopmentExtractionAttempt",
    "ReproducibilityCheck",
    "StrictFactMatch",
    "ValueAlignment",
    "PredicateCounts",
    "ChallengeCaseAssessment",
    "DevelopmentEvaluationReport",
]
