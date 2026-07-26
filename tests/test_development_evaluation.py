"""Neutral in-memory tests for the Stage 3B.4A development evaluator."""

from __future__ import annotations

import builtins
import hashlib
import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import document_intelligence.extraction.baseline_gold as baseline_gold_module
import document_intelligence.extraction.deterministic as deterministic_module
from document_intelligence.extraction import (
    ChallengeCaseAssessment,
    DevelopmentEvaluationError,
    DevelopmentEvaluationReport,
    DevelopmentExtractionAttempt,
    MetricFraction,
    ReproducibilityCheck,
    align_normalized_values,
    canonical_development_evaluation_json,
    evaluate_development_candidates,
    match_strict_facts,
    normalize_comparison_text,
)
from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
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


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_SOURCES = ("S001", "S002", "S003", "S004", "S006")
CASE_SPECS = (
    ("PGC-V01-S001-001", "S001", "ambiguous", "route_to_review"),
    ("PGC-V01-S004-001", "S004", "unsupported", "do_not_extract"),
    (
        "PGC-V01-S006-001",
        "S006",
        "missing_expected_value",
        "preserve_missing",
    ),
)


def _public_source_id(number: str) -> str:
    return f"S{number}"


@pytest.fixture(scope="module")
def neutral_gold() -> DevelopmentGoldBundle:
    facts: list[GoldFactAnnotation] = []
    for source_id in DEVELOPMENT_SOURCES:
        for index in range(1, 6):
            facts.append(
                GoldFactAnnotation(
                    annotation_id=f"PG-V01-{source_id}-{index:03d}",
                    source_id=source_id,
                    document_family="neutral-family",
                    split="development",
                    subject_text=f"Neutral subject {index}",
                    subject_type=SubjectType.OTHER,
                    predicate="recommendation",
                    raw_value=f"Use neutral control {index}",
                    normalized_value=f"Use neutral control {index}",
                    value_type=ValueType.STRING,
                    qualifiers={},
                    expected_fact_state="unknown",
                    evidence_block_id=f"NEUTRAL-{source_id}-BLOCK-{index}",
                    evidence_location_type=LocationType.PAGE,
                    evidence_location_value=str(index),
                    evidence_excerpt=(
                        f"Neutral evidence {index} supports the bounded test record."
                    ),
                    review_status=AnnotationReviewStatus.OWNER_VERIFIED,
                    annotation_method="AI-assisted draft with local source review",
                    notes="Owner verified this invented neutral record.",
                )
            )
    cases = tuple(
        GoldChallengeCase(
            case_id=case_id,
            source_id=source_id,
            split="development",
            case_type=case_type,
            description="Invented neutral challenge for evaluator contract testing.",
            evidence_block_ids=[f"NEUTRAL-{source_id}-CASE-BLOCK"],
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
        development_public_source_ids=DEVELOPMENT_SOURCES,
        facts=tuple(facts),
        challenge_cases=cases,
    )


def _result_for_source(
    gold: DevelopmentGoldBundle,
    source_id: str,
) -> CandidateExtractionResult:
    source_facts = [fact for fact in gold.facts if fact.source_id == source_id]
    evidence = [
        CandidateEvidenceReference(
            evidence_id=f"NEUTRAL-EVIDENCE-{source_id}-{index:03d}",
            source_id=source_id,
            block_id=fact.evidence_block_id,
            location_type=fact.evidence_location_type,
            location_value=fact.evidence_location_value,
            text_excerpt=fact.evidence_excerpt,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        for index, fact in enumerate(source_facts, start=1)
    ]
    candidates = [
        CandidateFact(
            candidate_id=f"NEUTRAL-CANDIDATE-{source_id}-{index:03d}",
            source_id=source_id,
            document_family=fact.document_family,
            subject_text=fact.subject_text,
            subject_type=fact.subject_type,
            predicate=fact.predicate,
            raw_value=fact.raw_value,
            normalized_value=fact.normalized_value,
            value_type=fact.value_type,
            qualifiers=fact.qualifiers,
            evidence_ids=[evidence[index - 1].evidence_id],
            confidence=0.9,
            review_status=CandidateReviewStatus.NOT_REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=[],
        )
        for index, fact in enumerate(source_facts, start=1)
    ]
    return CandidateExtractionResult(
        batch_id=f"NEUTRAL-BATCH-{source_id}",
        source_ids=[source_id],
        entities=[],
        evidence_references=evidence,
        candidate_facts=candidates,
        warnings=[],
    )


def _empty_result(source_id: str) -> CandidateExtractionResult:
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
    gold: DevelopmentGoldBundle,
    *,
    suffix: str = "",
) -> tuple[DevelopmentExtractionAttempt, ...]:
    return tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=_result_for_source(gold, source_id),
            canonical_output_sha256=_hash(source_id, suffix),
        )
        for source_id in DEVELOPMENT_SOURCES
    )


def _assessments(
    *,
    outcomes: tuple[str, str, str] = ("passed", "passed", "passed"),
) -> tuple[ChallengeCaseAssessment, ...]:
    return tuple(
        ChallengeCaseAssessment(
            case_id=case_id,
            expected_behavior=expected_behavior,
            outcome=outcome,
            related_candidate_ids=(),
            related_warning_codes=(),
            rationale="Owner assessed the invented neutral challenge outcome.",
        )
        for (case_id, _, _, expected_behavior), outcome in zip(CASE_SPECS, outcomes)
    )


def _evaluate(
    gold: DevelopmentGoldBundle,
    *,
    primary: tuple[DevelopmentExtractionAttempt, ...] | None = None,
    repeat: tuple[DevelopmentExtractionAttempt, ...] | None = None,
    assessments: tuple[ChallengeCaseAssessment, ...] | None = None,
) -> DevelopmentEvaluationReport:
    primary_attempts = _attempts(gold) if primary is None else primary
    return evaluate_development_candidates(
        gold=gold,
        primary_attempts=primary_attempts,
        repeat_attempts=primary_attempts if repeat is None else repeat,
        challenge_assessments=(
            _assessments() if assessments is None else assessments
        ),
    )


def _replace_attempt(
    attempts: tuple[DevelopmentExtractionAttempt, ...],
    source_id: str,
    replacement: DevelopmentExtractionAttempt,
) -> tuple[DevelopmentExtractionAttempt, ...]:
    return tuple(
        replacement if item.source_id == source_id else item for item in attempts
    )


def _assessments_with_references(
    *,
    candidate_ids: tuple[str, ...] = (),
    warning_codes: tuple[str, ...] = (),
) -> tuple[ChallengeCaseAssessment, ...]:
    assessments = _assessments()
    first = assessments[0].model_copy(
        update={
            "related_candidate_ids": candidate_ids,
            "related_warning_codes": warning_codes,
        }
    )
    return (first, *assessments[1:])


def test_metric_fraction_contract() -> None:
    assert MetricFraction.from_counts(2, 4) == MetricFraction(
        numerator=2,
        denominator=4,
        value=0.5,
    )
    assert MetricFraction.from_counts(0, 0).value is None

    with pytest.raises(ValidationError, match="null"):
        MetricFraction(numerator=0, denominator=0, value=0.0)
    with pytest.raises(ValidationError, match="equal"):
        MetricFraction(numerator=1, denominator=2, value=0.6)
    with pytest.raises(ValidationError, match="exceed"):
        MetricFraction(numerator=3, denominator=2, value=1.5)


def test_development_attempt_success_and_failure_contract(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    result = _result_for_source(neutral_gold, "S001")
    success = DevelopmentExtractionAttempt(
        source_id="S001",
        result=result,
        canonical_output_sha256="A" * 64,
    )
    failure = DevelopmentExtractionAttempt(
        source_id="S001",
        error_code="parser_output_unavailable",
    )

    assert success.result is result
    assert failure.result is None and failure.canonical_output_sha256 is None

    with pytest.raises(ValidationError, match="exactly one"):
        DevelopmentExtractionAttempt(
            source_id="S001",
            result=result,
            error_code="unexpected_failure",
            canonical_output_sha256="A" * 64,
        )
    with pytest.raises(ValidationError, match="SHA-256"):
        DevelopmentExtractionAttempt(source_id="S001", result=result)
    with pytest.raises(ValidationError, match="snake_case"):
        DevelopmentExtractionAttempt(source_id="S001", error_code="C:\\secret")


def test_attempt_source_must_match_result_exactly(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    with pytest.raises(ValidationError, match="exactly match"):
        DevelopmentExtractionAttempt(
            source_id="S002",
            result=_result_for_source(neutral_gold, "S001"),
            canonical_output_sha256="A" * 64,
        )


def test_reproducibility_states() -> None:
    passed = ReproducibilityCheck(
        source_id="S001",
        first_output_sha256="A" * 64,
        second_output_sha256="A" * 64,
        byte_identical=True,
        status="passed",
    )
    failed = ReproducibilityCheck(
        source_id="S001",
        first_output_sha256="A" * 64,
        second_output_sha256="B" * 64,
        byte_identical=False,
        status="failed",
    )
    unavailable = ReproducibilityCheck(
        source_id="S001",
        first_output_sha256="A" * 64,
        second_output_sha256=None,
        byte_identical=None,
        status="unavailable",
    )

    assert (passed.status, failed.status, unavailable.status) == (
        "passed",
        "failed",
        "unavailable",
    )
    with pytest.raises(ValidationError, match="equal"):
        ReproducibilityCheck(
            source_id="S001",
            first_output_sha256="A" * 64,
            second_output_sha256="B" * 64,
            byte_identical=True,
            status="passed",
        )


def test_challenge_assessment_is_explicit_sorted_and_path_free() -> None:
    assessment = ChallengeCaseAssessment(
        case_id="PGC-V01-S001-001",
        expected_behavior="route_to_review",
        outcome="passed",
        related_candidate_ids=("CAND-A", "CAND-B"),
        related_warning_codes=("warning_a", "warning_b"),
        rationale="Owner assessed the neutral behavior.",
    )

    assert assessment.assessment_method == "owner_review"
    with pytest.raises(ValidationError, match="sorted"):
        assessment.model_copy(
            update={"related_candidate_ids": ("CAND-B", "CAND-A")}
        ).model_validate(
            {
                **assessment.model_dump(),
                "related_candidate_ids": ("CAND-B", "CAND-A"),
            }
        )
    with pytest.raises(ValidationError, match="absolute path"):
        ChallengeCaseAssessment(
            case_id="PGC-V01-S001-001",
            expected_behavior="route_to_review",
            outcome="passed",
            rationale="Reviewed at C:\\private\\record.txt",
        )


@pytest.mark.parametrize("warning_code", ("WarningCode", "warning-code"))
def test_challenge_assessment_warning_codes_require_snake_case(
    warning_code: str,
) -> None:
    with pytest.raises(ValidationError, match="lowercase snake_case"):
        ChallengeCaseAssessment(
            case_id="PGC-V01-S001-001",
            expected_behavior="route_to_review",
            outcome="passed",
            related_warning_codes=(warning_code,),
            rationale="Owner assessed the invented neutral challenge.",
        )


def test_perfect_neutral_evaluation_computes_exact_metrics(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(neutral_gold)

    assert (report.true_positive, report.false_positive, report.false_negative) == (
        25,
        0,
        0,
    )
    assert report.fact_precision == MetricFraction.from_counts(25, 25)
    assert report.fact_recall == MetricFraction.from_counts(25, 25)
    assert report.fact_f1 == MetricFraction.from_counts(50, 50)
    assert report.normalized_value_exact_match == MetricFraction.from_counts(25, 25)
    assert report.schema_valid_result_rate == MetricFraction.from_counts(5, 5)
    assert report.evidence_source_accuracy == MetricFraction.from_counts(25, 25)
    assert report.evidence_location_accuracy == MetricFraction.from_counts(25, 25)
    assert report.development_challenge_case_pass_rate == MetricFraction.from_counts(
        3, 3
    )
    assert report.all_outputs_byte_identical is True
    assert report.warnings == ()


def test_report_count_reconciliation_and_forbidden_fields(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(neutral_gold)
    invalid = report.model_dump()
    invalid["total_candidate_count"] = 24
    with pytest.raises(ValidationError, match="candidate source counts"):
        DevelopmentEvaluationReport.model_validate(invalid)

    for forbidden in ("timestamp", "output_path", "source_text", "fact_state"):
        invalid = report.model_dump()
        invalid[forbidden] = "not permitted"
        with pytest.raises(ValidationError, match="Extra inputs"):
            DevelopmentEvaluationReport.model_validate(invalid)

    invalid = report.model_dump()
    invalid["source_ids"] = ("S001", "S002", "S003", "S004", "S999")
    with pytest.raises(ValidationError, match="frozen development"):
        DevelopmentEvaluationReport.model_validate(invalid)


def test_report_rejects_non_development_strict_match_source(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    invalid = _evaluate(neutral_gold).model_dump()
    invalid["strict_matches"][0]["source_id"] = _public_source_id("005")

    with pytest.raises(ValidationError, match="non-development source"):
        DevelopmentEvaluationReport.model_validate(invalid)


@pytest.mark.parametrize("source_id", (_public_source_id("007"), "S999"))
def test_report_rejects_non_development_value_alignment_source(
    neutral_gold: DevelopmentGoldBundle,
    source_id: str,
) -> None:
    invalid = _evaluate(neutral_gold).model_dump()
    invalid["value_alignments"][0]["source_id"] = source_id

    with pytest.raises(ValidationError, match="non-development source"):
        DevelopmentEvaluationReport.model_validate(invalid)


@pytest.mark.parametrize(
    "case_id",
    (
        f"PGC-V01-{_public_source_id('005')}-001",
        f"PGC-V01-{_public_source_id('007')}-001",
        "PGC-V01-S999-001",
    ),
)
def test_report_rejects_substituted_challenge_case_id(
    neutral_gold: DevelopmentGoldBundle,
    case_id: str,
) -> None:
    invalid = _evaluate(neutral_gold).model_dump()
    invalid["challenge_case_assessments"][2]["case_id"] = case_id
    invalid["challenge_case_assessments"] = tuple(
        sorted(
            invalid["challenge_case_assessments"],
            key=lambda item: item["case_id"],
        )
    )

    with pytest.raises(ValidationError, match="frozen development cases"):
        DevelopmentEvaluationReport.model_validate(invalid)


@pytest.mark.parametrize(
    ("collection", "field", "message"),
    (
        ("strict_matches", "candidate_id", "strict match candidate IDs"),
        ("strict_matches", "annotation_id", "strict match annotation IDs"),
        ("value_alignments", "candidate_id", "value alignment candidate IDs"),
        ("value_alignments", "annotation_id", "value alignment annotation IDs"),
    ),
)
def test_report_rejects_reused_pair_identity(
    neutral_gold: DevelopmentGoldBundle,
    collection: str,
    field: str,
    message: str,
) -> None:
    invalid = _evaluate(neutral_gold).model_dump()
    invalid[collection][1][field] = invalid[collection][0][field]

    with pytest.raises(ValidationError, match=message):
        DevelopmentEvaluationReport.model_validate(invalid)


def test_exactly_five_unique_development_attempts_are_required(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    with pytest.raises(DevelopmentEvaluationError, match="exactly five"):
        _evaluate(neutral_gold, primary=attempts[:-1])

    duplicate = (*attempts[:-1], attempts[0])
    with pytest.raises(DevelopmentEvaluationError, match="duplicate"):
        _evaluate(neutral_gold, primary=duplicate)

    unauthorized = DevelopmentExtractionAttempt(
        source_id="S999",
        result=_empty_result("S999"),
        canonical_output_sha256="C" * 64,
    )
    with pytest.raises(DevelopmentEvaluationError, match="frozen development"):
        _evaluate(neutral_gold, primary=(*attempts[:-1], unauthorized))


def test_primary_and_repeat_inventories_must_match(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = _attempts(neutral_gold)
    unauthorized = DevelopmentExtractionAttempt(
        source_id="S999",
        result=_empty_result("S999"),
        canonical_output_sha256="D" * 64,
    )
    repeat = (*attempts[:-1], unauthorized)

    with pytest.raises(DevelopmentEvaluationError, match="frozen development"):
        _evaluate(neutral_gold, primary=attempts, repeat=repeat)


def test_challenge_assessment_inventory_and_behavior_are_exact(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    assessments = _assessments()
    with pytest.raises(DevelopmentEvaluationError, match="exactly three"):
        _evaluate(neutral_gold, assessments=assessments[:-1])

    wrong_id = ChallengeCaseAssessment(
        case_id="PGC-V01-S001-999",
        expected_behavior="route_to_review",
        outcome="passed",
        rationale="Owner assessed an unknown neutral case.",
    )
    with pytest.raises(DevelopmentEvaluationError, match="IDs"):
        _evaluate(neutral_gold, assessments=(*assessments[:-1], wrong_id))

    wrong_behavior = ChallengeCaseAssessment(
        case_id="PGC-V01-S001-001",
        expected_behavior="do_not_extract",
        outcome="passed",
        rationale="Owner assessed the neutral case.",
    )
    with pytest.raises(DevelopmentEvaluationError, match="expected_behavior"):
        _evaluate(
            neutral_gold,
            assessments=(wrong_behavior, *assessments[1:]),
        )


def test_evaluator_rejects_unknown_challenge_candidate_reference(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    assessments = _assessments_with_references(
        candidate_ids=("UNKNOWN-NEUTRAL-CANDIDATE",)
    )

    with pytest.raises(DevelopmentEvaluationError, match="unknown candidate ID"):
        _evaluate(neutral_gold, assessments=assessments)


def test_evaluator_rejects_unknown_challenge_warning_reference(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    assessments = _assessments_with_references(
        warning_codes=("unknown_neutral_warning",)
    )

    with pytest.raises(DevelopmentEvaluationError, match="unknown warning code"):
        _evaluate(neutral_gold, assessments=assessments)


def test_evaluator_accepts_existing_challenge_candidate_reference(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    candidate_id = "NEUTRAL-CANDIDATE-S001-001"
    report = _evaluate(
        neutral_gold,
        assessments=_assessments_with_references(candidate_ids=(candidate_id,)),
    )

    assert report.challenge_case_assessments[0].related_candidate_ids == (
        candidate_id,
    )


@pytest.mark.parametrize("warning_level", ("result", "candidate"))
def test_evaluator_accepts_observed_warning_code_prefix(
    neutral_gold: DevelopmentGoldBundle,
    warning_level: str,
) -> None:
    primary = list(_attempts(neutral_gold))
    result = primary[0].result
    assert result is not None
    payload = result.model_dump()
    observed_warning = "neutral_warning:NEUTRAL-BLOCK:1-2:NEUTRAL-RULE"
    if warning_level == "result":
        payload["warnings"] = [observed_warning]
    else:
        payload["candidate_facts"][0]["warnings"] = [observed_warning]
    changed_result = CandidateExtractionResult.model_validate(payload)
    primary[0] = DevelopmentExtractionAttempt(
        source_id="S001",
        result=changed_result,
        canonical_output_sha256=_hash("S001", warning_level),
    )
    attempts = tuple(primary)

    report = _evaluate(
        neutral_gold,
        primary=attempts,
        repeat=attempts,
        assessments=_assessments_with_references(
            warning_codes=("neutral_warning",)
        ),
    )

    assert report.challenge_case_assessments[0].related_warning_codes == (
        "neutral_warning",
    )


def test_evaluator_accepts_empty_challenge_references(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(neutral_gold, assessments=_assessments())

    assert all(
        not assessment.related_candidate_ids
        and not assessment.related_warning_codes
        for assessment in report.challenge_case_assessments
    )


def test_failed_source_remains_in_denominator_and_reproducibility(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    primary = _attempts(neutral_gold)
    failed = DevelopmentExtractionAttempt(
        source_id="S001",
        error_code="candidate_generation_failed",
    )
    primary = _replace_attempt(primary, "S001", failed)

    report = _evaluate(neutral_gold, primary=primary, repeat=_attempts(neutral_gold))

    assert report.attempted_source_count == 5
    assert report.schema_valid_source_count == 4
    assert report.failed_source_count == 1
    assert report.schema_valid_result_rate == MetricFraction.from_counts(4, 5)
    assert report.candidate_counts_by_source["S001"] == 0
    assert (report.true_positive, report.false_negative) == (20, 5)
    assert report.fact_f1 == MetricFraction.from_counts(40, 45)
    assert report.reproducibility_checks[0].status == "unavailable"
    assert "failed_source_attempt" in report.warnings


def test_review_required_and_duplicate_candidates_remain_in_population(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    primary = list(_attempts(neutral_gold))
    source_result = primary[0].result
    assert source_result is not None
    first = source_result.candidate_facts[0]
    review_fact = first.model_copy(
        update={"review_status": CandidateReviewStatus.REQUIRED}
    )
    duplicate = first.model_copy(update={"candidate_id": "NEUTRAL-DUPLICATE-S001"})
    payload = source_result.model_dump()
    payload["candidate_facts"] = [
        review_fact.model_dump(),
        *[item.model_dump() for item in source_result.candidate_facts[1:]],
        duplicate.model_dump(),
    ]
    changed_result = CandidateExtractionResult.model_validate(payload)
    primary[0] = DevelopmentExtractionAttempt(
        source_id="S001",
        result=changed_result,
        canonical_output_sha256="E" * 64,
    )

    report = _evaluate(neutral_gold, primary=tuple(primary), repeat=tuple(primary))

    assert report.total_candidate_count == 26
    assert report.review_required_candidate_count == 1
    assert report.duplicate_candidate_count == 1
    assert report.false_positive == 1
    assert "semantic_duplicate_candidate" in report.warnings


def test_evidence_metrics_use_strict_matches_only(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    primary = list(_attempts(neutral_gold))
    source_result = primary[0].result
    assert source_result is not None
    extra = source_result.candidate_facts[0].model_copy(
        update={
            "candidate_id": "NEUTRAL-WRONG-VALUE-S001",
            "normalized_value": "Different neutral value",
        }
    )
    payload = source_result.model_dump()
    payload["candidate_facts"].append(extra.model_dump())
    changed_result = CandidateExtractionResult.model_validate(payload)
    primary[0] = DevelopmentExtractionAttempt(
        source_id="S001",
        result=changed_result,
        canonical_output_sha256="F" * 64,
    )

    report = _evaluate(neutral_gold, primary=tuple(primary), repeat=tuple(primary))

    assert report.false_positive == 1
    assert report.evidence_source_accuracy.denominator == 25
    assert report.evidence_location_accuracy == MetricFraction.from_counts(25, 25)


def test_empty_candidate_alignment_metric_is_null(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    attempts = tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=_empty_result(source_id),
            canonical_output_sha256=_hash(source_id, "empty"),
        )
        for source_id in DEVELOPMENT_SOURCES
    )
    report = _evaluate(neutral_gold, primary=attempts, repeat=attempts)

    assert report.normalized_value_exact_match == MetricFraction.from_counts(0, 0)
    assert report.fact_precision.value is None
    assert report.fact_recall.value == 0.0
    assert report.fact_f1.value is None


def test_challenge_pass_rate_uses_explicit_owner_outcomes(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(
        neutral_gold,
        assessments=_assessments(outcomes=("passed", "failed", "passed")),
    )

    assert report.development_challenge_case_pass_rate == MetricFraction.from_counts(
        2, 3
    )


def test_repeat_mismatch_is_reported_per_source(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    primary = _attempts(neutral_gold)
    repeat = list(primary)
    first = repeat[0]
    assert first.result is not None
    repeat[0] = DevelopmentExtractionAttempt(
        source_id=first.source_id,
        result=first.result,
        canonical_output_sha256="F" * 64,
    )

    report = _evaluate(neutral_gold, primary=primary, repeat=tuple(repeat))

    assert report.reproducibility_checks[0].status == "failed"
    assert report.all_outputs_byte_identical is False
    assert "non_identical_repeat_output" in report.warnings


def test_canonical_report_json_is_byte_identical_and_newline_terminated(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(neutral_gold)
    first = canonical_development_evaluation_json(report)
    second = canonical_development_evaluation_json(report)

    assert first.encode() == second.encode()
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert json.loads(first)["report_schema_version"] == "0.1"
    with pytest.raises(DevelopmentEvaluationError, match="validated"):
        canonical_development_evaluation_json({})  # type: ignore[arg-type]


def test_compact_match_records_exclude_semantic_content(
    neutral_gold: DevelopmentGoldBundle,
) -> None:
    report = _evaluate(neutral_gold)
    match_fields = set(type(report.strict_matches[0]).model_fields)
    alignment_fields = set(type(report.value_alignments[0]).model_fields)

    for forbidden in (
        "subject_text",
        "raw_value",
        "normalized_value",
        "qualifiers",
        "evidence_excerpt",
        "notes",
    ):
        assert forbidden not in match_fields
        assert forbidden not in alignment_fields


def test_evaluator_performs_no_io_network_extraction_or_gold_loading(
    neutral_gold: DevelopmentGoldBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = _attempts(neutral_gold)
    assessments = _assessments()

    def reject(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external operation is forbidden")

    monkeypatch.setattr(builtins, "open", reject)
    monkeypatch.setattr(Path, "open", reject)
    monkeypatch.setattr(socket, "socket", reject)
    monkeypatch.setattr(
        deterministic_module,
        "extract_deterministic_candidates",
        reject,
    )
    monkeypatch.setattr(baseline_gold_module, "load_baseline_gold", reject)

    report = evaluate_development_candidates(
        gold=neutral_gold,
        primary_attempts=primary,
        repeat_attempts=primary,
        challenge_assessments=assessments,
    )

    assert report.true_positive == 25


def test_package_lazy_exports_resolve_to_implementation_objects() -> None:
    import document_intelligence.extraction as extraction

    for name, expected in {
        "MetricFraction": MetricFraction,
        "DevelopmentExtractionAttempt": DevelopmentExtractionAttempt,
        "ReproducibilityCheck": ReproducibilityCheck,
        "DevelopmentEvaluationReport": DevelopmentEvaluationReport,
        "DevelopmentEvaluationError": DevelopmentEvaluationError,
        "normalize_comparison_text": normalize_comparison_text,
        "match_strict_facts": match_strict_facts,
        "align_normalized_values": align_normalized_values,
        "evaluate_development_candidates": evaluate_development_candidates,
        "canonical_development_evaluation_json": (
            canonical_development_evaluation_json
        ),
    }.items():
        assert getattr(extraction, name) is expected


def test_no_evaluation_artifact_is_staged_or_created() -> None:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert "artifacts/" not in staged.replace("\\", "/")
    assert not list((ROOT / "artifacts").rglob("*development*evaluation*.json"))
