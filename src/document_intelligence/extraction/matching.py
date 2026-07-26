"""Executable strict matching semantics for deterministic-baseline-v0.1."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from document_intelligence.extraction.annotations import GoldFactAnnotation
from document_intelligence.extraction.evaluation_models import (
    PredicateCounts,
    StrictFactMatch,
    ValueAlignment,
)
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    NormalizedMoney,
    ValueType,
)
from document_intelligence.extraction.predicates import validate_predicate_usage


_SINGLE_QUOTES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
    }
)
_DOUBLE_QUOTES = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
    }
)
_DASHES = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\ufe58": "-",
        "\ufe63": "-",
        "\uff0d": "-",
    }
)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class _StrictMatchingResult:
    strict_matches: tuple[StrictFactMatch, ...]
    unmatched_candidate_ids: tuple[str, ...]
    unmatched_annotation_ids: tuple[str, ...]
    qualifier_over_specifications: tuple[tuple[str, tuple[str, ...]], ...]
    qualifier_over_specification_count: int
    per_predicate_counts: tuple[PredicateCounts, ...]
    duplicate_candidate_count: int


def normalize_comparison_text(value: str) -> str:
    """Apply the frozen protocol-v0.1 comparison normalization sequence."""
    if not isinstance(value, str):
        raise TypeError("comparison text must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = normalized.translate(_SINGLE_QUOTES)
    normalized = normalized.translate(_DOUBLE_QUOTES)
    normalized = normalized.translate(_DASHES)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    if normalized.endswith((".", "!", "?")):
        normalized = normalized[:-1]
    return normalized.strip()


def _decimal_token(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric comparison value")
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("numeric comparison value is invalid") from error
    if not converted.is_finite():
        raise ValueError("numeric comparison value must be finite")
    if converted == 0:
        return "0"
    return format(converted.normalize(), "f")


def _typed_value_key(value_type: ValueType, value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if value_type in {
        ValueType.STRING,
        ValueType.STATUS,
        ValueType.PERSON,
        ValueType.ORGANISATION,
        ValueType.OTHER,
    }:
        if not isinstance(value, str):
            raise ValueError("text value_type requires a string value")
        return ("text", normalize_comparison_text(value))
    if value_type in {ValueType.NUMBER, ValueType.PERCENTAGE}:
        return ("number", _decimal_token(value))
    if value_type is ValueType.MONEY:
        if not isinstance(value, NormalizedMoney):
            raise ValueError("money value_type requires NormalizedMoney")
        return ("money", _decimal_token(value.amount), value.currency)
    if value_type is ValueType.DATE:
        if not isinstance(value, str):
            raise ValueError("date value_type requires a source-precision string")
        return ("date", normalize_comparison_text(value))
    if value_type is ValueType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("boolean value_type requires a bool")
        return ("boolean", value)
    if value_type is ValueType.LIST:
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError("list value_type requires an ordered string list")
        return (
            "list",
            tuple(normalize_comparison_text(item) for item in value),
        )
    raise ValueError(f"unsupported value_type: {value_type.value}")


def _qualifier_value_key(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, str):
        return ("text", normalize_comparison_text(value))
    if isinstance(value, (int, float, Decimal)):
        return ("number", _decimal_token(value))
    if isinstance(value, list):
        return ("list", tuple(_qualifier_value_key(item) for item in value))
    raise ValueError("unsupported qualifier value")


def _qualifier_mapping_key(qualifiers: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        (name, _qualifier_value_key(value))
        for name, value in sorted(qualifiers.items())
    )


def _qualifiers_match(
    candidate: CandidateFact,
    gold: GoldFactAnnotation,
) -> tuple[bool, tuple[str, ...]]:
    for name, gold_value in gold.qualifiers.items():
        if name not in candidate.qualifiers:
            return False, ()
        if _qualifier_value_key(candidate.qualifiers[name]) != _qualifier_value_key(
            gold_value
        ):
            return False, ()
    extras = tuple(sorted(set(candidate.qualifiers) - set(gold.qualifiers)))
    return True, extras


def _base_key(fact: CandidateFact | GoldFactAnnotation) -> tuple[Any, ...]:
    return (
        fact.source_id,
        normalize_comparison_text(fact.subject_text),
        fact.subject_type.value,
        fact.predicate,
        fact.value_type.value,
    )


def _strict_base_key(fact: CandidateFact | GoldFactAnnotation) -> tuple[Any, ...]:
    return (*_base_key(fact), _typed_value_key(fact.value_type, fact.normalized_value))


def _gold_strict_key(gold: GoldFactAnnotation) -> tuple[Any, ...]:
    return (*_strict_base_key(gold), _qualifier_mapping_key(gold.qualifiers))


def _candidate_duplicate_key(candidate: CandidateFact) -> tuple[Any, ...]:
    return (
        *_strict_base_key(candidate),
        _qualifier_mapping_key(candidate.qualifiers),
    )


def _stable_key_text(value: tuple[Any, ...]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _inventory(
    results: Sequence[CandidateExtractionResult],
) -> tuple[
    tuple[CandidateFact, ...],
    dict[str, tuple[CandidateFact, CandidateExtractionResult]],
]:
    candidates: list[CandidateFact] = []
    by_id: dict[str, tuple[CandidateFact, CandidateExtractionResult]] = {}
    for result in results:
        if not isinstance(result, CandidateExtractionResult):
            raise TypeError("results must contain CandidateExtractionResult objects")
        for candidate in result.candidate_facts:
            validate_predicate_usage(
                predicate=candidate.predicate,
                subject_type=candidate.subject_type,
                value_type=candidate.value_type,
                qualifiers=candidate.qualifiers,
            )
            if candidate.candidate_id in by_id:
                raise ValueError("candidate IDs must be unique across results")
            by_id[candidate.candidate_id] = (candidate, result)
            candidates.append(candidate)
    return tuple(sorted(candidates, key=lambda item: item.candidate_id)), by_id


def _referenced_evidence(
    candidate: CandidateFact,
    result: CandidateExtractionResult,
) -> tuple[CandidateEvidenceReference, ...]:
    evidence_by_id = {
        evidence.evidence_id: evidence for evidence in result.evidence_references
    }
    return tuple(evidence_by_id[evidence_id] for evidence_id in candidate.evidence_ids)


def _evidence_diagnostics(
    candidate: CandidateFact,
    result: CandidateExtractionResult,
    gold: GoldFactAnnotation,
) -> tuple[bool, bool, bool]:
    evidence = _referenced_evidence(candidate, result)
    source_match = any(item.source_id == gold.source_id for item in evidence)
    location_match = any(
        item.block_id == gold.evidence_block_id
        and item.location_type == gold.evidence_location_type
        and item.location_value == gold.evidence_location_value
        for item in evidence
    )
    excerpt_match = any(
        normalize_comparison_text(item.text_excerpt)
        == normalize_comparison_text(gold.evidence_excerpt)
        for item in evidence
    )
    return source_match, location_match, excerpt_match


def _has_matching_evidence_block(
    candidate: CandidateFact,
    result: CandidateExtractionResult,
    gold: GoldFactAnnotation,
) -> bool:
    return any(
        item.block_id == gold.evidence_block_id
        for item in _referenced_evidence(candidate, result)
    )


def _count_duplicates(candidates: Sequence[CandidateFact]) -> int:
    counts = Counter(_candidate_duplicate_key(candidate) for candidate in candidates)
    return sum(count - 1 for count in counts.values() if count > 1)


def match_strict_facts(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[GoldFactAnnotation],
) -> _StrictMatchingResult:
    """Strictly pair candidates and gold once within each source and semantic key."""
    candidates, candidate_index = _inventory(results)
    gold = tuple(sorted(gold_facts, key=lambda item: item.annotation_id))
    gold_ids = [item.annotation_id for item in gold]
    if len(gold_ids) != len(set(gold_ids)):
        raise ValueError("annotation IDs must be unique")

    groups: dict[tuple[Any, ...], list[GoldFactAnnotation]] = defaultdict(list)
    for annotation in gold:
        groups[_gold_strict_key(annotation)].append(annotation)

    matched_candidate_ids: set[str] = set()
    matched_annotation_ids: set[str] = set()
    matches: list[StrictFactMatch] = []
    for strict_key in sorted(groups, key=_stable_key_text):
        annotations = sorted(
            groups[strict_key],
            key=lambda item: item.annotation_id,
        )
        compatible: list[tuple[CandidateFact, tuple[str, ...]]] = []
        for candidate in candidates:
            if candidate.candidate_id in matched_candidate_ids:
                continue
            if _strict_base_key(candidate) != _strict_base_key(annotations[0]):
                continue
            qualifier_match, extras = _qualifiers_match(candidate, annotations[0])
            if qualifier_match:
                compatible.append((candidate, extras))
        compatible.sort(key=lambda item: item[0].candidate_id)
        for (candidate, extras), annotation in zip(compatible, annotations):
            result = candidate_index[candidate.candidate_id][1]
            source_match, location_match, excerpt_match = _evidence_diagnostics(
                candidate,
                result,
                annotation,
            )
            matches.append(
                StrictFactMatch(
                    source_id=candidate.source_id,
                    candidate_id=candidate.candidate_id,
                    annotation_id=annotation.annotation_id,
                    predicate=candidate.predicate,
                    qualifier_over_specification=extras,
                    evidence_source_match=source_match,
                    evidence_location_match=location_match,
                    evidence_excerpt_exact_match=excerpt_match,
                )
            )
            matched_candidate_ids.add(candidate.candidate_id)
            matched_annotation_ids.add(annotation.annotation_id)

    ordered_matches = tuple(
        sorted(
            matches,
            key=lambda item: (item.source_id, item.candidate_id, item.annotation_id),
        )
    )
    unmatched_candidates = tuple(
        sorted(
            candidate.candidate_id
            for candidate in candidates
            if candidate.candidate_id not in matched_candidate_ids
        )
    )
    unmatched_annotations = tuple(
        sorted(
            annotation.annotation_id
            for annotation in gold
            if annotation.annotation_id not in matched_annotation_ids
        )
    )
    over_specifications = tuple(
        (match.candidate_id, match.qualifier_over_specification)
        for match in ordered_matches
        if match.qualifier_over_specification
    )

    candidate_by_id = {item.candidate_id: item for item in candidates}
    gold_by_id = {item.annotation_id: item for item in gold}
    tp = Counter(match.predicate for match in ordered_matches)
    fp = Counter(candidate_by_id[item].predicate for item in unmatched_candidates)
    fn = Counter(gold_by_id[item].predicate for item in unmatched_annotations)
    predicates = sorted(set(tp) | set(fp) | set(fn))
    per_predicate = tuple(
        PredicateCounts(
            predicate=predicate,
            true_positive=tp[predicate],
            false_positive=fp[predicate],
            false_negative=fn[predicate],
        )
        for predicate in predicates
    )
    return _StrictMatchingResult(
        strict_matches=ordered_matches,
        unmatched_candidate_ids=unmatched_candidates,
        unmatched_annotation_ids=unmatched_annotations,
        qualifier_over_specifications=over_specifications,
        qualifier_over_specification_count=sum(
            len(names) for _, names in over_specifications
        ),
        per_predicate_counts=per_predicate,
        duplicate_candidate_count=_count_duplicates(candidates),
    )


def align_normalized_values(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[GoldFactAnnotation],
) -> tuple[ValueAlignment, ...]:
    """Greedily align compatible facts without using normalized value in the key."""
    candidates, candidate_index = _inventory(results)
    gold = tuple(sorted(gold_facts, key=lambda item: item.annotation_id))
    gold_ids = [item.annotation_id for item in gold]
    if len(gold_ids) != len(set(gold_ids)):
        raise ValueError("annotation IDs must be unique")

    ranked_pairs: list[
        tuple[bool, bool, str, str, CandidateFact, GoldFactAnnotation]
    ] = []
    for candidate in candidates:
        result = candidate_index[candidate.candidate_id][1]
        for annotation in gold:
            if _base_key(candidate) != _base_key(annotation):
                continue
            qualifier_match, _ = _qualifiers_match(candidate, annotation)
            if not qualifier_match:
                continue
            ranked_pairs.append(
                (
                    _has_matching_evidence_block(candidate, result, annotation),
                    normalize_comparison_text(candidate.raw_value)
                    == normalize_comparison_text(annotation.raw_value),
                    candidate.candidate_id,
                    annotation.annotation_id,
                    candidate,
                    annotation,
                )
            )
    ranked_pairs.sort(
        key=lambda item: (
            not item[0],
            not item[1],
            item[2],
            item[3],
        )
    )

    used_candidates: set[str] = set()
    used_annotations: set[str] = set()
    alignments: list[ValueAlignment] = []
    for _, _, candidate_id, annotation_id, candidate, annotation in ranked_pairs:
        if candidate_id in used_candidates or annotation_id in used_annotations:
            continue
        used_candidates.add(candidate_id)
        used_annotations.add(annotation_id)
        alignments.append(
            ValueAlignment(
                source_id=candidate.source_id,
                candidate_id=candidate_id,
                annotation_id=annotation_id,
                predicate=candidate.predicate,
                normalized_value_match=(
                    _typed_value_key(candidate.value_type, candidate.normalized_value)
                    == _typed_value_key(annotation.value_type, annotation.normalized_value)
                ),
            )
        )
    return tuple(
        sorted(
            alignments,
            key=lambda item: (item.source_id, item.candidate_id, item.annotation_id),
        )
    )


__all__ = [
    "normalize_comparison_text",
    "match_strict_facts",
    "align_normalized_values",
]
