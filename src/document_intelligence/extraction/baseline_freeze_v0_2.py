"""Pure process-gate validation for deterministic-baseline-v0.2 freeze."""

from __future__ import annotations

from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.development_run_models_v0_2 import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    HELD_OUT_ACCESS,
    PARSER_COMMIT,
    PLANNING_MERGE_COMMIT,
    BaselineFreezeReferences,
    DevelopmentObservationLock,
    DevelopmentPreparationManifest,
    FinalizationRecord,
)
from document_intelligence.extraction.evaluation_models_v0_2 import (
    DevelopmentEvaluationReport,
    MetricFraction,
)


EXPERIMENT_ID = "deterministic-baseline-v0.2"
SHA256_PATTERN = r"^[0-9A-F]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
PROCESS_GATE_IDS = (
    "all_sources_complete_both_passes",
    "zero_unhandled_extraction_exceptions",
    "candidate_schema_valid",
    "repeat_outputs_byte_identical",
    "exact_output_hashes_revalidated",
    "exact_metrics_reconciled",
    "challenge_cases_owner_assessed",
    "held_out_semantics_not_loaded",
    "source_independent_rules",
    "protected_v0_1_hashes_valid",
    "protected_planning_hashes_valid",
    "implementation_commit_precedes_observation",
    "artifact_identities_agree",
    "observation_lock_hash_revalidated",
)
QUALITY_TARGET_IDS = (
    "strict_tp_greater_than_zero",
    "commitment_candidates_below_243",
    "total_candidates_below_288",
    "ambiguous_relationship_routed_to_review",
    "zero_incompatible_predicate_subject_candidate",
    "no_predicate_family_dominates",
    "fewer_semantic_duplicates_than_v0_1",
)
METRIC_NAMES = (
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


class BaselineFreezeError(RuntimeError):
    """Raised when mandatory process evidence cannot support a v0.2 freeze."""


class FreezeProcessEvidence(BaseModel):
    """Explicit pure inputs for every mandatory process gate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    primary_success_count: int = Field(ge=0, le=5)
    repeat_success_count: int = Field(ge=0, le=5)
    unhandled_extraction_exception_count: int = Field(ge=0)
    schema_valid_primary_count: int = Field(ge=0, le=5)
    schema_valid_repeat_count: int = Field(ge=0, le=5)
    byte_identical_source_count: int = Field(ge=0, le=5)
    exact_output_hashes_revalidated: bool
    exact_metrics_reconciled: bool
    owner_assessment_count: int = Field(ge=0, le=3)
    held_out_semantic_content_loaded: bool
    source_specific_rule_detected: bool
    protected_v0_1_hashes_valid: bool
    protected_planning_hashes_valid: bool
    implementation_commit_precedes_observation: bool
    artifact_identities_agree: bool
    observation_lock_hash_revalidated: bool


class ProcessGateOutcome(BaseModel):
    """One passed mandatory process gate retained in the freeze manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    gate_id: Literal[
        "all_sources_complete_both_passes",
        "zero_unhandled_extraction_exceptions",
        "candidate_schema_valid",
        "repeat_outputs_byte_identical",
        "exact_output_hashes_revalidated",
        "exact_metrics_reconciled",
        "challenge_cases_owner_assessed",
        "held_out_semantics_not_loaded",
        "source_independent_rules",
        "protected_v0_1_hashes_valid",
        "protected_planning_hashes_valid",
        "implementation_commit_precedes_observation",
        "artifact_identities_agree",
        "observation_lock_hash_revalidated",
    ]
    outcome: Literal["passed"] = "passed"
    evidence: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_evidence(self) -> ProcessGateOutcome:
        if self.evidence != self.evidence.strip():
            raise ValueError("gate evidence must be trimmed")
        if "file://" in self.evidence or "\\" in self.evidence:
            raise ValueError("gate evidence must not contain a local path")
        return self


class QualityTargetOutcome(BaseModel):
    """One visible but non-binding v0.2 quality target."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    target_id: Literal[
        "strict_tp_greater_than_zero",
        "commitment_candidates_below_243",
        "total_candidates_below_288",
        "ambiguous_relationship_routed_to_review",
        "zero_incompatible_predicate_subject_candidate",
        "no_predicate_family_dominates",
        "fewer_semantic_duplicates_than_v0_1",
    ]
    outcome: Literal["met", "not_met", "not_applicable"]
    non_binding: Literal[True] = True
    observed: str = Field(min_length=1, max_length=200)


class BaselineFreezeManifest(BaseModel):
    """Legal v0.2 freeze emitted only after all process gates pass."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    freeze_schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.2"] = EXPERIMENT_ID
    experiment_version: Literal["0.2"] = "0.2"
    freeze_status: Literal["frozen_after_development_process_acceptance"] = (
        "frozen_after_development_process_acceptance"
    )
    freeze_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    planning_merge_commit: Literal[
        "f224c4e385fab5c4e0348bcf251015630cea9af8"
    ] = PLANNING_MERGE_COMMIT
    config_sha256: str = Field(pattern=SHA256_PATTERN)
    corpus_version: Literal["stage1-corpus-v1.0"] = "stage1-corpus-v1.0"
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"] = (
        PARSER_COMMIT
    )
    public_gold_version: Literal["public-gold-v0.1"] = "public-gold-v0.1"
    public_gold_facts_sha256: Literal[
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ]
    public_gold_cases_sha256: Literal[
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ]
    candidate_schema_version: Literal["0.1"] = "0.1"
    predicate_vocabulary_version: Literal["0.1"] = "0.1"
    matching_protocol_version: Literal["0.1"] = "0.1"
    development_source_ids: tuple[str, ...]
    development_challenge_case_ids: tuple[str, ...]
    primary_candidate_output_hashes: dict[str, str]
    repeat_candidate_output_hashes: dict[str, str]
    evidence_references: BaselineFreezeReferences
    metric_fractions: dict[str, MetricFraction]
    process_gate_outcomes: tuple[ProcessGateOutcome, ...]
    non_binding_quality_targets: tuple[QualityTargetOutcome, ...]
    minimum_f1_gate_applies: Literal[False] = False
    held_out_access: Literal[
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    ] = HELD_OUT_ACCESS
    held_out_execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> BaselineFreezeManifest:
        if self.development_source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("development source inventory is not frozen")
        if self.development_challenge_case_ids != DEVELOPMENT_CASE_IDS:
            raise ValueError("development challenge inventory is not frozen")
        for label, values in (
            ("primary_candidate_output_hashes", self.primary_candidate_output_hashes),
            ("repeat_candidate_output_hashes", self.repeat_candidate_output_hashes),
        ):
            if tuple(values) != DEVELOPMENT_SOURCE_IDS:
                raise ValueError(f"{label} must use frozen source order")
            if any(not re.fullmatch(SHA256_PATTERN, value) for value in values.values()):
                raise ValueError(f"{label} contains an invalid SHA-256")
        if self.primary_candidate_output_hashes != self.repeat_candidate_output_hashes:
            raise ValueError("primary and repeat output hashes must be identical")
        if tuple(self.metric_fractions) != METRIC_NAMES:
            raise ValueError("metric_fractions must use exact deterministic inventory")
        if tuple(item.gate_id for item in self.process_gate_outcomes) != PROCESS_GATE_IDS:
            raise ValueError("every process gate must be present in frozen order")
        if tuple(item.target_id for item in self.non_binding_quality_targets) != (
            QUALITY_TARGET_IDS
        ):
            raise ValueError("every quality target must be present in frozen order")
        return self


def validate_process_gates(
    evidence: FreezeProcessEvidence,
) -> tuple[ProcessGateOutcome, ...]:
    """Fail closed on the first unsatisfied mandatory process gate."""
    if not isinstance(evidence, FreezeProcessEvidence):
        raise BaselineFreezeError("process evidence must be validated")
    checks = (
        (
            "all_sources_complete_both_passes",
            evidence.primary_success_count == 5 and evidence.repeat_success_count == 5,
            "5 primary and 5 repeat source attempts completed",
        ),
        (
            "zero_unhandled_extraction_exceptions",
            evidence.unhandled_extraction_exception_count == 0,
            "all extraction failures were bounded and none remained unhandled",
        ),
        (
            "candidate_schema_valid",
            evidence.schema_valid_primary_count == 5
            and evidence.schema_valid_repeat_count == 5,
            "all 10 candidate outputs validated against schema 0.1",
        ),
        (
            "repeat_outputs_byte_identical",
            evidence.byte_identical_source_count == 5,
            "all 5 primary and repeat output pairs are byte-identical",
        ),
        (
            "exact_output_hashes_revalidated",
            evidence.exact_output_hashes_revalidated,
            "every stored candidate output hash revalidated",
        ),
        (
            "exact_metrics_reconciled",
            evidence.exact_metrics_reconciled,
            "all exact metric numerators and denominators reconcile",
        ),
        (
            "challenge_cases_owner_assessed",
            evidence.owner_assessment_count == 3,
            "all 3 development challenge cases have explicit owner outcomes",
        ),
        (
            "held_out_semantics_not_loaded",
            not evidence.held_out_semantic_content_loaded,
            "held-out semantic content was not loaded",
        ),
        (
            "source_independent_rules",
            not evidence.source_specific_rule_detected,
            "reviewed extractor inventory contains no source-specific rule",
        ),
        (
            "protected_v0_1_hashes_valid",
            evidence.protected_v0_1_hashes_valid,
            "protected v0.1 semantic and observation hashes remain valid",
        ),
        (
            "protected_planning_hashes_valid",
            evidence.protected_planning_hashes_valid,
            "all frozen v0.2 planning hashes remain valid",
        ),
        (
            "implementation_commit_precedes_observation",
            evidence.implementation_commit_precedes_observation,
            "implementation commit was verified before first observation",
        ),
        (
            "artifact_identities_agree",
            evidence.artifact_identities_agree,
            "preparation observation and final report identities agree",
        ),
        (
            "observation_lock_hash_revalidated",
            evidence.observation_lock_hash_revalidated,
            "the immutable observation lock hash revalidated",
        ),
    )
    outcomes: list[ProcessGateOutcome] = []
    for gate_id, passed, message in checks:
        if not passed:
            raise BaselineFreezeError(f"process gate failed: {gate_id}")
        outcomes.append(
            ProcessGateOutcome(gate_id=gate_id, outcome="passed", evidence=message)
        )
    return tuple(outcomes)


def report_metric_fractions(
    report: DevelopmentEvaluationReport,
) -> dict[str, MetricFraction]:
    """Project complete report fractions into stable manifest order."""
    if not isinstance(report, DevelopmentEvaluationReport):
        raise BaselineFreezeError("a complete v0.2 evaluation report is required")
    return {name: getattr(report, name) for name in METRIC_NAMES}


def evaluate_quality_targets(
    *,
    report: DevelopmentEvaluationReport,
    ambiguous_relationship_emitted: bool,
    incompatible_predicate_subject_candidate_count: int,
    v0_1_semantic_duplicate_count: int,
) -> tuple[QualityTargetOutcome, ...]:
    """Report quality targets without turning any target into a freeze gate."""
    commitment_count = report.candidate_counts_by_predicate.get("commitment", 0)
    dominant = max(report.candidate_counts_by_predicate.values(), default=0)
    target_values = (
        (
            "strict_tp_greater_than_zero",
            report.true_positive > 0,
            f"strict_tp={report.true_positive}",
        ),
        (
            "commitment_candidates_below_243",
            commitment_count < 243,
            f"commitment_candidates={commitment_count}",
        ),
        (
            "total_candidates_below_288",
            report.total_candidate_count < 288,
            f"total_candidates={report.total_candidate_count}",
        ),
        (
            "ambiguous_relationship_routed_to_review",
            (not ambiguous_relationship_emitted)
            or report.review_required_candidate_count > 0,
            (
                "ambiguous_relationship_not_emitted"
                if not ambiguous_relationship_emitted
                else f"review_required={report.review_required_candidate_count}"
            ),
        ),
        (
            "zero_incompatible_predicate_subject_candidate",
            incompatible_predicate_subject_candidate_count == 0,
            (
                "incompatible_candidates="
                f"{incompatible_predicate_subject_candidate_count}"
            ),
        ),
        (
            "no_predicate_family_dominates",
            report.total_candidate_count == 0 or dominant < report.total_candidate_count,
            f"largest_predicate_population={dominant}",
        ),
        (
            "fewer_semantic_duplicates_than_v0_1",
            report.duplicate_candidate_count < v0_1_semantic_duplicate_count,
            (
                f"v0_2_duplicates={report.duplicate_candidate_count};"
                f"v0_1_duplicates={v0_1_semantic_duplicate_count}"
            ),
        ),
    )
    values: list[QualityTargetOutcome] = []
    for target_id, met, observed in target_values:
        outcome = "met" if met else "not_met"
        if (
            target_id == "ambiguous_relationship_routed_to_review"
            and not ambiguous_relationship_emitted
        ):
            outcome = "not_applicable"
        values.append(
            QualityTargetOutcome(
                target_id=target_id, outcome=outcome, observed=observed
            )
        )
    return tuple(values)


def build_baseline_freeze_manifest(
    *,
    preparation: DevelopmentPreparationManifest,
    observation_lock: DevelopmentObservationLock,
    report: DevelopmentEvaluationReport,
    finalization: FinalizationRecord,
    process_evidence: FreezeProcessEvidence,
    primary_output_hashes: dict[str, str],
    repeat_output_hashes: dict[str, str],
    quality_targets: tuple[QualityTargetOutcome, ...],
    freeze_date: str | None = None,
) -> BaselineFreezeManifest:
    """Build a legal manifest after pure identity and process reconciliation."""
    identities = {
        preparation.experiment_id,
        observation_lock.experiment_id,
        report.experiment_id,
        finalization.experiment_id,
    }
    commits = {
        preparation.implementation_commit,
        observation_lock.implementation_commit,
        finalization.implementation_commit,
    }
    if identities != {EXPERIMENT_ID} or len(commits) != 1:
        raise BaselineFreezeError("preparation observation and final identities differ")
    if report.true_positive != observation_lock.preliminary_evaluation.true_positive:
        raise BaselineFreezeError("final true-positive count differs from observation")
    if report.false_positive != observation_lock.preliminary_evaluation.false_positive:
        raise BaselineFreezeError("final false-positive count differs from observation")
    if report.false_negative != observation_lock.preliminary_evaluation.false_negative:
        raise BaselineFreezeError("final false-negative count differs from observation")
    gates = validate_process_gates(process_evidence)
    return BaselineFreezeManifest(
        freeze_date=freeze_date or date.today().isoformat(),
        implementation_commit=preparation.implementation_commit,
        config_sha256=preparation.config_sha256,
        public_gold_facts_sha256=preparation.public_gold_facts_sha256,
        public_gold_cases_sha256=preparation.public_gold_cases_sha256,
        development_source_ids=DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=DEVELOPMENT_CASE_IDS,
        primary_candidate_output_hashes=primary_output_hashes,
        repeat_candidate_output_hashes=repeat_output_hashes,
        evidence_references=finalization.evidence_references,
        metric_fractions=report_metric_fractions(report),
        process_gate_outcomes=gates,
        non_binding_quality_targets=quality_targets,
    )


def validate_freeze_against_evidence(
    *,
    manifest: BaselineFreezeManifest,
    report: DevelopmentEvaluationReport,
    process_evidence: FreezeProcessEvidence,
) -> None:
    """Revalidate a manifest without filesystem access or quality gating."""
    if manifest.metric_fractions != report_metric_fractions(report):
        raise BaselineFreezeError("freeze metrics differ from final report")
    if manifest.process_gate_outcomes != validate_process_gates(process_evidence):
        raise BaselineFreezeError("freeze process gates differ from evidence")


__all__ = [
    "EXPERIMENT_ID",
    "PROCESS_GATE_IDS",
    "QUALITY_TARGET_IDS",
    "BaselineFreezeError",
    "FreezeProcessEvidence",
    "ProcessGateOutcome",
    "QualityTargetOutcome",
    "BaselineFreezeManifest",
    "validate_process_gates",
    "report_metric_fractions",
    "evaluate_quality_targets",
    "build_baseline_freeze_manifest",
    "validate_freeze_against_evidence",
]
