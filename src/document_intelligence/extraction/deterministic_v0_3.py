"""Pure, additive deterministic-baseline-v0.3 candidate extraction."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from document_intelligence.extraction.deterministic_v0_2 import (
    extract_deterministic_candidates_v0_2,
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
from document_intelligence.ingestion.models import BlockType, DocumentBlock, ParsedDocument


DETERMINISTIC_BASELINE_VERSION = "deterministic-baseline-v0.3"

_CANDIDATE_BLOCK_TYPES = {
    BlockType.PAGE_TEXT,
    BlockType.SLIDE_TITLE,
    BlockType.SHAPE_TEXT,
    BlockType.TABLE,
    BlockType.EMAIL_BODY,
}
_POLICY_CONTEXT_RE = re.compile(
    r"\b(?:action\s+plan|policy|recommendations?|strategy|framework)\b",
    re.IGNORECASE,
)
_NUMBERED_ITEM_RE = re.compile(
    r"(?:^|\s)(?P<identifier>\d{1,3})\.\s+"
    r"(?P<action>[^.!?]{5,500}[.!?])"
)
_RECOMMENDATION_VERBS = frozenset(
    {
        "adopt",
        "appoint",
        "commit",
        "continue",
        "create",
        "develop",
        "ensure",
        "establish",
        "expand",
        "fund",
        "identify",
        "implement",
        "increase",
        "introduce",
        "launch",
        "publish",
        "reform",
        "require",
        "review",
        "set",
        "support",
        "work",
    }
)
_ACTION_RATIO_PATTERNS = (
    re.compile(
        r"\b(?:have|has|had)\s+(?:now\s+)?(?P<status>met)\s+"
        r"(?:our|the|their)\s+commitments?\s+against\s+"
        r"(?P<done>\d+)\s+of\s+(?:the\s+)?(?P<total>\d+)\s+actions?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<done>\d+)\s+(?:out\s+of|of)\s+(?:the\s+)?"
        r"(?P<total>\d+)\s+actions?\s+(?:were\s+|are\s+|have\s+been\s+)?"
        r"(?P<status>completed|met)\b",
        re.IGNORECASE,
    ),
)
_MONEY_TOKEN = (
    r"(?P<currency>GBP|USD|EUR|\N{POUND SIGN}|\N{DOLLAR SIGN}|\N{EURO SIGN})"
    r"\s*(?P<amount>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>thousand|million|billion|k|m|bn)?"
)
_BUDGET_CONTEXT_RE = re.compile(
    r"(?:launch|development|creation)\s+of\s+"
    r"(?P<subject>[A-Z][A-Za-z0-9'&()\-/ ]{1,78}?)\s*:\s*"
    r".{0,100}?\b(?:has|have)\s+committed\s+"
    r"(?P<ceiling>up\s+to\s+)?" + _MONEY_TOKEN,
    re.IGNORECASE,
)
_BUDGET_TO_RE = re.compile(
    r"\b(?:has|have)\s+committed\s+(?P<ceiling>up\s+to\s+)?"
    + _MONEY_TOKEN
    + r"\s+to\s+(?P<subject>[A-Z][A-Za-z0-9'&()\-/ ]{1,78}?)"
    r"(?=\s+[-\N{EN DASH}\N{EM DASH}]|[.,;]|$)",
    re.IGNORECASE,
)
_WEAK_TRIGGER_RE = re.compile(
    r"^(?:will(?:\s+not)?|plans?\s+to|intends?\s+to)\s+",
    re.IGNORECASE,
)
_ACTION_MODIFIER_RE = re.compile(
    r"^(?:also|continue\s+to|immediately|now|only|still)\s+",
    re.IGNORECASE,
)
_AGENTIVE_ACTION_VERBS = frozenset(
    {
        "adopt",
        "appoint",
        "build",
        "commit",
        "create",
        "deliver",
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
        "support",
        "take",
        "work",
    }
)
_GENERIC_ACTOR_HEAD_RE = re.compile(
    r"\b(?:agency|authority|board|council|department|government|office|"
    r"organisation|organization|programme|program|project|regulator|service|team|unit)\b",
    re.IGNORECASE,
)
_IMPERSONAL_OR_FIRST_PERSON_RE = re.compile(
    r"^(?:and\s+)?(?:i|it|we|you|this|that|these|those|there)\b",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(
    r"^(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{4}$",
    re.IGNORECASE,
)
_PUBLICATION_CODE_RE = re.compile(r"^[A-Z]{1,5}\s*\d{2,6}$")
_WHITESPACE_RE = re.compile(r"\s+")


class DeterministicExtractionV03Error(RuntimeError):
    """Raised when v0.3 cannot produce a schema-valid result."""


@dataclass(frozen=True, slots=True)
class _AddedCandidate:
    rule_id: str
    block: DocumentBlock
    start: int
    end: int
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: Any
    value_type: ValueType
    qualifiers: dict[str, Any]
    confidence: float


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(_canonical(parts).encode("utf-8")).hexdigest().upper()


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _collapsed_text_with_offsets(value: str) -> tuple[str, tuple[int, ...]]:
    output: list[str] = []
    offsets: list[int] = []
    for token in re.finditer(r"\S+", value):
        if output:
            output.append(" ")
            offsets.append(token.start())
        for position, character in enumerate(token.group(0), start=token.start()):
            output.append(character)
            offsets.append(position)
    return "".join(output), tuple(offsets)


def _original_span(offsets: tuple[int, ...], start: int, end: int) -> tuple[int, int]:
    return offsets[start], offsets[end - 1] + 1


def _policy_subject(document: ParsedDocument) -> str | None:
    title = _normalize_whitespace(document.title or "")
    if not title:
        return None
    title = title.split(":", 1)[0].strip()
    parts = [
        part.strip()
        for part in re.split(r"\s+[-\N{EN DASH}\N{EM DASH}]\s+", title)
        if part.strip()
    ]
    eligible = [
        part
        for part in parts
        if not _PUBLICATION_CODE_RE.fullmatch(part)
        and not _MONTH_YEAR_RE.fullmatch(part)
        and _POLICY_CONTEXT_RE.search(part)
    ]
    if eligible:
        return max(eligible, key=len)
    if _POLICY_CONTEXT_RE.search(title):
        return title
    return None


def _new_candidates(document: ParsedDocument) -> list[_AddedCandidate]:
    policy_subject = _policy_subject(document)
    additions: list[_AddedCandidate] = []
    for block in sorted(document.blocks, key=lambda item: item.sequence):
        if block.block_type not in _CANDIDATE_BLOCK_TYPES:
            continue
        collapsed, offsets = _collapsed_text_with_offsets(block.text)
        if not collapsed:
            continue
        if policy_subject is not None:
            for match in _NUMBERED_ITEM_RE.finditer(collapsed):
                action = _normalize_whitespace(match.group("action"))
                first_word = re.match(r"[A-Za-z]+", action)
                recommendation_like = (
                    first_word is not None
                    and first_word.group(0).casefold() in _RECOMMENDATION_VERBS
                ) or re.search(r"\bshould\s+[A-Za-z]+", action, re.IGNORECASE)
                if not recommendation_like:
                    continue
                identifier = int(match.group("identifier"))
                start, end = _original_span(offsets, match.start("identifier"), match.end("action"))
                if end - start > 240:
                    continue
                additions.append(
                    _AddedCandidate(
                        rule_id="V03-RULE-REC-NUMBERED-001",
                        block=block,
                        start=start,
                        end=end,
                        subject_text=f"{policy_subject} recommendation {identifier}",
                        subject_type=SubjectType.RECOMMENDATION,
                        predicate="recommendation",
                        raw_value=action,
                        normalized_value=action,
                        value_type=ValueType.STRING,
                        qualifiers={"recommendation_id": identifier},
                        confidence=0.9,
                    )
                )
            for pattern in _ACTION_RATIO_PATTERNS:
                for match in pattern.finditer(collapsed):
                    status = match.group("status").casefold()
                    done = int(match.group("done"))
                    total = int(match.group("total"))
                    if total <= 0 or done > total:
                        continue
                    start, end = _original_span(offsets, match.start(), match.end())
                    additions.append(
                        _AddedCandidate(
                            rule_id="V03-RULE-ACTION-RATIO-001",
                            block=block,
                            start=start,
                            end=end,
                            subject_text=policy_subject,
                            subject_type=SubjectType.POLICY,
                            predicate="action_status",
                            raw_value=f"Commitments {status} against {done} of the {total} actions.",
                            normalized_value=f"{done} of {total} actions {status}",
                            value_type=ValueType.STATUS,
                            qualifiers={},
                            confidence=0.9,
                        )
                    )
        for pattern in (_BUDGET_CONTEXT_RE, _BUDGET_TO_RE):
            for match in pattern.finditer(collapsed):
                subject = _normalize_whitespace(match.group("subject")).strip(" -")
                subject = re.sub(r"^the\s+", "", subject, flags=re.IGNORECASE)
                if not subject[0].isupper() or not 1 <= len(subject.split()) <= 10:
                    continue
                amount = Decimal(match.group("amount").replace(",", ""))
                scale = (match.group("scale") or "").casefold()
                multiplier = {
                    "": Decimal("1"),
                    "k": Decimal("1000"),
                    "thousand": Decimal("1000"),
                    "m": Decimal("1000000"),
                    "million": Decimal("1000000"),
                    "bn": Decimal("1000000000"),
                    "billion": Decimal("1000000000"),
                }[scale]
                currency = {
                    "£": "GBP",
                    "$": "USD",
                    "€": "EUR",
                    "gbp": "GBP",
                    "usd": "USD",
                    "eur": "EUR",
                }[match.group("currency").casefold()]
                start, end = _original_span(offsets, match.start(), match.end())
                if end - start > 240:
                    continue
                raw = _normalize_whitespace(collapsed[match.start() : match.end()])
                additions.append(
                    _AddedCandidate(
                        rule_id="V03-RULE-BUD-COMMITTED-001",
                        block=block,
                        start=start,
                        end=end,
                        subject_text=subject,
                        subject_type=SubjectType.PROGRAMME,
                        predicate="budget",
                        raw_value=raw,
                        normalized_value=NormalizedMoney(
                            amount=amount * multiplier,
                            currency=currency,
                        ),
                        value_type=ValueType.MONEY,
                        qualifiers={"budget_status": "committed"},
                        confidence=0.9,
                    )
                )
    return additions


def _retain_parent_commitment(fact: CandidateFact) -> bool:
    if fact.predicate != "commitment" or fact.confidence >= 0.9:
        return True
    trigger = _WEAK_TRIGGER_RE.match(fact.raw_value)
    if trigger is None:
        return False
    if _IMPERSONAL_OR_FIRST_PERSON_RE.match(fact.subject_text):
        return False
    if fact.subject_type not in {
        SubjectType.INITIATIVE,
        SubjectType.ORGANISATION,
        SubjectType.POLICY,
        SubjectType.PROGRAMME,
    } and _GENERIC_ACTOR_HEAD_RE.search(fact.subject_text) is None:
        return False
    action = fact.raw_value[trigger.end() :].strip()
    while True:
        modifier = _ACTION_MODIFIER_RE.match(action)
        if modifier is None:
            break
        action = action[modifier.end() :].strip()
    verb = re.match(r"[A-Za-z]+", action)
    return verb is not None and verb.group(0).casefold() in _AGENTIVE_ACTION_VERBS


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
    return "V03-CAND-" + _digest([rule_id, _semantic_key(fact), block_id])


def _evidence_id(source_id: str, block_id: str, excerpt: str) -> str:
    return "V03-EVID-" + _digest([source_id, block_id, excerpt])


def _document_family(document: ParsedDocument) -> str:
    value = document.metadata.get("document_family")
    return value.strip() if isinstance(value, str) and value.strip() else document.document_id


def extract_deterministic_candidates_v0_3_with_rules(
    document: ParsedDocument,
) -> tuple[CandidateExtractionResult, dict[str, str]]:
    """Extract one document and return deterministic candidate-to-rule attribution."""

    if not isinstance(document, ParsedDocument):
        raise DeterministicExtractionV03Error(
            "document must be a validated ParsedDocument"
        )
    if document.source_id is None or not document.source_id.strip():
        raise DeterministicExtractionV03Error("document requires a source_id")
    parent = extract_deterministic_candidates_v0_2(document)
    parent_evidence = {item.evidence_id: item for item in parent.evidence_references}
    evidence: dict[str, CandidateEvidenceReference] = {}
    facts: list[CandidateFact] = []
    attribution: dict[str, str] = {}

    def append_fact(
        fact: CandidateFact,
        reference: CandidateEvidenceReference,
        rule_id: str,
    ) -> None:
        evidence_id = _evidence_id(fact.source_id, reference.block_id, reference.text_excerpt)
        remapped_reference = reference.model_copy(update={"evidence_id": evidence_id})
        evidence.setdefault(evidence_id, remapped_reference)
        candidate_id = _candidate_id(fact, reference.block_id, rule_id)
        remapped_fact = fact.model_copy(
            update={"candidate_id": candidate_id, "evidence_ids": [evidence_id]}
        )
        facts.append(remapped_fact)
        attribution[candidate_id] = rule_id

    for fact in parent.candidate_facts:
        if not _retain_parent_commitment(fact):
            continue
        reference = parent_evidence[fact.evidence_ids[0]]
        rule_id = (
            "V03-POLICY-COMMITMENT-PRECISION-002"
            if fact.predicate == "commitment"
            else "V03-POLICY-V02-CARRYOVER-001"
        )
        append_fact(fact, reference, rule_id)

    family = _document_family(document)
    for draft in _new_candidates(document):
        excerpt = draft.block.text[draft.start : draft.end]
        reference = CandidateEvidenceReference(
            evidence_id="temporary-evidence-id",
            source_id=document.source_id,
            block_id=draft.block.block_id,
            location_type=draft.block.location.location_type,
            location_value=draft.block.location.location_value,
            text_excerpt=excerpt,
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        fact = CandidateFact(
            candidate_id="temporary-candidate-id",
            source_id=document.source_id,
            document_family=family,
            subject_text=draft.subject_text,
            subject_type=draft.subject_type,
            predicate=draft.predicate,
            raw_value=draft.raw_value,
            normalized_value=draft.normalized_value,
            value_type=draft.value_type,
            qualifiers=draft.qualifiers,
            evidence_ids=[reference.evidence_id],
            confidence=draft.confidence,
            review_status=CandidateReviewStatus.NOT_REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=[],
        )
        append_fact(fact, reference, draft.rule_id)

    retained: list[CandidateFact] = []
    seen: set[str] = set()
    for fact in facts:
        key = _semantic_key(fact)
        if key in seen:
            continue
        seen.add(key)
        retained.append(fact)
    retained_ids = {item.candidate_id for item in retained}
    attribution = {
        candidate_id: rule_id
        for candidate_id, rule_id in attribution.items()
        if candidate_id in retained_ids
    }
    referenced_evidence = {
        evidence_id for fact in retained for evidence_id in fact.evidence_ids
    }
    try:
        result = CandidateExtractionResult(
            batch_id="V03-BATCH-"
            + _digest([document.source_id, document.checksum_sha256]),
            source_ids=[document.source_id],
            entities=[],
            evidence_references=sorted(
                (evidence[item] for item in referenced_evidence),
                key=lambda item: item.evidence_id,
            ),
            candidate_facts=sorted(
                retained,
                key=lambda item: (item.source_id, item.candidate_id),
            ),
            warnings=parent.warnings,
        )
    except ValidationError as error:
        raise DeterministicExtractionV03Error(
            "deterministic v0.3 output violates CandidateExtractionResult schema 0.1"
        ) from error
    return result, attribution


def extract_deterministic_candidates_v0_3(
    document: ParsedDocument,
) -> CandidateExtractionResult:
    """Transform one validated in-memory document without external access."""

    result, _ = extract_deterministic_candidates_v0_3_with_rules(document)
    return result


def canonical_candidate_result_json_v0_3(result: CandidateExtractionResult) -> str:
    """Serialize a validated v0.3 result to canonical deterministic JSON."""

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
    "DeterministicExtractionV03Error",
    "canonical_candidate_result_json_v0_3",
    "extract_deterministic_candidates_v0_3",
    "extract_deterministic_candidates_v0_3_with_rules",
]
