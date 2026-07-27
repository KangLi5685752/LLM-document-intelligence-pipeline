"""Neutral pure-evaluator tests for deterministic-baseline-v0.2."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
)
from document_intelligence.extraction.development_evaluation_v0_2 import (
    DevelopmentEvaluationError,
    canonical_development_evaluation_json,
    evaluate_development_candidates,
    evaluate_preliminary_development_candidates,
)
from document_intelligence.extraction.evaluation_models_v0_2 import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    ChallengeCaseAssessment,
    DevelopmentEvaluationReport,
    DevelopmentExtractionAttempt,
    MetricFraction,
    PreliminaryDevelopmentEvaluationReport,
)
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType


CASE_SPECS = (
    (DEVELOPMENT_CASE_IDS[0], "S001", "ambiguous", "route_to_review"),
    (DEVELOPMENT_CASE_IDS[1], "S004", "unsupported", "do_not_extract"),
    (
        DEVELOPMENT_CASE_IDS[2],
        "S006",
        "missing_expected_value",
        "preserve_missing",
    ),
)


@pytest.fixture()
def neutral_gold() -> DevelopmentGoldBundle:
    facts = tuple(
        GoldFactAnnotation(
            annotation_id=f"PG-V01-{source_id}-{index:03d}",
            source_id=source_id,
            document_family="invented-neutral-family",
            split="development",
            subject_text=f"Neutral subject {index}",
            subject_type=SubjectType.OTHER,
            predicate="recommendation",
            raw_value=f"Use neutral control {index}",
            normalized_value=f"Use neutral control {index}",
            value_type=ValueType.STRING,
            qualifiers={"recommendation_id": f"N-{index}"},
            expected_fact_state="unknown",
            evidence_block_id=f"NEUTRAL-{source_id}-BLOCK-{index}",
            evidence_location_type=LocationType.PAGE,
            evidence_location_value=str(index),
            evidence_excerpt=f"Invented evidence for neutral control {index}.",
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            annotation_method="AI-assisted draft with local source review",
            notes="Owner verified this invented neutral record.",
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
        for index in range(1, 6)
    )
    cases = tuple(
        GoldChallengeCase(
            case_id=case_id,
            source_id=source_id,
            split="development",
            case_type=case_type,
            description="Invented neutral challenge.",
            evidence_block_ids=[f"NEUTRAL-{source_id}-CASE"],
            evidence_location_values=["1"],
            expected_behavior=expected_behavior,
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            notes="Owner verified this invented neutral challenge.",
        )
        for case_id, source_id, case_type, expected_behavior in CASE_SPECS
    )
    return DevelopmentGoldBundle(
        experiment_id="deterministic-baseline-v0.1",
        experiment_schema_version="0.1",
        public_gold_version="public-gold-v0.1",
        annotation_schema_version="0.1",
        case_schema_version="0.1",
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
        facts_sha256="A" * 64,
        cases_sha256="B" * 64,
        development_public_source_ids=DEVELOPMENT_SOURCE_IDS,
        facts=facts,
        challenge_cases=cases,
    )


def _result(gold: DevelopmentGoldBundle, source_id: str) -> CandidateExtractionResult:
    facts = tuple(item for item in gold.facts if item.source_id == source_id)
    evidence = [
        CandidateEvidenceReference(
            evidence_id=f"NEUTRAL-EVIDENCE-{source_id}-{index:03d}",
            source_id=source_id,
            block_id=item.evidence_block_id,
            location_type=item.evidence_location_type,
            location_value=item.evidence_location_value,
            text_excerpt=item.evidence_excerpt,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        for index, item in enumerate(facts, start=1)
    ]
    candidates = [
        CandidateFact(
            candidate_id=f"NEUTRAL-CANDIDATE-{source_id}-{index:03d}",
            source_id=source_id,
            document_family=item.document_family,
            subject_text=item.subject_text,
            subject_type=item.subject_type,
            predicate=item.predicate,
            raw_value=item.raw_value,
            normalized_value=item.normalized_value,
            value_type=item.value_type,
            qualifiers=item.qualifiers,
            evidence_ids=[evidence[index - 1].evidence_id],
            confidence=0.9,
            review_status=CandidateReviewStatus.NOT_REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=[],
        )
        for index, item in enumerate(facts, start=1)
    ]
    return CandidateExtractionResult(
        batch_id=f"NEUTRAL-BATCH-{source_id}",
        source_ids=[source_id],
        entities=[],
        evidence_references=evidence,
        candidate_facts=candidates,
        warnings=[],
    )


def _empty(source_id: str) -> CandidateExtractionResult:
    return CandidateExtractionResult(
        batch_id=f"NEUTRAL-EMPTY-{source_id}",
        source_ids=[source_id],
        entities=[],
        evidence_references=[],
        candidate_facts=[],
        warnings=[],
    )


def _hash(source_id: str, suffix: str = "") -> str:
    return hashlib.sha256(f"{source_id}:{suffix}".encode()).hexdigest().upper()


def _attempts(
    gold: DevelopmentGoldBundle, suffix: str = ""
) -> tuple[DevelopmentExtractionAttempt, ...]:
    return tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=_result(gold, source_id),
            canonical_output_sha256=_hash(source_id, suffix),
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )


def _assessments() -> tuple[ChallengeCaseAssessment, ...]:
    return tuple(
        ChallengeCaseAssessment(
            case_id=case_id,
            expected_behavior=expected_behavior,
            outcome="passed",
            related_candidate_ids=(),
            related_warning_codes=(),
            rationale="Owner assessed the invented neutral behavior.",
        )
        for case_id, _, _, expected_behavior in CASE_SPECS
    )


def _replace(
    attempts: tuple[DevelopmentExtractionAttempt, ...],
    source_id: str,
    replacement: DevelopmentExtractionAttempt,
) -> tuple[DevelopmentExtractionAttempt, ...]:
    return tuple(replacement if item.source_id == source_id else item for item in attempts)


def _changed_result(
    result: CandidateExtractionResult, candidate_payloads: list[dict[str, object]]
) -> CandidateExtractionResult:
    payload = result.model_dump()
    payload["candidate_facts"] = candidate_payloads
    return CandidateExtractionResult.model_validate(payload)


def test_metric_fraction_is_exact_and_rejects_v0_1_identity() -> None:
    assert MetricFraction.from_counts(2, 4).value == 0.5
    assert MetricFraction.from_counts(0, 0).value is None
    with pytest.raises(ValidationError, match="equal"):
        MetricFraction(numerator=1, denominator=2, value=0.6)
    with pytest.raises(ValidationError):
        MetricFraction(
            experiment_id="deterministic-baseline-v0.1",
            numerator=1,
            denominator=1,
            value=1.0,
        )


def test_perfect_neutral_complete_evaluation(neutral_gold: DevelopmentGoldBundle) -> None:
    attempts = _attempts(neutral_gold)
    report = evaluate_development_candidates(
        gold=neutral_gold,
        primary_attempts=attempts,
        repeat_attempts=attempts,
        challenge_assessments=_assessments(),
    )
    assert isinstance(report, DevelopmentEvaluationReport)
    assert report.experiment_id == "deterministic-baseline-v0.2"
    assert (report.true_positive, report.false_positive, report.false_negative) == (
        25,
        0,
        0,
    )
    assert report.fact_precision == MetricFraction.from_counts(25, 25)
    assert report.fact_recall == MetricFraction.from_counts(25, 25)
    assert report.fact_f1 == MetricFraction.from_counts(50, 50)
    assert report.development_challenge_case_pass_rate == MetricFraction.from_counts(
        3, 3
    )


def test_zero_candidates_preserve_gold_denominator(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=_empty(source_id),
            canonical_output_sha256=_hash(source_id, "empty"),
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=attempts,
        repeat_attempts=attempts,
    )
    assert (report.true_positive, report.false_positive, report.false_negative) == (
        0,
        0,
        25,
    )
    assert report.fact_precision.value is None
    assert report.fact_recall == MetricFraction.from_counts(0, 25)


def test_unmatched_candidate_and_annotation_are_deterministic(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = list(_attempts(neutral_gold))
    result = attempts[0].result
    assert result is not None
    first = result.candidate_facts[0]
    payloads = [item.model_dump() for item in result.candidate_facts[1:]]
    payloads.append(
        first.model_copy(
            update={
                "candidate_id": "NEUTRAL-UNMATCHED-CANDIDATE",
                "subject_text": "Different neutral subject",
            }
        ).model_dump()
    )
    changed = _changed_result(result, payloads)
    attempts[0] = DevelopmentExtractionAttempt(
        source_id="S001", result=changed, canonical_output_sha256="C" * 64
    )
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=tuple(attempts),
        repeat_attempts=tuple(attempts),
    )
    assert report.false_positive == 1 and report.false_negative == 1
    assert report.unmatched_candidate_ids == ("NEUTRAL-UNMATCHED-CANDIDATE",)
    assert report.unmatched_annotation_ids == ("PG-V01-S001-001",)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("normalized_value", "Different neutral value"),
        ("qualifiers", {"recommendation_id": "WRONG"}),
    ),
)
def test_value_and_qualifier_mismatch_are_false_positive_and_false_negative(
    neutral_gold: DevelopmentGoldBundle, field: str, value: object
) -> None:
    attempts = list(_attempts(neutral_gold))
    result = attempts[0].result
    assert result is not None
    candidates = list(result.candidate_facts)
    candidates[0] = candidates[0].model_copy(update={field: value})
    changed = _changed_result(result, [item.model_dump() for item in candidates])
    attempts[0] = DevelopmentExtractionAttempt(
        source_id="S001", result=changed, canonical_output_sha256="D" * 64
    )
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=tuple(attempts),
        repeat_attempts=tuple(attempts),
    )
    assert report.false_positive == 1 and report.false_negative == 1


def test_evidence_mismatch_is_visible_on_strict_match(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = list(_attempts(neutral_gold))
    result = attempts[0].result
    assert result is not None
    payload = result.model_dump()
    payload["evidence_references"][0]["location_value"] = "99"
    payload["evidence_references"][0]["text_excerpt"] = "Different invented evidence."
    changed = CandidateExtractionResult.model_validate(payload)
    attempts[0] = DevelopmentExtractionAttempt(
        source_id="S001", result=changed, canonical_output_sha256="E" * 64
    )
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=tuple(attempts),
        repeat_attempts=tuple(attempts),
    )
    match = next(item for item in report.strict_matches if item.source_id == "S001")
    assert match.evidence_source_match is True
    assert match.evidence_location_match is False
    assert match.evidence_excerpt_exact_match is False


def test_duplicate_and_review_required_candidates_remain_counted(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = list(_attempts(neutral_gold))
    result = attempts[0].result
    assert result is not None
    first = result.candidate_facts[0]
    candidates = [
        first.model_copy(update={"review_status": CandidateReviewStatus.REQUIRED}),
        *result.candidate_facts[1:],
        first.model_copy(update={"candidate_id": "NEUTRAL-DUPLICATE"}),
    ]
    changed = _changed_result(result, [item.model_dump() for item in candidates])
    attempts[0] = DevelopmentExtractionAttempt(
        source_id="S001", result=changed, canonical_output_sha256="F" * 64
    )
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=tuple(attempts),
        repeat_attempts=tuple(attempts),
    )
    assert report.total_candidate_count == 26
    assert report.duplicate_candidate_count == 1
    assert report.review_required_candidate_count == 1
    assert "semantic_duplicate_candidate" in report.warnings


def test_failed_source_is_not_treated_as_do_not_extract(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    failed = DevelopmentExtractionAttempt(
        source_id="S001", error_code="neutral_extraction_failure"
    )
    primary = _replace(attempts, "S001", failed)
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=primary,
        repeat_attempts=attempts,
    )
    assert isinstance(report, PreliminaryDevelopmentEvaluationReport)
    assert report.schema_valid_source_count == 4
    assert report.failed_source_count == 1
    assert report.candidate_counts_by_source["S001"] == 0
    assert (report.true_positive, report.false_negative) == (20, 5)
    assert report.schema_valid_result_rate == MetricFraction.from_counts(4, 5)
    assert report.reproducibility_checks[0].status == "unavailable"
    with pytest.raises(DevelopmentEvaluationError, match="five successful"):
        evaluate_development_candidates(
            gold=neutral_gold,
            primary_attempts=primary,
            repeat_attempts=attempts,
            challenge_assessments=_assessments(),
        )


def test_complete_evaluation_requires_explicit_owner_assessments(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    with pytest.raises(DevelopmentEvaluationError, match="three explicit"):
        evaluate_development_candidates(
            gold=neutral_gold,
            primary_attempts=attempts,
            repeat_attempts=attempts,
            challenge_assessments=(),
        )


def test_repeat_mismatch_blocks_complete_report(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    primary = _attempts(neutral_gold)
    repeat = list(primary)
    result = repeat[0].result
    assert result is not None
    repeat[0] = DevelopmentExtractionAttempt(
        source_id="S001", result=result, canonical_output_sha256="9" * 64
    )
    preliminary = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=primary,
        repeat_attempts=tuple(repeat),
    )
    assert preliminary.all_outputs_byte_identical is False
    with pytest.raises(DevelopmentEvaluationError, match="byte-identical"):
        evaluate_development_candidates(
            gold=neutral_gold,
            primary_attempts=primary,
            repeat_attempts=tuple(repeat),
            challenge_assessments=_assessments(),
        )


def test_attempt_inventory_rejects_missing_additional_and_duplicate(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    with pytest.raises(DevelopmentEvaluationError, match="exactly five"):
        evaluate_preliminary_development_candidates(
            gold=neutral_gold,
            primary_attempts=attempts[:-1],
            repeat_attempts=attempts,
        )
    duplicate = (*attempts[:-1], attempts[0])
    with pytest.raises(DevelopmentEvaluationError, match="duplicate"):
        evaluate_preliminary_development_candidates(
            gold=neutral_gold,
            primary_attempts=duplicate,
            repeat_attempts=attempts,
        )
    additional = DevelopmentExtractionAttempt(
        source_id="S999",
        result=_empty("S999"),
        canonical_output_sha256="A" * 64,
    )
    with pytest.raises(DevelopmentEvaluationError, match="frozen development"):
        evaluate_preliminary_development_candidates(
            gold=neutral_gold,
            primary_attempts=(*attempts[:-1], additional),
            repeat_attempts=attempts,
        )


def test_report_rejects_v0_1_identity_and_extra_fields(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=attempts,
        repeat_attempts=attempts,
    )
    payload = report.model_dump()
    payload["experiment_id"] = "deterministic-baseline-v0.1"
    with pytest.raises(ValidationError):
        PreliminaryDevelopmentEvaluationReport.model_validate(payload)
    payload = report.model_dump()
    payload["absolute_output_path"] = "invented"
    with pytest.raises(ValidationError, match="Extra inputs"):
        PreliminaryDevelopmentEvaluationReport.model_validate(payload)


def test_canonical_report_is_repeatable_and_deterministically_ordered(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = tuple(reversed(_attempts(neutral_gold)))
    report = evaluate_preliminary_development_candidates(
        gold=neutral_gold,
        primary_attempts=attempts,
        repeat_attempts=attempts,
    )
    first = canonical_development_evaluation_json(report)
    second = canonical_development_evaluation_json(report)
    assert first.encode() == second.encode()
    assert first.endswith("\n") and not first.endswith("\n\n")
    payload = json.loads(first)
    assert payload["experiment_id"] == "deterministic-baseline-v0.2"
    assert list(payload["candidate_counts_by_source"]) == list(DEVELOPMENT_SOURCE_IDS)
