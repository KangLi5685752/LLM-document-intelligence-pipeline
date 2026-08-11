"""Focused offline coverage for the portfolio extraction and RAG path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
    SourceLocation,
)
from document_intelligence.portfolio import cli
from document_intelligence.portfolio.extraction import (
    extract_project_facts,
    search_project_facts,
)
from document_intelligence.portfolio.models import (
    FactType,
    PortfolioFactDraft,
    PortfolioFactExtraction,
    RetrievalQuestion,
    RetrievalRecord,
    SupportStatus,
)
from document_intelligence.portfolio.rag import answer_question
from document_intelligence.portfolio.retrieval import (
    RRF_K,
    HybridIndex,
    LexicalIndex,
    SemanticIndex,
    build_retrieval_records,
    evaluate_retrieval,
    load_retrieval_questions,
    load_retrieval_records,
)


def _document(source_id: str = "DEMO") -> ParsedDocument:
    return ParsedDocument(
        document_id=f"DOC-{source_id}",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=f"{source_id}.pdf",
        checksum_sha256="A" * 64,
        blocks=[
            DocumentBlock(
                block_id=f"DOC-{source_id}-B0001",
                sequence=1,
                block_type=BlockType.PAGE_TEXT,
                text="The programme will expand secure compute capacity by 2030.",
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value="page 1",
                    page_number=1,
                ),
            ),
            DocumentBlock(
                block_id=f"DOC-{source_id}-B0002",
                sequence=2,
                block_type=BlockType.PAGE_TEXT,
                text="The delivery team owns the implementation risk.",
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value="page 2",
                    page_number=2,
                ),
            ),
        ],
        parse_status=ParseStatus.SUCCESS,
    )


def _draft_response(evidence_id: str, **overrides: Any) -> str:
    fact = {
        "fact_type": "commitment",
        "subject": "The programme",
        "statement": "The programme will expand secure compute capacity by 2030.",
        "value": "by 2030",
        "evidence_ids": [evidence_id],
        "confidence": 0.94,
        "support_status": "supported",
        "review_required": False,
    }
    fact.update(overrides)
    return json.dumps({"facts": [fact]})


class KeywordEmbedder:
    """Small deterministic embedder that never downloads a model."""

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.casefold()
            rows.append(
                [
                    float("compute" in lowered or "infrastructure" in lowered),
                    float("risk" in lowered or "delivery" in lowered),
                    0.1,
                ]
            )
        return np.asarray(rows, dtype=np.float64)


class FixedEmbedder:
    """Return explicitly assigned vectors for hybrid-ranking tests."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray([self._vectors[text] for text in texts], dtype=np.float64)


def _record(block_id: str, text: str) -> RetrievalRecord:
    return RetrievalRecord(
        evidence_id=f"DEMO:{block_id}",
        source_id="DEMO",
        block_id=block_id,
        location_type="page",
        location_value="page 1",
        text=text,
    )


def test_fact_schema_routes_ambiguous_claims_to_review() -> None:
    fact = PortfolioFactDraft.model_validate(
        json.loads(
            _draft_response(
                "DEMO:DOC-DEMO-B0001",
                support_status="ambiguous",
                review_required=True,
            )
        )["facts"][0]
    )
    assert fact.support_status is SupportStatus.AMBIGUOUS
    assert fact.review_required is True


def test_fact_schema_rejects_ambiguous_claim_without_review() -> None:
    with pytest.raises(ValidationError, match="ambiguous facts must require review"):
        PortfolioFactDraft.model_validate(
            json.loads(
                _draft_response(
                    "DEMO:DOC-DEMO-B0001",
                    support_status="ambiguous",
                    review_required=False,
                )
            )["facts"][0]
        )


def test_extraction_hydrates_exact_evidence_and_builds_stable_fact_id() -> None:
    document = _document()
    evidence_id = "DEMO:DOC-DEMO-B0001"
    responder = lambda payload: _draft_response(evidence_id)
    first = extract_project_facts(document, responder=responder)
    second = extract_project_facts(document, responder=responder)

    assert first == second
    assert first.facts[0].fact_id.startswith("FACT-")
    assert first.facts[0].evidence[0].model_dump() == {
        "evidence_id": evidence_id,
        "source_id": "DEMO",
        "block_id": "DOC-DEMO-B0001",
        "location_type": "page",
        "location_value": "page 1",
        "excerpt": "The programme will expand secure compute capacity by 2030.",
    }


def test_extraction_rejects_unknown_evidence_id() -> None:
    with pytest.raises(ValueError, match="unknown evidence IDs"):
        extract_project_facts(
            _document(), responder=lambda payload: _draft_response("DEMO:UNKNOWN")
        )


def test_extraction_payload_uses_strict_no_tools_responses_contract() -> None:
    observed: dict[str, Any] = {}

    def responder(payload: dict[str, Any]) -> str:
        observed.update(payload)
        return _draft_response("DEMO:DOC-DEMO-B0001")

    extract_project_facts(_document(), responder=responder)
    assert observed["model"] == "gpt-5.4-mini"
    assert observed["store"] is False
    assert observed["tools"] == []
    assert observed["tool_choice"] == "none"
    assert observed["text"]["format"]["strict"] is True
    assert observed["max_output_tokens"] == 4096
    assert observed["reasoning"] == {"effort": "none"}


def test_structured_search_filters_type_and_text() -> None:
    extraction = extract_project_facts(
        _document(),
        responder=lambda payload: _draft_response("DEMO:DOC-DEMO-B0001"),
    )
    assert search_project_facts(
        [extraction], fact_type="commitment", query="COMPUTE"
    ) == extraction.facts
    assert search_project_facts([extraction], fact_type="risk", query="compute") == []


def test_retrieval_ranks_semantically_matching_block_first() -> None:
    records = build_retrieval_records(_document())
    hits = SemanticIndex(records, KeywordEmbedder()).search(
        "What compute infrastructure is planned?", top_k=2
    )
    assert [hit.block_id for hit in hits] == [
        "DOC-DEMO-B0001",
        "DOC-DEMO-B0002",
    ]
    assert hits[0].score > hits[1].score


def test_lexical_retrieval_prefers_an_exact_rare_token() -> None:
    records = [
        _record("B0001", "A general programme delivery update."),
        _record("B0002", "The zephyrite milestone is due this quarter."),
    ]
    hits = LexicalIndex(records).search("zephyrite", top_k=2)
    assert hits[0].block_id == "B0002"
    assert hits[0].score > hits[1].score


def test_rrf_combines_rankings_and_breaks_fused_ties_deterministically() -> None:
    records = [
        _record("B0001", "lexical-token appears here"),
        _record("B0002", "semantic proxy"),
    ]
    embedder = FixedEmbedder(
        {
            "lexical-token": [1.0, 0.0],
            "lexical-token appears here": [0.0, 1.0],
            "semantic proxy": [1.0, 0.0],
        }
    )
    hits = HybridIndex(records, embedder).search("lexical-token", top_k=2)
    expected_tied_score = 1.0 / (RRF_K + 1) + 1.0 / (RRF_K + 2)
    assert [hit.block_id for hit in hits] == ["B0001", "B0002"]
    assert hits[0].score == pytest.approx(expected_tied_score)
    assert hits[1].score == pytest.approx(expected_tied_score)


def test_hybrid_retrieval_recovers_expected_record_in_small_corpus() -> None:
    records = [
        _record("B0001", "The quasar roadmap names a delivery checkpoint."),
        _record("B0002", "A separate staffing note."),
        _record("B0003", "A semantic proxy for the roadmap."),
    ]
    embedder = FixedEmbedder(
        {
            "quasar roadmap": [1.0, 0.0],
            "The quasar roadmap names a delivery checkpoint.": [0.8, 0.2],
            "A separate staffing note.": [0.0, 1.0],
            "A semantic proxy for the roadmap.": [1.0, 0.0],
        }
    )
    hits = HybridIndex(records, embedder).search("quasar roadmap", top_k=3)
    assert hits[0].evidence_id == "DEMO:B0001"


def test_selected_source_loading_does_not_open_unselected_json(tmp_path: Path) -> None:
    (tmp_path / "DEMO.json").write_text(
        _document().model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (tmp_path / "UNSELECTED.json").write_text("not-json\n", encoding="utf-8")
    records = load_retrieval_records(tmp_path, source_ids={"DEMO"})
    assert len(records) == 2


def test_grounded_answer_hydrates_valid_citation() -> None:
    records = build_retrieval_records(_document())
    answer = answer_question(
        records,
        "What compute capacity is planned?",
        embedder=KeywordEmbedder(),
        responder=lambda payload: json.dumps(
            {
                "answer": "Secure compute capacity will expand by 2030 "
                "[DEMO:DOC-DEMO-B0001].",
                "citations": ["DEMO:DOC-DEMO-B0001"],
            }
        ),
        top_k=1,
    )
    assert answer.citations[0].location_value == "page 1"
    assert answer.retrieved_evidence[0].block_id == "DOC-DEMO-B0001"


def test_grounded_answer_rejects_invented_citation() -> None:
    with pytest.raises(ValueError, match="unknown citations"):
        answer_question(
            build_retrieval_records(_document()),
            "What compute capacity is planned?",
            embedder=KeywordEmbedder(),
            responder=lambda payload: json.dumps(
                {
                    "answer": "It will expand [DEMO:INVENTED].",
                    "citations": ["DEMO:INVENTED"],
                }
            ),
            top_k=1,
        )


def test_grounded_answer_allows_explicit_insufficient_evidence_refusal() -> None:
    answer = answer_question(
        build_retrieval_records(_document()),
        "What is the final programme cost?",
        embedder=KeywordEmbedder(),
        responder=lambda payload: json.dumps(
            {"answer": "The supplied evidence is insufficient.", "citations": []}
        ),
    )
    assert answer.citations == []
    assert "insufficient" in answer.answer


def test_retrieval_evaluation_calculates_hit_at_k_and_mrr() -> None:
    records = build_retrieval_records(_document("S001"))
    questions = [
        RetrievalQuestion(
            id="Q1",
            question="What compute infrastructure is planned?",
            expected_source_id="S001",
            expected_block_ids=["DOC-S001-B0001"],
        ),
        RetrievalQuestion(
            id="Q2",
            question="Who owns the delivery risk?",
            expected_source_id="S001",
            expected_block_ids=["DOC-S001-B0002"],
        ),
    ]
    report = evaluate_retrieval(
        records, questions, embedder=KeywordEmbedder(), include_diagnostics=True
    )
    assert report.question_count == 2
    assert report.hit_at_1 == 1.0
    assert report.hit_at_3 == 1.0
    assert report.hit_at_5 == 1.0
    assert report.mean_reciprocal_rank == 1.0
    assert report.question_diagnostics is not None
    assert [item.first_relevant_rank for item in report.question_diagnostics] == [
        1,
        1,
    ]
    assert report.question_diagnostics[0].top_5_evidence_ids == [
        "S001:DOC-S001-B0001",
        "S001:DOC-S001-B0002",
    ]


def test_committed_benchmark_has_fifteen_development_only_questions() -> None:
    root = Path(__file__).resolve().parents[1]
    questions = load_retrieval_questions(
        root / "data" / "evaluation" / "rag_dev_questions.json"
    )
    assert len(questions) == 15
    assert {question.expected_source_id for question in questions} == {
        "S001",
        "S002",
        "S003",
        "S004",
        "S006",
    }


def test_search_cli_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    extraction = extract_project_facts(
        _document(),
        responder=lambda payload: _draft_response("DEMO:DOC-DEMO-B0001"),
    )
    path = tmp_path / "DEMO.facts.json"
    path.write_text(extraction.model_dump_json(indent=2) + "\n", encoding="utf-8")
    assert cli.main(
        ["search", "--facts", str(path), "--type", "commitment", "--query", "compute"]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["match_count"] == 1
    assert output["matches"][0]["fact_type"] == FactType.COMMITMENT.value
