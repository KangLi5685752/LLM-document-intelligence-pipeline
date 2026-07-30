"""Pure, additive deterministic-baseline-v0.4 candidate extraction."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_v0_2 import (
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.extraction.deterministic_v0_3 import (
    extract_deterministic_candidates_v0_3,
)
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    EvidenceStatus,
    SubjectType,
)
from document_intelligence.ingestion.models import BlockType, DocumentBlock, ParsedDocument


DETERMINISTIC_BASELINE_VERSION = "deterministic-baseline-v0.4"

_FIRST_PERSON_RE = re.compile(r"^(?:we|our)\b", re.IGNORECASE)
_GENERIC_GOVERNMENT_RE = re.compile(r"^(?:the\s+)?government$", re.IGNORECASE)
_ORGANISATION_HEAD_RE = re.compile(
    r"\b(?:administration|agency|association|authority|board|commission|"
    r"company|corporation|council|department|foundation|government|group|"
    r"institute|limited|ministry|office|secretariat|service|university)\b",
    re.IGNORECASE,
)
_EXPLICIT_ACTOR_HEAD_RE = re.compile(
    r"\b(?:administration|agency|association|authority|board|commission|"
    r"company|corporation|council|department|foundation|government|group|"
    r"initiative|institute|limited|ministry|office|organisation|organization|"
    r"program|programme|project|secretariat|service|team|unit|university)\b",
    re.IGNORECASE,
)
_EXPLICIT_NAMED_ACTOR_RE = re.compile(
    r"^(?:The\s+)?[A-Z][A-Za-z&'-]*"
    r"(?:\s+(?:[A-Z][A-Za-z&'-]*|of|the|and|for)){0,11}$"
)
_GENERIC_ACTOR_SUBJECT_RE = re.compile(
    r"^(?:the\s+)?(?:agenc(?:y|ies)|authorit(?:y|ies)|boards?|commissions?|"
    r"councils?|departments?|ministries|offices?|organisations?|organizations?|"
    r"programmes?|programs?|projects?|regulators?|services?|teams?|units?)$",
    re.IGNORECASE,
)
_AUTHORING_ACTOR_KEY_RE = re.compile(
    r"(?:^|_)(?:author|authoring_body|issuing_body|responsible_department|"
    r"document_author|authored_by|issued_by)(?:$|_)",
    re.IGNORECASE,
)
_ROLE_AWARE_FRONT_MATTER_RE = re.compile(
    r"\b(?i:issued|published|authored|prepared|presented)\s+by\s+(?:the\s+)?"
    r"(?P<actor>[A-Z][A-Za-z&'-]*"
    r"(?:\s+(?:[A-Z][A-Za-z&'-]*|of|the|and|for)){1,11})"
    r"(?=\s*(?:[.;,]|$))"
)
_SOFTWARE_RE = re.compile(
    r"(?:microsoft|adobe|libreoffice|acrobat|word\b)",
    re.IGNORECASE,
)
_PERSON_NAME_RE = re.compile(
    r"^[A-Z][A-Za-z'-]+,\s*[A-Z][A-Za-z'-]+(?:\s|\(|$)"
)
_AFFIRMATIVE_WILL_RE = re.compile(r"^will\s+", re.IGNORECASE)
_LEADING_SEMANTIC_MODIFIER_RE = re.compile(
    r"^(?P<modifier>now|also|immediately|still|only)\b\s*", re.IGNORECASE
)
_NEGATED_WILL_RE = re.compile(r"^will\s+not\b", re.IGNORECASE)
_INTENT_OR_PLAN_RE = re.compile(
    r"^(?:intend(?:s)?\s+to|plan(?:s)?\s+to|commit(?:s)?\s+to|"
    r"has\s+committed\s+to)\b",
    re.IGNORECASE,
)
_SAFE_WRAPPER_RE = re.compile(
    r"^take\s+forward\s+the\s+recommendation\s+to\s+(?P<action>.+)$",
    re.IGNORECASE,
)
_TERMINAL_INCOMPLETE_RE = re.compile(
    r"\b(?:and|or|the|a|an|to|of|for|with|that|which|who|into|from|by)\s*[.,;:]?$",
    re.IGNORECASE,
)
_REPORTED_SPEECH_RE = re.compile(
    r"(?:\baccording\s+to\b[^.!?\n]{0,100},|"
    r"\b(?:said|stated|reported|wrote|announced|claimed|argued|told)\b"
    r"[^.!?\n]{0,100}(?:that|[:,]))\s*$",
    re.IGNORECASE,
)
_ATTRIBUTED_SUBJECT_RE = re.compile(
    r"(?:^according\s+to\b[^.!?\n]{1,100},\s*|"
    r"^.{1,100}\b(?:said|stated|reported|wrote|announced|claimed|argued|told)\b"
    r"[^.!?\n]{0,40}(?:that|[:,])\s*)"
    r"[\"'\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    r"\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}]?\s*"
    r"(?:we|our|(?:the\s+)?government)\b",
    re.IGNORECASE,
)
_QUOTED_SUBJECT_RE = re.compile(
    r"[\"'\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    r"\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}]\s*"
    r"(?:we|our|(?:the\s+)?government)\b",
    re.IGNORECASE,
)
_QUOTED_HISTORY_LINE_RE = re.compile(r"^\s*(?:>|\|)")
_NUMBERED_OR_BULLET_LINE_RE = re.compile(
    r"^(?:\d{1,3}[.)]|[-*\N{BULLET}])\s+"
)
_COMMON_ABBREVIATIONS = frozenset(
    {
        "dr",
        "e.g",
        "etc",
        "i.e",
        "mr",
        "mrs",
        "ms",
        "no",
        "prof",
        "st",
        "u.k",
        "u.s",
        "vs",
    }
)
_ELIGIBLE_ACTION_VERBS = frozenset(
    {
        "accept",
        "adopt",
        "appoint",
        "build",
        "commit",
        "create",
        "deliver",
        "deploy",
        "develop",
        "establish",
        "expand",
        "fund",
        "implement",
        "invest",
        "launch",
        "maintain",
        "open",
        "procure",
        "provide",
        "publish",
        "reform",
        "require",
        "scale",
        "seek",
        "set",
        "start",
        "support",
        "suspend",
        "take",
        "work",
    }
)
_CANDIDATE_BLOCK_TYPES = {
    BlockType.PAGE_TEXT,
    BlockType.SLIDE_TITLE,
    BlockType.SHAPE_TEXT,
    BlockType.TABLE,
    BlockType.EMAIL_BODY,
}
_WHITESPACE_RE = re.compile(r"\s+")


class DeterministicExtractionV04Error(RuntimeError):
    """Raised when v0.4 cannot produce a schema-valid result."""


@dataclass(frozen=True, slots=True)
class DeterministicV04Trace:
    """Aggregate source-independent operations applied to one document."""

    actor_resolution_methods: tuple[tuple[str, int], ...]
    value_normalisation_operations: tuple[tuple[str, int], ...]
    preserved_semantic_modifiers: tuple[tuple[str, int], ...]
    rejected_recovery_reasons: tuple[tuple[str, int], ...]
    candidate_traces: tuple["DeterministicV04CandidateTrace", ...]
    recovered_parent_candidate_count: int
    transformed_parent_candidate_count: int
    duplicate_candidate_count: int


@dataclass(frozen=True, slots=True)
class DeterministicV04CandidateTrace:
    """One commitment's deterministic parent and transformation provenance."""

    candidate_id: str
    source_id: str
    evidence_block_id: str
    parent_version: str
    parent_candidate_id: str
    parent_status: str
    original_subject: str
    final_subject: str
    actor_resolution_method: str
    actor_evidence_category: str
    original_raw_value: str
    final_raw_value: str
    original_normalized_value: Any
    final_normalized_value: Any
    value_normalisation_operation: str
    semantic_transformation_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _TrustedActor:
    value: str
    actor_kind: str
    method: str
    evidence_category: str


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(_canonical(parts).encode("utf-8")).hexdigest().upper()


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def _trim_actor(value: str) -> str:
    normalized = _normalize_whitespace(value).strip(" \t\r\n,;:.()[]{}")
    return re.sub(r"^(?:the\s+)", "", normalized, flags=re.IGNORECASE)


def _eligible_organisation(value: str) -> str | None:
    candidate = _trim_actor(value)
    if (
        not 2 <= len(candidate) <= 120
        or _SOFTWARE_RE.search(candidate)
        or _PERSON_NAME_RE.search(candidate)
        or len(candidate.split()) < 2
        or _TERMINAL_INCOMPLETE_RE.search(candidate)
    ):
        return None
    if candidate.isupper() and len(candidate.replace(" ", "")) <= 12:
        return None
    if not _ORGANISATION_HEAD_RE.search(candidate):
        return None
    return candidate


def _eligible_statement_actor(fact: CandidateFact) -> bool:
    """Recognise only a complete bounded actor-like statement subject."""

    subject = _normalize_whitespace(fact.subject_text)
    if (
        not 2 <= len(subject) <= 120
        or any(character in subject for character in ',:;"“”‘’()[]{}')
        or _TERMINAL_INCOMPLETE_RE.search(subject)
    ):
        return False
    if _GENERIC_ACTOR_SUBJECT_RE.fullmatch(subject):
        return True
    return (
        _EXPLICIT_NAMED_ACTOR_RE.fullmatch(subject) is not None
        and _EXPLICIT_ACTOR_HEAD_RE.search(subject) is not None
    )


def _trusted_document_actors(document: ParsedDocument) -> tuple[_TrustedActor, ...]:
    found: dict[tuple[str, str], _TrustedActor] = {}

    def add(value: str, method: str, evidence_category: str) -> None:
        actor = _eligible_organisation(value)
        if actor is None:
            return
        kind = "government" if "government" in actor.casefold() else "organisation"
        key = (actor.casefold(), kind)
        found.setdefault(
            key,
            _TrustedActor(actor, kind, method, evidence_category),
        )

    for value in document.authors_or_senders:
        add(value, "authors_or_senders", "direct_authorship_field")
    for key, value in sorted(document.metadata.items()):
        if not _AUTHORING_ACTOR_KEY_RE.search(key) or not isinstance(value, str):
            continue
        add(value, "authoring_metadata", "explicit_authoring_role")

    for block in sorted(document.blocks, key=lambda item: item.sequence)[:4]:
        if block.block_type not in _CANDIDATE_BLOCK_TYPES | {BlockType.METADATA}:
            continue
        for match in _ROLE_AWARE_FRONT_MATTER_RE.finditer(
            _normalize_whitespace(block.text[:2000])
        ):
            add(
                match.group("actor"),
                "role_aware_front_matter",
                "explicit_authorship_grammar",
            )
    return tuple(sorted(found.values(), key=lambda item: (item.value.casefold(), item.method)))


def _bounded_statement_context(
    fact: CandidateFact,
    reference: CandidateEvidenceReference,
    block: DocumentBlock,
) -> tuple[str, int]:
    occurrences = [
        match.start()
        for match in re.finditer(re.escape(reference.text_excerpt), block.text)
    ]
    if len(occurrences) != 1:
        return reference.text_excerpt, 0
    excerpt_start = occurrences[0]
    local_anchor = reference.text_excerpt.find(fact.subject_text)
    if local_anchor < 0:
        local_anchor = reference.text_excerpt.find(fact.raw_value)
    if local_anchor < 0:
        local_anchor = 0
    absolute_anchor = excerpt_start + local_anchor
    context_start = max(0, absolute_anchor - 180)
    context_end = min(
        len(block.text),
        excerpt_start + len(reference.text_excerpt) + 100,
    )
    return block.text[context_start:context_end], absolute_anchor - context_start


def _is_quoted_or_reported_context(
    fact: CandidateFact,
    reference: CandidateEvidenceReference,
    block: DocumentBlock,
) -> bool:
    subject = _normalize_whitespace(fact.subject_text)
    if _ATTRIBUTED_SUBJECT_RE.search(subject) or _QUOTED_SUBJECT_RE.search(subject):
        return True
    context, anchor = _bounded_statement_context(fact, reference, block)
    before = context[:anchor]
    from_anchor = context[anchor:]
    line_start = context.rfind("\n", 0, anchor) + 1
    line_end = context.find("\n", anchor)
    if line_end < 0:
        line_end = len(context)
    line = context[line_start:line_end]
    if _QUOTED_HISTORY_LINE_RE.match(line):
        return True
    if re.search(
        r"[\"\N{LEFT DOUBLE QUOTATION MARK}\N{LEFT SINGLE QUOTATION MARK}]\s*$",
        before[-12:],
    ):
        return True
    subject_window = from_anchor[:120]
    if _QUOTED_SUBJECT_RE.search(subject_window):
        return True
    bounded_prefix = before[-180:]
    if _REPORTED_SPEECH_RE.search(bounded_prefix):
        return True
    return re.search(
        r"\b(?:wrote|said|stated|reported):\s*$",
        bounded_prefix,
        re.IGNORECASE,
    ) is not None


def _resolve_actor(
    fact: CandidateFact,
    actors: tuple[_TrustedActor, ...],
    *,
    quoted_or_reported: bool,
) -> tuple[str, SubjectType, str, str]:
    subject = _normalize_whitespace(fact.subject_text)
    is_first_person = _FIRST_PERSON_RE.fullmatch(subject) is not None
    is_generic_government = _GENERIC_GOVERNMENT_RE.fullmatch(subject) is not None
    if quoted_or_reported:
        return (
            fact.subject_text,
            fact.subject_type,
            "quotation_or_reported_speech_blocked",
            "quotation_or_reported_speech",
        )
    if not is_first_person and not is_generic_government:
        if _eligible_statement_actor(fact):
            return (
                fact.subject_text,
                fact.subject_type,
                "explicit_statement_actor",
                "explicit_statement_actor",
            )
        return (
            fact.subject_text,
            fact.subject_type,
            "preserved_parent_subject",
            "non_actor_subject",
        )
    if len(actors) != 1:
        return fact.subject_text, fact.subject_type, "unresolved", "none_or_ambiguous"
    actor = actors[0]
    if is_generic_government and actor.actor_kind != "government":
        return fact.subject_text, fact.subject_type, "unresolved", "incompatible_actor"
    return actor.value, SubjectType.ORGANISATION, actor.method, actor.evidence_category


def _capitalise_initial(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]


def _action_verb(value: str) -> str | None:
    candidate = value.strip()
    modality = re.match(
        r"^(?:intend(?:s)?\s+to|plan(?:s)?\s+to|commit(?:s)?\s+to|"
        r"has\s+committed\s+to|will\s+not)\s+",
        candidate,
        re.IGNORECASE,
    )
    if modality is not None:
        candidate = candidate[modality.end() :]
    while True:
        modifier = _LEADING_SEMANTIC_MODIFIER_RE.match(candidate)
        if modifier is None:
            break
        candidate = candidate[modifier.end() :]
    match = re.match(r"[A-Za-z]+", candidate)
    return match.group(0).casefold() if match is not None else None


def _normalise_commitment_value(
    raw_value: str,
) -> tuple[str, str, tuple[str, ...]]:
    value = _normalize_whitespace(raw_value)
    if _NEGATED_WILL_RE.match(value):
        return _capitalise_initial(value), "negation_preserved", ()
    if _INTENT_OR_PLAN_RE.match(value):
        return _capitalise_initial(value), "intent_or_planning_preserved", ()
    match = _AFFIRMATIVE_WILL_RE.match(value)
    if match is None:
        return _capitalise_initial(value), "capitalisation_only", ()
    action = value[match.end() :].strip()
    preserved_modifiers: list[str] = []
    remaining = action
    while True:
        modifier = _LEADING_SEMANTIC_MODIFIER_RE.match(remaining)
        if modifier is None:
            break
        preserved_modifiers.append(modifier.group("modifier").casefold())
        remaining = remaining[modifier.end() :]
    wrapper = _SAFE_WRAPPER_RE.fullmatch(action)
    if wrapper is not None:
        embedded = wrapper.group("action").strip()
        if (
            _action_verb(embedded) in _ELIGIBLE_ACTION_VERBS
            and len(re.findall(r"[A-Za-z0-9]+", embedded)) >= 3
            and _TERMINAL_INCOMPLETE_RE.search(embedded) is None
            and not re.search(r"\b(?:not|might|may|could|perhaps)\b", embedded, re.I)
            and not re.search(r"\b(?:this|these|those|it|them|they)\b", embedded, re.I)
        ):
            return (
                _capitalise_initial(embedded),
                "safe_recommendation_wrapper_collapsed",
                tuple(preserved_modifiers),
            )
        return _capitalise_initial(value), "unsafe_wrapper_preserved", ()
    return (
        _capitalise_initial(action),
        "affirmative_will_removed",
        tuple(preserved_modifiers),
    )


def _parent_identity(fact: CandidateFact) -> str:
    dumped = fact.model_dump(mode="json")
    return _canonical(
        [
            fact.source_id,
            fact.subject_text,
            fact.subject_type.value,
            fact.predicate,
            fact.raw_value,
            dumped["normalized_value"],
            fact.value_type.value,
            fact.qualifiers,
            fact.confidence,
            fact.review_status.value,
            fact.warnings,
        ]
    )


def _semantic_key(fact: CandidateFact) -> str:
    return _canonical(
        [
            fact.source_id,
            _normalize_whitespace(fact.subject_text).casefold(),
            fact.subject_type.value,
            fact.predicate,
            fact.value_type.value,
            fact.model_dump(mode="json")["normalized_value"],
            fact.qualifiers,
        ]
    )


def _candidate_id(fact: CandidateFact, block_id: str, rule_id: str) -> str:
    return "V04-CAND-" + _digest([rule_id, _semantic_key(fact), block_id])


def _evidence_id(source_id: str, block_id: str, excerpt: str) -> str:
    return "V04-EVID-" + _digest([source_id, block_id, excerpt])


def _period_is_sentence_boundary(text: str, index: int, raw_start: int) -> bool:
    previous = text[index - 1] if index > raw_start else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and following.isdigit():
        return False
    prefix = text[max(raw_start, index - 16) : index]
    token = re.search(r"(?P<token>[A-Za-z](?:[A-Za-z.]*)?)$", prefix)
    if token is not None and token.group("token").casefold() in _COMMON_ABBREVIATIONS:
        return False
    if following and not following.isspace():
        return False
    return True


def _looks_like_heading(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 80 or stripped.endswith((".", "!", "?")):
        return False
    words = re.findall(r"[A-Za-z0-9]+", stripped)
    if not 1 <= len(words) <= 10:
        return False
    return stripped.isupper() or all(word[0].isupper() for word in words if word)


def _line_after(text: str, newline_index: int) -> str:
    start = newline_index + 1
    while start < len(text) and text[start] in "\r\n":
        start += 1
    end = text.find("\n", start)
    if end < 0:
        end = len(text)
    return text[start:end].strip("\r")


def _complete_parent_value(
    fact: CandidateFact,
    reference: CandidateEvidenceReference,
    block: DocumentBlock,
) -> tuple[str, str] | None:
    occurrences = [
        match.start()
        for match in re.finditer(re.escape(reference.text_excerpt), block.text)
    ]
    if len(occurrences) != 1:
        return None
    excerpt_start = occurrences[0]
    raw_in_excerpt = reference.text_excerpt.find(fact.raw_value)
    if raw_in_excerpt < 0:
        return None
    raw_start = excerpt_start + raw_in_excerpt
    parent_end = raw_start + len(fact.raw_value)
    if parent_end > len(block.text):
        return None
    boundary_end: int | None = None
    parent_last = parent_end - 1
    if (
        parent_last >= raw_start
        and block.text[parent_last] in "!?"
    ) or (
        parent_last >= raw_start
        and block.text[parent_last] == "."
        and _period_is_sentence_boundary(block.text, parent_last, raw_start)
    ):
        boundary_end = parent_end
    parenthetical_depth = (
        block.text[raw_start:parent_end].count("(")
        - block.text[raw_start:parent_end].count(")")
    )
    for index in range(parent_end, min(len(block.text), raw_start + 500)):
        if boundary_end is not None:
            break
        character = block.text[index]
        if character == "(":
            parenthetical_depth += 1
            continue
        if character == ")":
            parenthetical_depth = max(0, parenthetical_depth - 1)
            continue
        if character == "\n":
            next_line = _line_after(block.text, index)
            if _NUMBERED_OR_BULLET_LINE_RE.match(next_line) or _looks_like_heading(
                next_line
            ):
                return None
        if character in "!?" and parenthetical_depth == 0:
            boundary_end = index + 1
            break
        if (
            character == "."
            and parenthetical_depth == 0
            and _period_is_sentence_boundary(block.text, index, raw_start)
        ):
            boundary_end = index + 1
            break
    if boundary_end is None:
        return None
    evidence_end = boundary_end
    while evidence_end > excerpt_start and block.text[evidence_end - 1].isspace():
        evidence_end -= 1
    excerpt = block.text[excerpt_start:evidence_end]
    if not excerpt.strip() or len(excerpt) > 240:
        return None
    raw = _normalize_whitespace(block.text[raw_start:boundary_end]).strip()
    if len(raw.split()) < 3 or _TERMINAL_INCOMPLETE_RE.search(raw):
        return None
    parent_comparison = _normalize_whitespace(fact.raw_value).casefold()
    recovered_comparison = _normalize_whitespace(raw).casefold()
    if parent_comparison not in recovered_comparison:
        return None
    return raw, excerpt


def _trace(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((name, count) for name, count in counter.items() if count))


def _semantic_transformation_flags(
    original: CandidateFact,
    final: CandidateFact,
    *,
    value_operation: str,
    preserved_modifiers: tuple[str, ...],
) -> tuple[str, ...]:
    flags: list[str] = []
    if final.subject_text != original.subject_text:
        flags.append("actor_resolved")
    if final.subject_type is not original.subject_type:
        flags.append("subject_type_changed")
    if final.raw_value != original.raw_value:
        original_value = _normalize_whitespace(original.raw_value).casefold()
        final_value = _normalize_whitespace(final.raw_value).casefold()
        flags.append(
            "raw_value_extended"
            if original_value in final_value
            else "raw_value_changed"
        )
    if final.normalized_value != original.normalized_value:
        flags.append("normalized_value_changed")
    if value_operation == "safe_recommendation_wrapper_collapsed":
        flags.append("structural_wrapper_removed")
        if re.search(r"\b(?:our|its|their)\b", final.normalized_value, re.IGNORECASE):
            flags.append("possessive_preserved")
    flags.extend(f"semantic_modifier_preserved:{item}" for item in preserved_modifiers)
    return tuple(flags)


def extract_deterministic_candidates_v0_4_with_trace(
    document: ParsedDocument,
) -> tuple[CandidateExtractionResult, dict[str, str], DeterministicV04Trace]:
    """Extract one document with operation attribution and deterministic trace counts."""

    if not isinstance(document, ParsedDocument):
        raise DeterministicExtractionV04Error(
            "document must be a validated ParsedDocument"
        )
    if document.source_id is None or not document.source_id.strip():
        raise DeterministicExtractionV04Error("document requires a source_id")

    v03 = extract_deterministic_candidates_v0_3(document)
    v02 = extract_deterministic_candidates_v0_2(document)
    v03_evidence = {item.evidence_id: item for item in v03.evidence_references}
    v02_evidence = {item.evidence_id: item for item in v02.evidence_references}
    blocks = {item.block_id: item for item in document.blocks}
    actors = _trusted_document_actors(document)
    actor_counts: Counter[str] = Counter()
    value_counts: Counter[str] = Counter()
    modifier_counts: Counter[str] = Counter()
    recovery_rejections: Counter[str] = Counter()
    evidence: dict[str, CandidateEvidenceReference] = {}
    facts: list[CandidateFact] = []
    candidate_traces: list[DeterministicV04CandidateTrace] = []
    attribution: dict[str, str] = {}
    transformed_count = 0
    recovered_count = 0

    def append_fact(
        fact: CandidateFact,
        reference: CandidateEvidenceReference,
        rule_id: str,
        *,
        original: CandidateFact | None = None,
        parent_version: str | None = None,
        parent_status: str | None = None,
        actor_method: str | None = None,
        actor_evidence_category: str | None = None,
        value_operation: str | None = None,
        preserved_modifiers: tuple[str, ...] = (),
    ) -> None:
        evidence_id = _evidence_id(
            fact.source_id, reference.block_id, reference.text_excerpt
        )
        evidence.setdefault(
            evidence_id, reference.model_copy(update={"evidence_id": evidence_id})
        )
        candidate_id = _candidate_id(fact, reference.block_id, rule_id)
        remapped = fact.model_copy(
            update={"candidate_id": candidate_id, "evidence_ids": [evidence_id]}
        )
        facts.append(remapped)
        attribution[candidate_id] = rule_id
        if original is not None:
            if (
                parent_version is None
                or parent_status is None
                or actor_method is None
                or actor_evidence_category is None
                or value_operation is None
            ):
                raise DeterministicExtractionV04Error(
                    "commitment trace attribution is incomplete"
                )
            candidate_traces.append(
                DeterministicV04CandidateTrace(
                    candidate_id=candidate_id,
                    source_id=fact.source_id,
                    evidence_block_id=reference.block_id,
                    parent_version=parent_version,
                    parent_candidate_id=original.candidate_id,
                    parent_status=parent_status,
                    original_subject=original.subject_text,
                    final_subject=fact.subject_text,
                    actor_resolution_method=actor_method,
                    actor_evidence_category=actor_evidence_category,
                    original_raw_value=original.raw_value,
                    final_raw_value=fact.raw_value,
                    original_normalized_value=original.model_dump(mode="json")[
                        "normalized_value"
                    ],
                    final_normalized_value=fact.model_dump(mode="json")[
                        "normalized_value"
                    ],
                    value_normalisation_operation=value_operation,
                    semantic_transformation_flags=_semantic_transformation_flags(
                        original,
                        fact,
                        value_operation=value_operation,
                        preserved_modifiers=preserved_modifiers,
                    ),
                )
            )

    for fact in v03.candidate_facts:
        reference = v03_evidence[fact.evidence_ids[0]]
        rule_id = "V04-POLICY-V03-CARRYOVER-001"
        transformed = fact
        if fact.predicate == "commitment":
            block = blocks.get(reference.block_id)
            quoted_or_reported = (
                block is not None
                and _is_quoted_or_reported_context(fact, reference, block)
            )
            subject, subject_type, actor_method, actor_category = _resolve_actor(
                fact,
                actors,
                quoted_or_reported=quoted_or_reported,
            )
            normalized, value_operation, preserved_modifiers = (
                _normalise_commitment_value(fact.raw_value)
            )
            transformed = fact.model_copy(
                update={
                    "subject_text": subject,
                    "subject_type": subject_type,
                    "normalized_value": normalized,
                }
            )
            actor_counts[actor_method] += 1
            value_counts[value_operation] += 1
            modifier_counts.update(preserved_modifiers)
            if (
                subject != fact.subject_text
                or subject_type is not fact.subject_type
                or normalized != fact.normalized_value
            ):
                transformed_count += 1
            rule_id = (
                "V04-POLICY-COMMITMENT-VALUE-003"
                if normalized != fact.normalized_value
                else "V04-POLICY-COMMITMENT-ACTOR-002"
            )
            append_fact(
                transformed,
                reference,
                rule_id,
                original=fact,
                parent_version="deterministic-baseline-v0.3",
                parent_status="retained_v0_3",
                actor_method=actor_method,
                actor_evidence_category=actor_category,
                value_operation=value_operation,
                preserved_modifiers=preserved_modifiers,
            )
        else:
            append_fact(transformed, reference, rule_id)

    retained_parent = {_parent_identity(fact) for fact in v03.candidate_facts}
    for fact in v02.candidate_facts:
        first_person = (
            _FIRST_PERSON_RE.fullmatch(_normalize_whitespace(fact.subject_text))
            is not None
        )
        if (
            fact.predicate != "commitment"
            or _parent_identity(fact) in retained_parent
        ):
            continue
        reference = v02_evidence[fact.evidence_ids[0]]
        block = blocks.get(reference.block_id)
        if block is None:
            recovery_rejections["missing_evidence_block"] += 1
            continue
        quoted_or_reported = _is_quoted_or_reported_context(fact, reference, block)
        subject, subject_type, actor_method, actor_category = _resolve_actor(
            fact,
            actors,
            quoted_or_reported=quoted_or_reported,
        )
        resolved_first_person = (
            first_person
            and subject != fact.subject_text
            and actor_method
            not in {"unresolved", "quotation_or_reported_speech_blocked"}
        )
        explicit_organisation = (
            not first_person
            and actor_method == "explicit_statement_actor"
            and _ORGANISATION_HEAD_RE.search(fact.subject_text) is not None
            and len(fact.subject_text.split()) <= 12
            and "," not in fact.subject_text
            and re.search(r"\b(?:and|or)\b", fact.subject_text, re.IGNORECASE)
            is None
        )
        if not resolved_first_person and not explicit_organisation:
            recovery_rejections["actor_not_eligible_or_unresolved"] += 1
            continue
        completed = _complete_parent_value(fact, reference, block)
        if completed is None:
            recovery_rejections["unsafe_or_ambiguous_parent_completion"] += 1
            continue
        raw_value, excerpt = completed
        normalized, value_operation, preserved_modifiers = (
            _normalise_commitment_value(raw_value)
        )
        if _action_verb(normalized) not in _ELIGIBLE_ACTION_VERBS:
            recovery_rejections["ineligible_action"] += 1
            continue
        if value_operation == "unsafe_wrapper_preserved":
            recovery_rejections["unsafe_wrapper"] += 1
            continue
        recovered = fact.model_copy(
            update={
                "subject_text": subject,
                "subject_type": subject_type,
                "raw_value": raw_value,
                "normalized_value": normalized,
            }
        )
        recovered_reference = CandidateEvidenceReference(
            evidence_id="temporary-evidence-id",
            source_id=fact.source_id,
            block_id=block.block_id,
            location_type=block.location.location_type,
            location_value=block.location.location_value,
            text_excerpt=excerpt,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        actor_counts[actor_method] += 1
        value_counts[value_operation] += 1
        modifier_counts.update(preserved_modifiers)
        append_fact(
            recovered,
            recovered_reference,
            "V04-RULE-COMMITMENT-RECOVERY-004",
            original=fact,
            parent_version="deterministic-baseline-v0.2",
            parent_status="recovered_filtered_v0_2",
            actor_method=actor_method,
            actor_evidence_category=actor_category,
            value_operation=value_operation,
            preserved_modifiers=preserved_modifiers,
        )
        recovered_count += 1

    retained: list[CandidateFact] = []
    seen: set[str] = set()
    duplicates = 0
    for fact in facts:
        key = _semantic_key(fact)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        retained.append(fact)
    retained_ids = {item.candidate_id for item in retained}
    attribution = {
        candidate_id: rule_id
        for candidate_id, rule_id in attribution.items()
        if candidate_id in retained_ids
    }
    retained_trace_by_id: dict[str, DeterministicV04CandidateTrace] = {}
    for item in candidate_traces:
        if item.candidate_id in retained_ids:
            retained_trace_by_id.setdefault(item.candidate_id, item)
    referenced_evidence = {
        evidence_id for fact in retained for evidence_id in fact.evidence_ids
    }
    try:
        result = CandidateExtractionResult(
            batch_id="V04-BATCH-"
            + _digest([document.source_id, document.checksum_sha256]),
            source_ids=[document.source_id],
            entities=[],
            evidence_references=sorted(
                (evidence[item] for item in referenced_evidence),
                key=lambda item: item.evidence_id,
            ),
            candidate_facts=sorted(
                retained, key=lambda item: (item.source_id, item.candidate_id)
            ),
            warnings=v03.warnings,
        )
    except ValidationError as error:
        raise DeterministicExtractionV04Error(
            "deterministic v0.4 output violates CandidateExtractionResult schema 0.1"
        ) from error
    return (
        result,
        attribution,
        DeterministicV04Trace(
            actor_resolution_methods=_trace(actor_counts),
            value_normalisation_operations=_trace(value_counts),
            preserved_semantic_modifiers=_trace(modifier_counts),
            rejected_recovery_reasons=_trace(recovery_rejections),
            candidate_traces=tuple(
                sorted(
                    retained_trace_by_id.values(),
                    key=lambda item: (item.source_id, item.candidate_id),
                )
            ),
            recovered_parent_candidate_count=recovered_count,
            transformed_parent_candidate_count=transformed_count,
            duplicate_candidate_count=duplicates,
        ),
    )


def extract_deterministic_candidates_v0_4_with_rules(
    document: ParsedDocument,
) -> tuple[CandidateExtractionResult, dict[str, str]]:
    """Extract one document and return deterministic candidate-to-rule attribution."""

    result, attribution, _ = extract_deterministic_candidates_v0_4_with_trace(document)
    return result, attribution


def extract_deterministic_candidates_v0_4(
    document: ParsedDocument,
) -> CandidateExtractionResult:
    """Transform one validated in-memory document without external access."""

    result, _, _ = extract_deterministic_candidates_v0_4_with_trace(document)
    return result


def canonical_candidate_result_json_v0_4(result: CandidateExtractionResult) -> str:
    """Serialize a validated v0.4 result to canonical deterministic JSON."""

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
    "DeterministicV04CandidateTrace",
    "DeterministicExtractionV04Error",
    "DeterministicV04Trace",
    "canonical_candidate_result_json_v0_4",
    "extract_deterministic_candidates_v0_4",
    "extract_deterministic_candidates_v0_4_with_rules",
    "extract_deterministic_candidates_v0_4_with_trace",
]
