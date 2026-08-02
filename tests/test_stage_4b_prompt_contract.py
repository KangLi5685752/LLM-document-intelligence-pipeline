"""Prompt asset, composition, and identity tests for Stage 4B."""

from __future__ import annotations

import re

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    InvocationRole,
    build_request_envelope,
    canonical_prompt_bytes,
    canonical_request_bytes,
    load_prompt_assets,
    prompt_sha256,
)
from document_intelligence.llm_extraction.prompting import PromptAssets


def _block(text: str = "A fictional initiative has a stated status."):
    return ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text=text,
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )


def _request(model_configuration_id: str = "fictional-model-configuration-v1"):
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="fictional-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id=model_configuration_id,
        evidence_blocks=(_block(),),
    )


def test_prompt_assets_load_after_normal_package_import() -> None:
    assets = load_prompt_assets()

    assert assets.system_prompt_bytes.startswith(b"You perform evidence-linked")
    assert assets.extraction_prompt_bytes.startswith(b"Extract only facts")


def test_committed_prompts_enforce_neutral_evidence_and_review_boundaries() -> None:
    assets = load_prompt_assets()
    text = (assets.system_prompt_bytes + assets.extraction_prompt_bytes).decode(
        "utf-8"
    )

    for phrase in (
        "Use only the ordered evidence blocks",
        "never invent",
        "abstention",
        "require human review",
        "unsupported inference",
        "gold labels",
        "expected answers",
        "not automatically authoritative",
        "CandidateExtractionResult schema 0.1",
    ):
        assert phrase.casefold() in text.casefold()
    assert not re.search(r"\bS00[1-7]\b", text)
    assert not re.search(r"\bPG(?:C)?-V\d+", text)
    for frozen_value in (
        "0.028089887640449437",
        "0.04926108374384237",
        "TP 5",
        "FP 173",
        "FN 20",
    ):
        assert frozen_value not in text


def test_canonical_prompt_and_request_identity_are_deterministic() -> None:
    first = _request()
    second = _request()

    assert first == second
    assert canonical_request_bytes(first) == canonical_request_bytes(second)
    assert first.prompt_sha256 == prompt_sha256(
        evidence_blocks=first.evidence_blocks,
        model_configuration_id=first.model_configuration_id,
    )
    assert re.fullmatch(r"[0-9A-F]{64}", first.prompt_sha256)
    assert re.fullmatch(r"[0-9A-F]{64}", first.canonical_request_sha256)
    assert b"\\" not in canonical_request_bytes(first)


def test_prompt_hash_changes_with_block_text_order_or_model_configuration() -> None:
    first = _block("First fictional block.")
    second = first.model_copy(
        update={
            "evidence_id": "fictional-evidence-002",
            "block_id": "fictional-block-002",
            "sequence": 2,
            "text": "Second fictional block.",
        }
    )

    base = prompt_sha256(
        evidence_blocks=(first, second),
        model_configuration_id="fictional-model-configuration-v1",
    )
    assert base != prompt_sha256(
        evidence_blocks=(second.model_copy(update={"sequence": 1}), first.model_copy(update={"sequence": 2})),
        model_configuration_id="fictional-model-configuration-v1",
    )
    assert base != prompt_sha256(
        evidence_blocks=(first.model_copy(update={"text": "Changed fictional block."}), second),
        model_configuration_id="fictional-model-configuration-v1",
    )
    assert base != prompt_sha256(
        evidence_blocks=(first, second),
        model_configuration_id="fictional-model-configuration-v2",
    )


def test_prompt_canonicalization_is_independent_of_checkout_newlines() -> None:
    lf_assets = PromptAssets(
        system_prompt_bytes=b"System line one.\nSystem line two.\n",
        extraction_prompt_bytes=b"Extraction line one.\nExtraction line two.\n",
    )
    crlf_assets = PromptAssets(
        system_prompt_bytes=b"System line one.\r\nSystem line two.\r\n",
        extraction_prompt_bytes=b"Extraction line one.\r\nExtraction line two.\r\n",
    )

    first = canonical_prompt_bytes(
        evidence_blocks=(_block(),),
        model_configuration_id="fictional-model-configuration-v1",
        assets=lf_assets,
    )
    second = canonical_prompt_bytes(
        evidence_blocks=(_block(),),
        model_configuration_id="fictional-model-configuration-v1",
        assets=crlf_assets,
    )
    assert first == second
    assert b"\r" not in first
