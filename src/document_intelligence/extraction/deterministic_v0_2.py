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
_AMBIGUOUS_METRIC_MAX_VALUES = 3
_AMBIGUOUS_METRIC_MAX_INTERPRETATIONS = 3
_SUBJECT_MIN_TOKENS = 1
_SUBJECT_MAX_TOKENS = 12
_SUBJECT_MAX_CHARACTERS = 79
_REQUIREMENT_ACTION_MIN_TOKENS = 1
_REQUIREMENT_ACTION_MAX_TOKENS = 40
_REQUIREMENT_ACTION_MAX_CHARACTERS = 240

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
_RECOMMENDATION_RULE = _RULES["V02-RULE-REC-001"]
_DECISION_RULE = _RULES["V02-RULE-DEC-001"]
_RISK_RULE = _RULES["V02-RULE-RISK-001"]
_BUDGET_RULE = _RULES["V02-RULE-BUD-001"]

_CANDIDATE_BLOCK_TYPES = {
    BlockType.PAGE_TEXT,
    BlockType.SLIDE_TITLE,
    BlockType.SHAPE_TEXT,
    BlockType.TABLE,
    BlockType.EMAIL_BODY,
}
_PARENT_MAX_EVIDENCE_LENGTH = 240

_NUMBERED_RECOMMENDATION_RE = re.compile(
    r"^(?P<label>Recommendation\s+(?P<identifier>\d+))\s*"
    r"[:\-\N{EN DASH}\N{EM DASH}]\s*(?P<action>.+)$",
    re.IGNORECASE,
)
_EXPLICIT_RECOMMENDATION_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?:recommends?|recommended)\s+"
    r"(?:that\s+)?(?P<action>.+)$",
    re.IGNORECASE,
)
_CONTEXT_RECOMMENDATION_RE = re.compile(
    r"^(?:recommends?|recommended)\s+(?:that\s+)?(?P<action>.+)$",
    re.IGNORECASE,
)

_DECISION_TRIGGER = (
    r"(?:decided\s+to|agreed\s+to|approved|selected|chose\s+to|resolved\s+to)"
)
_RISK_TRIGGER = (
    r"(?:(?:identified\s+)?risk\s+(?:of|that)|identified\s+risk\s*:|"
    r"threat\s+of|adverse\s+impact)"
)

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
_EXPLICIT_COMMITMENT_GOVERNOR_RE = re.compile(
    r"\b(?:(?:do|does|did)(?:\s+not)?|"
    r"(?:may|might|could|should|can|would)(?:\s+not)?)\s*$",
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
_NEGATED_REQUIREMENT_GOVERNOR_RE = re.compile(
    r"\b(?:(?:is|are|was|were)\s+)?not\s+$",
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
    r"^(?P<subject>.+?)\s+(?:(?:is|are|was|were|remains?|has\s+been|"
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
_ACTION_RATIO_RE = re.compile(
    r"(?P<value>\b\d+\s+(?:of|out\s+of)\s+\d+\s+"
    r"(?P<subject_noun>(?:identified\s+)?actions?)\s+"
    r"(?:(?:were|are|have\s+been)\s+)?(?:completed|met)\b)",
    re.IGNORECASE,
)
_PARENT_ACTION_CUE_RE = re.compile(
    r"\baction\b|\btask\b|\bmilestone\b|\bworkstream\b|"
    r"\bdeliverable\b|\brecommendation\b",
    re.IGNORECASE,
)
_ACTION_ID_RE = re.compile(
    r"\bAction\s+([A-Za-z0-9][A-Za-z0-9-]*)\b",
    re.IGNORECASE,
)

_PERCENT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|percentage(?:\s+points?)?|percent)(?![A-Za-z])",
    re.IGNORECASE,
)
_SIMPLE_NUMBER_RE = re.compile(
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<unit>participants|respondents|users|projects|services|cases|"
    r"requests|applications)\b",
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

_CURRENCY_RE = re.compile(
    r"(?:(?P<ceiling>up\s+to)\s+)?(?:"
    r"(?P<currency_prefix>GBP|USD|EUR|\N{POUND SIGN}|\N{DOLLAR SIGN}|"
    r"\N{EURO SIGN})\s*(?P<amount_prefix>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale_prefix>thousand|million|billion|k|m|bn)?|"
    r"(?P<amount_suffix>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale_suffix>thousand|million|billion|k|m|bn)?\s*"
    r"(?P<currency_suffix>GBP|USD|EUR))",
    re.IGNORECASE,
)

_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}
_MONTH_PERIOD_RE = re.compile(
    r"\b(?:in|during|for|as\s+of)\s+("
    + "|".join(_MONTHS)
    + r")\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_YEAR_PERIOD_RE = re.compile(
    r"\b(?:in|during|for|as\s+of)\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)

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
class _HeadingContext:
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Statement:
    block: DocumentBlock
    text: str
    start: int
    end: int
    heading_context: tuple[_HeadingContext, ...]


@dataclass(frozen=True, slots=True)
class _CandidateDraft:
    rule: DeterministicRuleDefinitionV02
    block: DocumentBlock
    statement_start: int
    statement_end: int
    evidence_start: int
    evidence_end: int
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
    parent_carryover: bool = False


@dataclass(frozen=True, slots=True)
class _ParentSubject:
    text: str
    subject_type: SubjectType
    confidence: float
    evidence_start: int


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


def _trim_parent_subject(value: str) -> str:
    trimmed = value.strip()
    marker = _LEADING_MARKER_RE.match(trimmed)
    if marker is not None:
        trimmed = trimmed[marker.end() :].strip()
    while trimmed and trimmed[-1] in ":;|,-":
        trimmed = trimmed[:-1].rstrip()
    return trimmed


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
    if count < _SUBJECT_MIN_TOKENS:
        return _COMMITMENT_WARNINGS["ineligible"]
    if count > _SUBJECT_MAX_TOKENS or len(value) > _SUBJECT_MAX_CHARACTERS:
        return _COMMITMENT_WARNINGS["too_long"]
    if _is_clause_like(value):
        return _COMMITMENT_WARNINGS["clause"]
    return None


def _eligible_generic_actor(value: str) -> bool:
    tokens = _tokens(value)
    normalized_tokens = tuple(token.casefold() for token in tokens)
    if not _SUBJECT_MIN_TOKENS <= len(tokens) <= _SUBJECT_MAX_TOKENS or len(
        value
    ) > _SUBJECT_MAX_CHARACTERS:
        return False
    if not re.search(r"[A-Za-z]", value) or _is_clause_like(value):
        return False
    if _normalize_comparison_text(value) in _IMPERSONAL_SUBJECTS:
        return False
    return bool(normalized_tokens) and normalized_tokens[-1] not in _DISALLOWED_GENERIC_HEADS


def _classify_subject(value: str, *, predicate: str) -> SubjectType:
    normalized = value.casefold()
    if predicate == "recommendation" and re.fullmatch(
        r"recommendation\s+\d+", normalized
    ):
        return SubjectType.RECOMMENDATION
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
    if predicate == "risk" and re.search(r"\brisk\b|\bthreat\b", normalized):
        return SubjectType.RISK
    if predicate == "decision" and "decision" in normalized:
        return SubjectType.DECISION
    if predicate == "metric" or re.search(
        r"\brate\b|\bmeasure\b|\bpopulation\b|\brespondents?\b|"
        r"\bparticipants?\b|\busers?\b|\bresidents?\b",
        normalized,
    ):
        return SubjectType.METRIC
    return SubjectType.OTHER


def _looks_like_heading(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) >= 120:
        return False
    if _NUMBERED_RECOMMENDATION_RE.match(stripped):
        return False
    if stripped.endswith(":"):
        return True
    if stripped.endswith((".", "!", "?")):
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&/\-]*", stripped)
    if not words or len(words) > 12:
        return False
    if stripped.isupper():
        return True
    prose_markers = {
        "approved",
        "are",
        "completed",
        "has",
        "have",
        "is",
        "must",
        "recommended",
        "recommends",
        "shall",
        "was",
        "were",
        "will",
    }
    if any(word.casefold() in prose_markers for word in words):
        return False
    title_like = sum(word[0].isupper() for word in words) >= max(
        1, len(words) - 1
    )
    return title_like


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
    pending_headings: list[_HeadingContext] = []
    for line_match in re.finditer(r"[^\r\n]+", block.text):
        raw_line = line_match.group(0)
        left = len(raw_line) - len(raw_line.lstrip())
        right = len(raw_line.rstrip())
        if right <= left:
            continue
        line = raw_line[left:right]
        line_start = line_match.start() + left
        if _looks_like_heading(line):
            heading_text = line[:-1].rstrip() if line.endswith(":") else line
            pending_headings.append(
                _HeadingContext(
                    text=heading_text,
                    start=line_start,
                    end=line_start + len(line),
                )
            )
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
) -> tuple[str | None, SubjectType | None, int | None, str | None]:
    eligible: dict[tuple[str, SubjectType], tuple[str, SubjectType, int]] = {}
    for heading in statement.heading_context:
        heading_text = _trim_subject_span(heading.text)
        if _has_leading_structural_marker(heading_text):
            continue
        warning = _subject_bounds_warning(heading_text)
        if warning is not None:
            continue
        subject_type = _classify_subject(heading_text, predicate="commitment")
        if subject_type not in _ALLOWED_ACTOR_TYPES:
            continue
        if subject_type is SubjectType.OTHER and not _eligible_generic_actor(
            heading_text
        ):
            continue
        key = (_normalize_comparison_text(heading_text), subject_type)
        eligible.setdefault(key, (heading_text, subject_type, heading.start))
    if len(eligible) > 1:
        return None, None, None, _COMMITMENT_WARNINGS["ambiguous_heading"]
    if not eligible:
        return None, None, None, _COMMITMENT_WARNINGS["ineligible"]
    subject_text, subject_type, evidence_start = next(iter(eligible.values()))
    return subject_text, subject_type, evidence_start, None


def _has_excluded_weak_prefix(value: str) -> bool:
    normalized = value.casefold()
    return any(
        re.match(rf"{re.escape(prefix)}(?:\b|$)", normalized) is not None
        for prefix in _EXCLUDED_WEAK_PREFIXES
    )


def _parent_warning(
    code: str,
    statement: _Statement,
    rule: DeterministicRuleDefinitionV02,
) -> str:
    return (
        f"{code}:{statement.block.block_id}:"
        f"{statement.start}-{statement.end}:{rule.rule_id}"
    )


def _parent_subject_is_ambiguous(value: str) -> bool:
    if " / " in value or ";" in value:
        return True
    parts = re.split(r"\s+(?:and|or)\s+", value, flags=re.IGNORECASE)
    if len(parts) < 2:
        return False
    organisation_terms = re.compile(
        r"\b(?:board|council|department|authority|agency|committee|team)\b",
        re.IGNORECASE,
    )
    return sum(bool(organisation_terms.search(part)) for part in parts) > 1


def _parent_context(statement: _Statement) -> _HeadingContext | None:
    if not statement.heading_context:
        return None
    context = statement.heading_context[-1]
    gap = statement.block.text[context.end : statement.start]
    if len(re.findall(r"\r\n|\r|\n", gap)) != 1:
        return None
    return context


def _resolve_parent_subject(
    statement: _Statement,
    rule: DeterministicRuleDefinitionV02,
    *,
    predicate: str,
    explicit_text: str | None,
    require_budget_type: bool = False,
) -> tuple[_ParentSubject | None, str | None]:
    if explicit_text is not None:
        text = _trim_parent_subject(explicit_text)
        confidence = 0.9
        evidence_start = statement.start
    else:
        context = _parent_context(statement)
        if context is None:
            return None, _parent_warning("abstained_missing_subject", statement, rule)
        text = context.text
        confidence = 0.7
        evidence_start = context.start
    if not text or len(text) >= 120 or text.casefold() in {
        "it",
        "it is",
        "it was",
        "this",
        "they",
        "there",
        "there is",
        "there was",
    }:
        return None, _parent_warning("abstained_missing_subject", statement, rule)
    if _parent_subject_is_ambiguous(text):
        return None, _parent_warning(
            "abstained_ambiguous_relationship", statement, rule
        )
    subject_type = _classify_subject(text, predicate=predicate)
    if predicate == "decision" and subject_type is SubjectType.OTHER:
        if _subject_bounds_warning(text) is not None or not _eligible_generic_actor(
            text
        ):
            return None, _GENERIC_ACTOR_WARNING
    if require_budget_type and subject_type not in {
        SubjectType.INITIATIVE,
        SubjectType.PROGRAMME,
        SubjectType.POLICY,
        SubjectType.ORGANISATION,
    }:
        return None, _parent_warning(
            "abstained_unsupported_subject_type", statement, rule
        )
    return _ParentSubject(text, subject_type, confidence, evidence_start), None


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
    evidence_start: int | None = None,
    evidence_end: int | None = None,
    parent_carryover: bool = False,
) -> _CandidateDraft:
    return _CandidateDraft(
        rule=rule,
        block=statement.block,
        statement_start=statement.start,
        statement_end=statement.end,
        evidence_start=(statement.start if evidence_start is None else evidence_start),
        evidence_end=(statement.end if evidence_end is None else evidence_end),
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
        parent_carryover=parent_carryover,
    )


def _parent_draft(
    statement: _Statement,
    rule: DeterministicRuleDefinitionV02,
    subject: _ParentSubject,
    *,
    predicate: str,
    raw_value: str,
    normalized_value: Any,
    value_type: ValueType,
    qualifiers: dict[str, Any] | None = None,
    confidence: float | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.SUPPORTED,
) -> _CandidateDraft:
    resolved_confidence = subject.confidence if confidence is None else confidence
    review_status = (
        CandidateReviewStatus.REQUIRED
        if resolved_confidence == 0.5
        or evidence_status is EvidenceStatus.AMBIGUOUS
        else CandidateReviewStatus.NOT_REQUIRED
    )
    return _draft(
        statement,
        rule,
        subject_text=subject.text,
        subject_type=subject.subject_type,
        predicate=predicate,
        raw_value=raw_value,
        normalized_value=normalized_value,
        value_type=value_type,
        qualifiers=qualifiers,
        confidence=resolved_confidence,
        evidence_status=evidence_status,
        review_status=review_status,
        evidence_start=subject.evidence_start,
        parent_carryover=True,
    )


def _match_recommendation(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    numbered = _NUMBERED_RECOMMENDATION_RE.match(statement.text)
    if numbered is not None:
        action = numbered.group("action").strip()
        if not action:
            return [], [
                _parent_warning(
                    "abstained_ambiguous_relationship",
                    statement,
                    _RECOMMENDATION_RULE,
                )
            ]
        subject = _ParentSubject(
            text=numbered.group("label"),
            subject_type=SubjectType.RECOMMENDATION,
            confidence=0.9,
            evidence_start=statement.start,
        )
        return [
            _parent_draft(
                statement,
                _RECOMMENDATION_RULE,
                subject,
                predicate="recommendation",
                raw_value=action,
                normalized_value=_normalize_whitespace(action),
                value_type=ValueType.STRING,
                qualifiers={
                    "recommendation_id": int(numbered.group("identifier"))
                },
            )
        ], []

    explicit = _EXPLICIT_RECOMMENDATION_RE.match(statement.text)
    contextual = _CONTEXT_RECOMMENDATION_RE.match(statement.text)
    if explicit is None and contextual is None:
        return [], []
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject, warning = _resolve_parent_subject(
        statement,
        _RECOMMENDATION_RULE,
        predicate="recommendation",
        explicit_text=(explicit.group("subject") if explicit is not None else None),
    )
    if subject is None:
        return [], [warning] if warning else []
    action = match.group("action").strip()
    if not action:
        return [], [
            _parent_warning(
                "abstained_ambiguous_relationship",
                statement,
                _RECOMMENDATION_RULE,
            )
        ]
    return [
        _parent_draft(
            statement,
            _RECOMMENDATION_RULE,
            subject,
            predicate="recommendation",
            raw_value=action,
            normalized_value=_normalize_whitespace(action),
            value_type=ValueType.STRING,
        )
    ], []


def _match_parent_actor_trigger(
    statement: _Statement,
    rule: DeterministicRuleDefinitionV02,
    *,
    predicate: str,
    trigger: str,
) -> tuple[list[_CandidateDraft], list[str]]:
    explicit = re.match(
        rf"^(?P<subject>.+?)\s+(?P<value>{trigger}\b.+)$",
        statement.text,
        flags=re.IGNORECASE,
    )
    contextual = re.match(
        rf"^(?P<value>{trigger}\b.+)$",
        statement.text,
        flags=re.IGNORECASE,
    )
    if explicit is None and contextual is None:
        return [], []
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject, warning = _resolve_parent_subject(
        statement,
        rule,
        predicate=predicate,
        explicit_text=(explicit.group("subject") if explicit is not None else None),
    )
    if subject is None:
        return [], [warning] if warning else []
    raw_value = match.group("value").strip()
    return [
        _parent_draft(
            statement,
            rule,
            subject,
            predicate=predicate,
            raw_value=raw_value,
            normalized_value=_normalize_whitespace(raw_value),
            value_type=ValueType.STRING,
        )
    ], []


def _match_decision(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    if re.search(
        r"\b(?:proposal|proposed|option)\b.*\b(?:approve|select|choose)\b",
        statement.text,
        flags=re.IGNORECASE,
    ):
        return [], []
    return _match_parent_actor_trigger(
        statement,
        _DECISION_RULE,
        predicate="decision",
        trigger=_DECISION_TRIGGER,
    )


def _match_risk(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    if re.search(_RISK_TRIGGER, statement.text, flags=re.IGNORECASE) is None:
        return [], []
    if statement.block.block_type is BlockType.TABLE:
        table = re.match(
            rf"^(?P<subject>[^|]{{1,100}}?)\s*\|\s*"
            rf"(?P<value>{_RISK_TRIGGER}.+)$",
            statement.text,
            flags=re.IGNORECASE,
        )
        if table is None:
            return [], [
                _parent_warning(
                    "skipped_flattened_table_relationship", statement, _RISK_RULE
                )
            ]
        subject_text = _trim_parent_subject(table.group("subject"))
        if not subject_text or _parent_subject_is_ambiguous(subject_text):
            return [], [
                _parent_warning(
                    "skipped_flattened_table_relationship", statement, _RISK_RULE
                )
            ]
        subject = _ParentSubject(
            text=subject_text,
            subject_type=_classify_subject(subject_text, predicate="risk"),
            confidence=0.5,
            evidence_start=statement.start,
        )
        raw_value = table.group("value").strip()
        return [
            _parent_draft(
                statement,
                _RISK_RULE,
                subject,
                predicate="risk",
                raw_value=raw_value,
                normalized_value=_normalize_whitespace(raw_value),
                value_type=ValueType.STRING,
                confidence=0.5,
                evidence_status=EvidenceStatus.AMBIGUOUS,
            )
        ], []

    patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+(?P<value>(?:may|could|will)\s+have\s+"
            r"an?\s+adverse\s+impact.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^(?P<subject>.+?)\s+(?P<value>(?:faces?\s+)?(?:an?\s+)?"
            rf"{_RISK_TRIGGER}.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^(?P<subject>.+?)\s*:\s*(?P<value>{_RISK_TRIGGER}.+)$",
            re.IGNORECASE,
        ),
    )
    explicit = next(
        (match for pattern in patterns if (match := pattern.match(statement.text))),
        None,
    )
    contextual = re.match(
        rf"^(?P<value>{_RISK_TRIGGER}.+)$",
        statement.text,
        flags=re.IGNORECASE,
    )
    if explicit is None and contextual is None:
        return [], [
            _parent_warning("abstained_missing_subject", statement, _RISK_RULE)
        ]
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject, warning = _resolve_parent_subject(
        statement,
        _RISK_RULE,
        predicate="risk",
        explicit_text=(explicit.group("subject") if explicit is not None else None),
    )
    if subject is None:
        return [], [warning] if warning else []
    raw_value = match.group("value").strip()
    return [
        _parent_draft(
            statement,
            _RISK_RULE,
            subject,
            predicate="risk",
            raw_value=raw_value,
            normalized_value=_normalize_whitespace(raw_value),
            value_type=ValueType.STRING,
        )
    ], []


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
    if trigger in _EXPLICIT_TRIGGERS and _EXPLICIT_COMMITMENT_GOVERNOR_RE.search(
        before
    ):
        return [], []
    raw_value = _normalize_whitespace(statement.text[trigger_match.start() :])
    if trigger in _WEAK_TRIGGERS and _has_excluded_weak_prefix(raw_value):
        return [], [_COMMITMENT_WARNINGS["copular"]]

    contextual = not before.strip()
    evidence_start: int | None = None
    if contextual:
        subject_text, subject_type, evidence_start, warning = (
            _commitment_subject_from_context(statement)
        )
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
            evidence_start=evidence_start,
        )
    ], []


def _population_qualifier(value: str) -> str | None:
    found = [cue for cue in _POPULATION_CUES if re.search(rf"\b{cue}\b", value, re.I)]
    return found[0] if len(found) == 1 else None


def _period_qualifier(value: str) -> str | None:
    years = _YEAR_RE.findall(value)
    return years[0] if len(years) == 1 else None


def _metric_name(subject: str, *, percentage: bool = True) -> str:
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9]+", subject)
        if word.casefold() not in {"a", "an", "the", "of", "for"}
    ]
    if percentage and words and words[-1] not in {"percentage", "rate", "share"}:
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
    return float(Decimal(raw))


def _parent_period_qualifier(value: str) -> str | None:
    month_match = _MONTH_PERIOD_RE.search(value)
    if month_match is not None:
        return f"{month_match.group(2)}-{_MONTHS[month_match.group(1).casefold()]}"
    year_match = _YEAR_PERIOD_RE.search(value)
    return year_match.group(1) if year_match is not None else None


def _value_first_population(
    statement: _Statement,
    value_match: re.Match[str],
) -> str | None:
    after_value = statement.text[value_match.end() :]
    population_match = re.match(
        r"\s+of\s+(?P<population>[A-Za-z][A-Za-z0-9 '\-/]{0,80}?)"
        r"(?=\s+(?:were|was|are|is|had|have|reported|used|completed|met|"
        r"said|received|adopted)\b)",
        after_value,
        flags=re.IGNORECASE,
    )
    return (
        population_match.group("population").strip()
        if population_match is not None
        else None
    )


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
    if _CURRENCY_RE.search(statement.text) or _ACTION_RATIO_RE.search(
        statement.text
    ):
        return [], []
    matches = list(_PERCENT_RE.finditer(statement.text))
    if not matches:
        number_matches = list(_SIMPLE_NUMBER_RE.finditer(statement.text))
        if len(number_matches) > 1:
            return [], [
                _parent_warning("abstained_multiple_values", statement, _METRIC_RULE)
            ]
        if not number_matches:
            return [], []
        value_match = number_matches[0]
        unit_text = value_match.group("unit")
        number_text = value_match.group("number").replace(",", "")
        normalized_number: int | float
        if "." in number_text:
            normalized_number = float(Decimal(number_text))
        else:
            normalized_number = int(number_text)
        qualifiers: dict[str, Any] = {
            "metric_name": _metric_name(
                unit_text + " count", percentage=False
            ),
            "unit": unit_text.casefold(),
            "population": unit_text,
        }
        period = _parent_period_qualifier(statement.text)
        if period is not None:
            qualifiers["period"] = period
        return [
            _draft(
                statement,
                _METRIC_RULE,
                subject_text=unit_text,
                subject_type=SubjectType.METRIC,
                predicate="metric",
                raw_value=value_match.group(0),
                normalized_value=normalized_number,
                value_type=ValueType.NUMBER,
                qualifiers=qualifiers,
                confidence=0.9,
                parent_carryover=True,
            )
        ], []
    if len(matches) > _AMBIGUOUS_METRIC_MAX_VALUES:
        return [], [_AMBIGUOUS_METRIC_BOUNDS_WARNING]

    if len(matches) == 1:
        prefix = statement.text[: matches[0].start()]
        subject_match = _METRIC_LINK_RE.match(prefix)
        population = _value_first_population(statement, matches[0])
        if subject_match is None and population is None:
            return [], []
        subject = (
            _trim_subject_span(subject_match.group("subject"))
            if subject_match is not None
            else population or ""
        )
        if not subject:
            return [], []
        qualifiers = _metric_qualifiers(subject, statement.text)
        if population is not None:
            qualifiers["population"] = population
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
                qualifiers=qualifiers,
                confidence=0.9,
            )
        ], []

    subjects = _ambiguous_metric_subjects(statement.text[: matches[0].start()])
    if not subjects:
        return [], []
    interpretations = [(subject, match) for subject in subjects for match in matches]
    if len(interpretations) > _AMBIGUOUS_METRIC_MAX_INTERPRETATIONS:
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
    trigger_match: re.Match[str] | None = None
    for candidate in _REQUIREMENT_TRIGGER_RE.finditer(statement.text):
        before_candidate = statement.text[: candidate.start()]
        trigger = _normalize_whitespace(candidate.group("trigger")).casefold()
        if trigger == "required to" and _NEGATED_REQUIREMENT_GOVERNOR_RE.search(
            before_candidate
        ):
            continue
        trigger_match = candidate
        break
    if trigger_match is None:
        return [], []
    before = statement.text[: trigger_match.start()]
    evidence_start: int | None = None
    if before.strip():
        subject = _trim_subject_span(before)
        confidence = 0.9
    else:
        context = _parent_context(statement)
        if context is None:
            return [], []
        subject = _trim_subject_span(context.text)
        confidence = 0.7
        evidence_start = context.start
    action = _normalize_whitespace(statement.text[trigger_match.end() :])
    action_tokens = _tokens(action)
    if (
        not _REQUIREMENT_ACTION_MIN_TOKENS
        <= len(action_tokens)
        <= _REQUIREMENT_ACTION_MAX_TOKENS
        or len(action) > _REQUIREMENT_ACTION_MAX_CHARACTERS
    ):
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
            confidence=confidence,
            evidence_start=evidence_start,
        )
    ], []


def _currency_and_amount(match: re.Match[str]) -> tuple[str, Decimal]:
    currency_token = match.group("currency_prefix") or match.group(
        "currency_suffix"
    )
    amount_token = match.group("amount_prefix") or match.group("amount_suffix")
    scale_token = match.group("scale_prefix") or match.group("scale_suffix")
    currency = {
        "£": "GBP",
        "$": "USD",
        "€": "EUR",
        "GBP": "GBP",
        "USD": "USD",
        "EUR": "EUR",
    }[currency_token.upper() if currency_token.isascii() else currency_token]
    scale = {
        None: Decimal("1"),
        "k": Decimal("1000"),
        "thousand": Decimal("1000"),
        "m": Decimal("1000000"),
        "million": Decimal("1000000"),
        "bn": Decimal("1000000000"),
        "billion": Decimal("1000000000"),
    }[scale_token.casefold() if scale_token else None]
    try:
        amount = Decimal(amount_token.replace(",", "")) * scale
    except InvalidOperation as error:
        raise DeterministicExtractionV02Error(
            "invalid bounded monetary amount"
        ) from error
    return currency, amount


def _budget_subject_text(
    statement: _Statement,
    amount_match: re.Match[str],
) -> str | None:
    prefix = statement.text[: amount_match.start()]
    leading_patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+(?:has|received|secured|was\s+granted|"
            r"is\s+allocated|was\s+allocated|will\s+receive)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<subject>.+?)\s+(?:(?:has\s+)?(?:an?\s+)?"
            r"(?:approved|committed|proposed)?\s*)"
            r"(?:budget|funding|investment|allocation)\b",
            re.IGNORECASE,
        ),
    )
    for pattern in leading_patterns:
        match = pattern.match(prefix)
        if match is not None:
            return match.group("subject")
    suffix = statement.text[amount_match.end() :]
    trailing = re.search(
        r"\b(?:allocated|granted|provided|committed|invested)\s+to\s+"
        r"(?P<subject>[^.;]+)",
        suffix,
        flags=re.IGNORECASE,
    )
    return trailing.group("subject") if trailing is not None else None


def _match_budget(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    if re.search(
        r"\bbudget\b|\bfunding\b|\bfunded\b|\binvestment\b|"
        r"\binvested\b|\ballocation\b|\ballocated\b",
        statement.text,
        flags=re.IGNORECASE,
    ) is None:
        return [], []
    amount_matches = list(_CURRENCY_RE.finditer(statement.text))
    if not amount_matches:
        return [], []
    if len(amount_matches) > 1:
        return [], [
            _parent_warning("abstained_multiple_values", statement, _BUDGET_RULE)
        ]
    amount_match = amount_matches[0]
    approximate_prefix = statement.text[
        max(0, amount_match.start() - 24) : amount_match.start()
    ]
    if re.search(
        r"\b(?:about|approximately|around|roughly|circa)\s*$",
        approximate_prefix,
        flags=re.IGNORECASE,
    ):
        return [], [
            _parent_warning(
                "abstained_ambiguous_relationship", statement, _BUDGET_RULE
            )
        ]
    subject, warning = _resolve_parent_subject(
        statement,
        _BUDGET_RULE,
        predicate="budget",
        explicit_text=_budget_subject_text(statement, amount_match),
        require_budget_type=True,
    )
    if subject is None:
        return [], [warning] if warning else []
    currency, amount = _currency_and_amount(amount_match)
    lowered = statement.text.casefold()
    qualifiers: dict[str, Any] = {}
    if amount_match.group("ceiling") is not None:
        qualifiers["budget_status"] = "ceiling"
    elif re.search(r"\bapproved\b", lowered):
        qualifiers["budget_status"] = "approved"
    elif re.search(r"\bcommitted\b", lowered):
        qualifiers["budget_status"] = "committed"
    elif re.search(r"\bproposed\b", lowered):
        qualifiers["budget_status"] = "proposed"
    return [
        _parent_draft(
            statement,
            _BUDGET_RULE,
            subject,
            predicate="budget",
            raw_value=amount_match.group(0),
            normalized_value=NormalizedMoney(amount=amount, currency=currency),
            value_type=ValueType.MONEY,
            qualifiers=qualifiers,
        )
    ], []


def _parent_action_id(value: str) -> str | None:
    match = _ACTION_ID_RE.search(value)
    return match.group(1) if match is not None else None


def _parent_action_status_draft(
    statement: _Statement,
    subject: _ParentSubject,
    raw_value: str,
) -> _CandidateDraft:
    qualifiers: dict[str, Any] = {}
    action_id = _parent_action_id(subject.text)
    if action_id is not None:
        qualifiers["action_id"] = action_id
    return _parent_draft(
        statement,
        _ACTION_STATUS_RULE,
        subject,
        predicate="action_status",
        raw_value=raw_value,
        normalized_value=_normalize_whitespace(raw_value),
        value_type=ValueType.STATUS,
        qualifiers=qualifiers,
    )


def _match_action_status(
    statement: _Statement,
) -> tuple[list[_CandidateDraft], list[str]]:
    ratio = _ACTION_RATIO_RE.search(statement.text)
    if ratio is not None:
        prefix_text = _trim_parent_subject(statement.text[: ratio.start()])
        explicit_text = (
            prefix_text
            if prefix_text and _PARENT_ACTION_CUE_RE.search(prefix_text)
            else ratio.group("subject_noun")
        )
        subject, warning = _resolve_parent_subject(
            statement,
            _ACTION_STATUS_RULE,
            predicate="action_status",
            explicit_text=explicit_text,
        )
        if subject is None:
            return [], [warning] if warning else []
        raw_value = ratio.group("value")
        qualifiers: dict[str, Any] = {}
        action_id = _parent_action_id(statement.text)
        if action_id is not None:
            qualifiers["action_id"] = action_id
        return [
            _parent_draft(
                statement,
                _ACTION_STATUS_RULE,
                subject,
                predicate="action_status",
                raw_value=raw_value,
                normalized_value=_normalize_whitespace(raw_value),
                value_type=ValueType.STATUS,
                qualifiers=qualifiers,
            )
        ], []

    match = _STATUS_RE.match(statement.text)
    if match is None:
        contextual = re.match(
            r"^(?P<value>not\s+started|in\s+progress|on\s+track|"
            r"delayed|completed|delivered|met)\b",
            statement.text,
            flags=re.IGNORECASE,
        )
        context = _parent_context(statement)
        if (
            contextual is None
            or context is None
            or _PARENT_ACTION_CUE_RE.search(context.text) is None
        ):
            return [], []
        subject, warning = _resolve_parent_subject(
            statement,
            _ACTION_STATUS_RULE,
            predicate="action_status",
            explicit_text=None,
        )
        if subject is None:
            return [], [warning] if warning else []
        return [
            _parent_action_status_draft(
                statement,
                subject,
                contextual.group("value"),
            )
        ], []
    subject = _trim_parent_subject(match.group("subject"))
    if _PARENT_ACTION_CUE_RE.search(subject) is not None:
        parent_subject, warning = _resolve_parent_subject(
            statement,
            _ACTION_STATUS_RULE,
            predicate="action_status",
            explicit_text=subject,
        )
        if parent_subject is None:
            return [], [warning] if warning else []
        return [
            _parent_action_status_draft(
                statement,
                parent_subject,
                match.group("value"),
            )
        ], []
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
] = (
    _match_recommendation,
    _match_commitment,
    _match_metric,
    _match_requirement,
    _match_action_status,
    _match_decision,
    _match_risk,
    _match_budget,
)
_MATCHER_PREDICATES = frozenset(
    {
        "action_status",
        "budget",
        "commitment",
        "decision",
        "metric",
        "recommendation",
        "requirement",
        "risk",
    }
)
_RULE_PREDICATES = frozenset(
    rule.predicate
    for rule in get_v0_2_rule_inventory()
    if rule.predicate is not None
)
if _RULE_PREDICATES != _MATCHER_PREDICATES:
    raise RuntimeError("v0.2 rule and matcher predicate inventories must agree")


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
            draft.evidence_start,
            draft.evidence_end,
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
        excerpt = draft.block.text[draft.evidence_start : draft.evidence_end]
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
                warnings.extend(observed_warnings)
                for candidate in matched:
                    evidence_text = block.text[
                        candidate.evidence_start : candidate.evidence_end
                    ]
                    if len(evidence_text) > _PARENT_MAX_EVIDENCE_LENGTH:
                        warnings.append(
                            _parent_warning(
                                "abstained_evidence_too_long",
                                statement,
                                candidate.rule,
                            )
                        )
                        continue
                    if candidate.parent_carryover and (
                        candidate.raw_value not in evidence_text
                        or candidate.subject_text not in evidence_text
                    ):
                        raise DeterministicExtractionV02Error(
                            "candidate spans are not exact block substrings"
                        )
                    drafts.append(candidate)
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
