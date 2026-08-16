"""One bounded Pydantic AI agent over the three Stage A document tools."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated

from pydantic import Field
from pydantic_ai import Agent, AgentRetries, ModelSettings, RunContext, ToolOutput
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from document_intelligence.agentic.models import (
    AgentAnswer,
    AgentAnswerDraft,
    AgentAnswerStatus,
    AgentCitation,
    AgentRetrieveEvidenceInput,
    AgentToolCallSummary,
    AgentUsage,
    ReadEvidenceBlockInput,
    ReadEvidenceBlockOutput,
    RetrieveEvidenceOutput,
    SearchProjectFactsInput,
    SearchProjectFactsOutput,
)
from document_intelligence.agentic.tools import DocumentToolService
from document_intelligence.portfolio.models import FactType


DEFAULT_USAGE_LIMITS = UsageLimits(
    request_limit=4,
    tool_calls_limit=4,
    output_tokens_limit=2_000,
    per_request_input_tokens_limit=30_000,
    count_tokens_before_request=True,
    cost_limit=Decimal("0.25"),
)
DEFAULT_MODEL_SETTINGS = ModelSettings(
    max_tokens=1_200,
    timeout=120,
    parallel_tool_calls=False,
)

AGENT_INSTRUCTIONS = """\
Answer only from information returned by the registered document tools.
Do not use pretrained or background knowledge as evidence.
Inspect evidence before supporting a factual claim. When structured facts support an
answer, inspect their supporting evidence when needed.
Never invent an evidence ID. Cite every answered claim with exact [SOURCE_ID:BLOCK_ID]
syntax and return the same evidence IDs in the final evidence_ids inventory.
If the available evidence is insufficient, return status insufficient_evidence, the
exact answer "Insufficient evidence.", and an empty evidence_ids list.
Do not keep calling tools merely to force an answer. Stay within the bounded tool
budget. Do not expose chain-of-thought, hidden analysis, or internal reflection.
"""

_CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9_-]+):([A-Za-z0-9_.-]+)\]")
_TOOL_ORDER = (
    "retrieve_evidence",
    "search_project_facts",
    "read_evidence_block",
)


class AgentGroundingError(ValueError):
    """Raised when a terminal draft cannot be grounded without repair."""


@dataclass
class _ToolStats:
    invocation_count: int = 0
    result_count: int = 0


@dataclass
class ToolUsageTracker:
    """Run-local evidence exposure and deterministic tool accounting."""

    exposed_evidence_ids: set[str] = field(default_factory=set)
    _stats: dict[str, _ToolStats] = field(default_factory=dict)

    def record(self, tool_name: str, evidence_ids: list[str], result_count: int) -> None:
        """Record one successful tool result and its exposed evidence inventory."""
        self.exposed_evidence_ids.update(evidence_ids)
        stats = self._stats.setdefault(tool_name, _ToolStats())
        stats.invocation_count += 1
        stats.result_count += result_count

    def summaries(self) -> list[AgentToolCallSummary]:
        """Return summaries in fixed registered-tool order."""
        units = {
            "retrieve_evidence": "evidence hit",
            "search_project_facts": "fact match",
            "read_evidence_block": "exact evidence block",
        }
        summaries: list[AgentToolCallSummary] = []
        for tool_name in _TOOL_ORDER:
            stats = self._stats.get(tool_name)
            if stats is None:
                continue
            unit = units[tool_name]
            if stats.result_count != 1:
                unit += "s"
            summaries.append(
                AgentToolCallSummary(
                    tool_name=tool_name,  # type: ignore[arg-type]
                    invocation_count=stats.invocation_count,
                    high_level_result=f"returned {stats.result_count} {unit}",
                )
            )
        return summaries


@dataclass
class AgentDependencies:
    """Injected deterministic dependencies local to one agent run."""

    tool_service: DocumentToolService
    tracker: ToolUsageTracker


document_agent = Agent[AgentDependencies, AgentAnswerDraft](
    model=None,
    output_type=ToolOutput(
        AgentAnswerDraft,
        name="submit_grounded_answer",
        description="Submit the final grounded answer or explicit abstention.",
        max_retries=0,
        strict=True,
    ),
    instructions=AGENT_INSTRUCTIONS,
    deps_type=AgentDependencies,
    model_settings=DEFAULT_MODEL_SETTINGS,
    retries=AgentRetries(tools=0, output=0),
    defer_model_check=True,
)


@document_agent.tool(retries=0)
def retrieve_evidence(
    ctx: RunContext[AgentDependencies],
    question: Annotated[str, Field(min_length=1)],
    source_ids: list[str] | None = None,
    top_k: Annotated[int, Field(ge=1, le=5)] = 5,
) -> RetrieveEvidenceOutput:
    """Retrieve existing evidence blocks with bounded hybrid search."""
    request = AgentRetrieveEvidenceInput(
        question=question,
        source_ids=source_ids,
        top_k=top_k,
    )
    output = ctx.deps.tool_service.retrieve_evidence(request)
    ctx.deps.tracker.record(
        "retrieve_evidence",
        [hit.evidence_id for hit in output.hits],
        len(output.hits),
    )
    return output


@document_agent.tool(retries=0)
def search_project_facts(
    ctx: RunContext[AgentDependencies],
    query: str | None = None,
    fact_type: FactType | None = None,
) -> SearchProjectFactsOutput:
    """Search existing structured project facts without changing them."""
    output = ctx.deps.tool_service.search_project_facts(
        SearchProjectFactsInput(query=query, fact_type=fact_type)
    )
    evidence_ids = [
        evidence_id
        for fact in output.facts
        for evidence_id in fact.evidence_ids
    ]
    ctx.deps.tracker.record(
        "search_project_facts", evidence_ids, len(output.facts)
    )
    return output


@document_agent.tool(retries=0)
def read_evidence_block(
    ctx: RunContext[AgentDependencies],
    evidence_id: Annotated[str, Field(min_length=1)],
) -> ReadEvidenceBlockOutput:
    """Read one exact existing evidence block by its application-issued ID."""
    output = ctx.deps.tool_service.read_evidence_block(
        ReadEvidenceBlockInput(evidence_id=evidence_id)
    )
    ctx.deps.tracker.record(
        "read_evidence_block", [output.record.evidence_id], 1
    )
    return output


def _hydrate_answer(
    *,
    question: str,
    draft: AgentAnswerDraft,
    dependencies: AgentDependencies,
    usage: AgentUsage,
) -> AgentAnswer:
    """Validate grounding once and hydrate provenance without a model retry."""
    inline_evidence_ids = [
        f"{source_id}:{block_id}"
        for source_id, block_id in _CITATION_PATTERN.findall(draft.answer)
    ]

    if draft.status is AgentAnswerStatus.INSUFFICIENT_EVIDENCE:
        if draft.answer != "Insufficient evidence.":
            raise AgentGroundingError(
                "insufficient_evidence must use the explicit abstention answer"
            )
        if draft.evidence_ids or inline_evidence_ids:
            raise AgentGroundingError(
                "insufficient_evidence must not include evidence IDs or citations"
            )
        return AgentAnswer(
            question=question,
            status=draft.status,
            answer=draft.answer,
            evidence_ids=[],
            citations=[],
            tool_call_summary=dependencies.tracker.summaries(),
            usage=usage,
        )

    if not set(draft.evidence_ids).issubset(
        dependencies.tracker.exposed_evidence_ids
    ):
        raise AgentGroundingError(
            "answered draft contains evidence not exposed by a successful tool"
        )
    if set(inline_evidence_ids) != set(draft.evidence_ids):
        raise AgentGroundingError(
            "inline citations do not reconcile with the evidence ID inventory"
        )

    citations: list[AgentCitation] = []
    for evidence_id in draft.evidence_ids:
        try:
            record = dependencies.tool_service.read_evidence_block(
                ReadEvidenceBlockInput(evidence_id=evidence_id)
            ).record
        except KeyError as exc:
            raise AgentGroundingError(
                f"answered draft references unknown evidence: {evidence_id}"
            ) from exc
        citations.append(
            AgentCitation(
                evidence_id=record.evidence_id,
                source_id=record.source_id,
                block_id=record.block_id,
                location_type=record.location_type,
                location_value=record.location_value,
            )
        )

    return AgentAnswer(
        question=question,
        status=draft.status,
        answer=draft.answer,
        evidence_ids=draft.evidence_ids,
        citations=citations,
        tool_call_summary=dependencies.tracker.summaries(),
        usage=usage,
    )


async def run_document_agent(
    question: str,
    *,
    tool_service: DocumentToolService,
    model: Model,
) -> AgentAnswer:
    """Run the single bounded agent and enforce application-owned grounding."""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be blank")
    dependencies = AgentDependencies(
        tool_service=tool_service,
        tracker=ToolUsageTracker(),
    )
    result = await document_agent.run(
        normalized_question,
        model=model,
        deps=dependencies,
        usage_limits=DEFAULT_USAGE_LIMITS,
    )
    raw_usage = result.usage
    usage = AgentUsage(
        requests=raw_usage.requests,
        tool_calls=raw_usage.tool_calls,
        input_tokens=raw_usage.input_tokens,
        output_tokens=raw_usage.output_tokens,
        total_tokens=raw_usage.total_tokens,
        approximate_cost_usd=raw_usage.cost,
    )
    return _hydrate_answer(
        question=normalized_question,
        draft=result.output,
        dependencies=dependencies,
        usage=usage,
    )
