"""Versioned candidate-extraction and public-annotation contracts."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
}


def __getattr__(name: str) -> Any:
    """Load public extraction attributes only when requested."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
