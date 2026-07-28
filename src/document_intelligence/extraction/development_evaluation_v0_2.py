"""Pure development-only evaluation for deterministic-baseline-v0.2."""

from __future__ import annotations

import json
from collections import Counter
from typing import Sequence

from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
)
from document_intelligence.extraction.evaluation_models_v0_2 import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    ChallengeCaseAssessment,
    DevelopmentEvaluationReport,
    DevelopmentExtractionAttempt,
    MetricFraction,
    PredicateCounts,
    PreliminaryDevelopmentEvaluationReport,
    ReproducibilityCheck,
    StrictFactMatch,
    ValueAlignment,
)
from document_intelligence.extraction.matching import (
    align_normalized_values,
    match_strict_facts,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateReviewStatus,
)


class DevelopmentEvaluationError(RuntimeError):
    """Raised when explicit v0.2 evaluation inputs violate the contract."""


def _attempt_inventory(
    attempts: Sequence[DevelopmentExtractionAttempt], label: str
) -> dict[str, DevelopmentExtractionAttempt]:
    if len(attempts) != len(DEVELOPMENT_SOURCE_IDS):
        raise DevelopmentEvaluationError(f"{label} must contain exactly five attempts")
    if any(not isinstance(item, DevelopmentExtractionAttempt) for item in attempts):
        raise DevelopmentEvaluationError(
            f"{label} must contain validated DevelopmentExtractionAttempt objects"
        )
    source_ids = tuple(item.source_id for item in attempts)
    if len(source_ids) != len(set(source_ids)):
        raise DevelopmentEvaluationError(f"{label} contains a duplicate source attempt")
    if set(source_ids) != set(DEVELOPMENT_SOURCE_IDS):
        raise DevelopmentEvaluationError(
            f"{label} must contain the frozen development source inventory"
        )
    return {item.source_id: item for item in attempts}


def _validate_gold(gold: DevelopmentGoldBundle) -> None:
    if not isinstance(gold, DevelopmentGoldBundle):
        raise DevelopmentEvaluationError("gold must be a DevelopmentGoldBundle")
    if gold.access_mode is not BaselineGoldAccessMode.DEVELOPMENT:
        raise DevelopmentEvaluationError("only development gold is permitted")
    if gold.development_public_source_ids != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentEvaluationError("gold source inventory is not frozen")
    allowed = set(DEVELOPMENT_SOURCE_IDS)
    if len(gold.facts) != 25 or any(
        item.split != "development" or item.source_id not in allowed
        for item in gold.facts
    ):
        raise DevelopmentEvaluationError("gold contains non-development fact content")
    if len(gold.challenge_cases) != 3 or any(
        item.split != "development" or item.source_id not in allowed
        for item in gold.challenge_cases
    ):
        raise DevelopmentEvaluationError(
            "gold contains non-development challenge-case content"
        )


def _reproducibility_checks(
    primary: dict[str, DevelopmentExtractionAttempt],
    repeat: dict[str, DevelopmentExtractionAttempt],
) -> tuple[ReproducibilityCheck, ...]:
    checks: list[ReproducibilityCheck] = []
    for source_id in DEVELOPMENT_SOURCE_IDS:
        first = primary[source_id].canonical_output_sha256
        second = repeat[source_id].canonical_output_sha256
        if first is None or second is None:
            status = "unavailable"
            identical = None
        elif first == second:
            status = "passed"
            identical = True
        else:
            status = "failed"
            identical = False
        checks.append(
            ReproducibilityCheck(
                source_id=source_id,
                primary_output_sha256=first,
                repeat_output_sha256=second,
                byte_identical=identical,
                status=status,
            )
        )
    return tuple(checks)


def _metric_f1(tp: int, fp: int, fn: int) -> MetricFraction:
    if tp == 0:
        return MetricFraction.from_counts(0, 0)
    return MetricFraction.from_counts(2 * tp, 2 * tp + fp + fn)


def _base_report_values(
    *,
    gold: DevelopmentGoldBundle,
    primary_attempts: Sequence[DevelopmentExtractionAttempt],
    repeat_attempts: Sequence[DevelopmentExtractionAttempt],
) -> dict[str, object]:
    _validate_gold(gold)
    primary = _attempt_inventory(primary_attempts, "primary_attempts")
    repeat = _attempt_inventory(repeat_attempts, "repeat_attempts")
    successful_results = tuple(
        primary[source_id].result
        for source_id in DEVELOPMENT_SOURCE_IDS
        if primary[source_id].result is not None
    )
    try:
        strict = match_strict_facts(successful_results, gold.facts)
        raw_alignments = align_normalized_values(successful_results, gold.facts)
    except (TypeError, ValueError) as error:
        raise DevelopmentEvaluationError(
            "candidate inputs violate matching protocol 0.1"
        ) from error

    strict_matches = tuple(
        StrictFactMatch.model_validate(item.model_dump())
        for item in strict.strict_matches
    )
    alignments = tuple(
        ValueAlignment.model_validate(item.model_dump()) for item in raw_alignments
    )
    predicate_counts = tuple(
        PredicateCounts.model_validate(item.model_dump())
        for item in strict.per_predicate_counts
    )
    candidate_counts_by_source = {
        source_id: (
            len(primary[source_id].result.candidate_facts)
            if primary[source_id].result is not None
            else 0
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    }
    candidates = tuple(
        candidate
        for result in successful_results
        for candidate in result.candidate_facts
    )
    candidate_counts_by_predicate = dict(
        sorted(Counter(item.predicate for item in candidates).items())
    )
    schema_valid_count = len(successful_results)
    failed_count = len(DEVELOPMENT_SOURCE_IDS) - schema_valid_count
    true_positive = len(strict_matches)
    false_positive = len(strict.unmatched_candidate_ids)
    false_negative = len(strict.unmatched_annotation_ids)
    reproducibility = _reproducibility_checks(primary, repeat)

    warnings: set[str] = set()
    if any(
        attempt.result is None
        for attempt in (*tuple(primary.values()), *tuple(repeat.values()))
    ):
        warnings.add("failed_source_attempt")
    if any(item.status == "failed" for item in reproducibility):
        warnings.add("non_identical_repeat_output")
    if strict.qualifier_over_specification_count:
        warnings.add("qualifier_over_specification")
    if strict.duplicate_candidate_count:
        warnings.add("semantic_duplicate_candidate")

    return {
        "source_ids": DEVELOPMENT_SOURCE_IDS,
        "attempted_source_count": len(DEVELOPMENT_SOURCE_IDS),
        "schema_valid_source_count": schema_valid_count,
        "failed_source_count": failed_count,
        "total_candidate_count": len(candidates),
        "candidate_counts_by_source": candidate_counts_by_source,
        "candidate_counts_by_predicate": candidate_counts_by_predicate,
        "review_required_candidate_count": sum(
            item.review_status is CandidateReviewStatus.REQUIRED for item in candidates
        ),
        "duplicate_candidate_count": strict.duplicate_candidate_count,
        "qualifier_over_specification_count": (
            strict.qualifier_over_specification_count
        ),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "fact_precision": MetricFraction.from_counts(
            true_positive, true_positive + false_positive
        ),
        "fact_recall": MetricFraction.from_counts(
            true_positive, true_positive + false_negative
        ),
        "fact_f1": _metric_f1(true_positive, false_positive, false_negative),
        "normalized_value_exact_match": MetricFraction.from_counts(
            sum(item.normalized_value_match for item in alignments), len(alignments)
        ),
        "schema_valid_result_rate": MetricFraction.from_counts(
            schema_valid_count, len(DEVELOPMENT_SOURCE_IDS)
        ),
        "evidence_source_accuracy": MetricFraction.from_counts(
            sum(item.evidence_source_match for item in strict_matches),
            len(strict_matches),
        ),
        "evidence_location_accuracy": MetricFraction.from_counts(
            sum(item.evidence_location_match for item in strict_matches),
            len(strict_matches),
        ),
        "evidence_excerpt_exact_match": MetricFraction.from_counts(
            sum(item.evidence_excerpt_exact_match for item in strict_matches),
            len(strict_matches),
        ),
        "per_predicate_counts": predicate_counts,
        "strict_matches": strict_matches,
        "value_alignments": alignments,
        "unmatched_candidate_ids": strict.unmatched_candidate_ids,
        "unmatched_annotation_ids": strict.unmatched_annotation_ids,
        "reproducibility_checks": reproducibility,
        "all_outputs_byte_identical": all(
            item.status == "passed" for item in reproducibility
        ),
        "warnings": tuple(sorted(warnings)),
    }


def evaluate_preliminary_development_candidates(
    *,
    gold: DevelopmentGoldBundle,
    primary_attempts: Sequence[DevelopmentExtractionAttempt],
    repeat_attempts: Sequence[DevelopmentExtractionAttempt],
) -> PreliminaryDevelopmentEvaluationReport:
    """Evaluate an explicit run without I/O, even when one or more sources failed."""
    return PreliminaryDevelopmentEvaluationReport(
        **_base_report_values(
            gold=gold,
            primary_attempts=primary_attempts,
            repeat_attempts=repeat_attempts,
        )
    )


def _challenge_inventory(
    gold: DevelopmentGoldBundle,
    assessments: Sequence[ChallengeCaseAssessment],
) -> tuple[ChallengeCaseAssessment, ...]:
    if len(assessments) != 3:
        raise DevelopmentEvaluationError(
            "exactly three explicit owner assessments are required"
        )
    if any(not isinstance(item, ChallengeCaseAssessment) for item in assessments):
        raise DevelopmentEvaluationError(
            "owner assessments must be validated ChallengeCaseAssessment objects"
        )
    case_ids = tuple(item.case_id for item in assessments)
    if len(case_ids) != len(set(case_ids)):
        raise DevelopmentEvaluationError("owner assessments contain duplicate case IDs")
    by_case = {item.case_id: item for item in gold.challenge_cases}
    if set(case_ids) != set(DEVELOPMENT_CASE_IDS) or set(case_ids) != set(by_case):
        raise DevelopmentEvaluationError(
            "owner assessment IDs must exactly match development challenge cases"
        )
    for item in assessments:
        if item.expected_behavior != by_case[item.case_id].expected_behavior:
            raise DevelopmentEvaluationError(
                "owner assessment expected_behavior disagrees with gold"
            )
    return tuple(sorted(assessments, key=lambda item: item.case_id))


def _validate_challenge_references(
    assessments: Sequence[ChallengeCaseAssessment],
    results: Sequence[CandidateExtractionResult],
) -> None:
    candidate_ids = {
        item.candidate_id for result in results for item in result.candidate_facts
    }
    warning_codes = {
        warning.split(":", 1)[0]
        for result in results
        for warning in (
            *result.warnings,
            *(value for item in result.candidate_facts for value in item.warnings),
        )
    }
    for item in assessments:
        if not set(item.related_candidate_ids).issubset(candidate_ids):
            raise DevelopmentEvaluationError(
                "owner assessment references an unknown candidate ID"
            )
        if not set(item.related_warning_codes).issubset(warning_codes):
            raise DevelopmentEvaluationError(
                "owner assessment references an unknown warning code"
            )


def evaluate_development_candidates(
    *,
    gold: DevelopmentGoldBundle,
    primary_attempts: Sequence[DevelopmentExtractionAttempt],
    repeat_attempts: Sequence[DevelopmentExtractionAttempt],
    challenge_assessments: Sequence[ChallengeCaseAssessment],
) -> DevelopmentEvaluationReport:
    """Build the complete report only for five reproducible successful sources."""
    preliminary = evaluate_preliminary_development_candidates(
        gold=gold,
        primary_attempts=primary_attempts,
        repeat_attempts=repeat_attempts,
    )
    if preliminary.failed_source_count or preliminary.schema_valid_source_count != 5:
        raise DevelopmentEvaluationError(
            "complete evaluation requires five successful primary attempts"
        )
    if not preliminary.all_outputs_byte_identical:
        raise DevelopmentEvaluationError(
            "complete evaluation requires byte-identical primary and repeat outputs"
        )
    assessments = _challenge_inventory(gold, challenge_assessments)
    results = tuple(
        item.result for item in primary_attempts if item.result is not None
    )
    _validate_challenge_references(assessments, results)
    payload = preliminary.model_dump()
    payload.update(
        {
            "report_status": "complete_owner_reviewed",
            "metrics_status": "finalized",
            "challenge_case_assessments": assessments,
            "development_challenge_case_pass_rate": MetricFraction.from_counts(
                sum(item.outcome == "passed" for item in assessments), 3
            ),
        }
    )
    return DevelopmentEvaluationReport.model_validate(payload)


evaluate_complete_development_candidates = evaluate_development_candidates


def canonical_development_evaluation_json(
    report: PreliminaryDevelopmentEvaluationReport,
) -> str:
    """Serialize a validated preliminary or complete report canonically."""
    if not isinstance(report, PreliminaryDevelopmentEvaluationReport):
        raise DevelopmentEvaluationError(
            "report must be a validated v0.2 development report"
        )
    return json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


canonical_preliminary_evaluation_json = canonical_development_evaluation_json


__all__ = [
    "DevelopmentEvaluationError",
    "evaluate_preliminary_development_candidates",
    "evaluate_development_candidates",
    "evaluate_complete_development_candidates",
    "canonical_development_evaluation_json",
    "canonical_preliminary_evaluation_json",
]
