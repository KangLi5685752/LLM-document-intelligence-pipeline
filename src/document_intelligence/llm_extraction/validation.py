"""Fail-closed structured output validation for Stage 4B."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    ExtractionMethod,
)
from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequest,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ValidatedCandidateOutput,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result


def _parse_strict_json(raw_response: str) -> dict[str, Any]:
    try:
        payload = json.loads(
            raw_response,
            parse_constant=_reject_non_json_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_JSON,
            "provider response is not strict JSON",
        ) from error
    if not isinstance(payload, dict):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_OUTPUT_SHAPE,
            "provider response top-level JSON value must be an object",
        )
    return payload


def _prevalidate_reference_shape(
    payload: dict[str, Any], request: LLMExtractionRequest
) -> None:
    source_ids = payload.get("source_ids")
    if isinstance(source_ids, list) and source_ids != [request.source_id]:
        raise Stage4BError(
            Stage4BErrorCode.SOURCE_MISMATCH,
            "result source_ids must contain only the request source_id",
        )

    evidence_references = payload.get("evidence_references")
    if isinstance(evidence_references, list):
        for reference in evidence_references:
            if not isinstance(reference, dict):
                continue
            evidence_id = reference.get("evidence_id")
            if isinstance(evidence_id, str) and not evidence_id.strip():
                raise Stage4BError(
                    Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE,
                    "evidence references must use a non-blank evidence_id",
                )
            source_id = reference.get("source_id")
            if isinstance(source_id, str) and source_id != request.source_id:
                raise Stage4BError(
                    Stage4BErrorCode.CROSS_SOURCE_EVIDENCE_REFERENCE,
                    "response evidence must belong to the request source",
                )

    candidate_facts = payload.get("candidate_facts")
    if isinstance(candidate_facts, list):
        for fact in candidate_facts:
            if not isinstance(fact, dict):
                continue
            evidence_ids = fact.get("evidence_ids")
            if isinstance(evidence_ids, list) and (
                not evidence_ids
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in evidence_ids
                )
            ):
                raise Stage4BError(
                    Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE,
                    "candidate facts require non-blank evidence_ids",
                )


def _schema_error_code(error: ValidationError) -> Stage4BErrorCode:
    messages = " ".join(item["msg"] for item in error.errors()).casefold()
    if "unknown predicate" in messages:
        return Stage4BErrorCode.INVALID_PREDICATE
    if "undeclared qualifiers" in messages or "requires meaningful qualifiers" in messages:
        return Stage4BErrorCode.INVALID_QUALIFIER
    if "evidence_ids must not be empty" in messages:
        return Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE
    return Stage4BErrorCode.SCHEMA_INVALID


def _validate_allowed_evidence(
    result: CandidateExtractionResult, request: LLMExtractionRequest
) -> None:
    approved = {block.evidence_id: block for block in request.evidence_blocks}
    for evidence in result.evidence_references:
        if evidence.source_id != request.source_id:
            raise Stage4BError(
                Stage4BErrorCode.CROSS_SOURCE_EVIDENCE_REFERENCE,
                f"evidence {evidence.evidence_id!r} belongs to another source",
            )
        block = approved.get(evidence.evidence_id)
        if block is None:
            raise Stage4BError(
                Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE,
                f"evidence {evidence.evidence_id!r} was not supplied in the request",
            )
        if (
            evidence.block_id != block.block_id
            or evidence.location_type is not block.location.location_type
            or evidence.location_value != block.location.location_value
        ):
            raise Stage4BError(
                Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE,
                f"evidence {evidence.evidence_id!r} does not match its approved block",
            )
    for fact in result.candidate_facts:
        if any(evidence_id not in approved for evidence_id in fact.evidence_ids):
            raise Stage4BError(
                Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE,
                f"candidate {fact.candidate_id!r} references evidence outside the request",
            )
        if fact.extraction_method is not ExtractionMethod.LLM:
            raise Stage4BError(
                Stage4BErrorCode.SCHEMA_INVALID,
                "Stage 4B candidate facts must use extraction_method 'llm'",
            )


def validate_provider_output(
    request: LLMExtractionRequest,
    response: LLMProviderResponse,
) -> ValidatedCandidateOutput:
    """Validate one exact provider response without repair, scoring, or I/O."""
    validate_request_identity(request)
    if response.request_id != request.request_id:
        raise Stage4BError(
            Stage4BErrorCode.RESPONSE_REQUEST_MISMATCH,
            "provider response request_id does not match the request",
        )
    if response.terminal_status is not ProviderTerminalStatus.SUCCESS:
        raise Stage4BError(
            Stage4BErrorCode.PROVIDER_NOT_SUCCESSFUL,
            f"provider terminal status is {response.terminal_status.value!r}",
        )

    payload = _parse_strict_json(response.raw_response)
    _prevalidate_reference_shape(payload, request)
    try:
        result = CandidateExtractionResult.model_validate(payload)
    except ValidationError as error:
        raise Stage4BError(
            _schema_error_code(error),
            "provider output does not satisfy the existing candidate contract",
        ) from error

    if tuple(result.source_ids) != (request.source_id,):
        raise Stage4BError(
            Stage4BErrorCode.SOURCE_MISMATCH,
            "validated result source_ids must equal the request source_id",
        )
    _validate_allowed_evidence(result, request)
    canonical_output = canonical_json_bytes(result.model_dump(mode="json"))
    return ValidatedCandidateOutput(
        request_id=request.request_id,
        source_id=request.source_id,
        candidate_result=result,
        canonical_output_sha256=uppercase_sha256_bytes(canonical_output),
    )


__all__ = ["validate_provider_output"]
