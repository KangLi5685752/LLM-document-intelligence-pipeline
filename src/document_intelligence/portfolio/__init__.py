"""Small portfolio-facing extraction and retrieval application layer."""

from document_intelligence.portfolio.extraction import extract_project_facts
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    GroundedAnswer,
    PortfolioFact,
    PortfolioFactExtraction,
    SupportStatus,
)
from document_intelligence.portfolio.rag import answer_question
from document_intelligence.portfolio.retrieval import (
    HybridIndex,
    SentenceTransformerEmbedder,
    build_retrieval_records,
    retrieve_blocks,
)

__all__ = [
    "EvidenceReference",
    "FactType",
    "GroundedAnswer",
    "HybridIndex",
    "PortfolioFact",
    "PortfolioFactExtraction",
    "SentenceTransformerEmbedder",
    "SupportStatus",
    "answer_question",
    "build_retrieval_records",
    "extract_project_facts",
    "retrieve_blocks",
]
