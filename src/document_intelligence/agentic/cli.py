"""Default-closed command line entry point for the bounded document agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from document_intelligence.agentic.agent import run_document_agent
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import PortfolioFactExtraction
from document_intelligence.portfolio.retrieval import (
    DEVELOPMENT_SOURCE_IDS,
    SentenceTransformerEmbedder,
    load_retrieval_records,
)


EXECUTION_CONFIRMATION = "EXECUTE_BOUNDED_DOCUMENT_AGENT_V1"
REAL_MODEL_NAME = "gpt-5.4-mini"


def build_parser() -> argparse.ArgumentParser:
    """Build the single real-execution command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument(
        "--source-id", action="append", dest="source_ids", required=True
    )
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--question", required=True)
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    parser.add_argument("--execute-real-agent", action="store_true")
    parser.add_argument("--confirm-execution")
    return parser


def _print_json(value: Any, *, stream: Any = sys.stdout) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream)


def _execution_authorized(args: argparse.Namespace) -> bool:
    return bool(
        args.execute_real_agent
        and args.confirm_execution == EXECUTION_CONFIRMATION
    )


def _validate_source_ids(source_ids: list[str]) -> list[str]:
    normalized = [source_id.strip() for source_id in source_ids]
    if any(not source_id for source_id in normalized):
        raise ValueError("source IDs must not be blank")
    if len(normalized) != len(set(normalized)):
        raise ValueError("source IDs must be unique")
    unsupported = set(normalized) - DEVELOPMENT_SOURCE_IDS
    if unsupported:
        raise ValueError(
            "real agent source IDs must be explicit development sources; rejected: "
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


def _read_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is required for explicitly authorized execution"
        )
    return api_key


def _build_real_model(api_key: str) -> OpenAIResponsesModel:
    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=120.0)
    provider = OpenAIProvider(openai_client=client)
    return OpenAIResponsesModel(REAL_MODEL_NAME, provider=provider)


def main(argv: list[str] | None = None) -> int:
    """Run one explicitly confirmed bounded real-agent query."""
    args = build_parser().parse_args(argv)
    if not _execution_authorized(args):
        _print_json(
            {
                "status": "execution_refused",
                "error": "both explicit real-agent execution gates are required",
            },
            stream=sys.stderr,
        )
        return 2

    source_ids = _validate_source_ids(args.source_ids)
    api_key = _read_api_key()
    model = _build_real_model(api_key)
    records = load_retrieval_records(args.parsed_root, source_ids=source_ids)
    service = DocumentToolService(
        retrieval_records=records,
        fact_extractions=_load_fact_extractions(args.facts, source_ids),
        embedder=SentenceTransformerEmbedder(args.embedding_model),
    )
    answer = asyncio.run(
        run_document_agent(args.question, tool_service=service, model=model)
    )
    _print_json(answer.model_dump(mode="json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
