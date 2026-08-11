"""Grounded question answering over retrieved ParsedDocument blocks."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from document_intelligence.portfolio.extraction import (
    DEFAULT_MODEL,
    StructuredResponder,
    build_structured_responses_payload,
    call_openai_responses,
)
from document_intelligence.portfolio.models import (
    GroundedAnswer,
    GroundedAnswerDraft,
    RagCitation,
    RetrievalRecord,
)
from document_intelligence.portfolio.retrieval import Embedder, HybridIndex


_CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+)\]")


def answer_question(
    records: Sequence[RetrievalRecord],
    question: str,
    *,
    embedder: Embedder,
    responder: StructuredResponder | None = None,
    top_k: int = 5,
    model: str = DEFAULT_MODEL,
) -> GroundedAnswer:
    """Retrieve evidence, request an answer, and reject invented citations."""
    hits = HybridIndex(records, embedder).search(question, top_k=top_k)
    evidence = [
        {"citation": f"[{hit.evidence_id}]", "text": hit.text} for hit in hits
    ]
    payload = build_structured_responses_payload(
        system_prompt=(
            "Answer only from the supplied retrieved blocks. If the evidence is "
            "insufficient, say so explicitly. Cite every supported claim using the "
            "exact supplied [SOURCE_ID:BLOCK_ID] citation. Never invent a citation."
        ),
        user_prompt=(
            f"Question: {question}\nRetrieved blocks:\n"
            + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        ),
        schema_name="portfolio_grounded_answer",
        schema=GroundedAnswerDraft.model_json_schema(),
        model=model,
    )
    response_function = responder if responder is not None else call_openai_responses
    raw = response_function(payload)
    try:
        draft = GroundedAnswerDraft.model_validate_json(raw)
    except Exception as exc:
        raise ValueError("LLM output failed grounded-answer schema validation") from exc

    allowed = {hit.evidence_id: hit for hit in hits}
    if len(draft.citations) != len(set(draft.citations)):
        raise ValueError("grounded-answer citations must be unique")
    unknown = [citation for citation in draft.citations if citation not in allowed]
    if unknown:
        raise ValueError(f"grounded answer referenced unknown citations: {unknown}")
    answer_citations = _CITATION_PATTERN.findall(draft.answer)
    if set(answer_citations) != set(draft.citations):
        raise ValueError("answer citation syntax does not match the citation inventory")

    citations = [
        RagCitation(
            evidence_id=citation,
            source_id=allowed[citation].source_id,
            block_id=allowed[citation].block_id,
            location_type=allowed[citation].location_type,
            location_value=allowed[citation].location_value,
        )
        for citation in draft.citations
    ]
    return GroundedAnswer(
        question=question,
        answer=draft.answer,
        citations=citations,
        retrieved_evidence=hits,
    )
