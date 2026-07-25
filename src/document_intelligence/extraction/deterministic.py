"""Pure deterministic candidate extraction for deterministic-baseline-v0.1."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_rules import (
    DeterministicRuleDefinition,
    get_deterministic_rule_inventory,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    NormalizedMoney,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    ParsedDocument,
)


DETERMINISTIC_BASELINE_VERSION = "deterministic-baseline-v0.1"

_ELIGIBLE_BLOCK_TYPES = {
    BlockType.PAGE_TEXT,
    BlockType.SLIDE_TITLE,
    BlockType.SHAPE_TEXT,
    BlockType.TABLE,
    BlockType.EMAIL_BODY,
}
_CONFIDENCE_VALUES = {0.5, 0.7, 0.9}
_MAX_EVIDENCE_LENGTH = 240

_NUMBERED_RECOMMENDATION_RE = re.compile(
    r"^(?P<label>Recommendation\s+(?P<identifier>\d+))\s*[:\-\N{EN DASH}\N{EM DASH}]\s*(?P<action>.+)$",
    re.IGNORECASE,
)
_EXPLICIT_RECOMMENDATION_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?:recommends?|recommended)\s+(?:that\s+)?(?P<action>.+)$",
    re.IGNORECASE,
)
_CONTEXT_RECOMMENDATION_RE = re.compile(
    r"^(?:recommends?|recommended)\s+(?:that\s+)?(?P<action>.+)$",
    re.IGNORECASE,
)

_COMMITMENT_TRIGGER = (
    r"(?:will(?:\s+not)?|commits?\s+to|has\s+committed\s+to|"
    r"intends?\s+to|plans?\s+to)"
)
_REQUIREMENT_TRIGGER = (
    r"(?:must(?:\s+not)?|shall(?:\s+not)?|is\s+required\s+to|"
    r"are\s+required\s+to|required\s+to)"
)
_DECISION_TRIGGER = (
    r"(?:decided\s+to|agreed\s+to|approved|selected|chose\s+to|resolved\s+to)"
)

_PERCENT_RE = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>%|percent(?:age\s+points?)?)(?![A-Za-z])",
    re.IGNORECASE,
)
_SIMPLE_NUMBER_RE = re.compile(
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<unit>participants|respondents|users|projects|services|cases|requests|applications)\b",
    re.IGNORECASE,
)
_ACTION_RATIO_RE = re.compile(
    r"(?P<value>\b\d+\s+(?:of|out\s+of)\s+\d+\s+"
    r"(?P<subject_noun>(?:identified\s+)?actions?)\s+"
    r"(?:(?:were|are|have\s+been)\s+)?(?:completed|met)\b)",
    re.IGNORECASE,
)

_CURRENCY_RE = re.compile(
    r"(?:(?P<ceiling>up\s+to)\s+)?(?:"
    r"(?P<currency_prefix>GBP|USD|EUR|\N{POUND SIGN}|\N{DOLLAR SIGN}|\N{EURO SIGN})\s*"
    r"(?P<amount_prefix>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale_prefix>thousand|million|billion|k|m|bn)?"
    r"|"
    r"(?P<amount_suffix>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale_suffix>thousand|million|billion|k|m|bn)?\s*"
    r"(?P<currency_suffix>GBP|USD|EUR)"
    r")",
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


class DeterministicExtractionError(ValueError):
    """Raised when deterministic extraction cannot honour its public contract."""


@dataclass(frozen=True, slots=True)
class _Heading:
    text: str
    start: int
    end: int
    line_number: int


@dataclass(frozen=True, slots=True)
class _Line:
    text: str
    start: int
    end: int
    line_number: int


@dataclass(frozen=True, slots=True)
class _Statement:
    block: DocumentBlock
    text: str
    start: int
    end: int
    line_number: int
    context: _Heading | None


@dataclass(frozen=True, slots=True)
class _ResolvedSubject:
    text: str
    subject_type: SubjectType
    confidence: float
    evidence_start: int


@dataclass(frozen=True, slots=True)
class _CandidateDraft:
    block: DocumentBlock
    rule: DeterministicRuleDefinition
    statement_start: int
    statement_end: int
    evidence_start: int
    evidence_end: int
    evidence_status: EvidenceStatus
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: Any
    value_type: ValueType
    qualifiers: dict[str, str | int | float | bool | None | list[str]]
    confidence: float
    review_status: CandidateReviewStatus


@dataclass(frozen=True, slots=True)
class _RuleOutcome:
    candidates: tuple[_CandidateDraft, ...] = ()
    warnings: tuple[str, ...] = ()


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _canonical_value(value: Any) -> str:
    if isinstance(value, NormalizedMoney):
        payload: Any = value.model_dump(mode="json")
    else:
        payload = value
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _stable_digest(parts: list[Any]) -> str:
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _stable_id(prefix: str, parts: list[Any]) -> str:
    return prefix + _stable_digest(parts)


def _trim_span(text: str, start: int, end: int) -> tuple[str, int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return text[start:end], start, end


def _trim_subject_span(text: str, start: int, end: int) -> tuple[str, int, int]:
    value, start, end = _trim_span(text, start, end)
    while value and value[0] in "-\N{BULLET}":
        start += 1
        value, start, end = _trim_span(text, start, end)
    while value and value[-1] in ":;|,-":
        end -= 1
        value, start, end = _trim_span(text, start, end)
    return value, start, end


def _warning(
    code: str, statement: _Statement, rule: DeterministicRuleDefinition
) -> str:
    return (
        f"{code}:{statement.block.block_id}:"
        f"{statement.start}-{statement.end}:{rule.rule_id}"
    )


def _physical_lines(text: str) -> tuple[_Line, ...]:
    lines: list[_Line] = []
    offset = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        without_break = raw_line.rstrip("\r\n")
        leading = len(without_break) - len(without_break.lstrip())
        trailing_end = len(without_break.rstrip())
        if leading < trailing_end:
            lines.append(
                _Line(
                    text=without_break[leading:trailing_end],
                    start=offset + leading,
                    end=offset + trailing_end,
                    line_number=line_number,
                )
            )
        offset += len(raw_line)
    if text and not text.splitlines(keepends=True):
        stripped = text.strip()
        if stripped:
            start = text.index(stripped)
            lines.append(_Line(stripped, start, start + len(stripped), 1))
    return tuple(lines)


def _is_heading(line: _Line) -> bool:
    text = line.text
    if not text or len(text) >= 120:
        return False
    if text.endswith(":"):
        return True
    if text.endswith((".", "!", "?")):
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&/\-]*", text)
    if not words or len(words) > 12:
        return False
    if text.isupper():
        return True
    prose_markers = {
        "will",
        "must",
        "shall",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "recommends",
        "recommended",
        "approved",
        "completed",
    }
    if any(word.casefold() in prose_markers for word in words):
        return False
    title_like = sum(word[0].isupper() for word in words) >= max(1, len(words) - 1)
    return title_like


def _subdivide_line(line: _Line) -> tuple[tuple[str, int, int], ...]:
    if _NUMBERED_RECOMMENDATION_RE.match(line.text):
        return ((line.text, line.start, line.end),)
    segments: list[tuple[str, int, int]] = []
    relative_start = 0
    boundaries = list(
        re.finditer(r"(?<=[.!?])[ \t]+(?=[\"'\[(]?[A-Z0-9])", line.text)
    )
    for boundary in boundaries:
        value, start, end = _trim_span(
            line.text, relative_start, boundary.start()
        )
        if value:
            segments.append((value, line.start + start, line.start + end))
        relative_start = boundary.end()
    value, start, end = _trim_span(line.text, relative_start, len(line.text))
    if value:
        segments.append((value, line.start + start, line.start + end))
    return tuple(segments)


def _segment_block(block: DocumentBlock) -> tuple[_Statement, ...]:
    lines = _physical_lines(block.text)
    headings = {line.line_number: line for line in lines if _is_heading(line)}
    statements: list[_Statement] = []
    for line in lines:
        if line.line_number in headings:
            continue
        previous = headings.get(line.line_number - 1)
        context = None
        if previous is not None:
            subject_text = previous.text[:-1].rstrip() if previous.text.endswith(":") else previous.text
            context = _Heading(
                text=subject_text,
                start=previous.start,
                end=previous.end,
                line_number=previous.line_number,
            )
        for text, start, end in _subdivide_line(line):
            statements.append(
                _Statement(
                    block=block,
                    text=text,
                    start=start,
                    end=end,
                    line_number=line.line_number,
                    context=context,
                )
            )
    return tuple(statements)


def _classify_subject(text: str, *, predicate: str) -> SubjectType:
    normalized = text.casefold()
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


def _subject_is_ambiguous(text: str) -> bool:
    if " / " in text or ";" in text:
        return True
    parts = re.split(r"\s+(?:and|or)\s+", text, flags=re.IGNORECASE)
    if len(parts) < 2:
        return False
    organisation_terms = re.compile(
        r"\b(?:board|council|department|authority|agency|committee|team)\b",
        re.IGNORECASE,
    )
    return sum(bool(organisation_terms.search(part)) for part in parts) > 1


def _resolve_subject(
    statement: _Statement,
    rule: DeterministicRuleDefinition,
    *,
    predicate: str,
    subject_span: tuple[int, int] | None,
    require_budget_type: bool = False,
) -> tuple[_ResolvedSubject | None, str | None]:
    if subject_span is not None:
        text, _, _ = _trim_subject_span(
            statement.text, subject_span[0], subject_span[1]
        )
        confidence = 0.9
        evidence_start = statement.start
    elif statement.context is not None:
        text = statement.context.text
        confidence = 0.7
        evidence_start = statement.context.start
    else:
        return None, _warning("abstained_missing_subject", statement, rule)

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
        return None, _warning("abstained_missing_subject", statement, rule)
    if _subject_is_ambiguous(text):
        return None, _warning("abstained_ambiguous_relationship", statement, rule)
    subject_type = _classify_subject(text, predicate=predicate)
    if require_budget_type and subject_type not in {
        SubjectType.INITIATIVE,
        SubjectType.PROGRAMME,
        SubjectType.POLICY,
        SubjectType.ORGANISATION,
    }:
        return None, _warning("abstained_unsupported_subject_type", statement, rule)
    return (
        _ResolvedSubject(
            text=text,
            subject_type=subject_type,
            confidence=confidence,
            evidence_start=evidence_start,
        ),
        None,
    )


def _draft(
    statement: _Statement,
    rule: DeterministicRuleDefinition,
    subject: _ResolvedSubject,
    *,
    predicate: str,
    raw_value: str,
    normalized_value: Any,
    value_type: ValueType,
    qualifiers: dict[str, str | int | float | bool | None | list[str]] | None = None,
    confidence: float | None = None,
    evidence_status: EvidenceStatus = EvidenceStatus.SUPPORTED,
) -> _CandidateDraft:
    resolved_confidence = subject.confidence if confidence is None else confidence
    if resolved_confidence not in _CONFIDENCE_VALUES:
        raise DeterministicExtractionError("unsupported deterministic confidence band")
    review_status = (
        CandidateReviewStatus.REQUIRED
        if resolved_confidence == 0.5 or evidence_status is EvidenceStatus.AMBIGUOUS
        else CandidateReviewStatus.NOT_REQUIRED
    )
    return _CandidateDraft(
        block=statement.block,
        rule=rule,
        statement_start=statement.start,
        statement_end=statement.end,
        evidence_start=subject.evidence_start,
        evidence_end=statement.end,
        evidence_status=evidence_status,
        subject_text=subject.text,
        subject_type=subject.subject_type,
        predicate=predicate,
        raw_value=raw_value,
        normalized_value=normalized_value,
        value_type=value_type,
        qualifiers={} if qualifiers is None else qualifiers,
        confidence=resolved_confidence,
        review_status=review_status,
    )


def _match_recommendation(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    numbered = _NUMBERED_RECOMMENDATION_RE.match(statement.text)
    if numbered is not None:
        label = numbered.group("label")
        action, _, _ = _trim_span(
            statement.text, *numbered.span("action")
        )
        if not action:
            return _RuleOutcome(
                warnings=(_warning("abstained_ambiguous_relationship", statement, rule),)
            )
        subject = _ResolvedSubject(
            text=label,
            subject_type=SubjectType.RECOMMENDATION,
            confidence=0.9,
            evidence_start=statement.start,
        )
        return _RuleOutcome(
            candidates=(
                _draft(
                    statement,
                    rule,
                    subject,
                    predicate="recommendation",
                    raw_value=action,
                    normalized_value=_normalize_whitespace(action),
                    value_type=ValueType.STRING,
                    qualifiers={"recommendation_id": int(numbered.group("identifier"))},
                ),
            )
        )

    explicit = _EXPLICIT_RECOMMENDATION_RE.match(statement.text)
    contextual = _CONTEXT_RECOMMENDATION_RE.match(statement.text)
    if explicit is None and contextual is None:
        return _RuleOutcome()
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject_span = explicit.span("subject") if explicit is not None else None
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate="recommendation",
        subject_span=subject_span,
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    action, _, _ = _trim_span(statement.text, *match.span("action"))
    if not action:
        return _RuleOutcome(
            warnings=(_warning("abstained_ambiguous_relationship", statement, rule),)
        )
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate="recommendation",
                raw_value=action,
                normalized_value=_normalize_whitespace(action),
                value_type=ValueType.STRING,
            ),
        )
    )


def _match_actor_trigger(
    statement: _Statement,
    rule: DeterministicRuleDefinition,
    *,
    predicate: str,
    trigger: str,
) -> _RuleOutcome:
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
        return _RuleOutcome()
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject_span = explicit.span("subject") if explicit is not None else None
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate=predicate,
        subject_span=subject_span,
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    raw_value, _, _ = _trim_span(statement.text, *match.span("value"))
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate=predicate,
                raw_value=raw_value,
                normalized_value=_normalize_whitespace(raw_value),
                value_type=ValueType.STRING,
            ),
        )
    )


def _match_commitment(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    return _match_actor_trigger(
        statement,
        rule,
        predicate="commitment",
        trigger=_COMMITMENT_TRIGGER,
    )


def _match_requirement(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    return _match_actor_trigger(
        statement,
        rule,
        predicate="requirement",
        trigger=_REQUIREMENT_TRIGGER,
    )


def _match_decision(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    if re.search(
        r"\b(?:proposal|proposed|option)\b.*\b(?:approve|select|choose)\b",
        statement.text,
        flags=re.IGNORECASE,
    ):
        return _RuleOutcome()
    return _match_actor_trigger(
        statement,
        rule,
        predicate="decision",
        trigger=_DECISION_TRIGGER,
    )


def _match_risk(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    risk_trigger = (
        r"(?:(?:identified\s+)?risk\s+(?:of|that)|identified\s+risk\s*:|"
        r"threat\s+of|adverse\s+impact)"
    )
    if not re.search(risk_trigger, statement.text, flags=re.IGNORECASE):
        return _RuleOutcome()

    if statement.block.block_type is BlockType.TABLE:
        table = re.match(
            rf"^(?P<subject>[^|]{{1,100}}?)\s*\|\s*(?P<value>{risk_trigger}.+)$",
            statement.text,
            flags=re.IGNORECASE,
        )
        if table is None:
            return _RuleOutcome(
                warnings=(
                    _warning("skipped_flattened_table_relationship", statement, rule),
                )
            )
        subject_text, _, _ = _trim_subject_span(
            statement.text, *table.span("subject")
        )
        if not subject_text or _subject_is_ambiguous(subject_text):
            return _RuleOutcome(
                warnings=(
                    _warning("skipped_flattened_table_relationship", statement, rule),
                )
            )
        subject = _ResolvedSubject(
            text=subject_text,
            subject_type=_classify_subject(subject_text, predicate="risk"),
            confidence=0.5,
            evidence_start=statement.start,
        )
        raw_value, _, _ = _trim_span(statement.text, *table.span("value"))
        return _RuleOutcome(
            candidates=(
                _draft(
                    statement,
                    rule,
                    subject,
                    predicate="risk",
                    raw_value=raw_value,
                    normalized_value=_normalize_whitespace(raw_value),
                    value_type=ValueType.STRING,
                    confidence=0.5,
                    evidence_status=EvidenceStatus.AMBIGUOUS,
                ),
            )
        )

    patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+(?P<value>(?:may|could|will)\s+have\s+"
            r"an?\s+adverse\s+impact.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^(?P<subject>.+?)\s+(?P<value>(?:faces?\s+)?(?:an?\s+)?{risk_trigger}.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^(?P<subject>.+?)\s*:\s*(?P<value>{risk_trigger}.+)$",
            re.IGNORECASE,
        ),
    )
    explicit = next((pattern.match(statement.text) for pattern in patterns if pattern.match(statement.text)), None)
    contextual = re.match(
        rf"^(?P<value>{risk_trigger}.+)$",
        statement.text,
        flags=re.IGNORECASE,
    )
    if explicit is None and contextual is None:
        return _RuleOutcome(
            warnings=(_warning("abstained_missing_subject", statement, rule),)
        )
    match = explicit if explicit is not None else contextual
    assert match is not None
    subject_span = explicit.span("subject") if explicit is not None else None
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate="risk",
        subject_span=subject_span,
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    raw_value, _, _ = _trim_span(statement.text, *match.span("value"))
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate="risk",
                raw_value=raw_value,
                normalized_value=_normalize_whitespace(raw_value),
                value_type=ValueType.STRING,
            ),
        )
    )


def _snake_case_metric_name(subject: str, *, percentage: bool) -> str:
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9]+", subject)
        if word.casefold() not in {"a", "an", "the", "of", "for"}
    ]
    if not words:
        return ""
    if percentage and words[-1] not in {"rate", "percentage", "share"}:
        words.append("percentage")
    return "_".join(words[:10])


def _extract_period(text: str) -> str | None:
    month_match = _MONTH_PERIOD_RE.search(text)
    if month_match is not None:
        return f"{month_match.group(2)}-{_MONTHS[month_match.group(1).casefold()]}"
    year_match = _YEAR_PERIOD_RE.search(text)
    if year_match is not None:
        return year_match.group(1)
    return None


def _metric_subject_for_percentage(
    statement: _Statement, value_match: re.Match[str]
) -> tuple[tuple[int, int] | None, str | None]:
    after_value = statement.text[value_match.end() :]
    population_match = re.match(
        r"\s+of\s+(?P<population>[A-Za-z][A-Za-z0-9 '\-/]{0,80}?)"
        r"(?=\s+(?:were|was|are|is|had|have|reported|used|completed|met|said|received|adopted)\b)",
        after_value,
        flags=re.IGNORECASE,
    )
    if population_match is not None:
        start = value_match.end() + population_match.start("population")
        end = value_match.end() + population_match.end("population")
        population, start, end = _trim_span(statement.text, start, end)
        return (start, end), population

    before_value = statement.text[: value_match.start()]
    named_measure = re.match(
        r"^(?P<subject>.+?)\s+(?:was|were|is|are|reached|stood\s+at|measured)\s*$",
        before_value,
        flags=re.IGNORECASE,
    )
    if named_measure is not None:
        return named_measure.span("subject"), None
    return None, None


def _match_metric(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    if _CURRENCY_RE.search(statement.text) or _ACTION_RATIO_RE.search(statement.text):
        return _RuleOutcome()
    percentage_matches = list(_PERCENT_RE.finditer(statement.text))
    if len(percentage_matches) > 1:
        return _RuleOutcome(
            warnings=(_warning("abstained_multiple_values", statement, rule),)
        )
    if percentage_matches:
        value_match = percentage_matches[0]
        subject_span, population = _metric_subject_for_percentage(
            statement, value_match
        )
        subject, warning = _resolve_subject(
            statement,
            rule,
            predicate="metric",
            subject_span=subject_span,
        )
        if subject is None:
            return _RuleOutcome(warnings=(warning,) if warning else ())
        subject = _ResolvedSubject(
            text=subject.text,
            subject_type=SubjectType.METRIC,
            confidence=subject.confidence,
            evidence_start=subject.evidence_start,
        )
        metric_name = _snake_case_metric_name(subject.text, percentage=True)
        if not metric_name:
            return _RuleOutcome(
                warnings=(_warning("abstained_missing_subject", statement, rule),)
            )
        raw_value = value_match.group(0)
        qualifiers: dict[str, str | int | float | bool | None | list[str]] = {
            "metric_name": metric_name,
            "unit": "percent",
        }
        if population is not None:
            qualifiers["population"] = population
        period = _extract_period(statement.text)
        if period is not None:
            qualifiers["period"] = period
        return _RuleOutcome(
            candidates=(
                _draft(
                    statement,
                    rule,
                    subject,
                    predicate="metric",
                    raw_value=raw_value,
                    normalized_value=float(Decimal(value_match.group("number"))),
                    value_type=ValueType.PERCENTAGE,
                    qualifiers=qualifiers,
                ),
            )
        )

    number_matches = list(_SIMPLE_NUMBER_RE.finditer(statement.text))
    if len(number_matches) > 1:
        return _RuleOutcome(
            warnings=(_warning("abstained_multiple_values", statement, rule),)
        )
    if not number_matches:
        return _RuleOutcome()
    value_match = number_matches[0]
    unit_text = value_match.group("unit")
    unit_start, unit_end = value_match.span("unit")
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate="metric",
        subject_span=(unit_start, unit_end),
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    subject = _ResolvedSubject(
        text=subject.text,
        subject_type=SubjectType.METRIC,
        confidence=subject.confidence,
        evidence_start=subject.evidence_start,
    )
    number_text = value_match.group("number").replace(",", "")
    normalized_number: int | float
    if "." in number_text:
        normalized_number = float(Decimal(number_text))
    else:
        normalized_number = int(number_text)
    qualifiers = {
        "metric_name": _snake_case_metric_name(unit_text + " count", percentage=False),
        "unit": unit_text.casefold(),
        "population": unit_text,
    }
    period = _extract_period(statement.text)
    if period is not None:
        qualifiers["period"] = period
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate="metric",
                raw_value=value_match.group(0),
                normalized_value=normalized_number,
                value_type=ValueType.NUMBER,
                qualifiers=qualifiers,
            ),
        )
    )


def _currency_and_amount(match: re.Match[str]) -> tuple[str, Decimal]:
    currency_token = match.group("currency_prefix") or match.group("currency_suffix")
    amount_token = match.group("amount_prefix") or match.group("amount_suffix")
    scale_token = match.group("scale_prefix") or match.group("scale_suffix")
    currency = {
        "\N{POUND SIGN}": "GBP",
        "\N{DOLLAR SIGN}": "USD",
        "\N{EURO SIGN}": "EUR",
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
        raise DeterministicExtractionError("invalid bounded monetary amount") from error
    return currency, amount


def _budget_subject_span(
    statement: _Statement, amount_match: re.Match[str]
) -> tuple[int, int] | None:
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
            return match.span("subject")

    suffix = statement.text[amount_match.end() :]
    trailing = re.search(
        r"\b(?:allocated|granted|provided|committed|invested)\s+to\s+"
        r"(?P<subject>[^.;]+)",
        suffix,
        flags=re.IGNORECASE,
    )
    if trailing is not None:
        return (
            amount_match.end() + trailing.start("subject"),
            amount_match.end() + trailing.end("subject"),
        )
    return None


def _match_budget(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    if not re.search(
        r"\bbudget\b|\bfunding\b|\bfunded\b|\binvestment\b|\binvested\b|"
        r"\ballocation\b|\ballocated\b",
        statement.text,
        flags=re.IGNORECASE,
    ):
        return _RuleOutcome()
    amount_matches = list(_CURRENCY_RE.finditer(statement.text))
    if not amount_matches:
        return _RuleOutcome()
    if len(amount_matches) > 1:
        return _RuleOutcome(
            warnings=(_warning("abstained_multiple_values", statement, rule),)
        )
    amount_match = amount_matches[0]
    approximate_prefix = statement.text[
        max(0, amount_match.start() - 24) : amount_match.start()
    ]
    if re.search(
        r"\b(?:about|approximately|around|roughly|circa)\s*$",
        approximate_prefix,
        flags=re.IGNORECASE,
    ):
        return _RuleOutcome(
            warnings=(
                _warning("abstained_ambiguous_relationship", statement, rule),
            )
        )
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate="budget",
        subject_span=_budget_subject_span(statement, amount_match),
        require_budget_type=True,
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    currency, amount = _currency_and_amount(amount_match)
    lowered = statement.text.casefold()
    qualifiers: dict[str, str | int | float | bool | None | list[str]] = {}
    if amount_match.group("ceiling") is not None:
        qualifiers["budget_status"] = "ceiling"
    elif re.search(r"\bapproved\b", lowered):
        qualifiers["budget_status"] = "approved"
    elif re.search(r"\bcommitted\b", lowered):
        qualifiers["budget_status"] = "committed"
    elif re.search(r"\bproposed\b", lowered):
        qualifiers["budget_status"] = "proposed"
    raw_value = amount_match.group(0)
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate="budget",
                raw_value=raw_value,
                normalized_value=NormalizedMoney(amount=amount, currency=currency),
                value_type=ValueType.MONEY,
                qualifiers=qualifiers,
            ),
        )
    )


def _action_like_subject(text: str) -> bool:
    return bool(
        re.search(
            r"\baction\b|\btask\b|\bmilestone\b|\bworkstream\b|"
            r"\bdeliverable\b|\brecommendation\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _action_id(text: str) -> str | None:
    match = re.search(
        r"\bAction\s+([A-Za-z0-9][A-Za-z0-9-]*)\b", text, flags=re.IGNORECASE
    )
    return match.group(1) if match is not None else None


def _match_action_status(
    statement: _Statement, rule: DeterministicRuleDefinition
) -> _RuleOutcome:
    ratio = _ACTION_RATIO_RE.search(statement.text)
    if ratio is not None:
        prefix_text, prefix_start, prefix_end = _trim_subject_span(
            statement.text, 0, ratio.start()
        )
        if prefix_text and _action_like_subject(prefix_text):
            subject_span: tuple[int, int] | None = (prefix_start, prefix_end)
        else:
            subject_span = ratio.span("subject_noun")
        subject, warning = _resolve_subject(
            statement,
            rule,
            predicate="action_status",
            subject_span=subject_span,
        )
        if subject is None:
            return _RuleOutcome(warnings=(warning,) if warning else ())
        raw_value = ratio.group("value")
        qualifiers: dict[str, str | int | float | bool | None | list[str]] = {}
        action_id = _action_id(statement.text)
        if action_id is not None:
            qualifiers["action_id"] = action_id
        return _RuleOutcome(
            candidates=(
                _draft(
                    statement,
                    rule,
                    subject,
                    predicate="action_status",
                    raw_value=raw_value,
                    normalized_value=_normalize_whitespace(raw_value),
                    value_type=ValueType.STATUS,
                    qualifiers=qualifiers,
                ),
            )
        )

    explicit = re.match(
        r"^(?P<subject>.+?)\s+(?:(?:is|are|was|were|remains?|has\s+been|"
        r"have\s+been)\s+)?(?P<value>not\s+started|in\s+progress|on\s+track|"
        r"delayed|completed|delivered|met)\b",
        statement.text,
        flags=re.IGNORECASE,
    )
    contextual = re.match(
        r"^(?P<value>not\s+started|in\s+progress|on\s+track|delayed|"
        r"completed|delivered|met)\b",
        statement.text,
        flags=re.IGNORECASE,
    )
    if explicit is None and contextual is None:
        return _RuleOutcome()
    if explicit is not None:
        subject_text, _, _ = _trim_subject_span(
            statement.text, *explicit.span("subject")
        )
        if not _action_like_subject(subject_text):
            return _RuleOutcome()
        match = explicit
        subject_span = explicit.span("subject")
    else:
        assert contextual is not None
        if statement.context is None or not _action_like_subject(statement.context.text):
            return _RuleOutcome()
        match = contextual
        subject_span = None
    subject, warning = _resolve_subject(
        statement,
        rule,
        predicate="action_status",
        subject_span=subject_span,
    )
    if subject is None:
        return _RuleOutcome(warnings=(warning,) if warning else ())
    raw_value = match.group("value")
    qualifiers = {}
    action_id = _action_id(subject.text)
    if action_id is not None:
        qualifiers["action_id"] = action_id
    return _RuleOutcome(
        candidates=(
            _draft(
                statement,
                rule,
                subject,
                predicate="action_status",
                raw_value=raw_value,
                normalized_value=_normalize_whitespace(raw_value),
                value_type=ValueType.STATUS,
                qualifiers=qualifiers,
            ),
        )
    )


_MATCHERS: dict[
    str,
    Callable[[_Statement, DeterministicRuleDefinition], _RuleOutcome],
] = {
    "recommendation": _match_recommendation,
    "commitment": _match_commitment,
    "requirement": _match_requirement,
    "decision": _match_decision,
    "risk": _match_risk,
    "metric": _match_metric,
    "budget": _match_budget,
    "action_status": _match_action_status,
}


def _draft_sort_key(draft: _CandidateDraft) -> tuple[int, int, int, str]:
    signature = _stable_digest(
        [
            draft.subject_text,
            draft.subject_type.value,
            draft.predicate,
            _canonical_value(draft.normalized_value),
            dict(sorted(draft.qualifiers.items())),
            draft.evidence_start,
            draft.evidence_end,
        ]
    )
    return (
        draft.block.sequence,
        draft.statement_start,
        draft.rule.priority,
        signature,
    )


def _semantic_provenance_key(draft: _CandidateDraft) -> str:
    return _canonical_value(
        [
            draft.block.block_id,
            draft.statement_start,
            draft.statement_end,
            draft.rule.rule_id,
            draft.subject_text,
            draft.subject_type.value,
            draft.predicate,
            _canonical_value(draft.normalized_value),
            dict(sorted(draft.qualifiers.items())),
            draft.evidence_start,
            draft.evidence_end,
            draft.evidence_status.value,
        ]
    )


def extract_deterministic_candidates(
    document: ParsedDocument,
) -> CandidateExtractionResult:
    """Transform one ParsedDocument into one deterministic candidate result."""
    if not isinstance(document, ParsedDocument):
        raise DeterministicExtractionError("document must be a validated ParsedDocument")
    source_id = document.source_id
    if source_id is None or not source_id.strip() or source_id != source_id.strip():
        raise DeterministicExtractionError("ParsedDocument source_id must be non-empty")

    family_value = document.metadata.get("document_family")
    document_family = (
        family_value.strip()
        if isinstance(family_value, str) and family_value.strip()
        else document.document_id
    )
    rules = tuple(
        rule
        for rule in get_deterministic_rule_inventory()
        if rule.produces_candidates
    )
    drafts: list[_CandidateDraft] = []
    warnings: set[str] = set()
    for block in sorted(document.blocks, key=lambda item: item.sequence):
        if block.block_type not in _ELIGIBLE_BLOCK_TYPES:
            continue
        for statement in _segment_block(block):
            for rule in rules:
                assert rule.predicate is not None
                outcome = _MATCHERS[rule.predicate](statement, rule)
                warnings.update(outcome.warnings)
                for candidate in outcome.candidates:
                    evidence_text = block.text[
                        candidate.evidence_start : candidate.evidence_end
                    ]
                    if len(evidence_text) > _MAX_EVIDENCE_LENGTH:
                        warnings.add(
                            _warning(
                                "abstained_evidence_too_long", statement, rule
                            )
                        )
                        continue
                    if (
                        candidate.raw_value not in evidence_text
                        or candidate.subject_text not in evidence_text
                    ):
                        raise DeterministicExtractionError(
                            "candidate source spans are not exact block substrings"
                        )
                    drafts.append(candidate)

    ordered_drafts = sorted(drafts, key=_draft_sort_key)
    unique_drafts: list[_CandidateDraft] = []
    seen_candidates: set[str] = set()
    for candidate in ordered_drafts:
        key = _semantic_provenance_key(candidate)
        if key in seen_candidates:
            continue
        seen_candidates.add(key)
        unique_drafts.append(candidate)

    evidence_payloads: dict[
        tuple[str, str, str, int, int, str], dict[str, Any]
    ] = {}
    fact_payloads: list[dict[str, Any]] = []
    for candidate in unique_drafts:
        location = candidate.block.location
        evidence_key = (
            candidate.block.block_id,
            location.location_type.value,
            location.location_value,
            candidate.evidence_start,
            candidate.evidence_end,
            candidate.evidence_status.value,
        )
        evidence_id = _stable_id(
            "DET-EVID-",
            [
                source_id,
                candidate.block.block_id,
                location.location_type.value,
                location.location_value,
                candidate.evidence_start,
                candidate.evidence_end,
                candidate.evidence_status.value,
            ],
        )
        evidence_payloads.setdefault(
            evidence_key,
            {
                "evidence_id": evidence_id,
                "source_id": source_id,
                "block_id": candidate.block.block_id,
                "location_type": location.location_type,
                "location_value": location.location_value,
                "text_excerpt": candidate.block.text[
                    candidate.evidence_start : candidate.evidence_end
                ],
                "evidence_status": candidate.evidence_status,
            },
        )
        qualifiers = dict(sorted(candidate.qualifiers.items()))
        candidate_id = _stable_id(
            "DET-CAND-",
            [
                DETERMINISTIC_BASELINE_VERSION,
                source_id,
                candidate.block.block_id,
                candidate.rule.rule_id,
                candidate.statement_start,
                candidate.statement_end,
                candidate.subject_text,
                candidate.subject_type.value,
                candidate.predicate,
                _canonical_value(candidate.normalized_value),
                qualifiers,
                [evidence_id],
            ],
        )
        fact_payloads.append(
            {
                "candidate_id": candidate_id,
                "source_id": source_id,
                "document_family": document_family,
                "subject_text": candidate.subject_text,
                "subject_type": candidate.subject_type,
                "predicate": candidate.predicate,
                "raw_value": candidate.raw_value,
                "normalized_value": candidate.normalized_value,
                "value_type": candidate.value_type,
                "qualifiers": qualifiers,
                "evidence_ids": [evidence_id],
                "confidence": candidate.confidence,
                "review_status": candidate.review_status,
                "extraction_method": ExtractionMethod.DETERMINISTIC,
                "warnings": [],
            }
        )

    ordered_evidence = [
        evidence_payloads[key]
        for key in sorted(
            evidence_payloads,
            key=lambda key: (
                next(
                    block.sequence
                    for block in document.blocks
                    if block.block_id == key[0]
                ),
                key[3],
                key[4],
                key[5],
                evidence_payloads[key]["evidence_id"],
            ),
        )
    ]
    payload = {
        "schema_version": "0.1",
        "batch_id": _stable_id(
            "DET-BATCH-",
            [
                DETERMINISTIC_BASELINE_VERSION,
                source_id,
                document.checksum_sha256,
            ],
        ),
        "source_ids": [source_id],
        "entities": [],
        "evidence_references": ordered_evidence,
        "candidate_facts": fact_payloads,
        "warnings": sorted(warnings),
    }
    try:
        return CandidateExtractionResult.model_validate(payload)
    except ValidationError as error:
        raise DeterministicExtractionError(
            "deterministic output violates CandidateExtractionResult schema 0.1"
        ) from error


def canonical_candidate_result_json(result: CandidateExtractionResult) -> str:
    """Serialize one validated candidate result as canonical UTF-8 JSON text."""
    if not isinstance(result, CandidateExtractionResult):
        raise DeterministicExtractionError(
            "result must be a validated CandidateExtractionResult"
        )
    payload = result.model_dump(mode="json")
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


__all__ = [
    "DETERMINISTIC_BASELINE_VERSION",
    "DeterministicExtractionError",
    "extract_deterministic_candidates",
    "canonical_candidate_result_json",
]
