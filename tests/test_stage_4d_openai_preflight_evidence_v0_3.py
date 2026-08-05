"""Offline regression tests for frozen OpenAI synthetic-preflight v0.3 evidence."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from document_intelligence.llm_extraction.openai_preflight_execution_v0_3 import (
    ATTEMPT_MARKER_RELATIVE_PATH,
    FAILURE_RECORD_RELATIVE_PATH,
    SUCCESSFUL_RECORD_RELATIVE_PATH,
    OpenAIPreflightAttemptMarkerV03,
    attempt_marker_bytes,
    build_openai_preflight_execution_plan,
)
from document_intelligence.llm_extraction.openai_preflight_v0_3 import (
    OpenAIPreflightRecordV03,
    preflight_record_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPOSITORY_ROOT.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parent.parts)
ATTEMPT_PATH = REPOSITORY_ROOT.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parts)
SUCCESS_PATH = REPOSITORY_ROOT.joinpath(*SUCCESSFUL_RECORD_RELATIVE_PATH.parts)
FAILURE_PATH = REPOSITORY_ROOT.joinpath(*FAILURE_RECORD_RELATIVE_PATH.parts)

EXPECTED_ATTEMPT_OUTER_SHA256 = (
    "94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119"
)
EXPECTED_SUCCESS_OUTER_SHA256 = (
    "C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2"
)
EXPECTED_ATTEMPT_SELF_HASH = (
    "7FDEE6CFEFC6A9BAEC59BD702D7B0FBA4265DD049A11F43E5F5F5A4791036848"
)
EXPECTED_SUCCESS_SELF_HASH = (
    "1849C329F45D5BD0FA3472DB21FFBC60903C7449BC38BE05BFF6C3ACA219F974"
)
EXPECTED_EXECUTION_PLAN_SHA256 = (
    "21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5"
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
    OpenAIPreflightAttemptMarkerV03,
    OpenAIPreflightRecordV03,
]:
    attempt_bytes = ATTEMPT_PATH.read_bytes()
    success_bytes = SUCCESS_PATH.read_bytes()
    return (
        attempt_bytes,
        success_bytes,
        OpenAIPreflightAttemptMarkerV03.model_validate_json(attempt_bytes),
        OpenAIPreflightRecordV03.model_validate_json(success_bytes),
    )


def test_exact_v0_3_artifact_inventory_and_outer_hashes_are_frozen() -> None:
    expected_names = {ATTEMPT_PATH.name, SUCCESS_PATH.name}
    observed_names = {path.name for path in EVIDENCE_ROOT.glob("*v0.3*")}

    assert observed_names == expected_names
    assert ATTEMPT_PATH.is_file() and not ATTEMPT_PATH.is_symlink()
    assert SUCCESS_PATH.is_file() and not SUCCESS_PATH.is_symlink()
    assert not os.path.lexists(FAILURE_PATH)
    assert _outer_sha256(ATTEMPT_PATH) == EXPECTED_ATTEMPT_OUTER_SHA256
    assert _outer_sha256(SUCCESS_PATH) == EXPECTED_SUCCESS_OUTER_SHA256


def test_v0_3_models_canonical_bytes_self_hashes_and_plan_reconcile() -> None:
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


def test_v0_3_exact_safe_live_result_is_preserved() -> None:
    _, _, marker, record = _load_frozen_evidence()

    assert marker.preflight_id == "openai-gpt-5.4-mini-synthetic-preflight-v0.3"
    assert marker.authorization_scope == "single-synthetic-openai-preflight-v0.3"
    assert marker.maximum_provider_calls == 1
    assert record.preflight_id == marker.preflight_id
    assert record.authorization.scope == marker.authorization_scope
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
        "No extractable candidate facts were supported by the supplied evidence blocks.",
    )
    assert record.provider_call_count == 1
    assert record.retry_count == 0
    assert record.returned_model_identifier == "gpt-5.4-mini-2026-03-17"
    assert record.model_version_or_snapshot_provenance == "unavailable"
    assert record.provider_sdk_version == "2.46.0"
    assert record.input_tokens == 7332
    assert record.output_tokens == 155
    assert record.latency_ms == 4600
    assert record.estimated_actual_cost_usd == Decimal("0.0061965")
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


def test_v0_3_success_record_has_only_safe_fields_and_no_sensitive_payloads() -> None:
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
