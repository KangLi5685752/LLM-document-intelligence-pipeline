"""Small Pydantic schemas for deterministic read-only document tools."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from document_intelligence.portfolio.models import (
    FactType,
    PortfolioFact,
    RetrievalHit,
    RetrievalRecord,
)


class RetrieveEvidenceInput(BaseModel):
    """Validated input for hybrid evidence retrieval."""

    model_config = ConfigDict(extra="forbid")

    question: str
    source_ids: list[str] | None = Field(default=None, min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [source_id.strip() for source_id in value]
        if any(not source_id for source_id in normalized):
            raise ValueError("source_ids must not contain blank values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("source_ids must be unique")
        return normalized


class RetrieveEvidenceOutput(BaseModel):
    """Ranked existing retrieval hits."""

    model_config = ConfigDict(extra="forbid")

    hits: list[RetrievalHit]


class SearchProjectFactsInput(BaseModel):
    """Validated filters for existing structured fact search."""

    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    fact_type: FactType | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank when supplied")
        return normalized


class SearchProjectFactsOutput(BaseModel):
    """Matching existing portfolio facts."""

    model_config = ConfigDict(extra="forbid")

    facts: list[PortfolioFact]


class ReadEvidenceBlockInput(BaseModel):
    """Validated exact evidence lookup input."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("evidence_id must not be blank")
        return normalized


class ReadEvidenceBlockOutput(BaseModel):
    """The exact existing retrieval record selected by evidence ID."""

    model_config = ConfigDict(extra="forbid")

    record: RetrievalRecord


class AgentRetrieveEvidenceInput(RetrieveEvidenceInput):
    """Agent-v1 retrieval input with its narrower bounded result count."""

    top_k: int = Field(default=5, ge=1, le=5)


class AgentAnswerStatus(str, Enum):
    """Supported terminal states for the bounded document agent."""

    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AgentAnswerDraft(BaseModel):
    """Strict model-facing answer without application-owned provenance."""

    model_config = ConfigDict(extra="forbid")

    status: AgentAnswerStatus
    answer: str = Field(min_length=1)
    evidence_ids: list[str]

    @model_validator(mode="after")
    def validate_draft(self) -> AgentAnswerDraft:
        """Reject ambiguous text and evidence inventories at the schema boundary."""
        if self.answer != self.answer.strip():
            raise ValueError("answer must not contain surrounding whitespace")
        if any(
            not evidence_id.strip() or evidence_id != evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ValueError("evidence_ids must contain trimmed nonblank values")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        if self.status is AgentAnswerStatus.ANSWERED and not self.evidence_ids:
            raise ValueError("answered drafts require at least one evidence ID")
        return self


class AgentCitation(BaseModel):
    """Application-hydrated provenance for one cited evidence block."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    block_id: str
    location_type: str
    location_value: str


class AgentToolCallSummary(BaseModel):
    """Deterministic high-level accounting for one registered tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: Literal[
        "retrieve_evidence", "search_project_facts", "read_evidence_block"
    ]
    invocation_count: int = Field(ge=1)
    high_level_result: str = Field(min_length=1)


class AgentUsage(BaseModel):
    """Safe aggregate usage counters returned by Pydantic AI."""

    model_config = ConfigDict(extra="forbid")

    requests: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    approximate_cost_usd: Decimal | None


class AgentAnswer(BaseModel):
    """Grounded application response without model messages or reasoning traces."""

    model_config = ConfigDict(extra="forbid")

    question: str
    status: AgentAnswerStatus
    answer: str
    evidence_ids: list[str]
    citations: list[AgentCitation]
    tool_call_summary: list[AgentToolCallSummary]
    usage: AgentUsage
