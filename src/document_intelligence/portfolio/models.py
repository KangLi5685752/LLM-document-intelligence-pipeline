"""Lightweight public models for the portfolio extraction and RAG path."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactType(str, Enum):
    """Practical fact categories exposed by the portfolio interface."""

    COMMITMENT = "commitment"
    RECOMMENDATION = "recommendation"
    REQUIREMENT = "requirement"
    DECISION = "decision"
    RISK = "risk"
    METRIC = "metric"
    BUDGET = "budget"
    DATE = "date"
    OWNER = "owner"
    STATUS = "status"
    OTHER = "other"


class SupportStatus(str, Enum):
    """Whether supplied evidence clearly supports a fact."""

    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"


class PortfolioFactDraft(BaseModel):
    """Strict model-facing fact with only application-issued evidence IDs."""

    model_config = ConfigDict(extra="forbid")

    fact_type: FactType
    subject: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    value: str | None
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    support_status: SupportStatus
    review_required: bool

    @model_validator(mode="after")
    def validate_draft(self) -> PortfolioFactDraft:
        """Keep text, evidence identity, and review routing unambiguous."""
        for name in ("subject", "statement"):
            value = getattr(self, name)
            if value != value.strip():
                raise ValueError(f"{name} must not contain surrounding whitespace")
        if self.value is not None and (
            not self.value.strip() or self.value != self.value.strip()
        ):
            raise ValueError("value must be null or a trimmed nonblank string")
        if any(
            not item.strip() or item != item.strip() for item in self.evidence_ids
        ):
            raise ValueError("evidence_ids must contain trimmed nonblank values")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        if self.support_status is SupportStatus.AMBIGUOUS and not self.review_required:
            raise ValueError("ambiguous facts must require review")
        return self


class PortfolioFactDraftResponse(BaseModel):
    """Strict Structured Outputs response envelope."""

    model_config = ConfigDict(extra="forbid")

    facts: list[PortfolioFactDraft]


class EvidenceReference(BaseModel):
    """Application-hydrated source evidence for one extracted fact."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    block_id: str
    location_type: str
    location_value: str
    excerpt: str


class PortfolioFact(BaseModel):
    """Evidence-linked fact returned to users and structured search."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    fact_type: FactType
    subject: str
    statement: str
    value: str | None
    evidence_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    support_status: SupportStatus
    review_required: bool
    evidence: list[EvidenceReference]

    @model_validator(mode="after")
    def reconcile_evidence(self) -> PortfolioFact:
        """Require the hydrated evidence inventory to match the selected IDs."""
        if self.evidence_ids != [item.evidence_id for item in self.evidence]:
            raise ValueError("evidence does not match evidence_ids")
        return self


class PortfolioFactExtraction(BaseModel):
    """Human-readable extraction result for one ParsedDocument."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    source_id: str
    source_format: str
    facts: list[PortfolioFact]


class RetrievalRecord(BaseModel):
    """One ParsedDocument block prepared for semantic retrieval."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    block_id: str
    location_type: str
    location_value: str
    text: str


class RetrievalHit(RetrievalRecord):
    """One ranked retrieval record with its index-specific score."""

    score: float


class GroundedAnswerDraft(BaseModel):
    """Strict model-facing answer before citation hydration."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    citations: list[str]


class RagCitation(BaseModel):
    """Validated and hydrated citation returned with a grounded answer."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    block_id: str
    location_type: str
    location_value: str


class GroundedAnswer(BaseModel):
    """Citation-validated answer to a user question."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    citations: list[RagCitation]
    retrieved_evidence: list[RetrievalHit]


class RetrievalQuestion(BaseModel):
    """One labelled development question for retrieval evaluation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    expected_source_id: str
    expected_block_ids: list[str] = Field(min_length=1)


class RetrievalQuestionDiagnostic(BaseModel):
    """Per-question evidence ranking details for benchmark diagnosis."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    expected_evidence_ids: list[str] = Field(min_length=1)
    first_relevant_rank: int | None = Field(default=None, ge=1)
    top_5_evidence_ids: list[str]


class RetrievalEvaluationReport(BaseModel):
    """Aggregate ranking metrics for the development retrieval benchmark."""

    model_config = ConfigDict(extra="forbid")

    question_count: int = Field(ge=0)
    hit_at_1: float = Field(ge=0.0, le=1.0)
    hit_at_3: float = Field(ge=0.0, le=1.0)
    hit_at_5: float = Field(ge=0.0, le=1.0)
    mean_reciprocal_rank: float = Field(ge=0.0, le=1.0)
    question_diagnostics: list[RetrievalQuestionDiagnostic] | None = None
