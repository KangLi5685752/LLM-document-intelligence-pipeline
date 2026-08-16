"""Small Pydantic schemas for deterministic read-only document tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
