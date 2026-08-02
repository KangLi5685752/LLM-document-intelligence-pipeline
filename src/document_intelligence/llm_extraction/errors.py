"""Typed, stable failures for the Stage 4B LLM extraction boundary."""

from __future__ import annotations

from enum import Enum


class Stage4BErrorCode(str, Enum):
    """Machine-readable Stage 4B failure categories."""

    PROHIBITED_SOURCE = "prohibited_source"
    PROVIDER_NOT_SUCCESSFUL = "provider_not_successful"
    INVALID_JSON = "invalid_json"
    INVALID_OUTPUT_SHAPE = "invalid_output_shape"
    SCHEMA_INVALID = "schema_invalid"
    INVALID_PREDICATE = "invalid_predicate"
    INVALID_QUALIFIER = "invalid_qualifier"
    SOURCE_MISMATCH = "source_mismatch"
    UNKNOWN_EVIDENCE_REFERENCE = "unknown_evidence_reference"
    CROSS_SOURCE_EVIDENCE_REFERENCE = "cross_source_evidence_reference"
    MISSING_EVIDENCE_REFERENCE = "missing_evidence_reference"
    PROMPT_HASH_MISMATCH = "prompt_hash_mismatch"
    CANONICAL_REQUEST_HASH_MISMATCH = "canonical_request_hash_mismatch"
    RESPONSE_REQUEST_MISMATCH = "response_request_mismatch"
    MOCK_RESPONSE_NOT_FOUND = "mock_response_not_found"


class Stage4BError(ValueError):
    """Fail-closed Stage 4B exception with a stable error code."""

    def __init__(self, code: Stage4BErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code.value}: {message}")


__all__ = ["Stage4BError", "Stage4BErrorCode"]
