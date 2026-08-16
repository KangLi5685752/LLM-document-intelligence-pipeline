"""Bounded offline evaluation of document-agent orchestration and grounding."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic_ai import ModelSettings
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from document_intelligence.agentic.agent import run_document_agent
from document_intelligence.agentic.models import (
    AgentAnswer,
    AgentAnswerStatus,
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceOutput,
    SearchProjectFactsOutput,
)
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    PortfolioFact,
    PortfolioFactExtraction,
    RetrievalQuestion,
    RetrievalRecord,
    SupportStatus,
)
from document_intelligence.portfolio.retrieval import (
    DEVELOPMENT_SOURCE_IDS,
    SentenceTransformerEmbedder,
    load_retrieval_questions,
    load_retrieval_records,
)


EVALUATION_MODE = "offline_function_model"
RAG_CASE_COUNT = 15
ROUTING_CASE_COUNT = 5
MAX_CASE_COUNT = 20
_CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9_-]+):([A-Za-z0-9_.-]+)\]")


class RoutingFactFixture(BaseModel):
    """Minimal structured fact needed by one deterministic routing case."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    fact_type: FactType
    subject: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    value: str | None
    evidence_id: str = Field(min_length=1)


class AgentRoutingCase(BaseModel):
    """One explicit specialised routing or abstention case."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    category: Literal[
        "direct_retrieval",
        "structured_fact_search",
        "evidence_inspection",
        "insufficient_retrieval",
        "no_match_fact_search",
    ]
    question: str = Field(min_length=1)
    expected_status: AgentAnswerStatus
    expected_evidence_ids: list[str]
    acceptable_tool_sequences: list[list[str]] = Field(min_length=1)
    minimal_expected_tool_calls: int = Field(ge=0)
    fact_fixture: RoutingFactFixture | None = None

    @model_validator(mode="after")
    def validate_case(self) -> AgentRoutingCase:
        if len(self.expected_evidence_ids) != len(set(self.expected_evidence_ids)):
            raise ValueError("expected_evidence_ids must be unique")
        if any(not sequence for sequence in self.acceptable_tool_sequences):
            raise ValueError("acceptable tool sequences must not be empty")
        shortest = min(len(sequence) for sequence in self.acceptable_tool_sequences)
        if self.minimal_expected_tool_calls != shortest:
            raise ValueError(
                "minimal_expected_tool_calls must equal the shortest acceptable sequence"
            )
        needs_fact = self.category in {
            "structured_fact_search",
            "evidence_inspection",
        }
        if needs_fact != (self.fact_fixture is not None):
            raise ValueError("fact_fixture must appear only on structured fact routes")
        return self


class AgentEvaluationCaseOutcome(BaseModel):
    """Deterministic scoring outcome for one bounded evaluation case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    evaluation_group: Literal["rag_benchmark", "routing"]
    task_success: bool
    expected_status: AgentAnswerStatus
    actual_status: AgentAnswerStatus | None
    expected_evidence_ids: list[str]
    actual_evidence_ids: list[str]
    citation_valid: bool | None
    actual_tool_sequence: list[str]
    tool_selection_acceptable: bool
    unnecessary_tool_calls: int = Field(ge=0)
    error: str | None


class AgentEvaluationMetrics(BaseModel):
    """Primary bounded evaluation metrics with explicit denominators."""

    model_config = ConfigDict(extra="forbid")

    case_count: int
    task_success_count: int
    task_success_rate: float
    answered_case_count: int
    citation_valid_count: int
    citation_validity_rate: float
    abstention_case_count: int
    appropriate_abstention_count: int
    appropriate_abstention_rate: float
    tool_selection_acceptable_count: int
    tool_selection_acceptable_rate: float
    total_tool_calls: int
    unnecessary_tool_calls: int
    unnecessary_tool_call_rate: float
    average_tool_calls_per_task: float


class AgentEvaluationReport(BaseModel):
    """Stable machine-readable result of the bounded offline evaluation."""

    model_config = ConfigDict(extra="forbid")

    evaluation_mode: Literal["offline_function_model"] = EVALUATION_MODE
    benchmark_path: str
    benchmark_sha256: str
    routing_cases_path: str
    routing_cases_sha256: str
    development_source_ids: list[str]
    case_count: int
    aggregate_metrics: AgentEvaluationMetrics
    cases: list[AgentEvaluationCaseOutcome]
    real_smoke_performed: Literal[False] = False
    real_smoke_case_count: Literal[0] = 0
    real_latency_ms: None = None
    real_model_usage: None = None
    real_approximate_cost_usd: None = None


class OfflineFunctionModel(FunctionModel):
    """FunctionModel with deterministic local usage for pre-request enforcement."""

    def __init__(self, function: Any, **kwargs: Any) -> None:
        super().__init__(function, **kwargs)
        self._tool_call_trace: list[str] = []

    @property
    def tool_call_trace(self) -> tuple[str, ...]:
        """Chronological successful-model requests for registered document tools."""
        return tuple(self._tool_call_trace)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        response = await super().request(
            messages, model_settings, model_request_parameters
        )
        registered_tools = {
            "retrieve_evidence",
            "search_project_facts",
            "read_evidence_block",
        }
        self._tool_call_trace.extend(
            part.tool_name
            for part in response.parts
            if isinstance(part, ToolCallPart) and part.tool_name in registered_tools
        )
        return response

    async def count_tokens(
        self,
        _messages: list[ModelMessage],
        _model_settings: ModelSettings | None,
        _model_request_parameters: ModelRequestParameters,
    ) -> RequestUsage:
        return RequestUsage(input_tokens=100)


def load_routing_cases(path: Path | str) -> list[AgentRoutingCase]:
    """Load and enforce the exact five-case specialised fixture."""
    cases = TypeAdapter(list[AgentRoutingCase]).validate_json(
        Path(path).read_text(encoding="utf-8")
    )
    if len(cases) != ROUTING_CASE_COUNT:
        raise ValueError(f"routing fixture must contain exactly {ROUTING_CASE_COUNT} cases")
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("routing case IDs must be unique")
    return cases


def score_task_success(
    *,
    expected_status: AgentAnswerStatus,
    expected_evidence_ids: Sequence[str],
    actual_status: AgentAnswerStatus | None,
    actual_evidence_ids: Sequence[str],
) -> bool:
    """Apply the bounded status-and-evidence task-success definition."""
    if expected_status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE:
        return actual_status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE
    return bool(
        actual_status is AgentAnswerStatus.ANSWERED
        and set(expected_evidence_ids).intersection(actual_evidence_ids)
    )


def validate_citation_integrity(
    answer: AgentAnswer, tool_service: DocumentToolService
) -> bool:
    """Independently reconcile final, inline, hydrated, and stored evidence IDs."""
    if answer.status is not AgentAnswerStatus.ANSWERED:
        return False
    if len(answer.evidence_ids) != len(set(answer.evidence_ids)):
        return False
    if [citation.evidence_id for citation in answer.citations] != answer.evidence_ids:
        return False
    inline_ids = [
        f"{source_id}:{block_id}"
        for source_id, block_id in _CITATION_PATTERN.findall(answer.answer)
    ]
    if set(inline_ids) != set(answer.evidence_ids):
        return False
    try:
        records = [
            tool_service.read_evidence_block(
                ReadEvidenceBlockInput(evidence_id=evidence_id)
            ).record
            for evidence_id in answer.evidence_ids
        ]
    except KeyError:
        return False
    return all(
        citation.evidence_id == record.evidence_id
        and citation.source_id == record.source_id
        and citation.block_id == record.block_id
        and citation.location_type == record.location_type
        and citation.location_value == record.location_value
        for citation, record in zip(answer.citations, records, strict=True)
    )


def tool_sequence_is_acceptable(
    actual: Sequence[str], acceptable: Sequence[Sequence[str]]
) -> bool:
    """Require one exact permitted tool-name sequence."""
    return list(actual) in [list(sequence) for sequence in acceptable]


def count_unnecessary_tool_calls(
    actual: Sequence[str], acceptable: Sequence[Sequence[str]]
) -> int:
    """Count unmatched actual calls once against the closest allowed sequence."""
    if not acceptable:
        raise ValueError("at least one acceptable tool sequence is required")

    def common_subsequence_length(expected: Sequence[str]) -> int:
        previous = [0] * (len(expected) + 1)
        for actual_name in actual:
            current = [0]
            for index, expected_name in enumerate(expected, start=1):
                if actual_name == expected_name:
                    current.append(previous[index - 1] + 1)
                else:
                    current.append(max(previous[index], current[-1]))
            previous = current
        return previous[-1]

    return min(
        len(actual) - common_subsequence_length(sequence)
        for sequence in acceptable
    )


def aggregate_metrics(
    outcomes: Sequence[AgentEvaluationCaseOutcome],
) -> AgentEvaluationMetrics:
    """Aggregate primary metrics without semantic answer grading."""
    case_count = len(outcomes)
    task_success_count = sum(outcome.task_success for outcome in outcomes)
    answered = [
        outcome
        for outcome in outcomes
        if outcome.actual_status is AgentAnswerStatus.ANSWERED
    ]
    citation_valid_count = sum(outcome.citation_valid is True for outcome in answered)
    abstentions = [
        outcome
        for outcome in outcomes
        if outcome.evaluation_group == "routing"
        and outcome.expected_status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE
    ]
    appropriate_abstention_count = sum(
        outcome.actual_status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE
        for outcome in abstentions
    )
    acceptable_count = sum(
        outcome.tool_selection_acceptable for outcome in outcomes
    )
    total_tool_calls = sum(len(outcome.actual_tool_sequence) for outcome in outcomes)
    unnecessary_calls = sum(outcome.unnecessary_tool_calls for outcome in outcomes)

    def rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    return AgentEvaluationMetrics(
        case_count=case_count,
        task_success_count=task_success_count,
        task_success_rate=rate(task_success_count, case_count),
        answered_case_count=len(answered),
        citation_valid_count=citation_valid_count,
        citation_validity_rate=rate(citation_valid_count, len(answered)),
        abstention_case_count=len(abstentions),
        appropriate_abstention_count=appropriate_abstention_count,
        appropriate_abstention_rate=rate(
            appropriate_abstention_count, len(abstentions)
        ),
        tool_selection_acceptable_count=acceptable_count,
        tool_selection_acceptable_rate=rate(acceptable_count, case_count),
        total_tool_calls=total_tool_calls,
        unnecessary_tool_calls=unnecessary_calls,
        unnecessary_tool_call_rate=rate(unnecessary_calls, total_tool_calls),
        average_tool_calls_per_task=rate(total_tool_calls, case_count),
    )


def render_markdown(report: AgentEvaluationReport) -> str:
    """Render the short audit-style human-readable evaluation summary."""
    metrics = report.aggregate_metrics
    routing = [case for case in report.cases if case.evaluation_group == "routing"]
    failed_ids = [
        case.case_id
        for case in report.cases
        if not case.task_success
        or not case.tool_selection_acceptable
        or case.citation_valid is False
    ]
    lines = [
        "# Agent Evaluation",
        "",
        "## Evaluation scope",
        "",
        f"Offline FunctionModel evaluation over {report.case_count} cases: 15 existing RAG development questions and 5 specialised routing/abstention cases.",
        f"Development sources: {', '.join(report.development_source_ids)}. Real smoke performed: no.",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Task success | {metrics.task_success_count}/{metrics.case_count} ({metrics.task_success_rate:.4f}) |",
        f"| Citation validity | {metrics.citation_valid_count}/{metrics.answered_case_count} ({metrics.citation_validity_rate:.4f}) |",
        f"| Appropriate abstention | {metrics.appropriate_abstention_count}/{metrics.abstention_case_count} ({metrics.appropriate_abstention_rate:.4f}) |",
        f"| Acceptable tool selection | {metrics.tool_selection_acceptable_count}/{metrics.case_count} ({metrics.tool_selection_acceptable_rate:.4f}) |",
        f"| Unnecessary tool calls | {metrics.unnecessary_tool_calls}/{metrics.total_tool_calls} ({metrics.unnecessary_tool_call_rate:.4f}) |",
        f"| Average tool calls per task | {metrics.average_tool_calls_per_task:.4f} |",
        "",
        "## Routing/abstention results",
        "",
        "| Case | Category | Status | Tools | Success |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {case.case_id} | {case.category} | {case.actual_status.value if case.actual_status else 'error'} | {' → '.join(case.actual_tool_sequence) or 'none'} | {'yes' if case.task_success else 'no'} |"
            for case in routing
        ],
        "",
        "## Known failures",
        "",
        ", ".join(failed_ids) if failed_ids else "None.",
        "",
        "## Interpretation",
        "",
        "This offline FunctionModel evaluation measures deterministic orchestration, grounding, routing contracts and labelled evidence availability. It does not measure autonomous GPT-5.4-mini tool-selection quality.",
        "",
        "## Limitations",
        "",
        "No semantic answer grading, hosted-model decision-quality measurement, real latency, real model usage, or real cost measurement was performed.",
        "",
    ]
    return "\n".join(lines)


def _last_tool_return(
    messages: Sequence[ModelMessage], tool_name: str
) -> ToolReturnPart:
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in reversed(message.parts):
                if isinstance(part, ToolReturnPart) and part.tool_name == tool_name:
                    return part
    raise ValueError(f"missing tool return for {tool_name}")


def _response(parts: list[ToolCallPart]) -> ModelResponse:
    return ModelResponse(
        parts=parts,
        usage=RequestUsage(
            input_tokens=100,
            output_tokens=20,
            cost=Decimal("0"),
        ),
    )


def _final_response(
    info: AgentInfo,
    *,
    status: AgentAnswerStatus,
    evidence_id: str | None = None,
) -> ModelResponse:
    if status is AgentAnswerStatus.ANSWERED:
        assert evidence_id is not None
        answer = f"Labelled evidence is available [{evidence_id}]"
        evidence_ids = [evidence_id]
    else:
        answer = "Insufficient evidence."
        evidence_ids = []
    return _response(
        [
            ToolCallPart(
                info.output_tools[0].name,
                {
                    "status": status.value,
                    "answer": answer,
                    "evidence_ids": evidence_ids,
                },
            )
        ]
    )


def _rag_model(question: RetrievalQuestion) -> OfflineFunctionModel:
    expected_ids = {
        f"{question.expected_source_id}:{block_id}"
        for block_id in question.expected_block_ids
    }
    step = 0

    def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal step
        step += 1
        if step == 1:
            return _response(
                [
                    ToolCallPart(
                        "retrieve_evidence",
                        {"question": question.question, "top_k": 5},
                    )
                ]
            )
        result = RetrieveEvidenceOutput.model_validate(
            _last_tool_return(messages, "retrieve_evidence").content
        )
        available = next(
            (hit.evidence_id for hit in result.hits if hit.evidence_id in expected_ids),
            None,
        )
        return _final_response(
            info,
            status=(
                AgentAnswerStatus.ANSWERED
                if available is not None
                else AgentAnswerStatus.INSUFFICIENT_EVIDENCE
            ),
            evidence_id=available,
        )

    return OfflineFunctionModel(function, model_name=f"offline:{question.id}")


def _routing_model(case: AgentRoutingCase) -> OfflineFunctionModel:
    step = 0

    def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal step
        step += 1
        if case.category in {"direct_retrieval", "insufficient_retrieval"}:
            if step == 1:
                return _response(
                    [
                        ToolCallPart(
                            "retrieve_evidence",
                            {"question": case.question, "top_k": 5},
                        )
                    ]
                )
            result = RetrieveEvidenceOutput.model_validate(
                _last_tool_return(messages, "retrieve_evidence").content
            )
            available = next(
                (
                    hit.evidence_id
                    for hit in result.hits
                    if hit.evidence_id in case.expected_evidence_ids
                ),
                None,
            )
            return _final_response(
                info,
                status=(
                    AgentAnswerStatus.ANSWERED
                    if available is not None
                    else AgentAnswerStatus.INSUFFICIENT_EVIDENCE
                ),
                evidence_id=available,
            )

        if case.category == "no_match_fact_search":
            if step == 1:
                return _response(
                    [
                        ToolCallPart(
                            "search_project_facts",
                            {"query": "fictional zephyr registry"},
                        )
                    ]
                )
            facts = SearchProjectFactsOutput.model_validate(
                _last_tool_return(messages, "search_project_facts").content
            )
            if facts.facts:
                raise ValueError("no-match routing fixture unexpectedly returned facts")
            return _final_response(
                info, status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE
            )

        fixture = case.fact_fixture
        assert fixture is not None
        if step == 1:
            return _response(
                [
                    ToolCallPart(
                        "search_project_facts",
                        {"query": fixture.query, "fact_type": fixture.fact_type.value},
                    )
                ]
            )
        if step == 2:
            facts = SearchProjectFactsOutput.model_validate(
                _last_tool_return(messages, "search_project_facts").content
            )
            evidence_id = next(
                (
                    evidence_id
                    for fact in facts.facts
                    for evidence_id in fact.evidence_ids
                    if evidence_id in case.expected_evidence_ids
                ),
                None,
            )
            if evidence_id is None:
                return _final_response(
                    info, status=AgentAnswerStatus.INSUFFICIENT_EVIDENCE
                )
            return _response(
                [ToolCallPart("read_evidence_block", {"evidence_id": evidence_id})]
            )
        record = ReadEvidenceBlockOutput.model_validate(
            _last_tool_return(messages, "read_evidence_block").content
        ).record
        return _final_response(
            info,
            status=AgentAnswerStatus.ANSWERED,
            evidence_id=record.evidence_id,
        )

    return OfflineFunctionModel(function, model_name=f"offline:{case.id}")


async def _evaluate_case(
    *,
    case_id: str,
    category: str,
    evaluation_group: Literal["rag_benchmark", "routing"],
    question: str,
    expected_status: AgentAnswerStatus,
    expected_evidence_ids: list[str],
    acceptable_sequences: list[list[str]],
    model: OfflineFunctionModel,
    service: DocumentToolService,
) -> AgentEvaluationCaseOutcome:
    try:
        answer = await run_document_agent(
            question,
            tool_service=service,
            model=model,
        )
    except Exception as exc:
        sequence = list(model.tool_call_trace)
        return AgentEvaluationCaseOutcome(
            case_id=case_id,
            category=category,
            evaluation_group=evaluation_group,
            task_success=False,
            expected_status=expected_status,
            actual_status=None,
            expected_evidence_ids=expected_evidence_ids,
            actual_evidence_ids=[],
            citation_valid=None,
            actual_tool_sequence=sequence,
            tool_selection_acceptable=tool_sequence_is_acceptable(
                sequence, acceptable_sequences
            ),
            unnecessary_tool_calls=count_unnecessary_tool_calls(
                sequence, acceptable_sequences
            ),
            error=f"{type(exc).__name__}: {exc}",
        )
    sequence = list(model.tool_call_trace)
    return AgentEvaluationCaseOutcome(
        case_id=case_id,
        category=category,
        evaluation_group=evaluation_group,
        task_success=score_task_success(
            expected_status=expected_status,
            expected_evidence_ids=expected_evidence_ids,
            actual_status=answer.status,
            actual_evidence_ids=answer.evidence_ids,
        ),
        expected_status=expected_status,
        actual_status=answer.status,
        expected_evidence_ids=expected_evidence_ids,
        actual_evidence_ids=answer.evidence_ids,
        citation_valid=(
            validate_citation_integrity(answer, service)
            if answer.status is AgentAnswerStatus.ANSWERED
            else None
        ),
        actual_tool_sequence=sequence,
        tool_selection_acceptable=tool_sequence_is_acceptable(
            sequence, acceptable_sequences
        ),
        unnecessary_tool_calls=count_unnecessary_tool_calls(
            sequence, acceptable_sequences
        ),
        error=None,
    )


def _routing_fact_extractions(
    cases: Sequence[AgentRoutingCase], records: Sequence[RetrievalRecord]
) -> list[PortfolioFactExtraction]:
    records_by_id = {record.evidence_id: record for record in records}
    extractions: list[PortfolioFactExtraction] = []
    for case in cases:
        fixture = case.fact_fixture
        if fixture is None:
            continue
        try:
            record = records_by_id[fixture.evidence_id]
        except KeyError:
            raise ValueError(
                f"routing fact evidence does not exist: {fixture.evidence_id}"
            ) from None
        evidence = EvidenceReference(
            evidence_id=record.evidence_id,
            source_id=record.source_id,
            block_id=record.block_id,
            location_type=record.location_type,
            location_value=record.location_value,
            excerpt=record.text,
        )
        fact = PortfolioFact(
            fact_id=f"FACT-{case.id}",
            fact_type=fixture.fact_type,
            subject=fixture.subject,
            statement=fixture.statement,
            value=fixture.value,
            evidence_ids=[record.evidence_id],
            confidence=1.0,
            support_status=SupportStatus.SUPPORTED,
            review_required=False,
            evidence=[evidence],
        )
        extractions.append(
            PortfolioFactExtraction(
                document_id=f"ROUTING-{case.id}",
                source_id=record.source_id,
                source_format="fixture",
                facts=[fact],
            )
        )
    return extractions


async def evaluate_agent(
    *,
    records: Sequence[RetrievalRecord],
    questions: Sequence[RetrievalQuestion],
    routing_cases: Sequence[AgentRoutingCase],
    service: DocumentToolService,
) -> list[AgentEvaluationCaseOutcome]:
    """Run exactly the supplied bounded benchmark and routing cases sequentially."""
    if len(questions) != RAG_CASE_COUNT or len(routing_cases) != ROUTING_CASE_COUNT:
        raise ValueError("evaluation requires exactly 15 benchmark and 5 routing cases")
    if len(questions) + len(routing_cases) > MAX_CASE_COUNT:
        raise ValueError("agent evaluation exceeds the 20-case maximum")
    outcomes: list[AgentEvaluationCaseOutcome] = []
    for question in questions:
        expected_ids = [
            f"{question.expected_source_id}:{block_id}"
            for block_id in question.expected_block_ids
        ]
        outcomes.append(
            await _evaluate_case(
                case_id=question.id,
                category="rag_evidence_availability",
                evaluation_group="rag_benchmark",
                question=question.question,
                expected_status=AgentAnswerStatus.ANSWERED,
                expected_evidence_ids=expected_ids,
                acceptable_sequences=[["retrieve_evidence"]],
                model=_rag_model(question),
                service=service,
            )
        )
    for case in routing_cases:
        outcomes.append(
            await _evaluate_case(
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
    return outcomes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--routing-cases", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the bounded development-only FunctionModel evaluation once."""
    from pydantic_ai import models as pydantic_ai_models

    pydantic_ai_models.ALLOW_MODEL_REQUESTS = False
    args = build_parser().parse_args(argv)
    questions = load_retrieval_questions(args.benchmark)
    if len(questions) != RAG_CASE_COUNT:
        raise ValueError(f"benchmark must contain exactly {RAG_CASE_COUNT} questions")
    source_ids = {question.expected_source_id for question in questions}
    if not source_ids.issubset(DEVELOPMENT_SOURCE_IDS):
        raise ValueError("agent evaluation benchmark contains a non-development source")
    routing_cases = load_routing_cases(args.routing_cases)
    records = load_retrieval_records(args.parsed_root, source_ids=source_ids)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    service = DocumentToolService(
        retrieval_records=records,
        fact_extractions=_routing_fact_extractions(routing_cases, records),
        embedder=SentenceTransformerEmbedder(args.embedding_model),
    )
    outcomes = asyncio.run(
        evaluate_agent(
            records=records,
            questions=questions,
            routing_cases=routing_cases,
            service=service,
        )
    )
    metrics = aggregate_metrics(outcomes)
    report = AgentEvaluationReport(
        benchmark_path=args.benchmark.as_posix(),
        benchmark_sha256=_sha256(args.benchmark),
        routing_cases_path=args.routing_cases.as_posix(),
        routing_cases_sha256=_sha256(args.routing_cases),
        development_source_ids=sorted(source_ids),
        case_count=len(outcomes),
        aggregate_metrics=metrics,
        cases=outcomes,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
