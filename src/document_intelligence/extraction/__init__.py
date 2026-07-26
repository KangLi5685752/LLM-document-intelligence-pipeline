"""Versioned candidate-extraction and public-annotation contracts."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from document_intelligence.extraction.baseline_gold import (
        BaselineGoldAccessError,
        BaselineGoldAccessMode,
        BaselineGoldIntegrityError,
        DevelopmentGoldBundle,
        DevelopmentGoldSummary,
        HeldOutAccessDenied,
        load_baseline_gold,
        summarize_development_gold,
    )
    from document_intelligence.extraction.deterministic import (
        DETERMINISTIC_BASELINE_VERSION,
        DeterministicExtractionError,
        canonical_candidate_result_json,
        extract_deterministic_candidates,
    )
    from document_intelligence.extraction.deterministic_rules import (
        DeterministicRuleDefinition,
        get_deterministic_rule_inventory,
    )
    from document_intelligence.extraction.development_evaluation import (
        DevelopmentEvaluationError,
        canonical_development_evaluation_json,
        evaluate_development_candidates,
    )
    from document_intelligence.extraction.development_run import (
        DevelopmentRunError,
        FinalizedDevelopmentRun,
        PreparedDevelopmentRun,
        canonical_artifact_json,
        finalize_development_baseline_run,
        prepare_development_baseline_run,
    )
    from document_intelligence.extraction.development_run_models import (
        DevelopmentInputRecord,
        DevelopmentObservationLock,
        DevelopmentRunAttemptRecord,
        DevelopmentRunManifest,
        OwnerChallengeAssessmentEntry,
        OwnerChallengeAssessmentTemplate,
        OwnerChallengeReviewPacket,
        UnmatchedReviewInventory,
    )
    from document_intelligence.extraction.baseline_freeze import (
        AcceptanceGateOutcome,
        BaselineFreezeError,
        BaselineFreezeManifest,
        FinalErrorAnalysis,
    )
    from document_intelligence.extraction.evaluation_models import (
        ChallengeCaseAssessment,
        DevelopmentEvaluationReport,
        DevelopmentExtractionAttempt,
        MetricFraction,
        PredicateCounts,
        ReproducibilityCheck,
        StrictFactMatch,
        ValueAlignment,
    )
    from document_intelligence.extraction.matching import (
        align_normalized_values,
        match_strict_facts,
        normalize_comparison_text,
    )
    from document_intelligence.extraction.annotations import (
        AnnotationReviewStatus,
        GoldChallengeCase,
        GoldFactAnnotation,
        PublicGoldValidationReport,
        load_gold_challenge_cases,
        load_gold_fact_annotations,
        validate_public_gold_dataset,
    )
    from document_intelligence.extraction.models import (
        CandidateEntity,
        CandidateEvidenceReference,
        CandidateExtractionResult,
        CandidateFact,
        CandidateReviewStatus,
        EvidenceStatus,
        ExtractionMethod,
        NormalizedMoney,
        SubjectType,
        ValueType,
    )
    from document_intelligence.extraction.predicates import (
        PredicateDefinition,
        normalize_predicate,
    )


__all__ = [
    "SubjectType",
    "ValueType",
    "EvidenceStatus",
    "CandidateReviewStatus",
    "ExtractionMethod",
    "NormalizedMoney",
    "CandidateEntity",
    "CandidateEvidenceReference",
    "CandidateFact",
    "CandidateExtractionResult",
    "PredicateDefinition",
    "normalize_predicate",
    "AnnotationReviewStatus",
    "GoldFactAnnotation",
    "GoldChallengeCase",
    "PublicGoldValidationReport",
    "load_gold_fact_annotations",
    "load_gold_challenge_cases",
    "validate_public_gold_dataset",
    "BaselineGoldAccessMode",
    "BaselineGoldAccessError",
    "BaselineGoldIntegrityError",
    "HeldOutAccessDenied",
    "DevelopmentGoldBundle",
    "DevelopmentGoldSummary",
    "load_baseline_gold",
    "summarize_development_gold",
    "DETERMINISTIC_BASELINE_VERSION",
    "DeterministicExtractionError",
    "DeterministicRuleDefinition",
    "extract_deterministic_candidates",
    "canonical_candidate_result_json",
    "get_deterministic_rule_inventory",
    "MetricFraction",
    "DevelopmentExtractionAttempt",
    "ReproducibilityCheck",
    "StrictFactMatch",
    "ValueAlignment",
    "PredicateCounts",
    "ChallengeCaseAssessment",
    "DevelopmentEvaluationReport",
    "DevelopmentEvaluationError",
    "normalize_comparison_text",
    "match_strict_facts",
    "align_normalized_values",
    "evaluate_development_candidates",
    "canonical_development_evaluation_json",
    "DevelopmentInputRecord",
    "DevelopmentRunAttemptRecord",
    "DevelopmentRunManifest",
    "DevelopmentObservationLock",
    "OwnerChallengeReviewPacket",
    "OwnerChallengeAssessmentEntry",
    "OwnerChallengeAssessmentTemplate",
    "UnmatchedReviewInventory",
    "AcceptanceGateOutcome",
    "FinalErrorAnalysis",
    "BaselineFreezeManifest",
    "BaselineFreezeError",
    "DevelopmentRunError",
    "PreparedDevelopmentRun",
    "FinalizedDevelopmentRun",
    "canonical_artifact_json",
    "prepare_development_baseline_run",
    "finalize_development_baseline_run",
]


_EXPORT_MODULES = {
    "SubjectType": "document_intelligence.extraction.models",
    "ValueType": "document_intelligence.extraction.models",
    "EvidenceStatus": "document_intelligence.extraction.models",
    "CandidateReviewStatus": "document_intelligence.extraction.models",
    "ExtractionMethod": "document_intelligence.extraction.models",
    "NormalizedMoney": "document_intelligence.extraction.models",
    "CandidateEntity": "document_intelligence.extraction.models",
    "CandidateEvidenceReference": "document_intelligence.extraction.models",
    "CandidateFact": "document_intelligence.extraction.models",
    "CandidateExtractionResult": "document_intelligence.extraction.models",
    "PredicateDefinition": "document_intelligence.extraction.predicates",
    "normalize_predicate": "document_intelligence.extraction.predicates",
    "AnnotationReviewStatus": "document_intelligence.extraction.annotations",
    "GoldFactAnnotation": "document_intelligence.extraction.annotations",
    "GoldChallengeCase": "document_intelligence.extraction.annotations",
    "PublicGoldValidationReport": "document_intelligence.extraction.annotations",
    "load_gold_fact_annotations": "document_intelligence.extraction.annotations",
    "load_gold_challenge_cases": "document_intelligence.extraction.annotations",
    "validate_public_gold_dataset": "document_intelligence.extraction.annotations",
    "BaselineGoldAccessMode": "document_intelligence.extraction.baseline_gold",
    "BaselineGoldAccessError": "document_intelligence.extraction.baseline_gold",
    "BaselineGoldIntegrityError": "document_intelligence.extraction.baseline_gold",
    "HeldOutAccessDenied": "document_intelligence.extraction.baseline_gold",
    "DevelopmentGoldBundle": "document_intelligence.extraction.baseline_gold",
    "DevelopmentGoldSummary": "document_intelligence.extraction.baseline_gold",
    "load_baseline_gold": "document_intelligence.extraction.baseline_gold",
    "summarize_development_gold": "document_intelligence.extraction.baseline_gold",
    "DETERMINISTIC_BASELINE_VERSION": "document_intelligence.extraction.deterministic",
    "DeterministicExtractionError": "document_intelligence.extraction.deterministic",
    "DeterministicRuleDefinition": "document_intelligence.extraction.deterministic_rules",
    "extract_deterministic_candidates": "document_intelligence.extraction.deterministic",
    "canonical_candidate_result_json": "document_intelligence.extraction.deterministic",
    "get_deterministic_rule_inventory": "document_intelligence.extraction.deterministic_rules",
    "MetricFraction": "document_intelligence.extraction.evaluation_models",
    "DevelopmentExtractionAttempt": "document_intelligence.extraction.evaluation_models",
    "ReproducibilityCheck": "document_intelligence.extraction.evaluation_models",
    "StrictFactMatch": "document_intelligence.extraction.evaluation_models",
    "ValueAlignment": "document_intelligence.extraction.evaluation_models",
    "PredicateCounts": "document_intelligence.extraction.evaluation_models",
    "ChallengeCaseAssessment": "document_intelligence.extraction.evaluation_models",
    "DevelopmentEvaluationReport": "document_intelligence.extraction.evaluation_models",
    "DevelopmentEvaluationError": "document_intelligence.extraction.development_evaluation",
    "normalize_comparison_text": "document_intelligence.extraction.matching",
    "match_strict_facts": "document_intelligence.extraction.matching",
    "align_normalized_values": "document_intelligence.extraction.matching",
    "evaluate_development_candidates": "document_intelligence.extraction.development_evaluation",
    "canonical_development_evaluation_json": "document_intelligence.extraction.development_evaluation",
    "DevelopmentInputRecord": "document_intelligence.extraction.development_run_models",
    "DevelopmentRunAttemptRecord": "document_intelligence.extraction.development_run_models",
    "DevelopmentRunManifest": "document_intelligence.extraction.development_run_models",
    "DevelopmentObservationLock": "document_intelligence.extraction.development_run_models",
    "OwnerChallengeReviewPacket": "document_intelligence.extraction.development_run_models",
    "OwnerChallengeAssessmentEntry": "document_intelligence.extraction.development_run_models",
    "OwnerChallengeAssessmentTemplate": "document_intelligence.extraction.development_run_models",
    "UnmatchedReviewInventory": "document_intelligence.extraction.development_run_models",
    "AcceptanceGateOutcome": "document_intelligence.extraction.baseline_freeze",
    "FinalErrorAnalysis": "document_intelligence.extraction.baseline_freeze",
    "BaselineFreezeManifest": "document_intelligence.extraction.baseline_freeze",
    "BaselineFreezeError": "document_intelligence.extraction.baseline_freeze",
    "DevelopmentRunError": "document_intelligence.extraction.development_run",
    "PreparedDevelopmentRun": "document_intelligence.extraction.development_run",
    "FinalizedDevelopmentRun": "document_intelligence.extraction.development_run",
    "canonical_artifact_json": "document_intelligence.extraction.development_run",
    "prepare_development_baseline_run": "document_intelligence.extraction.development_run",
    "finalize_development_baseline_run": "document_intelligence.extraction.development_run",
}


def __getattr__(name: str) -> Any:
    """Load public extraction attributes only when requested."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
