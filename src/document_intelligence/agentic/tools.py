"""Injected, deterministic, read-only adapters over portfolio functionality."""

from __future__ import annotations

from collections.abc import Sequence

from document_intelligence.agentic.models import (
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    SearchProjectFactsInput,
    SearchProjectFactsOutput,
)
from document_intelligence.portfolio.extraction import (
    search_project_facts as portfolio_search_project_facts,
)
from document_intelligence.portfolio.models import (
    PortfolioFactExtraction,
    RetrievalRecord,
)
from document_intelligence.portfolio.retrieval import Embedder, HybridIndex


class DocumentToolService:
    """Provide three read-only tools over already-loaded portfolio data."""

    def __init__(
        self,
        *,
        retrieval_records: Sequence[RetrievalRecord],
        fact_extractions: Sequence[PortfolioFactExtraction],
        embedder: Embedder,
    ) -> None:
        self._retrieval_records = tuple(retrieval_records)
        self._fact_extractions = tuple(fact_extractions)
        evidence_ids = [record.evidence_id for record in self._retrieval_records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("retrieval evidence IDs must be unique")
        self._evidence_by_id = {
            record.evidence_id: record for record in self._retrieval_records
        }
        self._embedder = embedder
        self._retrieval_index = HybridIndex(self._retrieval_records, embedder)

    def retrieve_evidence(
        self, request: RetrieveEvidenceInput
    ) -> RetrieveEvidenceOutput:
        """Return existing hybrid-ranked hits, optionally restricted by source."""
        if request.source_ids is None:
            index = self._retrieval_index
        else:
            allowed_sources = set(request.source_ids)
            restricted_records = tuple(
                record
                for record in self._retrieval_records
                if record.source_id in allowed_sources
            )
            if not restricted_records:
                return RetrieveEvidenceOutput(hits=[])
            index = HybridIndex(restricted_records, self._embedder)
        return RetrieveEvidenceOutput(
            hits=index.search(request.question, top_k=request.top_k)
        )

    def search_project_facts(
        self, request: SearchProjectFactsInput
    ) -> SearchProjectFactsOutput:
        """Delegate without changing the existing structured-search semantics."""
        matches = portfolio_search_project_facts(
            self._fact_extractions,
            query=request.query,
            fact_type=(
                request.fact_type.value if request.fact_type is not None else None
            ),
        )
        return SearchProjectFactsOutput(facts=matches)

    def read_evidence_block(
        self, request: ReadEvidenceBlockInput
    ) -> ReadEvidenceBlockOutput:
        """Return the exact existing record for one evidence ID."""
        try:
            record = self._evidence_by_id[request.evidence_id]
        except KeyError:
            raise KeyError(f"unknown evidence_id: {request.evidence_id}") from None
        return ReadEvidenceBlockOutput(record=record)
