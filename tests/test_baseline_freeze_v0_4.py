"""Strict model tests for the additive deterministic v0.4 freeze contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.baseline_freeze_v0_4 import (
    CANDIDATE_COUNTS_BY_PREDICATE,
    CANDIDATE_COUNTS_BY_SOURCE,
    CANDIDATE_OUTPUT_SHA256,
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    FIXED_INPUT_REFERENCE_SHA256,
    MATCHED_ANNOTATION_IDS,
    PROCESS_GATE_IDS,
    CandidateOutputReferenceV04,
    DevelopmentEvaluationReportV04,
    FinalizationContractError,
    FinalizationInputReferencesV04,
    FinalizationProvenanceV04,
    FinalizationProcessEvidenceV04,
    FinalizationRecordV04,
    PARSED_DOCUMENT_SHA256,
    OwnerAssessmentIndependentReviewRecordV04,
    ProcessGateOutcomeV04,
    QualityObservationV04,
    fixed_quality_observations,
    fixed_strict_metrics,
    validate_process_gates,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = (
    REPOSITORY_ROOT
    / "evaluation/baselines/deterministic-baseline-v0.4/development"
    / "owner_assessment_independent_review_record.json"
)
EXPECTED_QUALITY_OBSERVATIONS = (
    ("strict_tp_greater_than_zero", "met", "Five strict true positives were observed."),
    ("total_candidates_below_v0_2", "met", "178 candidates is below the v0.2 total."),
    ("commitment_candidates_below_v0_2", "met", "25 commitments is below the v0.2 total."),
    ("duplicate_candidate_count_zero", "met", "Strict duplicate count is zero."),
    ("owner_challenge_pass_rate_three_of_three", "met", "Formal owner outcomes are 3 of 3 passed."),
    ("ambiguous_metric_relationship_routed_to_review", "met", "Ambiguous metric relationships remain routed to review."),
    ("s002_strict_commitment_recovery", "not_met", "S002 has zero strict matches."),
    ("f1_above_zero", "met", "Observed strict F1 is above zero."),
    ("exhaustive_precision_established", "not_applicable", "Sparse gold cannot establish exhaustive precision."),
)


def _valid_process_values() -> dict[str, object]:
    return {
        "required_commit_ancestry_valid": True,
        "repository_clean_before_finalization": True,
        "exact_development_source_inventory": True,
        "exact_development_challenge_inventory": True,
        "protected_v0_4_hashes_valid": True,
        "owner_preparation_hashes_valid": True,
        "completed_owner_assessment_hash_valid": True,
        "owner_validation_report_hash_valid": True,
        "independent_review_record_valid": True,
        "parsed_document_hashes_valid": True,
        "primary_success_count": 5,
        "repeat_success_count": 5,
        "unhandled_extraction_exception_count": 0,
        "schema_valid_primary_count": 5,
        "schema_valid_repeat_count": 5,
        "byte_identical_source_count": 5,
        "candidate_output_hashes_match_preparation": True,
        "candidate_counts_reconciled": True,
        "strict_matches_reconciled": True,
        "exact_metrics_reconciled": True,
        "owner_assessment_pass_count": 3,
        "owner_assessment_fail_count": 0,
        "owner_assessment_pending_count": 0,
        "owner_and_machine_provenance_separate": True,
        "automated_diagnostic_pass_count": 3,
        "no_post_v0_4_semantic_change": True,
        "source_specific_rule_detected": False,
        "sparse_gold_limitation_preserved": True,
        "held_out_semantic_content_loaded": False,
        "held_out_execution_authorized": False,
        "output_transaction_complete": True,
        "artifact_identities_agree": True,
    }


FAILURE_MUTATIONS = {
    "required_commit_ancestry_valid": {"required_commit_ancestry_valid": False},
    "repository_clean_before_finalization": {"repository_clean_before_finalization": False},
    "exact_development_source_inventory": {"exact_development_source_inventory": False},
    "exact_development_challenge_inventory": {"exact_development_challenge_inventory": False},
    "protected_v0_4_hashes_valid": {"protected_v0_4_hashes_valid": False},
    "owner_preparation_hashes_valid": {"owner_preparation_hashes_valid": False},
    "completed_owner_assessment_hash_valid": {"completed_owner_assessment_hash_valid": False},
    "owner_validation_report_hash_valid": {"owner_validation_report_hash_valid": False},
    "independent_review_record_valid": {"independent_review_record_valid": False},
    "parsed_document_hashes_valid": {"parsed_document_hashes_valid": False},
    "all_sources_complete_both_passes": {"repeat_success_count": 4},
    "zero_unhandled_extraction_exceptions": {"unhandled_extraction_exception_count": 1},
    "candidate_schema_valid": {"schema_valid_repeat_count": 4},
    "repeat_outputs_byte_identical": {"byte_identical_source_count": 4},
    "candidate_output_hashes_match_preparation": {"candidate_output_hashes_match_preparation": False},
    "candidate_counts_reconciled": {"candidate_counts_reconciled": False},
    "strict_matches_reconciled": {"strict_matches_reconciled": False},
    "exact_metrics_reconciled": {"exact_metrics_reconciled": False},
    "owner_assessments_complete": {"owner_assessment_pass_count": 2, "owner_assessment_fail_count": 1},
    "owner_and_machine_provenance_separate": {"owner_and_machine_provenance_separate": False},
    "automated_challenge_diagnostics_reconciled": {"automated_diagnostic_pass_count": 2},
    "no_post_v0_4_semantic_change": {"no_post_v0_4_semantic_change": False},
    "source_independent_rules": {"source_specific_rule_detected": True},
    "sparse_gold_limitation_preserved": {"sparse_gold_limitation_preserved": False},
    "held_out_semantics_not_loaded": {"held_out_semantic_content_loaded": True},
    "held_out_execution_not_authorized": {"held_out_execution_authorized": True},
    "output_transaction_complete": {"output_transaction_complete": False},
    "artifact_identities_agree": {"artifact_identities_agree": False},
}


def _candidate_reference(source_id: str = "S001") -> CandidateOutputReferenceV04:
    return CandidateOutputReferenceV04(
        source_id=source_id,
        primary_relative_path=f"primary/{source_id}.json",
        repeat_relative_path=f"repeat/{source_id}.json",
        primary_sha256=CANDIDATE_OUTPUT_SHA256[source_id],
        repeat_sha256=CANDIDATE_OUTPUT_SHA256[source_id],
        candidate_count=CANDIDATE_COUNTS_BY_SOURCE[source_id],
        byte_identical=True,
    )


def _provenance() -> FinalizationProvenanceV04:
    return FinalizationProvenanceV04(
        finalization_implementation_commit="d9cddfd21a302151213ea5cde27f400a382e1e64",
        input_references=FinalizationInputReferencesV04(
            **FIXED_INPUT_REFERENCE_SHA256
        ),
        parsed_document_sha256=dict(PARSED_DOCUMENT_SHA256),
        primary_candidate_sha256=dict(CANDIDATE_OUTPUT_SHA256),
        repeat_candidate_sha256=dict(CANDIDATE_OUTPUT_SHA256),
    )


def _report_values() -> dict[str, object]:
    return {
        "provenance": _provenance(),
        "development_source_ids": DEVELOPMENT_SOURCE_IDS,
        "development_challenge_case_ids": DEVELOPMENT_CASE_IDS,
        "candidate_counts_by_source": CANDIDATE_COUNTS_BY_SOURCE,
        "candidate_counts_by_predicate": CANDIDATE_COUNTS_BY_PREDICATE,
        "strict_metrics": fixed_strict_metrics(),
        "matched_annotation_ids": MATCHED_ANNOTATION_IDS,
        "formal_owner_outcomes": ("passed", "passed", "passed"),
        "non_binding_quality_observations": fixed_quality_observations(),
    }


def _record_values() -> dict[str, object]:
    gates = validate_process_gates(
        FinalizationProcessEvidenceV04(**_valid_process_values())
    )
    return {
        "finalization_status": "development_process_accepted",
        "provenance": _provenance(),
        "finalization_implementation_commit": "d9cddfd21a302151213ea5cde27f400a382e1e64",
        "input_references": FinalizationInputReferencesV04(
            **FIXED_INPUT_REFERENCE_SHA256
        ),
        "parsed_document_sha256": PARSED_DOCUMENT_SHA256,
        "candidate_outputs": tuple(
            _candidate_reference(source_id) for source_id in DEVELOPMENT_SOURCE_IDS
        ),
        "evaluation_report_sha256": "A" * 64,
        "final_error_analysis_sha256": "B" * 64,
        "strict_metrics": fixed_strict_metrics(),
        "matched_annotation_ids": MATCHED_ANNOTATION_IDS,
        "process_gate_outcomes": gates,
        "non_binding_quality_observations": fixed_quality_observations(),
    }


def test_valid_process_evidence_yields_exact_ordered_passes() -> None:
    outcomes = validate_process_gates(
        FinalizationProcessEvidenceV04(**_valid_process_values())
    )
    assert tuple(item.gate_id for item in outcomes) == PROCESS_GATE_IDS
    assert {item.outcome for item in outcomes} == {"passed"}


@pytest.mark.parametrize("gate_id", PROCESS_GATE_IDS)
def test_every_individual_process_gate_failure_is_rejected(gate_id: str) -> None:
    values = _valid_process_values()
    values.update(FAILURE_MUTATIONS[gate_id])
    with pytest.raises(FinalizationContractError, match=gate_id):
        validate_process_gates(FinalizationProcessEvidenceV04(**values))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("audit_verdict", "rejected"),
        ("critical_finding_count", 1),
        ("reviewed_feature_commit", "0" * 40),
        ("completed_assessment_sha256", "A" * 64),
        ("owner_judgment_authored_by_review_agent", True),
        ("held_out_execution_authorized", True),
        ("baseline_freeze_created", True),
    ),
)
def test_independent_review_record_is_fixed(field: str, value: object) -> None:
    payload = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    OwnerAssessmentIndependentReviewRecordV04.model_validate(payload)
    payload[field] = value
    with pytest.raises(ValidationError):
        OwnerAssessmentIndependentReviewRecordV04.model_validate(payload)


def test_fixed_input_hashes_reject_changed_evidence() -> None:
    FinalizationInputReferencesV04(**FIXED_INPUT_REFERENCE_SHA256)
    changed = dict(FIXED_INPUT_REFERENCE_SHA256)
    changed["config_sha256"] = "A" * 64
    with pytest.raises(ValidationError, match="input reference hashes"):
        FinalizationInputReferencesV04(**changed)


@pytest.mark.parametrize("source_id", ("S005", "S007"))
def test_held_out_candidate_reference_is_rejected(source_id: str) -> None:
    payload = _candidate_reference().model_dump()
    payload.update(
        source_id=source_id,
        primary_relative_path=f"primary/{source_id}.json",
        repeat_relative_path=f"repeat/{source_id}.json",
    )
    with pytest.raises(ValidationError):
        CandidateOutputReferenceV04.model_validate(payload)


def test_non_identical_candidate_hashes_are_rejected() -> None:
    payload = _candidate_reference().model_dump()
    payload["repeat_sha256"] = "A" * 64
    with pytest.raises(ValidationError, match="primary and repeat"):
        CandidateOutputReferenceV04.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("experiment_id", "arbitrary-baseline"),
        ("development_source_ids", ("S001",)),
        ("development_challenge_case_ids", ("PGC-FICTIONAL",)),
        ("candidate_counts_by_source", {"S001": 1}),
        ("candidate_counts_by_predicate", {"metric": 178}),
        ("matched_annotation_ids", ("PG-FICTIONAL",)),
    ),
)
def test_report_rejects_identity_inventory_and_metric_changes(
    field: str, value: object
) -> None:
    payload = _report_values()
    payload[field] = value
    with pytest.raises(ValidationError):
        DevelopmentEvaluationReportV04.model_validate(payload)


def test_process_and_quality_inventories_are_distinct() -> None:
    gates = validate_process_gates(
        FinalizationProcessEvidenceV04(**_valid_process_values())
    )
    observations = fixed_quality_observations()
    assert not ({item.gate_id for item in gates} & {item.observation_id for item in observations})
    assert {item.non_binding for item in observations} == {True}
    assert next(
        item for item in observations if item.observation_id == "s002_strict_commitment_recovery"
    ).outcome == "not_met"
    assert tuple(
        (item.observation_id, item.outcome, item.evidence) for item in observations
    ) == EXPECTED_QUALITY_OBSERVATIONS


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("outcome", "met"),
        ("evidence", "Fictional changed evidence."),
        ("non_binding", False),
        ("experiment_id", "fictional-v0.4"),
    ),
)
def test_quality_observation_rejects_changed_fixed_fields(
    field: str, value: object
) -> None:
    observation = next(
        item
        for item in fixed_quality_observations()
        if item.observation_id == "s002_strict_commitment_recovery"
    )
    payload = observation.model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        QualityObservationV04.model_validate(payload)


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "reordered"))
def test_finalization_record_rejects_changed_quality_inventory(mutation: str) -> None:
    payload = _record_values()
    observations = list(payload["non_binding_quality_observations"])
    if mutation == "missing":
        observations.pop()
    elif mutation == "duplicate":
        observations[-1] = observations[0]
    else:
        observations[0], observations[1] = observations[1], observations[0]
    payload["non_binding_quality_observations"] = tuple(observations)
    with pytest.raises(ValidationError, match="quality observations"):
        FinalizationRecordV04.model_validate(payload)


def test_unknown_quality_observation_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown"):
        QualityObservationV04(
            observation_id="fictional_quality_observation",
            outcome="met",
            evidence="Fictional evidence.",
        )


def test_unknown_failed_and_machine_specific_gate_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ProcessGateOutcomeV04(gate_id="minimum_f1", evidence="invented")
    with pytest.raises(ValidationError):
        ProcessGateOutcomeV04(
            gate_id=PROCESS_GATE_IDS[0], outcome="failed", evidence="failed"
        )
    with pytest.raises(ValidationError):
        ProcessGateOutcomeV04(
            gate_id=PROCESS_GATE_IDS[0],
            evidence=chr(67) + ":" + chr(92) + "local" + chr(92) + "artifact.json",
        )


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "reordered"))
def test_finalization_record_rejects_changed_gate_inventory(mutation: str) -> None:
    payload = _record_values()
    gates = list(payload["process_gate_outcomes"])
    if mutation == "missing":
        gates.pop()
    elif mutation == "duplicate":
        gates[-1] = gates[0]
    else:
        gates[0], gates[1] = gates[1], gates[0]
    payload["process_gate_outcomes"] = tuple(gates)
    with pytest.raises(ValidationError, match="gate inventory|gate.*order"):
        FinalizationRecordV04.model_validate(payload)


def test_extra_minimum_f1_and_production_claim_fields_are_rejected() -> None:
    report = _report_values()
    report["minimum_f1"] = 0.01
    with pytest.raises(ValidationError):
        DevelopmentEvaluationReportV04.model_validate(report)
    report = _report_values()
    report["production_readiness_claimed"] = True
    with pytest.raises(ValidationError):
        DevelopmentEvaluationReportV04.model_validate(report)
