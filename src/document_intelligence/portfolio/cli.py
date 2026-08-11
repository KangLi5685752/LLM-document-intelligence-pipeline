"""Command-line interfaces for portfolio extraction, search, and RAG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.portfolio.extraction import (
    DEFAULT_MODEL,
    extract_project_facts,
    search_project_facts,
)
from document_intelligence.portfolio.models import FactType, PortfolioFactExtraction
from document_intelligence.portfolio.rag import answer_question
from document_intelligence.portfolio.retrieval import (
    DEVELOPMENT_SOURCE_IDS,
    HybridIndex,
    SentenceTransformerEmbedder,
    evaluate_retrieval,
    load_retrieval_questions,
    load_retrieval_records,
)


DEFAULT_BENCHMARK = Path("data/evaluation/rag_dev_questions.json")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(_jsonable(value), ensure_ascii=False, indent=2))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_extractions(path: Path) -> list[PortfolioFactExtraction]:
    paths = [path] if path.is_file() else sorted(path.rglob("*.facts.json"))
    if not paths:
        raise ValueError("no fact extraction JSON files were found")
    return [
        PortfolioFactExtraction.model_validate_json(item.read_text(encoding="utf-8"))
        for item in paths
    ]


def _add_retrieval_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="Source ID to load; repeat to restrict the corpus safely.",
    )
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the shared parser for module and installed-script entry points."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="Extract evidence-linked facts")
    extract.add_argument("--input", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--model", default=DEFAULT_MODEL)

    search = commands.add_parser("search", help="Search extracted fact JSON")
    search.add_argument("--facts", type=Path, required=True)
    search.add_argument("--type", choices=[item.value for item in FactType])
    search.add_argument("--query")

    rag_search = commands.add_parser("rag-search", help="Retrieve relevant blocks")
    _add_retrieval_arguments(rag_search)
    rag_search.add_argument("--query", required=True)

    rag_query = commands.add_parser("rag-query", help="Answer from retrieved blocks")
    _add_retrieval_arguments(rag_query)
    rag_query.add_argument("--question", required=True)
    rag_query.add_argument("--model", default=DEFAULT_MODEL)

    evaluate = commands.add_parser("evaluate", help="Evaluate development retrieval")
    evaluate.add_argument("--parsed-root", type=Path, required=True)
    evaluate.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one portfolio application command."""
    args = build_parser().parse_args(argv)
    if args.command == "extract":
        document = ParsedDocument.model_validate_json(
            args.input.read_text(encoding="utf-8")
        )
        result = extract_project_facts(document, model=args.model)
        _write_json(args.output, result)
        _print_json(result)
        return 0

    if args.command == "search":
        results = search_project_facts(
            _load_extractions(args.facts), fact_type=args.type, query=args.query
        )
        _print_json({"match_count": len(results), "matches": results})
        return 0

    if args.command in {"rag-search", "rag-query"}:
        records = load_retrieval_records(
            args.parsed_root, source_ids=args.source_ids
        )
        embedder = SentenceTransformerEmbedder(args.embedding_model)
        if args.command == "rag-search":
            _print_json(HybridIndex(records, embedder).search(args.query, top_k=args.top_k))
        else:
            _print_json(
                answer_question(
                    records,
                    args.question,
                    embedder=embedder,
                    top_k=args.top_k,
                    model=args.model,
                )
            )
        return 0

    if args.command == "evaluate":
        questions = load_retrieval_questions(args.benchmark)
        requested_sources = {question.expected_source_id for question in questions}
        if not requested_sources.issubset(DEVELOPMENT_SOURCE_IDS):
            raise ValueError("retrieval benchmark must contain development sources only")
        records = load_retrieval_records(
            args.parsed_root, source_ids=requested_sources
        )
        report = evaluate_retrieval(
            records,
            questions,
            embedder=SentenceTransformerEmbedder(args.embedding_model),
            include_diagnostics=True,
        )
        if args.output is not None:
            _write_json(args.output, report)
        _print_json(report)
        return 0

    raise AssertionError(f"unsupported command: {args.command}")


def _entrypoint(command: str) -> int:
    return main([command, *sys.argv[1:]])


def main_extract() -> int:
    return _entrypoint("extract")


def main_search() -> int:
    return _entrypoint("search")


def main_rag_search() -> int:
    return _entrypoint("rag-search")


def main_rag_query() -> int:
    return _entrypoint("rag-query")


def main_evaluate() -> int:
    return _entrypoint("evaluate")


if __name__ == "__main__":
    raise SystemExit(main())
