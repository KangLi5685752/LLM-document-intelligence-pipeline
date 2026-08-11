"""Simple evidence-ID-first LLM fact extraction."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.portfolio.models import (
    EvidenceReference,
    PortfolioFact,
    PortfolioFactDraft,
    PortfolioFactDraftResponse,
    PortfolioFactExtraction,
)


DEFAULT_MODEL = "gpt-5.4-mini"
StructuredResponder = Callable[[dict[str, Any]], str]


def build_structured_responses_payload(
    *,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build the text-only, no-tools Responses payload used by the app layer."""
    return {
        "model": model,
        "max_output_tokens": 4096,
        "reasoning": {"effort": "none"},
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
        "store": False,
        "tools": [],
        "tool_choice": "none",
    }


def _response_output_text(response: Any) -> str:
    parts: list[str] = []
    for output_item in getattr(response, "output", ()) or ():
        if getattr(output_item, "type", None) != "message":
            continue
        for content_item in getattr(output_item, "content", ()) or ():
            if getattr(content_item, "type", None) == "refusal":
                raise RuntimeError("OpenAI refused the structured extraction request")
            if getattr(content_item, "type", None) == "output_text":
                text = getattr(content_item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
    if len(parts) != 1 or not parts[0].strip():
        raise RuntimeError("OpenAI response did not contain one structured output")
    return parts[0]


def call_openai_responses(payload: dict[str, Any]) -> str:
    """Perform one explicit OpenAI call; tests inject a responder instead."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for LLM extraction and grounded QA"
        )
    from openai import OpenAI

    client = OpenAI(api_key=api_key).with_options(max_retries=0, timeout=120.0)
    response = client.responses.create(**payload)
    if getattr(response, "status", None) != "completed":
        raise RuntimeError("OpenAI response did not complete successfully")
    return _response_output_text(response)


def _evidence_catalog(document: ParsedDocument) -> dict[str, EvidenceReference]:
    if document.source_id is None or not document.source_id.strip():
        raise ValueError("ParsedDocument source_id is required for fact extraction")
    catalog: dict[str, EvidenceReference] = {}
    for block in document.blocks:
        if not block.text.strip():
            continue
        evidence_id = f"{document.source_id}:{block.block_id}"
        catalog[evidence_id] = EvidenceReference(
            evidence_id=evidence_id,
            source_id=document.source_id,
            block_id=block.block_id,
            location_type=block.location.location_type.value,
            location_value=block.location.location_value,
            excerpt=block.text,
        )
    return catalog


def _fact_id(source_id: str, ordinal: int, draft: PortfolioFactDraft) -> str:
    payload = {
        "source_id": source_id,
        "ordinal": ordinal,
        **draft.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"FACT-{hashlib.sha256(encoded).hexdigest()[:16].upper()}"


def _prompt_blocks(catalog: Mapping[str, EvidenceReference]) -> list[dict[str, str]]:
    return [
        {"evidence_id": evidence_id, "text": evidence.excerpt}
        for evidence_id, evidence in catalog.items()
    ]


def extract_project_facts(
    document: ParsedDocument,
    *,
    responder: StructuredResponder | None = None,
    model: str = DEFAULT_MODEL,
) -> PortfolioFactExtraction:
    """Extract useful facts and hydrate all provenance in application code."""
    catalog = _evidence_catalog(document)
    system_prompt = (
        "Extract only useful project or document facts from the supplied blocks. "
        "Do not emit titles or generic headings unless they are genuinely useful. "
        "Every fact must cite one or more supplied evidence IDs. Do not invent "
        "information or provenance; omit unsupported facts. Mark ambiguous claims "
        "support_status=ambiguous and review_required=true."
    )
    user_prompt = "Evidence blocks:\n" + json.dumps(
        _prompt_blocks(catalog), ensure_ascii=False, separators=(",", ":")
    )
    payload = build_structured_responses_payload(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="portfolio_fact_extraction",
        schema=PortfolioFactDraftResponse.model_json_schema(),
        model=model,
    )
    response_function = responder if responder is not None else call_openai_responses
    raw = response_function(payload)
    try:
        draft_response = PortfolioFactDraftResponse.model_validate_json(raw)
    except Exception as exc:
        raise ValueError("LLM output failed portfolio fact schema validation") from exc

    facts: list[PortfolioFact] = []
    source_id = document.source_id
    assert source_id is not None
    for ordinal, draft in enumerate(draft_response.facts, start=1):
        unknown = [item for item in draft.evidence_ids if item not in catalog]
        if unknown:
            raise ValueError(f"LLM output referenced unknown evidence IDs: {unknown}")
        evidence = [catalog[item] for item in draft.evidence_ids]
        facts.append(
            PortfolioFact(
                fact_id=_fact_id(source_id, ordinal, draft),
                **draft.model_dump(),
                evidence=evidence,
            )
        )
    return PortfolioFactExtraction(
        document_id=document.document_id,
        source_id=source_id,
        source_format=document.source_format.value,
        facts=facts,
    )


def search_project_facts(
    extractions: Iterable[PortfolioFactExtraction],
    *,
    fact_type: str | None = None,
    query: str | None = None,
) -> list[PortfolioFact]:
    """Filter local facts by type and case-insensitive useful text."""
    normalized_query = query.casefold().strip() if query else None
    matches: list[PortfolioFact] = []
    for extraction in extractions:
        for fact in extraction.facts:
            if fact_type is not None and fact.fact_type.value != fact_type:
                continue
            searchable = " ".join(
                item for item in (fact.subject, fact.statement, fact.value) if item
            ).casefold()
            if normalized_query and normalized_query not in searchable:
                continue
            matches.append(fact)
    return matches
