"""Installation-safe prompts and deterministic Stage 4B request identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Iterable

from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    OUTPUT_CONTRACT_ID,
    PROMPT_VERSION,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)


PROMPT_PACKAGE = "document_intelligence.llm_extraction.prompts"
SYSTEM_PROMPT_NAME = "system_v0_1.txt"
EXTRACTION_PROMPT_NAME = "extraction_v0_1.txt"


@dataclass(frozen=True)
class PromptAssets:
    """Exact versioned prompt bytes before canonical newline normalization."""

    system_prompt_bytes: bytes
    extraction_prompt_bytes: bytes


def uppercase_sha256_bytes(value: bytes) -> str:
    """Return an uppercase SHA-256 for exact bytes."""
    return hashlib.sha256(value).hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically without platform newlines."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_prompt_asset_bytes(value: bytes, name: str) -> bytes:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error
    if text.startswith("\ufeff"):
        raise ValueError(f"{name} must not contain a UTF-8 byte-order mark")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        raise ValueError(f"{name} must not be blank")
    return normalized.encode("utf-8")


def load_prompt_assets() -> PromptAssets:
    """Load versioned prompt assets through the installed package."""
    prompt_root = resources.files(PROMPT_PACKAGE)
    return PromptAssets(
        system_prompt_bytes=prompt_root.joinpath(SYSTEM_PROMPT_NAME).read_bytes(),
        extraction_prompt_bytes=prompt_root.joinpath(
            EXTRACTION_PROMPT_NAME
        ).read_bytes(),
    )


def canonical_prompt_bytes(
    *,
    evidence_blocks: Iterable[ApprovedEvidenceBlock],
    model_configuration_id: str,
    prompt_version: str = PROMPT_VERSION,
    output_contract_id: str = OUTPUT_CONTRACT_ID,
    assets: PromptAssets | None = None,
) -> bytes:
    """Compose exact prompt identity from prompts, blocks, and output contract."""
    selected_assets = assets or load_prompt_assets()
    system_bytes = _canonical_prompt_asset_bytes(
        selected_assets.system_prompt_bytes, SYSTEM_PROMPT_NAME
    )
    extraction_bytes = _canonical_prompt_asset_bytes(
        selected_assets.extraction_prompt_bytes, EXTRACTION_PROMPT_NAME
    )
    blocks = tuple(evidence_blocks)
    payload = {
        "extraction_prompt": extraction_bytes.decode("utf-8"),
        "extraction_prompt_sha256": uppercase_sha256_bytes(extraction_bytes),
        "model_configuration_id": model_configuration_id,
        "ordered_evidence_blocks": [
            block.model_dump(mode="json") for block in blocks
        ],
        "output_contract_id": output_contract_id,
        "prompt_version": prompt_version,
        "system_prompt": system_bytes.decode("utf-8"),
        "system_prompt_sha256": uppercase_sha256_bytes(system_bytes),
    }
    return canonical_json_bytes(payload)


def prompt_sha256(
    *,
    evidence_blocks: Iterable[ApprovedEvidenceBlock],
    model_configuration_id: str,
    prompt_version: str = PROMPT_VERSION,
    output_contract_id: str = OUTPUT_CONTRACT_ID,
    assets: PromptAssets | None = None,
) -> str:
    """Return the canonical uppercase prompt identity."""
    return uppercase_sha256_bytes(
        canonical_prompt_bytes(
            evidence_blocks=evidence_blocks,
            model_configuration_id=model_configuration_id,
            prompt_version=prompt_version,
            output_contract_id=output_contract_id,
            assets=assets,
        )
    )


def canonical_request_bytes(request: LLMExtractionRequest) -> bytes:
    """Serialize a request identity excluding its self-referential hash."""
    return canonical_json_bytes(
        request.model_dump(
            mode="json",
            exclude={"canonical_request_sha256"},
        )
    )


def canonical_request_sha256(request: LLMExtractionRequest) -> str:
    """Return the uppercase identity of the canonical request bytes."""
    return uppercase_sha256_bytes(canonical_request_bytes(request))


def build_request_envelope(
    *,
    invocation_role: InvocationRole,
    request_id: str,
    source_id: str,
    document_sha256: str,
    provider_configuration_id: str,
    model_configuration_id: str,
    evidence_blocks: Iterable[ApprovedEvidenceBlock],
) -> LLMExtractionRequest:
    """Build and validate a canonical Stage 4B request envelope."""
    blocks = tuple(evidence_blocks)
    prompt_identity = prompt_sha256(
        evidence_blocks=blocks,
        model_configuration_id=model_configuration_id,
    )
    provisional = LLMExtractionRequest(
        experiment_id=EXPERIMENT_ID,
        invocation_role=invocation_role,
        request_id=request_id,
        source_id=source_id,
        document_sha256=document_sha256,
        prompt_version=PROMPT_VERSION,
        prompt_sha256=prompt_identity,
        canonical_request_sha256="0" * 64,
        provider_configuration_id=provider_configuration_id,
        model_configuration_id=model_configuration_id,
        output_contract_id=OUTPUT_CONTRACT_ID,
        evidence_blocks=blocks,
    )
    request_identity = canonical_request_sha256(provisional)
    return LLMExtractionRequest.model_validate(
        {
            **provisional.model_dump(mode="python"),
            "canonical_request_sha256": request_identity,
        }
    )


def validate_request_identity(request: LLMExtractionRequest) -> None:
    """Fail closed when prompt or canonical request identity has drifted."""
    expected_prompt = prompt_sha256(
        evidence_blocks=request.evidence_blocks,
        model_configuration_id=request.model_configuration_id,
        prompt_version=request.prompt_version,
        output_contract_id=request.output_contract_id,
    )
    if request.prompt_sha256 != expected_prompt:
        raise Stage4BError(
            Stage4BErrorCode.PROMPT_HASH_MISMATCH,
            "request prompt_sha256 does not match canonical prompt composition",
        )
    expected_request = canonical_request_sha256(request)
    if request.canonical_request_sha256 != expected_request:
        raise Stage4BError(
            Stage4BErrorCode.CANONICAL_REQUEST_HASH_MISMATCH,
            "canonical_request_sha256 does not match canonical request bytes",
        )


__all__ = [
    "PromptAssets",
    "build_request_envelope",
    "canonical_json_bytes",
    "canonical_prompt_bytes",
    "canonical_request_bytes",
    "canonical_request_sha256",
    "load_prompt_assets",
    "prompt_sha256",
    "uppercase_sha256_bytes",
    "validate_request_identity",
]
