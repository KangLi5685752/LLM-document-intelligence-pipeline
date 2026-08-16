"""Focused offline tests for the bounded Stage C evaluation layer."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from pydantic_ai import models as pydantic_ai_models
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo
from pydantic_ai.usage import RequestUsage

from document_intelligence.agentic.evaluation import (
    AgentEvaluationCaseOutcome,
    AgentEvaluationReport,
    AgentRoutingCase,
    OfflineFunctionModel,
    RoutingFactFixture,
    _evaluate_case,
    _routing_model,
    aggregate_metrics,
    count_unnecessary_tool_calls,
    load_routing_cases,
    render_markdown,
    score_task_success,
    tool_sequence_is_acceptable,
    validate_citation_integrity,
)
from document_intelligence.agentic.models import (
    AgentAnswer,
    AgentAnswerStatus,
    AgentCitation,
    AgentUsage,
)
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    PortfolioFact,
    PortfolioFactExtraction,
    RetrievalRecord,
    SupportStatus,
)
from document_intelligence.portfolio.retrieval import (
    DEVELOPMENT_SOURCE_IDS,
    load_retrieval_questions,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTING_FIXTURE = ROOT / "data/evaluation/agent_routing_cases.json"
RAG_BENCHMARK = ROOT / "data/evaluation/rag_dev_questions.json"
EVIDENCE_ID = "S001:DOC-S001-B0001"


@pytest.fixture(autouse=True)
def deny_real_model_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pydantic_ai_models, "ALLOW_MODEL_REQUESTS", False)


class FakeEmbedder:
    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray([[1.0, 0.1] for _ in texts], dtype=np.float64)


def _record() -> RetrievalRecord:
    return RetrievalRecord(
        evidence_id=EVIDENCE_ID,
        source_id="S001",
        block_id="DOC-S001-B0001",
        location_type="page",
        location_value="page 1",
        text="A fictional programme expands compute capacity.",
    )


def _service() -> DocumentToolService:
    return DocumentToolService(
        retrieval_records=[_record()],
        fact_extractions=[],
        embedder=FakeEmbedder(),
    )


def _service_with_fact() -> DocumentToolService:
    record = _record()
    evidence = EvidenceReference(
        evidence_id=record.evidence_id,
        source_id=record.source_id,
        block_id=record.block_id,
        location_type=record.location_type,
        location_value=record.location_value,
        excerpt=record.text,
    )
    fact = PortfolioFact(
        fact_id="FACT-FICTIONAL",
        fact_type=FactType.COMMITMENT,
        subject="Fictional programme",
        statement="Fictional programme expands compute capacity.",
        value="compute capacity",
        evidence_ids=[record.evidence_id],
        confidence=1.0,
        support_status=SupportStatus.SUPPORTED,
        review_required=False,
        evidence=[evidence],
    )
    return DocumentToolService(
        retrieval_records=[record],
        fact_extractions=[
            PortfolioFactExtraction(
                document_id="DOC-FICTIONAL",
                source_id="S001",
                source_format="fixture",
                facts=[fact],
            )
        ],
        embedder=FakeEmbedder(),
    )


def _answer(*, citation_id: str = EVIDENCE_ID) -> AgentAnswer:
    return AgentAnswer(
        question="What is planned?",
        status=AgentAnswerStatus.ANSWERED,
        answer=f"Compute capacity expands [{citation_id}]",
        evidence_ids=[EVIDENCE_ID],
        citations=[
            AgentCitation(
                evidence_id=EVIDENCE_ID,
                source_id="S001",
                block_id="DOC-S001-B0001",
                location_type="page",
                location_value="page 1",
            )
        ],
        tool_call_summary=[],
        usage=AgentUsage(
            requests=1,
            tool_calls=0,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            approximate_cost_usd=Decimal("0"),
        ),
    )


def _outcome(
    case_id: str,
    *,
    status: AgentAnswerStatus,
    group: str,
    citation_valid: bool | None,
    tools: list[str],
) -> AgentEvaluationCaseOutcome:
    return AgentEvaluationCaseOutcome(
        case_id=case_id,
        category="fixture",
        evaluation_group=group,  # type: ignore[arg-type]
        task_success=True,
        expected_status=status,
        actual_status=status,
        expected_evidence_ids=([EVIDENCE_ID] if status is AgentAnswerStatus.ANSWERED else []),
        actual_evidence_ids=([EVIDENCE_ID] if status is AgentAnswerStatus.ANSWERED else []),
        citation_valid=citation_valid,
        actual_tool_sequence=tools,
        tool_selection_acceptable=True,
        unnecessary_tool_calls=0,
        error=None,
    )


def _report() -> AgentEvaluationReport:
    outcomes = [
        _outcome(
            "CASE-1",
            status=AgentAnswerStatus.ANSWERED,
            group="rag_benchmark",
            citation_valid=True,
            tools=["retrieve_evidence"],
        ),
        _outcome(
            "CASE-2",
            status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE,
            group="routing",
            citation_valid=None,
            tools=["search_project_facts"],
        ),
    ]
    return AgentEvaluationReport(
        benchmark_path="data/evaluation/rag_dev_questions.json",
        benchmark_sha256="A" * 64,
        routing_cases_path="data/evaluation/agent_routing_cases.json",
        routing_cases_sha256="B" * 64,
        development_source_ids=["S001"],
        case_count=2,
        aggregate_metrics=aggregate_metrics(outcomes),
        cases=outcomes,
    )


def test_task_success_scoring_uses_status_and_labelled_evidence() -> None:
    assert score_task_success(
        expected_status=AgentAnswerStatus.ANSWERED,
        expected_evidence_ids=[EVIDENCE_ID],
        actual_status=AgentAnswerStatus.ANSWERED,
        actual_evidence_ids=[EVIDENCE_ID],
    )
    assert not score_task_success(
        expected_status=AgentAnswerStatus.ANSWERED,
        expected_evidence_ids=[EVIDENCE_ID],
        actual_status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE,
        actual_evidence_ids=[],
    )


def test_citation_validity_is_independently_reconciled() -> None:
    assert validate_citation_integrity(_answer(), _service())
    assert not validate_citation_integrity(
        _answer(citation_id="S001:DOC-S001-B9999"), _service()
    )


def test_appropriate_abstention_scoring_uses_explicit_expected_status() -> None:
    assert score_task_success(
        expected_status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE,
        expected_evidence_ids=[],
        actual_status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE,
        actual_evidence_ids=[],
    )


def test_tool_sequence_requires_an_exact_allowed_sequence() -> None:
    acceptable = [
        ["retrieve_evidence"],
        ["search_project_facts", "read_evidence_block"],
    ]
    assert tool_sequence_is_acceptable(["retrieve_evidence"], acceptable)
    assert not tool_sequence_is_acceptable(
        ["retrieve_evidence", "read_evidence_block"], acceptable
    )


def test_unnecessary_tool_calls_count_length_excess_and_unexpected_tools() -> None:
    assert count_unnecessary_tool_calls(
        ["retrieve_evidence", "read_evidence_block"],
        [["retrieve_evidence"]],
    ) == 1
    assert count_unnecessary_tool_calls(
        ["retrieve_evidence", "read_evidence_block"],
        [["retrieve_evidence", "search_project_facts"]],
    ) == 1
    assert count_unnecessary_tool_calls(
        ["search_project_facts", "read_evidence_block"],
        [["search_project_facts", "read_evidence_block"]],
    ) == 0
    actual = ["read_evidence_block", "retrieve_evidence"]
    assert count_unnecessary_tool_calls(
        actual, [["search_project_facts"]]
    ) <= len(actual)


def test_aggregate_metrics_include_average_tool_calls_and_denominators() -> None:
    report = _report()
    metrics = report.aggregate_metrics
    assert metrics.case_count == 2
    assert metrics.task_success_count == 2
    assert metrics.answered_case_count == 1
    assert metrics.citation_valid_count == 1
    assert metrics.abstention_case_count == 1
    assert metrics.appropriate_abstention_count == 1
    assert metrics.total_tool_calls == 2
    assert metrics.average_tool_calls_per_task == 1.0


def test_report_serialization_keeps_real_smoke_fields_explicitly_empty() -> None:
    payload = json.loads(_report().model_dump_json())
    assert payload["evaluation_mode"] == "offline_function_model"
    assert payload["real_smoke_performed"] is False
    assert payload["real_smoke_case_count"] == 0
    assert payload["real_latency_ms"] is None
    assert payload["real_model_usage"] is None
    assert payload["real_approximate_cost_usd"] is None
    assert "messages" not in json.dumps(payload)


def test_markdown_summary_has_required_scope_and_claim_boundary() -> None:
    markdown = render_markdown(_report())
    assert markdown.startswith("# Agent Evaluation\n")
    for heading in (
        "## Evaluation scope",
        "## Aggregate metrics",
        "## Routing/abstention results",
        "## Known failures",
        "## Interpretation",
        "## Limitations",
    ):
        assert heading in markdown
    assert "does not measure autonomous GPT-5.4-mini tool-selection quality" in markdown


def test_routing_fixture_contains_exactly_five_bounded_cases() -> None:
    cases = load_routing_cases(ROUTING_FIXTURE)
    assert len(cases) == 5
    assert len({case.id for case in cases}) == 5
    assert sum(case.fact_fixture is not None for case in cases) == 2


def test_existing_rag_benchmark_is_exactly_fifteen_development_questions() -> None:
    questions = load_retrieval_questions(RAG_BENCHMARK)
    assert len(questions) == 15
    assert {question.expected_source_id for question in questions}.issubset(
        DEVELOPMENT_SOURCE_IDS
    )
    assert not {"S005", "S007"}.intersection(
        question.expected_source_id for question in questions
    )


def test_structured_routing_script_crosses_typed_exact_read_boundary() -> None:
    case = AgentRoutingCase(
        id="ROUTE-FICTIONAL",
        category="structured_fact_search",
        question="What capacity expands?",
        expected_status=AgentAnswerStatus.ANSWERED,
        expected_evidence_ids=[EVIDENCE_ID],
        acceptable_tool_sequences=[
            ["search_project_facts", "read_evidence_block"]
        ],
        minimal_expected_tool_calls=2,
        fact_fixture=RoutingFactFixture(
            query="compute capacity",
            fact_type=FactType.COMMITMENT,
            subject="Fictional programme",
            statement="Fictional programme expands compute capacity.",
            value="compute capacity",
            evidence_id=EVIDENCE_ID,
        ),
    )
    service = _service_with_fact()
    outcome = asyncio.run(
        _evaluate_case(
            case_id=case.id,
            category=case.category,
            evaluation_group="routing",
            question=case.question,
            expected_status=case.expected_status,
            expected_evidence_ids=case.expected_evidence_ids,
            acceptable_sequences=case.acceptable_tool_sequences,
            model=_routing_model(case),
            service=service,
        )
    )
    assert outcome.task_success
    assert outcome.error is None
    assert outcome.actual_tool_sequence == [
        "search_project_facts",
        "read_evidence_block",
    ]


def test_chronological_trace_preserves_and_rejects_reversed_tool_order() -> None:
    step = 0

    def reversed_script(
        _messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        nonlocal step
        step += 1
        if step == 1:
            part = ToolCallPart(
                "read_evidence_block", {"evidence_id": EVIDENCE_ID}
            )
        elif step == 2:
            part = ToolCallPart(
                "search_project_facts", {"query": "compute capacity"}
            )
        else:
            part = ToolCallPart(
                info.output_tools[0].name,
                {
                    "status": "answered",
                    "answer": f"Compute capacity expands [{EVIDENCE_ID}]",
                    "evidence_ids": [EVIDENCE_ID],
                },
            )
        return ModelResponse(
            parts=[part],
            usage=RequestUsage(
                input_tokens=10,
                output_tokens=5,
                cost=Decimal("0"),
            ),
        )

    model = OfflineFunctionModel(reversed_script)
    outcome = asyncio.run(
        _evaluate_case(
            case_id="ROUTE-REVERSED",
            category="fixture",
            evaluation_group="routing",
            question="What capacity expands?",
            expected_status=AgentAnswerStatus.ANSWERED,
            expected_evidence_ids=[EVIDENCE_ID],
            acceptable_sequences=[
                ["search_project_facts", "read_evidence_block"]
            ],
            model=model,
            service=_service_with_fact(),
        )
    )
    assert outcome.actual_tool_sequence == [
        "read_evidence_block",
        "search_project_facts",
    ]
    assert outcome.tool_selection_acceptable is False
    assert outcome.unnecessary_tool_calls == 1
