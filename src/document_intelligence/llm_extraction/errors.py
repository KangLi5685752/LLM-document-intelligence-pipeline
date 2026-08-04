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
    INVALID_MANIFEST = "invalid_manifest"
    MANIFEST_HASH_MISMATCH = "manifest_hash_mismatch"
    DUPLICATE_INVOCATION = "duplicate_invocation"
    REQUEST_BUDGET_EXCEEDED = "request_budget_exceeded"
    ATTEMPT_BUDGET_EXCEEDED = "attempt_budget_exceeded"
    COST_BUDGET_EXCEEDED = "cost_budget_exceeded"
    CACHE_MISS = "cache_miss"
    CACHE_CONFLICT = "cache_conflict"
    CACHE_RECORD_INVALID = "cache_record_invalid"
    CACHE_HASH_MISMATCH = "cache_hash_mismatch"
    CACHE_PATH_ESCAPE = "cache_path_escape"
    CACHE_WRITE_FAILED = "cache_write_failed"
    RETRY_NOT_PERMITTED = "retry_not_permitted"
    EXECUTION_FAILED = "execution_failed"
    REPORT_CONFLICT = "report_conflict"
    PROVIDER_CONFIGURATION_MISMATCH = "provider_configuration_mismatch"
    MODEL_CONFIGURATION_MISMATCH = "model_configuration_mismatch"
    INVALID_PROVIDER_REQUEST = "invalid_provider_request"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    TRANSPORT_ERROR = "transport_error"
    PROVIDER_API_FAILURE = "provider_api_failure"
    INCOMPLETE_RESPONSE = "incomplete_response"
    FAILED_RESPONSE = "failed_response"
    RESPONSE_NOT_COMPLETED = "response_not_completed"
    MISSING_OUTPUT_TEXT = "missing_output_text"
    MISSING_PROVIDER_METADATA = "missing_provider_metadata"
    PROVIDER_REFUSAL = "provider_refusal"
    PREFLIGHT_AUTHORIZATION_INVALID = "preflight_authorization_invalid"
    PREFLIGHT_TERMS_INVALID = "preflight_terms_invalid"
    PREFLIGHT_VERSION_PROVENANCE_INVALID = (
        "preflight_version_provenance_invalid"
    )
    PREFLIGHT_PROVIDER_METADATA_INVALID = (
        "preflight_provider_metadata_invalid"
    )
    PREFLIGHT_OUTPUT_INVALID = "preflight_output_invalid"
    PREFLIGHT_RECORD_HASH_MISMATCH = "preflight_record_hash_mismatch"
    PREFLIGHT_EXECUTION_GATE_INVALID = "preflight_execution_gate_invalid"
    PREFLIGHT_INPUT_FILE_INVALID = "preflight_input_file_invalid"
    PREFLIGHT_ATTEMPT_ALREADY_EXISTS = "preflight_attempt_already_exists"
    PREFLIGHT_ARTIFACT_WRITE_FAILED = "preflight_artifact_write_failed"
    PREFLIGHT_API_KEY_MISSING = "preflight_api_key_missing"
    PREFLIGHT_API_KEY_INVALID = "preflight_api_key_invalid"
    PREFLIGHT_FAILURE_RECORD_HASH_MISMATCH = (
        "preflight_failure_record_hash_mismatch"
    )


class Stage4BError(ValueError):
    """Fail-closed Stage 4B exception with a stable error code."""

    def __init__(self, code: Stage4BErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code.value}: {message}")


__all__ = ["Stage4BError", "Stage4BErrorCode"]
