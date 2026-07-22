"""Strict candidate-extraction contracts preceding fact reconciliation."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from document_intelligence.ingestion.models import LocationType


CANDIDATE_EXTRACTION_SCHEMA_VERSION: Literal["0.1"] = "0.1"


class SubjectType(str, Enum):
    """Bounded subject categories for candidate facts and entities."""

    INITIATIVE = "initiative"
    PROGRAMME = "programme"
    POLICY = "policy"
    ORGANISATION = "organisation"
    RECOMMENDATION = "recommendation"
    RISK = "risk"
    DECISION = "decision"
    METRIC = "metric"
    OTHER = "other"


class ValueType(str, Enum):
    """Supported normalized-value categories."""

    STRING = "string"
    DATE = "date"
    MONEY = "money"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    STATUS = "status"
    PERSON = "person"
    ORGANISATION = "organisation"
    BOOLEAN = "boolean"
    LIST = "list"
    OTHER = "other"


class EvidenceStatus(str, Enum):
    """Whether a candidate evidence reference supports its fact."""

    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


class CandidateReviewStatus(str, Enum):
    """Whether a candidate must be routed to later human review."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"


class ExtractionMethod(str, Enum):
    """Permitted producers of the shared candidate contract."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    MANUAL_ANNOTATION = "manual_annotation"


class NormalizedMoney(BaseModel):
    """Currency-qualified, non-negative monetary value."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        """Use a stable non-exponent decimal representation in JSON."""
        return format(value, "f")


NormalizedValue: TypeAlias = (
    NormalizedMoney | str | int | float | bool | list[str] | None
)
QualifierValue: TypeAlias = str | int | float | bool | None | list[str]


def _require_trimmed(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    return value


class CandidateEntity(BaseModel):
    """Unreconciled entity proposed by an extraction method."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    canonical_name: str
    entity_type: SubjectType
    aliases: list[str] = Field(default_factory=list)
    source_ids: list[str]

    @model_validator(mode="after")
    def validate_entity(self) -> CandidateEntity:
        """Validate identity, aliases, and source membership."""
        _require_trimmed(self.entity_id, "entity_id")
        _require_trimmed(self.canonical_name, "canonical_name")
        if not self.source_ids:
            raise ValueError("source_ids must not be empty")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique")
        for source_id in self.source_ids:
            _require_trimmed(source_id, "source_id")
        for alias in self.aliases:
            _require_trimmed(alias, "alias")
            if alias.casefold() == self.canonical_name.casefold():
                raise ValueError("alias cannot equal canonical_name after casefold")
        if len({alias.casefold() for alias in self.aliases}) != len(self.aliases):
            raise ValueError("aliases must be unique after casefold")
        return self


class CandidateEvidenceReference(BaseModel):
    """Short evidence excerpt linked to an existing ParsedDocument block."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    block_id: str
    location_type: LocationType
    location_value: str
    text_excerpt: str = Field(max_length=240)
    evidence_status: EvidenceStatus

    @model_validator(mode="after")
    def validate_evidence(self) -> CandidateEvidenceReference:
        """Enforce stable identifiers and format-appropriate locators."""
        for field_name in ("evidence_id", "source_id", "block_id"):
            _require_trimmed(getattr(self, field_name), field_name)
        _require_trimmed(self.location_value, "location_value")
        if self.evidence_status is EvidenceStatus.SUPPORTED:
            _require_trimmed(self.text_excerpt, "text_excerpt")
        if self.location_type in {LocationType.PAGE, LocationType.SLIDE}:
            if not self.location_value.isascii() or not self.location_value.isdigit():
                raise ValueError("page and slide location values must be integers")
            if int(self.location_value) < 1:
                raise ValueError("page and slide locations must be positive and 1-based")
        return self


class CandidateFact(BaseModel):
    """One pre-reconciliation candidate fact with no final fact state."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    source_id: str
    document_family: str
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: NormalizedValue
    value_type: ValueType
    qualifiers: dict[str, QualifierValue] = Field(default_factory=dict)
    evidence_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    review_status: CandidateReviewStatus
    extraction_method: ExtractionMethod
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateFact:
        """Validate identifiers, evidence links, and review semantics."""
        from document_intelligence.extraction.predicates import (
            validate_predicate_usage,
        )

        self.predicate = validate_predicate_usage(
            predicate=self.predicate,
            subject_type=self.subject_type,
            value_type=self.value_type,
            qualifiers=self.qualifiers,
        )
        for field_name in (
            "candidate_id",
            "source_id",
            "document_family",
            "subject_text",
        ):
            _require_trimmed(getattr(self, field_name), field_name)
        if not self.evidence_ids:
            raise ValueError("evidence_ids must not be empty")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        for evidence_id in self.evidence_ids:
            _require_trimmed(evidence_id, "evidence_id")
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must not contain blank strings")
        if (
            self.extraction_method is ExtractionMethod.MANUAL_ANNOTATION
            and self.confidence == 1.0
            and self.review_status is CandidateReviewStatus.REQUIRED
        ):
            raise ValueError(
                "manual annotations require completed review before confidence 1.0"
            )
        return self


class CandidateExtractionResult(BaseModel):
    """Versioned batch of candidates produced before reconciliation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"] = CANDIDATE_EXTRACTION_SCHEMA_VERSION
    batch_id: str
    source_ids: list[str]
    entities: list[CandidateEntity] = Field(default_factory=list)
    evidence_references: list[CandidateEvidenceReference] = Field(default_factory=list)
    candidate_facts: list[CandidateFact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> CandidateExtractionResult:
        """Reconcile internal IDs and source/evidence references only."""
        _require_trimmed(self.batch_id, "batch_id")
        if not self.source_ids:
            raise ValueError("source_ids must not be empty")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique")
        for source_id in self.source_ids:
            _require_trimmed(source_id, "source_id")

        def require_unique(values: list[str], label: str) -> None:
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")

        require_unique([entity.entity_id for entity in self.entities], "entity IDs")
        require_unique(
            [evidence.evidence_id for evidence in self.evidence_references],
            "evidence IDs",
        )
        require_unique(
            [fact.candidate_id for fact in self.candidate_facts], "candidate IDs"
        )
        evidence_by_id = {
            evidence.evidence_id: evidence for evidence in self.evidence_references
        }
        source_ids = set(self.source_ids)
        for entity in self.entities:
            if not set(entity.source_ids).issubset(source_ids):
                raise ValueError("entity source IDs must exist in result source_ids")
        for fact in self.candidate_facts:
            if fact.source_id not in source_ids:
                raise ValueError("fact source_id must exist in result source_ids")
            missing = [
                evidence_id
                for evidence_id in fact.evidence_ids
                if evidence_id not in evidence_by_id
            ]
            if missing:
                raise ValueError(f"fact has dangling evidence IDs: {', '.join(missing)}")
            referenced = [evidence_by_id[item] for item in fact.evidence_ids]
            if any(evidence.source_id != fact.source_id for evidence in referenced):
                raise ValueError("fact and evidence source IDs must match")
            if any(
                evidence.evidence_status is EvidenceStatus.SUPPORTED
                for evidence in referenced
            ) and not fact.raw_value.strip():
                raise ValueError("supported candidate facts require a non-blank raw_value")
            if (
                fact.extraction_method is ExtractionMethod.MANUAL_ANNOTATION
                and fact.confidence == 1.0
                and any(
                    evidence.evidence_status is not EvidenceStatus.SUPPORTED
                    for evidence in referenced
                )
            ):
                raise ValueError(
                    "manual confidence 1.0 requires supported evidence references"
                )
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("warnings must not contain blank strings")
        return self
