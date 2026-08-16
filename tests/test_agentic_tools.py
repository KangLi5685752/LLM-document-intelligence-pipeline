"""Focused offline tests for the three Stage A read-only tool adapters."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

import document_intelligence.agentic.tools as agentic_tools
from document_intelligence.agentic.models import (
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    SearchProjectFactsInput,
    SearchProjectFactsOutput,
)
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    PortfolioFact,
    PortfolioFactExtraction,
    RetrievalHit,
    RetrievalRecord,
    SupportStatus,
)


class FakeEmbedder:
    """Deterministic local vectors with no model download or provider access."""

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append(
                [
                    float("compute" in lowered),
                    float("risk" in lowered),
                    0.1,
                ]
            )
        return np.asarray(vectors, dtype=np.float64)


def _record(source_id: str, ordinal: int, text: str) -> RetrievalRecord:
    block_id = f"DOC-{source_id}-B{ordinal:04d}"
    return RetrievalRecord(
        evidence_id=f"{source_id}:{block_id}",
        source_id=source_id,
        block_id=block_id,
        location_type="page",
        location_value=f"page {ordinal}",
        text=text,
    )


def _fact_extraction(record: RetrievalRecord) -> PortfolioFactExtraction:
    evidence = EvidenceReference(
        evidence_id=record.evidence_id,
        source_id=record.source_id,
        block_id=record.block_id,
        location_type=record.location_type,
        location_value=record.location_value,
        excerpt=record.text,
    )
    fact = PortfolioFact(
        fact_id="FACT-DEMO0001",
        fact_type=FactType.COMMITMENT,
        subject="The programme",
        statement="The programme will expand compute capacity.",
        value="compute capacity",
        evidence_ids=[record.evidence_id],
        confidence=0.9,
        support_status=SupportStatus.SUPPORTED,
        review_required=False,
        evidence=[evidence],
    )
    return PortfolioFactExtraction(
        document_id=f"DOC-{record.source_id}",
        source_id=record.source_id,
        source_format="PDF",
        facts=[fact],
    )


@pytest.fixture
def tool_data() -> tuple[
    list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
]:
    records = [
        _record("S001", 1, "The programme will expand secure compute capacity."),
        _record("S002", 1, "The delivery team owns the implementation risk."),
    ]
    extractions = [_fact_extraction(records[0])]
    service = DocumentToolService(
        retrieval_records=records,
        fact_extractions=extractions,
        embedder=FakeEmbedder(),
    )
    return records, extractions, service


def test_retrieve_evidence_returns_typed_existing_hybrid_hits(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    _, _, service = tool_data
    result = service.retrieve_evidence(
        RetrieveEvidenceInput(question="What compute capacity is planned?", top_k=2)
    )
    assert isinstance(result, RetrieveEvidenceOutput)
    assert all(isinstance(hit, RetrievalHit) for hit in result.hits)
    assert result.hits[0].evidence_id == "S001:DOC-S001-B0001"


def test_retrieve_evidence_restricts_the_corpus_before_ranking(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    _, _, service = tool_data
    result = service.retrieve_evidence(
        RetrieveEvidenceInput(
            question="What compute capacity is planned?",
            source_ids=["S002"],
            top_k=5,
        )
    )
    assert [hit.source_id for hit in result.hits] == ["S002"]


def test_fact_search_delegates_to_existing_portfolio_search(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, extractions, service = tool_data
    expected = extractions[0].facts
    observed: dict[str, object] = {}

    def fake_search(
        supplied: object, *, query: str | None, fact_type: str | None
    ) -> list[PortfolioFact]:
        observed.update(
            supplied=tuple(supplied), query=query, fact_type=fact_type  # type: ignore[arg-type]
        )
        return expected

    monkeypatch.setattr(agentic_tools, "portfolio_search_project_facts", fake_search)
    result = service.search_project_facts(
        SearchProjectFactsInput(query="compute", fact_type=FactType.COMMITMENT)
    )
    assert isinstance(result, SearchProjectFactsOutput)
    assert result.facts == expected
    assert observed == {
        "supplied": tuple(extractions),
        "query": "compute",
        "fact_type": "commitment",
    }


def test_read_evidence_block_returns_the_original_record_and_provenance(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    records, _, service = tool_data
    result = service.read_evidence_block(
        ReadEvidenceBlockInput(evidence_id=records[0].evidence_id)
    )
    assert isinstance(result, ReadEvidenceBlockOutput)
    assert result.record is records[0]
    assert result.record.model_dump() == records[0].model_dump()


def test_read_evidence_block_rejects_unknown_evidence_id(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    _, _, service = tool_data
    with pytest.raises(KeyError) as exc_info:
        service.read_evidence_block(ReadEvidenceBlockInput(evidence_id="S999:UNKNOWN"))
    assert exc_info.value.args == ("unknown evidence_id: S999:UNKNOWN",)


def test_tool_inputs_reject_blank_or_out_of_bounds_values() -> None:
    with pytest.raises(ValidationError):
        RetrieveEvidenceInput(question=" ")
    with pytest.raises(ValidationError):
        RetrieveEvidenceInput(question="valid", top_k=0)
    with pytest.raises(ValidationError):
        RetrieveEvidenceInput(question="valid", top_k=21)
    with pytest.raises(ValidationError):
        RetrieveEvidenceInput(question="valid", source_ids=[])
    with pytest.raises(ValidationError):
        SearchProjectFactsInput(query="\t")
    with pytest.raises(ValidationError):
        ReadEvidenceBlockInput(evidence_id="")


def test_tools_do_not_mutate_supplied_records_or_facts(
    tool_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    records, extractions, service = tool_data
    records_before = [record.model_dump_json() for record in records]
    extractions_before = [item.model_dump_json() for item in extractions]

    service.retrieve_evidence(RetrieveEvidenceInput(question="compute", top_k=2))
    service.search_project_facts(SearchProjectFactsInput(query="compute"))
    service.read_evidence_block(
        ReadEvidenceBlockInput(evidence_id=records[0].evidence_id)
    )

    assert [record.model_dump_json() for record in records] == records_before
    assert [item.model_dump_json() for item in extractions] == extractions_before
