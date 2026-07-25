"""Pure in-memory Stage 3B development evaluation orchestration."""

from __future__ import annotations

import json
from typing import Sequence

from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
)
from document_intelligence.extraction.evaluation_models import (
    ChallengeCaseAssessment,
    DevelopmentEvaluationReport,
    DevelopmentExtractionAttempt,
    MetricFraction,
    ReproducibilityCheck,
)
from document_intelligence.extraction.matching import (
    align_normalized_values,
    match_strict_facts,
)
from document_intelligence.extraction.models import CandidateReviewStatus


_DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")


class DevelopmentEvaluationError(RuntimeError):
    """Raised when supplied development evaluation inputs violate the contract."""


def _attempt_inventory(
    attempts: Sequence[DevelopmentExtractionAttempt],
    label: str,
) -> dict[str, DevelopmentExtractionAttempt]:
    if len(attempts) != 5:
        raise DevelopmentEvaluationError(f"{label} must contain exactly five attempts")
    if any(not isinstance(item, DevelopmentExtractionAttempt) for item in attempts):
        raise DevelopmentEvaluationError(
            f"{label} must contain validated DevelopmentExtractionAttempt objects"
        )
    source_ids = [item.source_id for item in attempts]
    if len(source_ids) != len(set(source_ids)):
        raise DevelopmentEvaluationError(f"{label} contains a duplicate source attempt")
    if set(source_ids) != set(_DEVELOPMENT_SOURCE_IDS):
        raise DevelopmentEvaluationError(
            f"{label} must contain the frozen development source inventory"
        )
    return {item.source_id: item for item in attempts}


def _validate_gold(gold: DevelopmentGoldBundle) -> None:
    if not isinstance(gold, DevelopmentGoldBundle):
        raise DevelopmentEvaluationError("gold must be a validated DevelopmentGoldBundle")
    if gold.access_mode is not BaselineGoldAccessMode.DEVELOPMENT:
        raise DevelopmentEvaluationError("only development gold is permitted")
    if gold.development_public_source_ids != _DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentEvaluationError("gold source inventory is not the frozen development set")
    allowed = set(_DEVELOPMENT_SOURCE_IDS)
    if len(gold.facts) != 25 or any(
        fact.split != "development" or fact.source_id not in allowed
        for fact in gold.facts
    ):
        raise DevelopmentEvaluationError("gold contains non-development fact content")
    if len(gold.challenge_cases) != 3 or any(
        case.split != "development" or case.source_id not in allowed
        for case in gold.challenge_cases
    ):
        raise DevelopmentEvaluationError(
            "gold contains non-development challenge-case content"
        )


def _challenge_inventory(
    gold: DevelopmentGoldBundle,
    assessments: Sequence[ChallengeCaseAssessment],
) -> tuple[ChallengeCaseAssessment, ...]:
    if len(assessments) != 3:
        raise DevelopmentEvaluationError(
            "exactly three challenge-case assessments are required"
        )
    if any(not isinstance(item, ChallengeCaseAssessment) for item in assessments):
        raise DevelopmentEvaluationError(
            "challenge assessments must be validated ChallengeCaseAssessment objects"
        )
    case_ids = [item.case_id for item in assessments]
    if len(case_ids) != len(set(case_ids)):
        raise DevelopmentEvaluationError("challenge assessments contain duplicate case IDs")
    expected = {case.case_id: case for case in gold.challenge_cases}
    if set(case_ids) != set(expected):
        raise DevelopmentEvaluationError(
            "challenge assessment IDs must exactly match development cases"
        )
    for assessment in assessments:
        if assessment.expected_behavior != expected[assessment.case_id].expected_behavior:
            raise DevelopmentEvaluationError(
                "challenge expected_behavior disagrees with development gold"
            )
    return tuple(sorted(assessments, key=lambda item: item.case_id))


def _reproducibility_checks(
    primary: dict[str, DevelopmentExtractionAttempt],
    repeat: dict[str, DevelopmentExtractionAttempt],
) -> tuple[ReproducibilityCheck, ...]:
    checks: list[ReproducibilityCheck] = []
    for source_id in _DEVELOPMENT_SOURCE_IDS:
        first_hash = primary[source_id].canonical_output_sha256
        second_hash = repeat[source_id].canonical_output_sha256
        if first_hash is None or second_hash is None:
            status = "unavailable"
            byte_identical = None
        elif first_hash == second_hash:
            status = "passed"
            byte_identical = True
        else:
            status = "failed"
            byte_identical = False
        checks.append(
            ReproducibilityCheck(
                source_id=source_id,
                first_output_sha256=first_hash,
                second_output_sha256=second_hash,
                byte_identical=byte_identical,
                status=status,
            )
        )
    return tuple(checks)


def evaluate_development_candidates(
    *,
    gold: DevelopmentGoldBundle,
    primary_attempts: Sequence[DevelopmentExtractionAttempt],
    repeat_attempts: Sequence[DevelopmentExtractionAttempt],
    challenge_assessments: Sequence[ChallengeCaseAssessment],
) -> DevelopmentEvaluationReport:
    """Evaluate supplied development candidates without performing any I/O."""
    _validate_gold(gold)
    primary = _attempt_inventory(primary_attempts, "primary_attempts")
    repeat = _attempt_inventory(repeat_attempts, "repeat_attempts")
    if set(primary) != set(repeat):
        raise DevelopmentEvaluationError("primary and repeat source inventories differ")
    assessments = _challenge_inventory(gold, challenge_assessments)

    successful_results = tuple(
        primary[source_id].result
        for source_id in _DEVELOPMENT_SOURCE_IDS
        if primary[source_id].result is not None
    )
    try:
        strict = match_strict_facts(successful_results, gold.facts)
        alignments = align_normalized_values(successful_results, gold.facts)
    except (TypeError, ValueError) as error:
        raise DevelopmentEvaluationError(
            "candidate inputs violate the strict matching contract"
        ) from error

    candidate_counts = {
        source_id: (
            len(primary[source_id].result.candidate_facts)
            if primary[source_id].result is not None
            else 0
        )
        for source_id in _DEVELOPMENT_SOURCE_IDS
    }
    candidates = tuple(
        candidate
        for result in successful_results
        for candidate in result.candidate_facts
    )
    schema_valid_count = len(successful_results)
    failed_count = 5 - schema_valid_count
    true_positive = len(strict.strict_matches)
    false_positive = len(strict.unmatched_candidate_ids)
    false_negative = len(strict.unmatched_annotation_ids)
    reproducibility = _reproducibility_checks(primary, repeat)

    warnings: set[str] = set()
    if any(
        attempt.result is None
        for attempt in (*tuple(primary.values()), *tuple(repeat.values()))
    ):
        warnings.add("failed_source_attempt")
    if any(check.status == "failed" for check in reproducibility):
        warnings.add("non_identical_repeat_output")
    if strict.qualifier_over_specification_count:
        warnings.add("qualifier_over_specification")
    if strict.duplicate_candidate_count:
        warnings.add("semantic_duplicate_candidate")

    fact_f1 = (
        MetricFraction.from_counts(0, 0)
        if true_positive == 0
        else MetricFraction.from_counts(
            2 * true_positive,
            2 * true_positive + false_positive + false_negative,
        )
    )
    return DevelopmentEvaluationReport(
        source_ids=_DEVELOPMENT_SOURCE_IDS,
        attempted_source_count=5,
        schema_valid_source_count=schema_valid_count,
        failed_source_count=failed_count,
        total_candidate_count=len(candidates),
        candidate_counts_by_source=candidate_counts,
        review_required_candidate_count=sum(
            candidate.review_status is CandidateReviewStatus.REQUIRED
            for candidate in candidates
        ),
        duplicate_candidate_count=strict.duplicate_candidate_count,
        qualifier_over_specification_count=(
            strict.qualifier_over_specification_count
        ),
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        fact_precision=MetricFraction.from_counts(
            true_positive,
            true_positive + false_positive,
        ),
        fact_recall=MetricFraction.from_counts(
            true_positive,
            true_positive + false_negative,
        ),
        fact_f1=fact_f1,
        normalized_value_exact_match=MetricFraction.from_counts(
            sum(item.normalized_value_match for item in alignments),
            len(alignments),
        ),
        schema_valid_result_rate=MetricFraction.from_counts(schema_valid_count, 5),
        evidence_source_accuracy=MetricFraction.from_counts(
            sum(item.evidence_source_match for item in strict.strict_matches),
            true_positive,
        ),
        evidence_location_accuracy=MetricFraction.from_counts(
            sum(item.evidence_location_match for item in strict.strict_matches),
            true_positive,
        ),
        evidence_excerpt_exact_match=MetricFraction.from_counts(
            sum(
                item.evidence_excerpt_exact_match
                for item in strict.strict_matches
            ),
            true_positive,
        ),
        development_challenge_case_pass_rate=MetricFraction.from_counts(
            sum(item.outcome == "passed" for item in assessments),
            3,
        ),
        per_predicate_counts=strict.per_predicate_counts,
        strict_matches=strict.strict_matches,
        value_alignments=alignments,
        unmatched_candidate_ids=strict.unmatched_candidate_ids,
        unmatched_annotation_ids=strict.unmatched_annotation_ids,
        challenge_case_assessments=assessments,
        reproducibility_checks=reproducibility,
        all_outputs_byte_identical=all(
            item.status == "passed" for item in reproducibility
        ),
        warnings=tuple(sorted(warnings)),
    )


def canonical_development_evaluation_json(
    report: DevelopmentEvaluationReport,
) -> str:
    """Serialize a validated report to deterministic canonical JSON text."""
    if not isinstance(report, DevelopmentEvaluationReport):
        raise DevelopmentEvaluationError(
            "report must be a validated DevelopmentEvaluationReport"
        )
    return json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


__all__ = [
    "DevelopmentEvaluationError",
    "evaluate_development_candidates",
    "canonical_development_evaluation_json",
]
