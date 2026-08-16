"""Offline routing and safety tests for the bounded Stage B document agent."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from pydantic_ai import models as pydantic_ai_models
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

import document_intelligence.agentic.cli as agentic_cli
from document_intelligence.agentic.agent import (
    DEFAULT_USAGE_LIMITS,
    AgentGroundingError,
    run_document_agent,
)
from document_intelligence.agentic.models import AgentAnswer, AgentAnswerStatus
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import (
    EvidenceReference,
    FactType,
    PortfolioFact,
    PortfolioFactExtraction,
    RetrievalRecord,
    SupportStatus,
)


EVIDENCE_ID = "S001:DOC-S001-B0001"
SECOND_EVIDENCE_ID = "S002:DOC-S002-B0001"


@pytest.fixture(autouse=True)
def deny_real_model_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail every test if it accidentally leaves Pydantic AI's offline boundary."""
    monkeypatch.setattr(pydantic_ai_models, "ALLOW_MODEL_REQUESTS", False)


class FakeEmbedder:
    """Deterministic local vectors with no download or provider access."""

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


class OfflineFunctionModel(FunctionModel):
    """FunctionModel with deterministic local counting for pre-request limits."""

    async def count_tokens(
        self,
        _messages: list[Any],
        _model_settings: Any,
        _model_request_parameters: Any,
    ) -> RequestUsage:
        return RequestUsage(input_tokens=10)


def _record(source_id: str, text: str) -> RetrievalRecord:
    block_id = f"DOC-{source_id}-B0001"
    return RetrievalRecord(
        evidence_id=f"{source_id}:{block_id}",
        source_id=source_id,
        block_id=block_id,
        location_type="page",
        location_value="page 1",
        text=text,
    )


def _service() -> DocumentToolService:
    records = [
        _record("S001", "The programme will expand secure compute capacity."),
        _record("S002", "The delivery team owns the implementation risk."),
    ]
    evidence = EvidenceReference(
        evidence_id=records[0].evidence_id,
        source_id=records[0].source_id,
        block_id=records[0].block_id,
        location_type=records[0].location_type,
        location_value=records[0].location_value,
        excerpt=records[0].text,
    )
    fact = PortfolioFact(
        fact_id="FACT-DEMO0001",
        fact_type=FactType.COMMITMENT,
        subject="The programme",
        statement="The programme will expand compute capacity.",
        value="compute capacity",
        evidence_ids=[records[0].evidence_id],
        confidence=0.9,
        support_status=SupportStatus.SUPPORTED,
        review_required=False,
        evidence=[evidence],
    )
    extraction = PortfolioFactExtraction(
        document_id="DOC-S001",
        source_id="S001",
        source_format="PDF",
        facts=[fact],
    )
    return DocumentToolService(
        retrieval_records=records,
        fact_extractions=[extraction],
        embedder=FakeEmbedder(),
    )


def _function_model(
    responses: list[tuple[str, dict[str, Any]]],
    *,
    inspect_info: Callable[[AgentInfo], None] | None = None,
) -> tuple[OfflineFunctionModel, list[str]]:
    calls: list[str] = []

    def function(_messages: list[Any], info: AgentInfo) -> ModelResponse:
        if inspect_info is not None:
            inspect_info(info)
        tool_name, arguments = responses[len(calls)]
        if tool_name == "__output__":
            tool_name = info.output_tools[0].name
        calls.append(tool_name)
        return ModelResponse(
            parts=[ToolCallPart(tool_name, arguments)],
            usage=RequestUsage(
                input_tokens=10,
                output_tokens=5,
                cost=Decimal("0.001"),
            ),
        )

    return OfflineFunctionModel(function), calls


def _run(model: FunctionModel, *, question: str = "What is planned?") -> AgentAnswer:
    return asyncio.run(
        run_document_agent(question, tool_service=_service(), model=model)
    )


def test_case_a_retrieve_then_answer_has_grounded_citation_and_usage() -> None:
    observed_schemas: list[dict[str, Any]] = []

    def inspect_info(info: AgentInfo) -> None:
        assert [tool.name for tool in info.function_tools] == [
            "retrieve_evidence",
            "search_project_facts",
            "read_evidence_block",
        ]
        observed_schemas.append(info.function_tools[0].parameters_json_schema)

    model, calls = _function_model(
        [
            (
                "retrieve_evidence",
                {"question": "planned compute", "source_ids": ["S001"], "top_k": 1},
            ),
            (
                "__output__",
                {
                    "status": "answered",
                    "answer": "The programme will expand compute capacity "
                    "[S001:DOC-S001-B0001]",
                    "evidence_ids": [EVIDENCE_ID],
                },
            ),
        ],
        inspect_info=inspect_info,
    )

    result = _run(model)

    assert result.status is AgentAnswerStatus.ANSWERED
    assert result.evidence_ids == [EVIDENCE_ID]
    assert result.citations[0].model_dump() == {
        "evidence_id": EVIDENCE_ID,
        "source_id": "S001",
        "block_id": "DOC-S001-B0001",
        "location_type": "page",
        "location_value": "page 1",
    }
    assert [item.model_dump() for item in result.tool_call_summary] == [
        {
            "tool_name": "retrieve_evidence",
            "invocation_count": 1,
            "high_level_result": "returned 1 evidence hit",
        }
    ]
    assert calls == ["retrieve_evidence", "submit_grounded_answer"]
    top_k_schema = observed_schemas[0]["properties"]["top_k"]
    assert top_k_schema["minimum"] == 1
    assert top_k_schema["maximum"] == 5
    assert result.usage.requests == 2
    assert result.usage.tool_calls >= 1
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.total_tokens == (
        result.usage.input_tokens + result.usage.output_tokens
    )
    assert result.usage.approximate_cost_usd == Decimal("0.002")
    assert result.usage.model_dump(mode="json")["approximate_cost_usd"] == "0.002"
    assert "reasoning" not in AgentAnswer.model_fields
    assert "messages" not in AgentAnswer.model_fields


def test_default_usage_limits_count_input_tokens_before_each_request() -> None:
    assert DEFAULT_USAGE_LIMITS.request_limit == 4
    assert DEFAULT_USAGE_LIMITS.tool_calls_limit == 4
    assert DEFAULT_USAGE_LIMITS.output_tokens_limit == 2_000
    assert DEFAULT_USAGE_LIMITS.per_request_input_tokens_limit == 30_000
    assert DEFAULT_USAGE_LIMITS.cost_limit == Decimal("0.25")
    assert DEFAULT_USAGE_LIMITS.count_tokens_before_request is True


def test_case_b_fact_search_then_exact_read_then_answer() -> None:
    model, calls = _function_model(
        [
            ("search_project_facts", {"query": "compute", "fact_type": "commitment"}),
            ("read_evidence_block", {"evidence_id": EVIDENCE_ID}),
            (
                "__output__",
                {
                    "status": "answered",
                    "answer": "Compute capacity will expand [S001:DOC-S001-B0001]",
                    "evidence_ids": [EVIDENCE_ID],
                },
            ),
        ]
    )

    result = _run(model)

    assert result.status is AgentAnswerStatus.ANSWERED
    assert result.citations[0].evidence_id == EVIDENCE_ID
    assert [item.tool_name for item in result.tool_call_summary] == [
        "search_project_facts",
        "read_evidence_block",
    ]
    assert [item.high_level_result for item in result.tool_call_summary] == [
        "returned 1 fact match",
        "returned 1 exact evidence block",
    ]
    assert calls == [
        "search_project_facts",
        "read_evidence_block",
        "submit_grounded_answer",
    ]


def test_case_c_insufficient_evidence_abstains_without_citations() -> None:
    model, calls = _function_model(
        [
            ("retrieve_evidence", {"question": "unsupported topic", "top_k": 2}),
            (
                "__output__",
                {
                    "status": "insufficient_evidence",
                    "answer": "Insufficient evidence.",
                    "evidence_ids": [],
                },
            ),
        ]
    )

    result = _run(model, question="What is not documented?")

    assert result.status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer == "Insufficient evidence."
    assert result.evidence_ids == []
    assert result.citations == []
    assert calls == ["retrieve_evidence", "submit_grounded_answer"]


def test_invented_unexposed_evidence_fails_closed_without_retry() -> None:
    model, calls = _function_model(
        [
            (
                "retrieve_evidence",
                {"question": "planned compute", "source_ids": ["S001"], "top_k": 1},
            ),
            (
                "__output__",
                {
                    "status": "answered",
                    "answer": "Invented claim [S999:DOC-S999-B9999]",
                    "evidence_ids": ["S999:DOC-S999-B9999"],
                },
            ),
        ]
    )

    with pytest.raises(
        AgentGroundingError,
        match="evidence not exposed by a successful tool",
    ):
        _run(model)
    assert calls == ["retrieve_evidence", "submit_grounded_answer"]


def test_inline_citation_inventory_mismatch_fails_closed_without_retry() -> None:
    model, calls = _function_model(
        [
            ("retrieve_evidence", {"question": "compute and risk", "top_k": 2}),
            (
                "__output__",
                {
                    "status": "answered",
                    "answer": "Risk is assigned [S002:DOC-S002-B0001]",
                    "evidence_ids": [EVIDENCE_ID],
                },
            ),
        ]
    )

    with pytest.raises(AgentGroundingError, match="do not reconcile"):
        _run(model)
    assert calls == ["retrieve_evidence", "submit_grounded_answer"]


def test_insufficient_evidence_rejects_unsupported_answer_or_citation() -> None:
    model, _ = _function_model(
        [
            ("retrieve_evidence", {"question": "unknown", "top_k": 1}),
            (
                "__output__",
                {
                    "status": "insufficient_evidence",
                    "answer": "It probably exists [S001:DOC-S001-B0001]",
                    "evidence_ids": [EVIDENCE_ID],
                },
            ),
        ]
    )

    with pytest.raises(AgentGroundingError, match="explicit abstention"):
        _run(model)


def test_pydantic_ai_tool_budget_prevents_excessive_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    executions = 0
    original = service.retrieve_evidence

    def counted(request: Any) -> Any:
        nonlocal executions
        executions += 1
        return original(request)

    monkeypatch.setattr(service, "retrieve_evidence", counted)

    def excessive(_messages: list[Any], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "retrieve_evidence",
                    {"question": f"query {index}", "top_k": 1},
                    tool_call_id=f"call-{index}",
                )
                for index in range(5)
            ],
            usage=RequestUsage(
                input_tokens=10,
                output_tokens=5,
                cost=Decimal("0.001"),
            ),
        )

    with pytest.raises(UsageLimitExceeded, match="tool_calls_limit"):
        asyncio.run(
            run_document_agent(
                "Keep searching",
                tool_service=service,
                model=OfflineFunctionModel(excessive),
            )
        )
    assert executions <= 4


@pytest.mark.parametrize(
    "gate_arguments",
    [[], ["--execute-real-agent", "--confirm-execution", "wrong-token"]],
)
def test_cli_real_mode_is_closed_before_key_or_model_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gate_arguments: list[str],
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("real execution dependency was accessed")

    monkeypatch.setattr(agentic_cli, "_read_api_key", forbidden)
    monkeypatch.setattr(agentic_cli, "_build_real_model", forbidden)
    monkeypatch.setattr(agentic_cli, "load_retrieval_records", forbidden)
    result = agentic_cli.main(
        [
            "--parsed-root",
            "fictional",
            "--source-id",
            "S005",
            "--question",
            "What is planned?",
            *gate_arguments,
        ]
    )

    assert result == 2
    payload = __import__("json").loads(capsys.readouterr().err)
    assert payload["status"] == "execution_refused"
