"""In-process tests for the three-tool read-only MCP facade."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from mcp.client import Client
from mcp.server import MCPServer

import document_intelligence.agentic.mcp_server as mcp_module
from document_intelligence.agentic.mcp_server import build_mcp_server
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    PortfolioFact,
    PortfolioFactExtraction,
    RetrievalRecord,
    SupportStatus,
)


class FakeEmbedder:
    """Deterministic local embedder without model loading or network access."""

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [
                [
                    float("compute" in text.casefold()),
                    float("risk" in text.casefold()),
                    0.1,
                ]
                for text in texts
            ],
            dtype=np.float64,
        )


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
    return PortfolioFactExtraction(
        document_id=f"DOC-{record.source_id}",
        source_id=record.source_id,
        source_format="PDF",
        facts=[
            PortfolioFact(
                fact_id="FACT-FICTIONAL-001",
                fact_type=FactType.COMMITMENT,
                subject="The programme",
                statement="The programme will expand secure compute capacity.",
                value="secure compute capacity",
                evidence_ids=[record.evidence_id],
                confidence=0.9,
                support_status=SupportStatus.SUPPORTED,
                review_required=False,
                evidence=[evidence],
            )
        ],
    )


@pytest.fixture
def mcp_data() -> tuple[
    list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
]:
    records = [
        _record("S001", 1, "The programme will expand secure compute capacity."),
        _record("S002", 1, "The delivery team owns the implementation risk."),
    ]
    facts = [_fact_extraction(records[0])]
    service = DocumentToolService(
        retrieval_records=records,
        fact_extractions=facts,
        embedder=FakeEmbedder(),
    )
    return records, facts, service


def test_server_advertises_exact_typed_read_only_tools_and_no_other_capabilities(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    async def inspect_server() -> None:
        server = build_mcp_server(mcp_data[2])
        assert isinstance(server, MCPServer)
        async with Client(server, raise_exceptions=True) as client:
            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == [
                "retrieve_evidence",
                "search_project_facts",
                "read_evidence_block",
            ]
            schemas = {tool.name: tool.input_schema for tool in listed.tools}
            assert set(schemas["retrieve_evidence"]["properties"]) == {
                "question",
                "source_ids",
                "top_k",
            }
            assert schemas["retrieve_evidence"]["required"] == ["question"]
            assert set(schemas["search_project_facts"]["properties"]) == {
                "query",
                "fact_type",
            }
            assert set(schemas["read_evidence_block"]["properties"]) == {
                "evidence_id"
            }
            assert schemas["read_evidence_block"]["required"] == ["evidence_id"]
            assert all(tool.output_schema is not None for tool in listed.tools)
            assert all(
                tool.annotations is not None
                and tool.annotations.read_only_hint is True
                and tool.annotations.destructive_hint is False
                and tool.annotations.open_world_hint is False
                for tool in listed.tools
            )
            assert (await client.list_resources()).resources == []
            assert (await client.list_prompts()).prompts == []

    asyncio.run(inspect_server())


def test_retrieve_evidence_returns_structured_ranked_output_and_filters_sources(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    async def call_tools() -> None:
        async with Client(build_mcp_server(mcp_data[2]), raise_exceptions=True) as client:
            ranked = await client.call_tool(
                "retrieve_evidence",
                {"question": "What compute capacity is planned?", "top_k": 2},
            )
            assert ranked.is_error is False
            assert ranked.structured_content is not None
            assert ranked.structured_content["hits"][0]["evidence_id"] == (
                "S001:DOC-S001-B0001"
            )

            filtered = await client.call_tool(
                "retrieve_evidence",
                {
                    "question": "What compute capacity is planned?",
                    "source_ids": ["S002"],
                    "top_k": 5,
                },
            )
            assert [
                hit["source_id"] for hit in filtered.structured_content["hits"]
            ] == ["S002"]

    asyncio.run(call_tools())


def test_fact_search_and_exact_evidence_read_are_structured_and_non_mutating(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    records, facts, service = mcp_data
    records_before = [item.model_dump_json() for item in records]
    facts_before = [item.model_dump_json() for item in facts]

    async def call_tools() -> None:
        async with Client(build_mcp_server(service), raise_exceptions=True) as client:
            for _ in range(2):
                search = await client.call_tool(
                    "search_project_facts",
                    {"query": "compute", "fact_type": "commitment"},
                )
                assert search.is_error is False
                assert search.structured_content["facts"][0]["fact_id"] == (
                    "FACT-FICTIONAL-001"
                )

                evidence = await client.call_tool(
                    "read_evidence_block", {"evidence_id": records[0].evidence_id}
                )
                assert evidence.is_error is False
                assert evidence.structured_content["record"] == records[0].model_dump(
                    mode="json"
                )

    asyncio.run(call_tools())
    assert [item.model_dump_json() for item in records] == records_before
    assert [item.model_dump_json() for item in facts] == facts_before


def test_unknown_evidence_id_surfaces_as_mcp_tool_error(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
) -> None:
    async def call_unknown() -> None:
        async with Client(build_mcp_server(mcp_data[2]), raise_exceptions=True) as client:
            result = await client.call_tool(
                "read_evidence_block", {"evidence_id": "S001:UNKNOWN"}
            )
            assert result.is_error is True
            assert result.structured_content is None
            assert "unknown evidence_id: S001:UNKNOWN" in result.content[0].text  # type: ignore[union-attr]

    asyncio.run(call_unknown())


@pytest.mark.parametrize("source_id", ["S005", "S007", "S999"])
def test_unsupported_source_fails_before_document_loading(
    source_id: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden_loader(*args: Any, **kwargs: Any) -> list[RetrievalRecord]:
        raise AssertionError("document loading must not occur")

    monkeypatch.setattr(mcp_module, "load_retrieval_records", forbidden_loader)
    with pytest.raises(ValueError, match="explicit development sources"):
        mcp_module.main(
            ["--parsed-root", str(tmp_path), "--source-id", source_id]
        )


def test_fact_file_for_unrequested_source_is_rejected(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
    tmp_path: Path,
) -> None:
    fact_path = tmp_path / "unrequested.facts.json"
    fact_path.write_text(mcp_data[1][0].model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="unrequested source: S001"):
        mcp_module._load_fact_extractions(fact_path, ["S002"])


def test_valid_startup_loads_only_explicit_sources_and_runs_stdio(
    mcp_data: tuple[
        list[RetrievalRecord], list[PortfolioFactExtraction], DocumentToolService
    ],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    def fake_load(
        parsed_root: Path, *, source_ids: list[str]
    ) -> list[RetrievalRecord]:
        observed["parsed_root"] = parsed_root
        observed["source_ids"] = source_ids
        return mcp_data[0]

    class FakeServer:
        def run(self, transport: str) -> None:
            observed["transport"] = transport

    monkeypatch.setattr(mcp_module, "load_retrieval_records", fake_load)
    monkeypatch.setattr(mcp_module, "SentenceTransformerEmbedder", lambda _: FakeEmbedder())
    monkeypatch.setattr(
        mcp_module,
        "build_mcp_server",
        lambda service: observed.setdefault("service", service) and FakeServer(),
    )

    result = mcp_module.main(
        [
            "--parsed-root",
            str(tmp_path),
            "--source-id",
            "S001",
            "--source-id",
            "S002",
            "--embedding-model",
            "fictional-local-model",
        ]
    )
    assert result == 0
    assert observed["parsed_root"] == tmp_path
    assert observed["source_ids"] == ["S001", "S002"]
    assert isinstance(observed["service"], DocumentToolService)
    assert observed["transport"] == "stdio"
