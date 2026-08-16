"""Standalone stdio MCP facade over the three deterministic document tools."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Annotated

from mcp.server import MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

from document_intelligence.agentic.models import (
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    SearchProjectFactsInput,
    SearchProjectFactsOutput,
)
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import FactType, PortfolioFactExtraction
from document_intelligence.portfolio.retrieval import (
    DEVELOPMENT_SOURCE_IDS,
    SentenceTransformerEmbedder,
    load_retrieval_records,
)


SERVER_NAME = "LLM Document Intelligence"
SERVER_INSTRUCTIONS = (
    "Read-only document retrieval, structured fact search, and exact evidence "
    "inspection over explicitly loaded local sources."
)
READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
)


def build_mcp_server(tool_service: DocumentToolService) -> MCPServer:
    """Expose the existing injected document service through exactly three tools."""
    server = MCPServer(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        version="0.1.0",
    )

    @server.tool(annotations=READ_ONLY_ANNOTATIONS, structured_output=True)
    def retrieve_evidence(
        question: str,
        source_ids: list[str] | None = None,
        top_k: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> RetrieveEvidenceOutput:
        """Retrieve ranked evidence from the explicitly loaded document blocks."""
        return tool_service.retrieve_evidence(
            RetrieveEvidenceInput(
                question=question,
                source_ids=source_ids,
                top_k=top_k,
            )
        )

    @server.tool(annotations=READ_ONLY_ANNOTATIONS, structured_output=True)
    def search_project_facts(
        query: str | None = None,
        fact_type: FactType | None = None,
    ) -> SearchProjectFactsOutput:
        """Search the existing structured project facts without extracting new facts."""
        return tool_service.search_project_facts(
            SearchProjectFactsInput(query=query, fact_type=fact_type)
        )

    @server.tool(annotations=READ_ONLY_ANNOTATIONS, structured_output=True)
    def read_evidence_block(evidence_id: str) -> ReadEvidenceBlockOutput:
        """Read one exact evidence block and its existing provenance."""
        return tool_service.read_evidence_block(
            ReadEvidenceBlockInput(evidence_id=evidence_id)
        )

    return server


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone stdio server argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument(
        "--source-id", action="append", dest="source_ids", required=True
    )
    parser.add_argument("--facts", type=Path)
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    return parser


def _validate_source_ids(source_ids: list[str]) -> list[str]:
    normalized = [source_id.strip() for source_id in source_ids]
    if any(not source_id for source_id in normalized):
        raise ValueError("source IDs must not be blank")
    if len(normalized) != len(set(normalized)):
        raise ValueError("source IDs must be unique")
    unsupported = set(normalized) - DEVELOPMENT_SOURCE_IDS
    if unsupported:
        raise ValueError(
            "MCP source IDs must be explicit development sources; rejected: "
            + ", ".join(sorted(unsupported))
        )
    return normalized


def _load_fact_extractions(
    path: Path | None, source_ids: list[str]
) -> list[PortfolioFactExtraction]:
    if path is None:
        return []
    if path.is_file():
        paths = [path]
    else:
        paths = [
            match
            for source_id in sorted(source_ids)
            for match in sorted(path.rglob(f"{source_id}.facts.json"))
        ]
    if not paths:
        raise ValueError("no fact extraction JSON files were found")
    extractions = [
        PortfolioFactExtraction.model_validate_json(item.read_text(encoding="utf-8"))
        for item in paths
    ]
    unexpected_sources = {
        item.source_id for item in extractions if item.source_id not in source_ids
    }
    if unexpected_sources:
        raise ValueError(
            "fact extraction contains an unrequested source: "
            + ", ".join(sorted(unexpected_sources))
        )
    return extractions


def main(argv: list[str] | None = None) -> int:
    """Load explicit local sources and run the read-only MCP server over stdio."""
    args = build_parser().parse_args(argv)
    source_ids = _validate_source_ids(args.source_ids)
    records = load_retrieval_records(args.parsed_root, source_ids=source_ids)
    facts = _load_fact_extractions(args.facts, source_ids)
    tool_service = DocumentToolService(
        retrieval_records=records,
        fact_extractions=facts,
        embedder=SentenceTransformerEmbedder(args.embedding_model),
    )
    build_mcp_server(tool_service).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
