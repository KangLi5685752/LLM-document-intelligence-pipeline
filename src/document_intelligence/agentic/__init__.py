"""Typed read-only adapters for future agentic document access."""

from document_intelligence.agentic.models import (
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    SearchProjectFactsInput,
    SearchProjectFactsOutput,
)
from document_intelligence.agentic.tools import DocumentToolService

__all__ = [
    "DocumentToolService",
    "ReadEvidenceBlockInput",
    "ReadEvidenceBlockOutput",
    "RetrieveEvidenceInput",
    "RetrieveEvidenceOutput",
    "SearchProjectFactsInput",
    "SearchProjectFactsOutput",
]
