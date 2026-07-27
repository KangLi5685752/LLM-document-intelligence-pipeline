"""Pure deterministic-baseline-v0.2 candidate extraction."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_rules_v0_2 import (
    DeterministicRuleDefinitionV02,
    get_v0_2_rule_inventory,
)
from document_intelligence.extraction.models import (
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
    PREDICATE_REGISTRY,
    normalize_predicate,
    validate_predicate_usage,
)
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    ParsedDocument,
)


DETERMINISTIC_BASELINE_VERSION = "deterministic-baseline-v0.2"

_CONTRACT_WARNING = "abstained_incompatible_predicate_contract"
_GENERIC_ACTOR_WARNING = "abstained_ineligible_actor_noun_phrase"
_SUBJECT_SPAN_WARNING = "abstained_subject_span_out_of_bounds"
_AMBIGUOUS_METRIC_WARNING = "ambiguous_metric_value_relationship"
_AMBIGUOUS_METRIC_BOUNDS_WARNING = (
    "abstained_ambiguous_metric_bounds_exceeded"
)

_COMMITMENT_WARNINGS = {
    "ambiguous_heading": "abstained_commitment_ambiguous_heading_context",
    "clause": "abstained_commitment_clause_like_subject",
    "copular": "abstained_commitment_copular_or_passive",
    "ineligible": "abstained_commitment_ineligible_subject",
    "too_long": "abstained_commitment_subject_too_long",
}

_RULES = {item.rule_id: item for item in get_v0_2_rule_inventory()}
_COMMITMENT_EXPLICIT_RULE = _RULES["V02-RULE-COM-EXPLICIT-001"]
_COMMITMENT_WEAK_RULE = _RULES["V02-RULE-COM-WEAK-002"]
_METRIC_RULE = _RULES["V02-RULE-METRIC-001"]
_REQUIREMENT_RULE = _RULES["V02-RULE-REQ-001"]
_ACTION_STATUS_RULE = _RULES["V02-RULE-ACTION-001"]

_CANDIDATE_BLOCK_TYPES = {
    BlockType.PAGE_TEXT,
    BlockType.SLIDE_TITLE,
    BlockType.SHAPE_TEXT,
    BlockType.TABLE,
    BlockType.EMAIL_BODY,
    BlockType.QUOTED_HISTORY,
}

_EXPLICIT_TRIGGERS = ("has committed to", "commits to", "commit to")
_WEAK_TRIGGERS = (
    "intends to",
    "intend to",
    "plans to",
    "plan to",
    "will not",
    "will",
)
_COMMITMENT_TRIGGER_RE = re.compile(
    r"(?P<trigger>has\s+committed\s+to|commits\s+to|commit\s+to|"
    r"intends\s+to|intend\s+to|plans\s+to|plan\s+to|will\s+not|will)\b",
    re.IGNORECASE,
)
_EXCLUDED_WEAK_PREFIXES = (
    "intend to be",
    "intends to be",
    "plan to be",
    "plans to be",
    "will be",
    "will not be",
)
_CLAUSE_BOUNDARIES = (":", ";", "?", "!", "\n")
_SUBORDINATE_MARKERS = (
    "although",
    "because",
    "if",
    "that",
    "when",
    "where",
    "which",
    "while",
    "who",
)
_COORDINATED_FINITE_RE = re.compile(
    r"\b(?:and|or)\s+[A-Za-z][A-Za-z'-]*\s+"
    r"(?:is|are|was|were|will|must|shall|has|have|intends?|plans?|commits?)\b",
    re.IGNORECASE,
)
_DISALLOWED_GENERIC_HEADS = {
    "amount",
    "average",
    "baseline",
    "figure",
    "level",
    "measure",
    "metric",
    "number",
    "percentage",
    "population",
    "proportion",
    "rate",
    "ratio",
    "score",
    "share",
    "target",
    "total",
    "value",
}
_IMPERSONAL_SUBJECTS = {"it", "that", "there", "these", "this", "those"}
_ALLOWED_ACTOR_TYPES = {
    SubjectType.INITIATIVE,
    SubjectType.ORGANISATION,
    SubjectType.OTHER,
    SubjectType.POLICY,
    SubjectType.PROGRAMME,
}

_REQUIREMENT_TRIGGER_RE = re.compile(
    r"(?P<trigger>are\s+required\s+to|is\s+required\s+to|must\s+not|"
    r"shall\s+not|required\s+to|must|shall)\b",
    re.IGNORECASE,
)
_REQUIREMENT_WARNINGS = {
    "action": "abstained_requirement_ineligible_action",
    "subject": "abstained_requirement_ineligible_subject",
}

_STATUS_VALUES = (
    "not started",
    "in progress",
    "on track",
    "completed",
    "delayed",
    "delivered",
    "met",
)
_STATUS_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?:(?:is|are|was|were|remains|has\s+been|"
    r"have\s+been)\s+)?(?P<value>not\s+started|in\s+progress|on\s+track|"
    r"completed|delayed|delivered|met)\b",
    re.IGNORECASE,
)
_ACTION_CUES = {
    "action",
    "activity",
    "deliverable",
    "delivery",
    "implementation",
    "milestone",
    "phase",
    "progress",
    "recommendation",
    "rollout",
    "step",
    "task",
    "work",
    "workstream",
}
_ACTION_ALLOWED_TYPES = {
    SubjectType.INITIATIVE,
    SubjectType.POLICY,
    SubjectType.PROGRAMME,
}
_ACTION_WARNING = "abstained_action_status_ineligible_subject"

_PERCENT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent(?:age)?\b)",
    re.IGNORECASE,
)
_METRIC_LINK_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?:was|were|is|are|reached|stood\s+at|measured|"
    r"may\s+be)\s*$",
    re.IGNORECASE,
)
_POPULATION_CUES = (
    "participants",
    "people",
    "population",
    "respondents",
    "residents",
    "users",
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
_LEADING_MARKER_RE = re.compile(
    r"^\s*(?:(?:[-–—•])|(?:(?:[A-Za-z]|\d+)[.)]))\s+"
)
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?]+(?=\s|$)")
_SINGLE_QUOTES = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'"}
)
_DOUBLE_QUOTES = str.maketrans(
    {"\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"'}
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


class DeterministicExtractionV02Error(RuntimeError):
    """Raised when the v0.2 extractor cannot produce a valid result."""


class _PredicateContractIncompatibility(ValueError):
    """Identify only a frozen predicate-usage incompatibility."""


@dataclass(frozen=True, slots=True)
class _Statement:
    block: DocumentBlock
    text: str
    start: int
    end: int
    heading_context: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CandidateDraft:
    rule: DeterministicRuleDefinitionV02
    block: DocumentBlock
    statement_start: int
    statement_end: int
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: Any
    value_type: ValueType
    qualifiers: dict[str, Any]
    confidence: float
    evidence_status: EvidenceStatus
    review_status: CandidateReviewStatus
    warnings: tuple[str, ...] = ()


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _normalize_comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = normalized.translate(_SINGLE_QUOTES)
    normalized = normalized.translate(_DOUBLE_QUOTES)
    normalized = normalized.translate(_DASHES)
    normalized = _normalize_whitespace(normalized)
    if normalized.endswith((".", "!", "?")):
        normalized = normalized[:-1]
    return normalized.strip()


def _canonical_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _stable_digest(parts: list[Any]) -> str:
    return hashlib.sha256(_canonical_value(parts).encode("utf-8")).hexdigest().upper()


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value))


def _trim_subject_span(value: str) -> str:
    match = _LEADING_MARKER_RE.match(value)
    if match is not None:
        value = value[match.end() :]
    return _normalize_whitespace(value)


def _has_leading_structural_marker(value: str) -> bool:
    return _LEADING_MARKER_RE.match(value) is not None


def _is_clause_like(value: str) -> bool:
    normalized = value.casefold()
    if any(marker in value for marker in _CLAUSE_BOUNDARIES):
        return True
    if any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in _SUBORDINATE_MARKERS):
        return True
    return _COORDINATED_FINITE_RE.search(value) is not None


def _subject_bounds_warning(value: str) -> str | None:
    count = len(_tokens(value))
    if count < 1:
        return _COMMITMENT_WARNINGS["ineligible"]
    if count > 12 or len(value) > 79:
        return _COMMITMENT_WARNINGS["too_long"]
    if _is_clause_like(value):
        return _COMMITMENT_WARNINGS["clause"]
    return None


def _eligible_generic_actor(value: str) -> bool:
    tokens = _tokens(value)
    normalized_tokens = tuple(token.casefold() for token in tokens)
    if not 1 <= len(tokens) <= 12 or len(value) > 79:
        return False
    if not re.search(r"[A-Za-z]", value) or _is_clause_like(value):
        return False
    if _normalize_comparison_text(value) in _IMPERSONAL_SUBJECTS:
        return False
    return bool(normalized_tokens) and normalized_tokens[-1] not in _DISALLOWED_GENERIC_HEADS


def _classify_subject(value: str, *, predicate: str) -> SubjectType:
    normalized = value.casefold()
    if re.search(r"\bprogramme?s?\b|\bprograms?\b", normalized):
        return SubjectType.PROGRAMME
    if re.search(r"\bpolicy\b|\bstrategy\b|\bframework\b|\bplan\b", normalized):
        return SubjectType.POLICY
    if re.search(
        r"\bproject\b|\binitiative\b|\bplatform\b|\bservice\b|\bsystem\b",
        normalized,
    ):
        return SubjectType.INITIATIVE
    if re.search(
        r"\bgovernment\b|\bdepartment\b|\bboard\b|\bcouncil\b|"
        r"\bauthority\b|\bregulator\b|\borganisation\b|\borganization\b|"
        r"\bagency\b|\bcommittee\b|\boffice\b|\bteam\b",
        normalized,
    ):
        return SubjectType.ORGANISATION
    if predicate == "metric" or re.search(
        r"\brate\b|\bmeasure\b|\bpopulation\b|\brespondents?\b|"
        r"\bparticipants?\b|\busers?\b|\bresidents?\b",
        normalized,
    ):
        return SubjectType.METRIC
    return SubjectType.OTHER


def _looks_like_heading(value: str) -> bool:
    stripped = value.strip().rstrip(":").strip()
    if not stripped or len(_tokens(stripped)) > 12 or len(stripped) > 79:
        return False
    if re.search(r"[.!?]$", value.strip()):
        return False
    if _COMMITMENT_TRIGGER_RE.search(stripped):
        return False
    if _REQUIREMENT_TRIGGER_RE.search(stripped) or _PERCENT_RE.search(stripped):
        return False
    return _STATUS_RE.match(stripped) is None


def _sentence_spans(value: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(value):
        prefix = value[: match.start()]
        if match.group(0).startswith(".") and re.fullmatch(
            r"\s*(?:[A-Za-z]|\d+)", prefix
        ):
            continue
        spans.append((start, match.end()))
        start = match.end()
    if start < len(value):
        spans.append((start, len(value)))
    return tuple(spans)


def _statements(block: DocumentBlock) -> tuple[_Statement, ...]:
    statements: list[_Statement] = []
    pending_headings: list[str] = []
    for line_match in re.finditer(r"[^\r\n]+", block.text):
        raw_line = line_match.group(0)
        left = len(raw_line) - len(raw_line.lstrip())
        right = len(raw_line.rstrip())
        if right <= left:
            continue
        line = raw_line[left:right]
        line_start = line_match.start() + left
        if _looks_like_heading(line):
            pending_headings.append(_trim_subject_span(line.rstrip(":").strip()))
            continue
        for span_start, span_end in _sentence_spans(line):
            raw_statement = line[span_start:span_end]
            leading = len(raw_statement) - len(raw_statement.lstrip())
            trailing = len(raw_statement.rstrip())
            if trailing <= leading:
                continue
            start = line_start + span_start + leading
            end = line_start + span_start + trailing
            statements.append(
                _Statement(
                    block=block,
                    text=block.text[start:end],
                    start=start,
                    end=end,
                    heading_context=tuple(pending_headings),
                )
            )
        pending_headings.clear()
    return tuple(statements)


def _commitment_subject_from_context(
    statement: _Statement,
) -> tuple[str | None, SubjectType | None, str | None]:
    eligible: dict[tuple[str, SubjectType], tuple[str, SubjectType]] = {}
    for heading in statement.heading_context:
        if _has_leading_structural_marker(heading):
            continue
        warning = _subject_bounds_warning(heading)
        if warning is not None:
            continue
        subject_type = _classify_subject(heading, predicate="commitment")
        if subject_type not in _ALLOWED_ACTOR_TYPES:
            continue
        if subject_type is SubjectType.OTHER and not _eligible_generic_actor(heading):
            continue
        key = (_normalize_comparison_text(heading), subject_type)
        eligible.setdefault(key, (heading, subject_type))
    if len(eligible) > 1:
        return None, None, _COMMITMENT_WARNINGS["ambiguous_heading"]
    if not eligible:
        return None, None, _COMMITMENT_WARNINGS["ineligible"]
    subject_text, subject_type = next(iter(eligible.values()))
    return subject_text, subject_type, None


def _has_excluded_weak_prefix(value: str) -> bool:
    normalized = value.casefold()
    return any(
        re.match(rf"{re.escape(prefix)}(?:\b|$)", normalized) is not None
        for prefix in _EXCLUDED_WEAK_PREFIXES
    )


def _draft(
    statement: _Statement,
    rule: DeterministicRuleDefinitionV02,
    *,
    subject_text: str,
    subject_type: SubjectType,
    predicate: str,
    raw_value: str,
    normalized_value: Any,
    value_type: ValueType,
    qualifiers: dict[str, Any] | None = None,
    confidence: float,
    evidence_status: EvidenceStatus = EvidenceStatus.SUPPORTED,
    review_status: CandidateReviewStatus = CandidateReviewStatus.NOT_REQUIRED,
    warnings: tuple[str, ...] = (),
) -> _CandidateDraft:
    return _CandidateDraft(
        rule=rule,
        block=statement.block,
        statement_start=statement.start,
        statement_end=statement.end,
        subject_text=subject_text,
        subject_type=subject_type,
        predicate=predicate,
        raw_value=raw_value,
        normalized_value=normalized_value,
        value_type=value_type,
        qualifiers=qualifiers or {},
        confidence=confidence,
        evidence_status=evidence_status,
        review_status=review_status,
        warnings=warnings,
    )


def _match_commitment(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    trigger_match = _COMMITMENT_TRIGGER_RE.search(statement.text)
    if trigger_match is None:
        return [], []
    before = statement.text[: trigger_match.start()]
    if before and not before[-1].isspace():
        return [], []
    trigger = _normalize_whitespace(trigger_match.group("trigger")).casefold()
    raw_value = _normalize_whitespace(statement.text[trigger_match.start() :])
    if trigger in _WEAK_TRIGGERS and _has_excluded_weak_prefix(raw_value):
        return [], [_COMMITMENT_WARNINGS["copular"]]

    contextual = not before.strip()
    if contextual:
        subject_text, subject_type, warning = _commitment_subject_from_context(statement)
        if warning is not None or subject_text is None or subject_type is None:
            return [], [warning or _COMMITMENT_WARNINGS["ineligible"]]
        confidence = 0.7
    else:
        subject_text = _trim_subject_span(before)
        if _has_leading_structural_marker(subject_text):
            return [], [
                _COMMITMENT_WARNINGS["ineligible"],
                _SUBJECT_SPAN_WARNING,
            ]
        warning = _subject_bounds_warning(subject_text)
        if warning is not None:
            warnings = [warning]
            if warning == _COMMITMENT_WARNINGS["too_long"]:
                warnings.append(_SUBJECT_SPAN_WARNING)
            return [], warnings
        subject_type = _classify_subject(subject_text, predicate="commitment")
        if subject_type is not SubjectType.METRIC:
            if subject_type not in _ALLOWED_ACTOR_TYPES:
                return [], [_COMMITMENT_WARNINGS["ineligible"]]
            if subject_type is SubjectType.OTHER and not _eligible_generic_actor(
                subject_text
            ):
                return [], [
                    _COMMITMENT_WARNINGS["ineligible"],
                    _GENERIC_ACTOR_WARNING,
                ]
        confidence = 0.9 if trigger in _EXPLICIT_TRIGGERS else 0.7

    rule = (
        _COMMITMENT_EXPLICIT_RULE
        if trigger in _EXPLICIT_TRIGGERS
        else _COMMITMENT_WEAK_RULE
    )
    return [
        _draft(
            statement,
            rule,
            subject_text=subject_text,
            subject_type=subject_type,
            predicate="commitment",
            raw_value=raw_value,
            normalized_value=raw_value,
            value_type=ValueType.STRING,
            confidence=confidence,
        )
    ], []


def _population_qualifier(value: str) -> str | None:
    found = [cue for cue in _POPULATION_CUES if re.search(rf"\b{cue}\b", value, re.I)]
    return found[0] if len(found) == 1 else None


def _period_qualifier(value: str) -> str | None:
    years = _YEAR_RE.findall(value)
    return years[0] if len(years) == 1 else None


def _metric_name(subject: str) -> str:
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9]+", subject)
        if word.casefold() not in {"a", "an", "the", "of", "for"}
    ]
    if words and words[-1] not in {"percentage", "rate", "share"}:
        words.append("percentage")
    return "_".join(words[:10])


def _metric_qualifiers(subject: str, statement_text: str) -> dict[str, Any]:
    qualifiers: dict[str, Any] = {
        "metric_name": _metric_name(subject),
        "unit": "percent",
    }
    population = _population_qualifier(statement_text)
    if population is not None:
        qualifiers["population"] = population
    period = _period_qualifier(statement_text)
    if period is not None:
        qualifiers["period"] = period
    return qualifiers


def _percentage_value(match: re.Match[str]) -> int | float:
    raw = match.group("value")
    converted = Decimal(raw)
    return int(converted) if converted == converted.to_integral() else float(converted)


def _ambiguous_metric_subjects(prefix: str) -> tuple[str, ...]:
    cleaned = re.sub(
        r"\s+(?:may\s+be|was|were|is|are|reached|stood\s+at|measured)\s*$",
        "",
        prefix,
        flags=re.IGNORECASE,
    ).strip(" ,:;-")
    if not cleaned:
        return ()
    parts = tuple(_trim_subject_span(item) for item in re.split(r"\s+and\s+", cleaned, flags=re.I))
    return tuple(item for item in parts if item)


def _match_metric(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    matches = list(_PERCENT_RE.finditer(statement.text))
    if not matches:
        return [], []
    if len(matches) > 3:
        return [], [_AMBIGUOUS_METRIC_BOUNDS_WARNING]

    if len(matches) == 1:
        prefix = statement.text[: matches[0].start()]
        subject_match = _METRIC_LINK_RE.match(prefix)
        if subject_match is None:
            return [], []
        subject = _trim_subject_span(subject_match.group("subject"))
        if not subject:
            return [], []
        return [
            _draft(
                statement,
                _METRIC_RULE,
                subject_text=subject,
                subject_type=_classify_subject(subject, predicate="metric"),
                predicate="metric",
                raw_value=matches[0].group(0),
                normalized_value=_percentage_value(matches[0]),
                value_type=ValueType.PERCENTAGE,
                qualifiers=_metric_qualifiers(subject, statement.text),
                confidence=0.9,
            )
        ], []

    subjects = _ambiguous_metric_subjects(statement.text[: matches[0].start()])
    if not subjects:
        return [], []
    interpretations = [(subject, match) for subject in subjects for match in matches]
    if len(interpretations) > 3:
        return [], [_AMBIGUOUS_METRIC_BOUNDS_WARNING]
    drafts = [
        _draft(
            statement,
            _METRIC_RULE,
            subject_text=subject,
            subject_type=_classify_subject(subject, predicate="metric"),
            predicate="metric",
            raw_value=match.group(0),
            normalized_value=_percentage_value(match),
            value_type=ValueType.PERCENTAGE,
            qualifiers=_metric_qualifiers(subject, statement.text),
            confidence=0.5,
            evidence_status=EvidenceStatus.AMBIGUOUS,
            review_status=CandidateReviewStatus.REQUIRED,
            warnings=(_AMBIGUOUS_METRIC_WARNING,),
        )
        for subject, match in interpretations
    ]
    return drafts, []


def _match_requirement(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    trigger_match = _REQUIREMENT_TRIGGER_RE.search(statement.text)
    if trigger_match is None or not statement.text[: trigger_match.start()].strip():
        return [], []
    subject = _trim_subject_span(statement.text[: trigger_match.start()])
    action = _normalize_whitespace(statement.text[trigger_match.end() :])
    action_tokens = _tokens(action)
    if not 1 <= len(action_tokens) <= 40 or len(action) > 240:
        return [], [_REQUIREMENT_WARNINGS["action"]]
    if _has_leading_structural_marker(subject):
        return [], [_REQUIREMENT_WARNINGS["subject"], _SUBJECT_SPAN_WARNING]
    subject_warning = _subject_bounds_warning(subject)
    if subject_warning is not None:
        warnings = [_REQUIREMENT_WARNINGS["subject"]]
        if subject_warning == _COMMITMENT_WARNINGS["too_long"]:
            warnings.append(_SUBJECT_SPAN_WARNING)
        return [], warnings
    subject_type = _classify_subject(subject, predicate="requirement")
    if subject_type not in _ALLOWED_ACTOR_TYPES:
        return [], [_REQUIREMENT_WARNINGS["subject"]]
    if subject_type is SubjectType.OTHER and not _eligible_generic_actor(subject):
        return [], [_REQUIREMENT_WARNINGS["subject"], _GENERIC_ACTOR_WARNING]
    raw_value = _normalize_whitespace(statement.text[trigger_match.start() :])
    return [
        _draft(
            statement,
            _REQUIREMENT_RULE,
            subject_text=subject,
            subject_type=subject_type,
            predicate="requirement",
            raw_value=raw_value,
            normalized_value=raw_value,
            value_type=ValueType.STRING,
            confidence=0.9,
        )
    ], []


def _match_action_status(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    match = _STATUS_RE.match(statement.text)
    if match is None:
        return [], []
    subject = _trim_subject_span(match.group("subject"))
    subject_type = _classify_subject(subject, predicate="action_status")
    subject_tokens = {token.casefold() for token in _tokens(subject)}
    if (
        subject_type not in _ACTION_ALLOWED_TYPES
        or not subject_tokens.intersection(_ACTION_CUES)
        or _subject_bounds_warning(subject) is not None
    ):
        return [], [_ACTION_WARNING]
    raw_value = _normalize_whitespace(match.group("value"))
    return [
        _draft(
            statement,
            _ACTION_STATUS_RULE,
            subject_text=subject,
            subject_type=subject_type,
            predicate="action_status",
            raw_value=raw_value,
            normalized_value=raw_value.casefold(),
            value_type=ValueType.STATUS,
            confidence=0.9,
        )
    ], []


_MATCHERS: tuple[
    Callable[[_Statement], tuple[list[_CandidateDraft], list[str]]], ...
] = (_match_commitment, _match_metric, _match_requirement, _match_action_status)


def _decimal_token(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric candidate value")
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("numeric candidate value is invalid") from error
    if not converted.is_finite():
        raise ValueError("numeric candidate value must be finite")
    if converted == 0:
        return "0"
    return format(converted.normalize(), "f")


def _typed_value_key(value_type: ValueType, value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if value_type in {ValueType.STRING, ValueType.STATUS, ValueType.OTHER}:
        return ("text", _normalize_comparison_text(str(value)))
    if value_type in {ValueType.NUMBER, ValueType.PERCENTAGE}:
        return ("number", _decimal_token(value))
    if value_type is ValueType.MONEY and isinstance(value, NormalizedMoney):
        return ("money", _decimal_token(value.amount), value.currency)
    if value_type is ValueType.BOOLEAN:
        return ("boolean", value)
    if value_type is ValueType.LIST and isinstance(value, list):
        return ("list", tuple(_normalize_comparison_text(item) for item in value))
    return (value_type.value, _canonical_value(value))


def _qualifier_key(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, str):
        return ("text", _normalize_comparison_text(value))
    if isinstance(value, (int, float, Decimal)):
        return ("number", _decimal_token(value))
    if isinstance(value, list):
        return ("list", tuple(_qualifier_key(item) for item in value))
    raise ValueError("unsupported qualifier value")


def _duplicate_key(source_id: str, draft: _CandidateDraft) -> tuple[Any, ...]:
    return (
        source_id,
        _normalize_comparison_text(draft.subject_text),
        draft.subject_type.value,
        draft.predicate,
        draft.value_type.value,
        _typed_value_key(draft.value_type, draft.normalized_value),
        tuple((name, _qualifier_key(value)) for name, value in sorted(draft.qualifiers.items())),
    )


def _stable_candidate_signature(draft: _CandidateDraft) -> str:
    return _stable_digest(
        [
            draft.subject_text,
            draft.subject_type.value,
            draft.predicate,
            _typed_value_key(draft.value_type, draft.normalized_value),
            tuple(sorted(draft.qualifiers.items())),
            draft.statement_start,
            draft.statement_end,
        ]
    )


def _retention_order(draft: _CandidateDraft) -> tuple[int, int, int, str]:
    return (
        draft.block.sequence,
        draft.statement_start,
        draft.rule.priority,
        _stable_candidate_signature(draft),
    )


def _evidence_id(source_id: str, draft: _CandidateDraft) -> str:
    return "V02-EVID-" + _stable_digest(
        [
            source_id,
            draft.block.block_id,
            draft.statement_start,
            draft.statement_end,
            draft.evidence_status.value,
        ]
    )


def _candidate_id(source_id: str, draft: _CandidateDraft) -> str:
    return "V02-CAND-" + _stable_digest(
        [
            source_id,
            draft.rule.rule_id,
            _duplicate_key(source_id, draft),
            draft.block.block_id,
            draft.statement_start,
            draft.statement_end,
        ]
    )


def _output_order(source_id: str, draft: _CandidateDraft) -> tuple[Any, ...]:
    return (
        draft.block.sequence,
        draft.statement_start,
        _normalize_comparison_text(draft.subject_text),
        _canonical_value(_typed_value_key(draft.value_type, draft.normalized_value)),
        _candidate_id(source_id, draft),
    )


def _document_family(document: ParsedDocument) -> str:
    candidate = document.metadata.get("document_family")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return document.document_id


def _meaningful_qualifier(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(
            isinstance(item, str) and bool(item.strip()) for item in value
        )
    return True


def _validate_candidate_contract(draft: _CandidateDraft) -> None:
    try:
        predicate = normalize_predicate(draft.predicate)
    except ValueError as error:
        raise _PredicateContractIncompatibility(str(error)) from error
    definition = PREDICATE_REGISTRY[predicate]
    if draft.subject_type not in definition.allowed_subject_types:
        raise _PredicateContractIncompatibility(
            f"predicate {predicate!r} does not allow subject_type "
            f"{draft.subject_type.value!r}"
        )
    if draft.value_type not in definition.allowed_value_types:
        raise _PredicateContractIncompatibility(
            f"predicate {predicate!r} does not allow value_type "
            f"{draft.value_type.value!r}"
        )
    missing = sorted(
        name
        for name in definition.required_qualifiers
        if name not in draft.qualifiers
        or not _meaningful_qualifier(draft.qualifiers[name])
    )
    if missing:
        raise _PredicateContractIncompatibility(
            f"predicate {predicate!r} requires meaningful qualifiers: "
            f"{', '.join(missing)}"
        )
    declared = set(definition.required_qualifiers) | set(
        definition.optional_qualifiers
    )
    unknown = sorted(set(draft.qualifiers) - declared)
    if unknown:
        raise _PredicateContractIncompatibility(
            f"predicate {predicate!r} received undeclared qualifiers: "
            f"{', '.join(unknown)}"
        )
    canonical = validate_predicate_usage(
        predicate=predicate,
        subject_type=draft.subject_type,
        value_type=draft.value_type,
        qualifiers=draft.qualifiers,
    )
    if canonical != predicate:
        raise RuntimeError("predicate validation returned an inconsistent name")


def _build_result(
    document: ParsedDocument,
    drafts: list[_CandidateDraft],
    warnings: list[str],
) -> CandidateExtractionResult:
    if document.source_id is None or not document.source_id.strip():
        raise DeterministicExtractionV02Error("document requires a source_id")
    source_id = document.source_id
    ordered = sorted(drafts, key=_retention_order)
    unique: list[_CandidateDraft] = []
    seen: set[tuple[Any, ...]] = set()
    for draft in ordered:
        key = _duplicate_key(source_id, draft)
        if key in seen:
            continue
        seen.add(key)
        unique.append(draft)

    guarded: list[_CandidateDraft] = []
    for draft in unique:
        try:
            _validate_candidate_contract(draft)
        except _PredicateContractIncompatibility:
            warnings.append(_CONTRACT_WARNING)
            continue
        guarded.append(draft)

    guarded.sort(key=lambda item: _output_order(source_id, item))
    evidence_by_id: dict[str, CandidateEvidenceReference] = {}
    facts: list[CandidateFact] = []
    family = _document_family(document)
    for draft in guarded:
        evidence_id = _evidence_id(source_id, draft)
        excerpt = draft.block.text[draft.statement_start : draft.statement_end]
        if len(excerpt) > 240:
            raise DeterministicExtractionV02Error(
                "candidate evidence exceeds the schema limit"
            )
        evidence_by_id.setdefault(
            evidence_id,
            CandidateEvidenceReference(
                evidence_id=evidence_id,
                source_id=source_id,
                block_id=draft.block.block_id,
                location_type=draft.block.location.location_type,
                location_value=draft.block.location.location_value,
                text_excerpt=excerpt,
                evidence_status=draft.evidence_status,
            ),
        )
        facts.append(
            CandidateFact(
                candidate_id=_candidate_id(source_id, draft),
                source_id=source_id,
                document_family=family,
                subject_text=draft.subject_text,
                subject_type=draft.subject_type,
                predicate=draft.predicate,
                raw_value=draft.raw_value,
                normalized_value=draft.normalized_value,
                value_type=draft.value_type,
                qualifiers=draft.qualifiers,
                evidence_ids=[evidence_id],
                confidence=draft.confidence,
                review_status=draft.review_status,
                extraction_method=ExtractionMethod.DETERMINISTIC,
                warnings=sorted(set(draft.warnings)),
            )
        )

    return CandidateExtractionResult(
        batch_id="V02-BATCH-" + _stable_digest([source_id, document.checksum_sha256]),
        source_ids=[source_id],
        entities=[],
        evidence_references=sorted(
            evidence_by_id.values(), key=lambda item: item.evidence_id
        ),
        candidate_facts=facts,
        warnings=sorted(set(warnings)),
    )


def extract_deterministic_candidates_v0_2(
    document: ParsedDocument,
) -> CandidateExtractionResult:
    """Transform one validated in-memory ParsedDocument without external access."""

    if not isinstance(document, ParsedDocument):
        raise DeterministicExtractionV02Error(
            "document must be a validated ParsedDocument"
        )
    drafts: list[_CandidateDraft] = []
    warnings: list[str] = []
    for block in sorted(document.blocks, key=lambda item: item.sequence):
        if block.block_type not in _CANDIDATE_BLOCK_TYPES:
            continue
        for statement in _statements(block):
            for matcher in _MATCHERS:
                matched, observed_warnings = matcher(statement)
                drafts.extend(matched)
                warnings.extend(observed_warnings)
    try:
        return _build_result(document, drafts, warnings)
    except ValidationError as error:
        raise DeterministicExtractionV02Error(
            "deterministic v0.2 output violates CandidateExtractionResult schema 0.1"
        ) from error


def canonical_candidate_result_json_v0_2(result: CandidateExtractionResult) -> str:
    """Serialize a validated candidate result to canonical deterministic JSON."""

    if not isinstance(result, CandidateExtractionResult):
        raise TypeError("result must be a CandidateExtractionResult")
    return json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


__all__ = [
    "DETERMINISTIC_BASELINE_VERSION",
    "DeterministicExtractionV02Error",
    "canonical_candidate_result_json_v0_2",
    "extract_deterministic_candidates_v0_2",
]
