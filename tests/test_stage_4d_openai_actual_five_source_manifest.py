"""Regression tests for the frozen actual Stage 4D five-source manifest."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.openai_development_manifest import (
    APPROVED_SOURCE_ORDER,
    OpenAIDevelopmentManifestV01,
    development_manifest_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
)

EXPECTED_OUTER_SHA256 = (
    "15DF5E959040B399EDF8CA5455B5060EF71B6672C97D9901E6DB084FE9ACC069"
)
EXPECTED_SELF_HASH = (
    "05ABF3D0FA785B845E0853B907B911EE1A9439F0997052D3603E025AAAA30D0E"
)
EXPECTED_CONTEXT_SELF_HASH = (
    "09717CDFE8EFBF669047515AB2258E1C42BF1527AE2A7E7A79F8E2602D2FADF2"
)
EXPECTED_PRICING_REVIEW_SHA256 = (
    "42CF744C6728D84AE344BE86A41686943538281A63F476950DFD03ADB0233F25"
)
EXPECTED_DATA_CONTROLS_REVIEW_SHA256 = (
    "A15479B7927DCAC2DCBB0DD3AFE43BBAA2160C849B4E71698DA29849B820C7EE"
)


def _artifact_bytes() -> bytes:
    return ARTIFACT_PATH.read_bytes()


def _load_manifest() -> OpenAIDevelopmentManifestV01:
    return OpenAIDevelopmentManifestV01.model_validate_json(_artifact_bytes())


def _all_mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_all_mapping_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_all_mapping_keys(nested))
    return keys


def test_actual_manifest_exact_file_identity_is_frozen() -> None:
    raw_bytes = _artifact_bytes()

    assert ARTIFACT_PATH.is_file()
    assert not ARTIFACT_PATH.is_symlink()
    assert len(raw_bytes) == 90809
    assert raw_bytes.endswith(b"\n")
    assert not raw_bytes.endswith(b"\n\n")
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw_bytes
    assert hashlib.sha256(raw_bytes).hexdigest().upper() == EXPECTED_OUTER_SHA256


def test_actual_manifest_revalidates_to_exact_canonical_model_bytes() -> None:
    raw_bytes = _artifact_bytes()
    manifest = _load_manifest()

    assert development_manifest_bytes(manifest) == raw_bytes
    assert manifest.manifest_sha256 == EXPECTED_SELF_HASH
    assert manifest.manifest_schema_version == "0.1"
    assert manifest.experiment_id == "llm-extraction-baseline-v0.1"
    assert manifest.provider_identifier == "openai"
    assert manifest.requested_model_alias == "gpt-5.4-mini"
    assert (
        manifest.returned_preflight_model_identifier
        == "gpt-5.4-mini-2026-03-17"
    )
    assert manifest.model_version_or_snapshot_provenance == "unavailable"
    assert manifest.provider_sdk_version == "2.46.0"


def test_actual_manifest_has_exact_approved_inventory_and_repeat_boundary() -> None:
    manifest = _load_manifest()
    routes = manifest.source_routes
    invocations = manifest.invocations

    assert tuple(route.source_id for route in routes) == APPROVED_SOURCE_ORDER
    assert len(routes) == 5
    assert len(invocations) == 8

    primary = [
        item
        for item in invocations
        if item.invocation_role.value == "primary"
    ]
    repeat = [
        item
        for item in invocations
        if item.invocation_role.value == "repeat"
    ]

    assert len(primary) == 7
    assert len(repeat) == 1
    assert {item.source_id for item in primary} == set(APPROVED_SOURCE_ORDER)
    assert Counter(item.source_id for item in primary) == {
        "S001": 1,
        "S002": 1,
        "S003": 1,
        "S004": 3,
        "S006": 1,
    }
    assert invocations[-1] == repeat[0]
    assert repeat[0].request_id == "llm-v0.1-S004-repeat-001"
    assert (
        repeat[0].repeated_primary_request_id
        == "llm-v0.1-S004-primary-001"
    )
    assert max(item.provider_payload_bytes for item in invocations) == 199892
    assert all(item.provider_payload_bytes <= 200000 for item in invocations)
    assert all(
        item.provider_payload_bytes + item.maximum_output_tokens <= 400000
        for item in invocations
    )


def test_actual_manifest_budget_reviews_and_authorization_are_frozen() -> None:
    manifest = _load_manifest()
    budget = manifest.execution_budget

    assert budget.primary_request_count == 7
    assert budget.repeat_request_count == 1
    assert budget.maximum_provider_calls == 8
    assert budget.maximum_total_attempts == 8
    assert budget.maximum_retries_per_invocation == 0
    assert budget.provider_side_retries == 0
    assert budget.maximum_output_token_budget == 32768
    assert budget.aggregate_planning_cost_usd == Decimal("0.3594405")
    assert (
        budget.aggregate_conservative_cost_ceiling_usd
        == Decimal("0.9953895")
    )
    assert budget.planned_authorization_cap_usd == Decimal("1.25")
    assert (
        budget.aggregate_conservative_cost_ceiling_usd
        < budget.planned_authorization_cap_usd
    )
    assert budget.same_day_pricing_review_required is True

    expected_review_time = datetime(
        2026, 8, 6, 1, 26, 53, tzinfo=timezone.utc
    )
    assert manifest.pricing_review.reviewed_at_utc == expected_review_time
    assert manifest.data_controls_review.reviewed_at_utc == expected_review_time
    assert (
        manifest.pricing_review.review_sha256
        == EXPECTED_PRICING_REVIEW_SHA256
    )
    assert (
        manifest.data_controls_review.review_sha256
        == EXPECTED_DATA_CONTROLS_REVIEW_SHA256
    )
    assert (
        manifest.context_limit_observation.observation_sha256
        == EXPECTED_CONTEXT_SELF_HASH
    )
    assert (
        manifest.context_limit_observation.exact_context_window_tokens
        == 400000
    )

    assert manifest.manifest_review_status == "pending_independent_review"
    assert manifest.execution_authorization_required is True
    assert manifest.execution_authorization_status == "not_provided"
    assert (
        manifest.access_policy.held_out_parsed_document_access_authorized
        is False
    )
    assert (
        manifest.access_policy.held_out_annotation_access_authorized
        is False
    )
    assert (
        manifest.access_policy.gold_labels_as_prompt_input_authorized
        is False
    )


def test_actual_manifest_is_hash_only_and_contains_no_execution_payloads() -> None:
    payload = json.loads(_artifact_bytes())
    keys = _all_mapping_keys(payload)

    forbidden_keys = {
        "api_key",
        "authorization_id",
        "candidate_facts",
        "candidate_output",
        "credential",
        "document_content",
        "provider_request_body",
        "provider_response",
        "raw_prompt",
        "source_text",
        "text",
    }
    assert keys.isdisjoint(forbidden_keys)

    invocation_sources = {
        item["source_id"] for item in payload["invocations"]
    }
    route_sources = {
        item["source_id"] for item in payload["source_routes"]
    }
    assert invocation_sources == set(APPROVED_SOURCE_ORDER)
    assert route_sources == set(APPROVED_SOURCE_ORDER)


def test_actual_manifest_rejects_tampered_self_hash() -> None:
    payload = json.loads(_artifact_bytes())
    payload["manifest_sha256"] = "F" * 64

    with pytest.raises(ValidationError, match="manifest_sha256"):
        OpenAIDevelopmentManifestV01.model_validate(payload)
