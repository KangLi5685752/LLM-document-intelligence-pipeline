"""Offline regression tests for frozen OpenAI synthetic-preflight v0.4 evidence."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from document_intelligence.llm_extraction.openai_preflight_execution_v0_4 import (
    ATTEMPT_MARKER_RELATIVE_PATH,
    FAILURE_RECORD_RELATIVE_PATH,
    SUCCESSFUL_RECORD_RELATIVE_PATH,
    OpenAIPreflightAttemptMarkerV04,
    attempt_marker_bytes,
    build_openai_preflight_execution_plan,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    OpenAIPreflightRecordV04,
    preflight_record_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPOSITORY_ROOT.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parent.parts)
ATTEMPT_PATH = REPOSITORY_ROOT.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parts)
SUCCESS_PATH = REPOSITORY_ROOT.joinpath(*SUCCESSFUL_RECORD_RELATIVE_PATH.parts)
FAILURE_PATH = REPOSITORY_ROOT.joinpath(*FAILURE_RECORD_RELATIVE_PATH.parts)

EXPECTED_ATTEMPT_OUTER_SHA256 = (
    "4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B"
)
EXPECTED_SUCCESS_OUTER_SHA256 = (
    "1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6"
)
EXPECTED_ATTEMPT_SELF_HASH = (
    "3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A"
)
EXPECTED_SUCCESS_SELF_HASH = (
    "36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF"
)
EXPECTED_EXECUTION_PLAN_SHA256 = (
    "F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E"
)
EXPECTED_TOP_LEVEL_FIELDS = {
    "api_surface",
    "authorization",
    "background_enabled",
    "canonical_request_sha256",
    "compatibility_status",
    "data_controls_observation",
    "document_sha256",
    "estimated_actual_cost_usd",
    "execution_timestamp_utc",
    "experiment_id",
    "input_classification",
    "input_tokens",
    "latency_ms",
    "local_output_validation_status",
    "model_configuration_id",
    "model_version_or_snapshot_provenance",
    "output_tokens",
    "parsed_output_sha256",
    "preflight_id",
    "preflight_record_sha256",
    "preflight_schema_version",
    "preflight_status",
    "pricing_observation",
    "prompt_sha256",
    "provider_call_count",
    "provider_configuration_id",
    "provider_identifier",
    "provider_payload_sha256",
    "provider_public_metadata_field_paths",
    "provider_public_metadata_sha256",
    "provider_request_id",
    "provider_response_id",
    "provider_sdk_version",
    "raw_response_sha256",
    "request_id",
    "requested_model_alias",
    "retry_count",
    "returned_model_identifier",
    "semantic_diagnostic",
    "store_requested",
    "streaming_enabled",
    "strict_schema_compatible",
    "strict_schema_sha256",
    "tools_enabled",
    "version_provenance_observed_from_same_provider_call",
    "version_provenance_source_response_id",
}
FORBIDDEN_FIELD_NAMES = {
    "api_key",
    "credential",
    "credential_fragment",
    "development_document",
    "document_content",
    "headers",
    "held_out_document",
    "http_headers",
    "provider_request_body",
    "provider_response_body",
    "raw_prompt",
    "raw_provider_output",
    "request_body",
    "response_body",
}


def _outer_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _field_paths(value: Any, prefix: tuple[str, ...] = ()) -> tuple[str, ...]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = (*prefix, str(key))
            paths.append(".".join(child_prefix))
            paths.extend(_field_paths(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_field_paths(child, (*prefix, str(index))))
    return tuple(paths)


def _load_frozen_evidence() -> tuple[
    bytes,
    bytes,
    OpenAIPreflightAttemptMarkerV04,
    OpenAIPreflightRecordV04,
]:
    attempt_bytes = ATTEMPT_PATH.read_bytes()
    success_bytes = SUCCESS_PATH.read_bytes()
    return (
        attempt_bytes,
        success_bytes,
        OpenAIPreflightAttemptMarkerV04.model_validate_json(attempt_bytes),
        OpenAIPreflightRecordV04.model_validate_json(success_bytes),
    )


def test_exact_v0_4_artifact_inventory_and_outer_hashes_are_frozen() -> None:
    expected_names = {ATTEMPT_PATH.name, SUCCESS_PATH.name}
    observed_names = {path.name for path in EVIDENCE_ROOT.glob("*v0.4*")}

    assert observed_names == expected_names
    assert ATTEMPT_PATH.is_file() and not ATTEMPT_PATH.is_symlink()
    assert SUCCESS_PATH.is_file() and not SUCCESS_PATH.is_symlink()
    assert not os.path.lexists(FAILURE_PATH)
    assert _outer_sha256(ATTEMPT_PATH) == EXPECTED_ATTEMPT_OUTER_SHA256
    assert _outer_sha256(SUCCESS_PATH) == EXPECTED_SUCCESS_OUTER_SHA256


def test_v0_4_models_canonical_bytes_self_hashes_and_plan_reconcile() -> None:
    attempt_bytes, success_bytes, marker, record = _load_frozen_evidence()
    plan = build_openai_preflight_execution_plan()

    assert attempt_bytes == attempt_marker_bytes(marker) + b"\n"
    assert success_bytes == preflight_record_bytes(record) + b"\n"
    assert marker.marker_sha256 == EXPECTED_ATTEMPT_SELF_HASH
    assert record.preflight_record_sha256 == EXPECTED_SUCCESS_SELF_HASH
    assert plan.execution_plan_sha256 == EXPECTED_EXECUTION_PLAN_SHA256
    assert marker.execution_plan_sha256 == plan.execution_plan_sha256
    assert record.canonical_request_sha256 == plan.canonical_request_sha256
    assert record.prompt_sha256 == plan.prompt_sha256
    assert record.document_sha256 == plan.synthetic_document_sha256
    assert record.strict_schema_sha256 == plan.strict_schema_sha256
    assert record.provider_payload_sha256 == plan.provider_payload_sha256
    assert record.prompt_sha256 == (
        "556DB1C4D2CDEAE0EEA49C60407246F956DF27850EF9001F7EDA0078F59CD283"
    )
    assert record.canonical_request_sha256 == (
        "58ADDE1DFABA56786840F0101D55BE54CBC08F7BFD55E41992AE4EC1A310789F"
    )
    assert record.document_sha256 == (
        "98A52939E982B1D7E9784B078C1483B85526AC0B7F62787B80A86C75127FF5FC"
    )
    assert record.strict_schema_sha256 == (
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    )
    assert record.provider_payload_sha256 == (
        "B1B5F4EB733DE4336FA593F1A7F381487A2E7C9B71FCAE03AAE7BFF29D63DF4B"
    )
    assert record.parsed_output_sha256 == (
        "194862DFE8AC13B2397C5C213A35DF67C3C4DAA5DB3A43B34E3F4393A8F0C4E3"
    )
    assert record.raw_response_sha256 == (
        "9A16D76AEC76724383D452B183A5E2568F2C2048FE11CC05BD130CC1D3421F93"
    )


def test_v0_4_exact_safe_live_result_is_preserved() -> None:
    _, _, marker, record = _load_frozen_evidence()

    assert marker.preflight_id == "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
    assert marker.authorization_scope == "single-synthetic-openai-preflight-v0.4"
    assert marker.maximum_provider_calls == 1
    assert record.preflight_id == marker.preflight_id
    assert record.authorization.scope == marker.authorization_scope
    assert record.preflight_schema_version == "0.4"
    assert record.experiment_id == "llm-extraction-baseline-v0.3"
    assert record.request_id == "llm-v0.3-S001-primary-999"
    assert record.input_classification == "synthetic_preflight_text"
    assert record.provider_identifier == "openai"
    assert record.api_surface == "responses"
    assert record.requested_model_alias == "gpt-5.4-mini"
    assert record.provider_configuration_id == (
        "openai-responses-text-strict-json-v0.2"
    )
    assert record.model_configuration_id == (
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    )
    assert record.authorization.authorization_id == (
        "openai-gpt-5.4-mini-synthetic-preflight-v0.4-2026-08-10-001"
    )
    assert record.authorization.authorized_by == "Kang Li"
    assert record.compatibility_status == "passed"
    assert record.preflight_status == "passed"
    assert record.strict_schema_compatible is True
    assert record.local_output_validation_status == "valid"
    assert record.semantic_diagnostic.semantic_diagnostic_status == (
        "valid_semantic_variance"
    )
    assert record.semantic_diagnostic.entity_count == 0
    assert record.semantic_diagnostic.evidence_reference_count == 1
    assert record.semantic_diagnostic.candidate_fact_count == 0
    assert record.semantic_diagnostic.warnings == (
        "No extractable facts present in the supplied evidence; abstained from emitting candidate facts.",
    )
    assert record.provider_call_count == 1
    assert record.retry_count == 0
    assert record.returned_model_identifier == "gpt-5.4-mini-2026-03-17"
    assert record.model_version_or_snapshot_provenance == "unavailable"
    assert record.provider_sdk_version == "2.46.0"
    assert record.input_tokens == 7594
    assert record.output_tokens == 177
    assert record.latency_ms == 4634
    assert record.estimated_actual_cost_usd == Decimal("0.006492")
    assert record.provider_public_metadata_field_paths == (
        "response.id",
        "response.model",
        "response._request_id",
        "sdk.version",
    )
    assert record.store_requested is False
    assert record.streaming_enabled is False
    assert record.background_enabled is False
    assert record.tools_enabled is False


def test_v0_4_success_record_has_only_safe_fields_and_no_sensitive_payloads() -> None:
    raw_bytes = SUCCESS_PATH.read_bytes()
    payload = json.loads(raw_bytes)
    paths = _field_paths(payload)
    normalized_bytes = raw_bytes.lower()

    assert set(payload) == EXPECTED_TOP_LEVEL_FIELDS
    assert set(payload["authorization"]) == {
        "authorization_id",
        "authorized_at_utc",
        "authorized_by",
        "maximum_provider_calls",
        "real_provider_preflight_authorized",
        "scope",
    }
    assert set(payload["semantic_diagnostic"]) == {
        "candidate_fact_count",
        "entity_count",
        "evidence_reference_count",
        "semantic_diagnostic_status",
        "warnings",
    }
    assert not {
        path
        for path in paths
        if path.rsplit(".", 1)[-1].casefold() in FORBIDDEN_FIELD_NAMES
    }
    for forbidden_literal in (
        b"sk-",
        b"bearer ",
        b"openai_api_key",
        b'"api_key"',
        b'"credential"',
        b'"raw_prompt"',
        b'"raw_provider_output"',
        b'"provider_request_body"',
        b'"provider_response_body"',
        b'"http_headers"',
    ):
        assert forbidden_literal not in normalized_bytes
