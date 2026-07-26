"""Final baseline-freeze contracts for deterministic-baseline-v0.1."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.development_run_models import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    DevelopmentInputRecord,
    UnmatchedAnnotationDiagnostic,
    UnmatchedCandidateDiagnostic,
)
from document_intelligence.extraction.evaluation_models import (
    ChallengeCaseAssessment,
    DevelopmentEvaluationReport,
    MetricFraction,
)


_SHA256_PATTERN = r"^[0-9A-F]{64}$"
_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_METRIC_NAMES = (
    "development_challenge_case_pass_rate",
    "evidence_excerpt_exact_match",
    "evidence_location_accuracy",
    "evidence_source_accuracy",
    "fact_f1",
    "fact_precision",
    "fact_recall",
    "normalized_value_exact_match",
    "schema_valid_result_rate",
)
_ACCEPTANCE_GATE_IDS = (
    "all_sources_complete",
    "candidate_schema_valid",
    "challenge_cases_owner_assessed",
    "exact_metrics_reported",
    "held_out_semantics_not_loaded",
    "no_minimum_f1_gate",
    "repeat_outputs_byte_identical",
    "source_independent_rules",
)


class BaselineFreezeError(RuntimeError):
    """Raised when final artifacts cannot satisfy the freeze contract."""


class AcceptanceGateOutcome(BaseModel):
    """One mandatory process acceptance gate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gate_id: Literal[
        "all_sources_complete",
        "candidate_schema_valid",
        "challenge_cases_owner_assessed",
        "exact_metrics_reported",
        "held_out_semantics_not_loaded",
        "no_minimum_f1_gate",
        "repeat_outputs_byte_identical",
        "source_independent_rules",
    ]
    outcome: Literal["passed"]
    evidence: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_evidence(self) -> AcceptanceGateOutcome:
        """Keep gate evidence concise and path-free."""
        if self.evidence != self.evidence.strip():
            raise ValueError("acceptance-gate evidence must be trimmed")
        if re.search(r"(?:[A-Za-z]:[\\/]|\\\\|file://)", self.evidence):
            raise ValueError("acceptance-gate evidence must not contain a path")
        return self


class FinalErrorAnalysis(BaseModel):
    """Final bounded analysis assembled after explicit owner assessments."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    analysis_method: Literal[
        "structural diagnostics plus owner challenge assessment"
    ] = "structural diagnostics plus owner challenge assessment"
    unmatched_annotations: tuple[UnmatchedAnnotationDiagnostic, ...]
    unmatched_candidates: tuple[UnmatchedCandidateDiagnostic, ...]
    challenge_case_assessments: tuple[ChallengeCaseAssessment, ...]
    semantic_interpretation_boundary: Literal[
        "structural similarity is not an automatic correctness judgment"
    ] = "structural similarity is not an automatic correctness judgment"

    @model_validator(mode="after")
    def validate_analysis(self) -> FinalErrorAnalysis:
        """Require the exact completed development challenge inventory."""
        if tuple(
            item.case_id for item in self.challenge_case_assessments
        ) != DEVELOPMENT_CASE_IDS:
            raise ValueError("final analysis requires the three development cases")
        return self


class BaselineFreezeManifest(BaseModel):
    """Versioned evidence gate after reviewed development evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    freeze_schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"] = (
        "deterministic-baseline-v0.1"
    )
    experiment_version: Literal["0.1"] = "0.1"
    freeze_status: Literal["frozen_after_development"] = (
        "frozen_after_development"
    )
    freeze_date: str = Field(pattern=_DATE_PATTERN)
    preparation_code_commit: str = Field(pattern=_COMMIT_PATTERN)
    corpus_version: Literal["stage1-corpus-v1.0"] = "stage1-corpus-v1.0"
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"]
    public_gold_version: Literal["public-gold-v0.1"] = "public-gold-v0.1"
    public_gold_facts_sha256: Literal[
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ]
    public_gold_cases_sha256: Literal[
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ]
    candidate_schema_version: Literal["0.1"] = "0.1"
    matching_protocol_version: Literal["0.1"] = "0.1"
    development_source_ids: tuple[str, ...]
    development_challenge_case_ids: tuple[str, ...]
    immutable_file_hashes: dict[str, str]
    parsed_inputs: tuple[DevelopmentInputRecord, ...]
    primary_candidate_output_hashes: dict[str, str]
    repeat_candidate_output_hashes: dict[str, str]
    development_run_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    observation_lock_sha256: str = Field(pattern=_SHA256_PATTERN)
    evaluation_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    challenge_assessment_sha256: str = Field(pattern=_SHA256_PATTERN)
    error_analysis_sha256: str = Field(pattern=_SHA256_PATTERN)
    metric_fractions: dict[str, MetricFraction]
    acceptance_gate_outcomes: tuple[AcceptanceGateOutcome, ...]
    all_outputs_byte_identical: Literal[True]
    held_out_access_status: Literal[
        "still_blocked_pending_separate_guarded_execution"
    ] = "still_blocked_pending_separate_guarded_execution"
    no_post_observation_semantic_changes: Literal[True]

    @model_validator(mode="after")
    def validate_manifest(self) -> BaselineFreezeManifest:
        """Reject incomplete, failed, held-out-enabling, or inconsistent freezes."""
        if self.development_source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("development_source_ids must match the frozen inventory")
        if self.development_challenge_case_ids != DEVELOPMENT_CASE_IDS:
            raise ValueError(
                "development_challenge_case_ids must match the development cases"
            )
        if tuple(item.source_id for item in self.parsed_inputs) != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("parsed_inputs must use the frozen source order")
        for label, values in (
            ("primary_candidate_output_hashes", self.primary_candidate_output_hashes),
            ("repeat_candidate_output_hashes", self.repeat_candidate_output_hashes),
        ):
            if tuple(values) != DEVELOPMENT_SOURCE_IDS:
                raise ValueError(f"{label} must use the frozen source order")
            if any(not re.fullmatch(_SHA256_PATTERN, value) for value in values.values()):
                raise ValueError(f"{label} contains an invalid SHA-256")
        if self.primary_candidate_output_hashes != self.repeat_candidate_output_hashes:
            raise ValueError("repeat candidate output hashes must be identical")
        if not self.immutable_file_hashes:
            raise ValueError("immutable_file_hashes must not be empty")
        if tuple(self.immutable_file_hashes) != tuple(
            sorted(self.immutable_file_hashes)
        ):
            raise ValueError("immutable_file_hashes must use sorted paths")
        if any(
            not re.fullmatch(_SHA256_PATTERN, value)
            for value in self.immutable_file_hashes.values()
        ):
            raise ValueError("immutable_file_hashes contains an invalid SHA-256")
        if tuple(self.metric_fractions) != _METRIC_NAMES:
            raise ValueError("metric_fractions must contain every frozen report metric")
        gate_ids = tuple(item.gate_id for item in self.acceptance_gate_outcomes)
        if gate_ids != _ACCEPTANCE_GATE_IDS:
            raise ValueError("every acceptance gate must be present and passed")
        return self


def report_metric_fractions(
    report: DevelopmentEvaluationReport,
) -> dict[str, MetricFraction]:
    """Project every exact report fraction into stable manifest order."""
    return {
        name: getattr(report, name)
        for name in _METRIC_NAMES
    }


def validate_freeze_against_report(
    *,
    manifest: BaselineFreezeManifest,
    report: DevelopmentEvaluationReport,
    current_immutable_file_hashes: dict[str, str],
) -> None:
    """Validate report metrics and current code against a freeze manifest."""
    if manifest.metric_fractions != report_metric_fractions(report):
        raise BaselineFreezeError("freeze metrics do not match the evaluation report")
    if manifest.immutable_file_hashes != current_immutable_file_hashes:
        raise BaselineFreezeError("immutable code or protocol hashes changed")
    if manifest.all_outputs_byte_identical != report.all_outputs_byte_identical:
        raise BaselineFreezeError("freeze reproducibility disagrees with the report")


__all__ = [
    "BaselineFreezeError",
    "AcceptanceGateOutcome",
    "FinalErrorAnalysis",
    "BaselineFreezeManifest",
    "report_metric_fractions",
    "validate_freeze_against_report",
]
