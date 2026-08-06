"""Regression tests for the frozen Stage 4D development execution plan."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.openai_development_execution_plan import (
    EXPECTED_EXECUTION_PLAN_SHA256,
    OpenAIDevelopmentExecutionPlanV01,
    development_execution_plan_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_execution_plan/"
    "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.1.json"
)

EXPECTED_OUTER_SHA256 = (
    "FFFE07FEA0F19FF46B4B5F060B012699BA1A68E6C9BDE94AF7E7CF93E6956F93"
)
EXPECTED_ARTIFACT_BYTES = 12641

EXPECTED_REQUEST_IDS = (
    "llm-v0.1-S001-primary-001",
    "llm-v0.1-S002-primary-001",
    "llm-v0.1-S003-primary-001",
    "llm-v0.1-S004-primary-001",
    "llm-v0.1-S004-primary-002",
    "llm-v0.1-S004-primary-003",
    "llm-v0.1-S006-primary-001",
    "llm-v0.1-S004-repeat-001",
)

EXPECTED_CACHE_IDENTITIES = (
    "F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393",
    "EC5404C802BD54EAFD90E08E56C727AF258F2B2BFFE706A3AE6954118E8704DE",
    "B8A877459D061497631CEBD9FF38209BA832A54D8284003ED47A5148F72F285C",
    "4282CF340940EEF55C3CAB2E630D5B1EE56BF5A0AC3EA798B006DA2F77C34A80",
    "8917AA5F5A4AE09290D7F331266B628698FC2D7AC0A0AB69B33ACAA5160E8345",
    "4BB0156C6FF7C3A50310FA8DE4D7C29675A31879712E79FA3F7F2B8226A804C4",
    "DE477D531FDB654FFDDDF040E9F4D47F447890B75DBBE2035A47032D5DD81E05",
    "3845479111B03DAAF1797E64E7C88E041F3EF19AFD882C4A4A0669D9BDB9A422",
)

EXPECTED_PAYLOAD_BYTES = (
    105273,
    82813,
    72736,
    199892,
    199780,
    90000,
    180192,
    199892,
)


def _artifact_bytes() -> bytes:
    return ARTIFACT_PATH.read_bytes()


def _plan() -> OpenAIDevelopmentExecutionPlanV01:
    return OpenAIDevelopmentExecutionPlanV01.model_validate_json(
        _artifact_bytes()
    )


def _all_mapping_keys(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            result.add(str(key))
            result.update(_all_mapping_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            result.update(_all_mapping_keys(nested))
    return result


def test_frozen_execution_plan_exact_file_identity() -> None:
    raw = _artifact_bytes()

    assert ARTIFACT_PATH.is_file()
    assert not ARTIFACT_PATH.is_symlink()
    assert len(raw) == EXPECTED_ARTIFACT_BYTES
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(raw).hexdigest().upper() == EXPECTED_OUTER_SHA256


def test_frozen_execution_plan_revalidates_to_exact_canonical_bytes() -> None:
    raw = _artifact_bytes()
    plan = _plan()

    assert plan.execution_plan_sha256 == EXPECTED_EXECUTION_PLAN_SHA256
    assert development_execution_plan_bytes(plan) == raw
    assert plan.execution_plan_schema_version == "0.1"
    assert plan.execution_id == (
        "openai-gpt-5.4-mini-five-source-development-execution-v0.1"
    )
    assert plan.authorization_scope == (
        "bounded-five-source-openai-development-execution-v0.1"
    )


def test_frozen_execution_plan_has_exact_invocation_inventory() -> None:
    plan = _plan()
    invocations = plan.invocations

    assert len(invocations) == 8
    assert tuple(item.request_id for item in invocations) == EXPECTED_REQUEST_IDS
    assert (
        tuple(item.cache_identity_sha256 for item in invocations)
        == EXPECTED_CACHE_IDENTITIES
    )
    assert (
        tuple(item.provider_payload_bytes for item in invocations)
        == EXPECTED_PAYLOAD_BYTES
    )
    assert [item.invocation_order for item in invocations] == list(range(1, 9))
    assert invocations[-1].invocation_role == "repeat"
    assert invocations[-1].repeated_primary_request_id == (
        "llm-v0.1-S004-primary-001"
    )
    assert len(
        {item.attempt_marker_relative_path for item in invocations}
    ) == 8
    assert len(
        {item.failure_record_relative_path for item in invocations}
    ) == 8


def test_frozen_execution_plan_budget_cache_and_authorization_boundaries() -> None:
    plan = _plan()
    controls = plan.execution_controls

    assert controls.maximum_provider_calls == 8
    assert controls.maximum_total_attempts == 8
    assert controls.maximum_retries_per_invocation == 0
    assert controls.provider_side_retries == 0
    assert controls.response_timeout_seconds == 120
    assert controls.maximum_output_token_budget == 32768
    assert controls.aggregate_conservative_cost_ceiling_usd == Decimal(
        "0.9953895"
    )
    assert controls.planned_authorization_cap_usd == Decimal("1.25")
    assert controls.same_day_pricing_review_required is True
    assert controls.same_day_data_controls_review_required is True

    assert plan.cache_policy.read_before_attempt_marker is True
    assert plan.cache_policy.append_only is True
    assert plan.cache_policy.cache_replacement_allowed is False
    assert plan.cache_policy.cache_bypass_allowed is False
    assert plan.cache_policy.successful_responses_only is True

    assert (
        plan.authorization_binding
        .explicit_project_owner_authorization_required
        is True
    )
    assert (
        plan.authorization_binding
        .authorization_not_created_by_readiness
        is True
    )
    assert (
        plan.authorization_binding
        .authorization_must_bind_execution_plan_sha256
        is True
    )
    assert (
        plan.authorization_binding
        .authorization_must_bind_manifest_sha256
        is True
    )


def test_frozen_execution_plan_is_hash_only_and_default_deny() -> None:
    payload = json.loads(_artifact_bytes())
    keys = _all_mapping_keys(payload)

    assert keys.isdisjoint(
        {
            "api_key",
            "authorization_id",
            "candidate_facts",
            "candidate_output",
            "credential",
            "document_content",
            "evidence_text",
            "provider_request_body",
            "provider_response",
            "raw_prompt",
            "raw_response",
            "source_text",
            "text",
        }
    )

    plan = _plan()
    assert plan.access_policy.approved_source_ids == (
        "S001",
        "S002",
        "S003",
        "S004",
        "S006",
    )
    assert plan.access_policy.explicitly_prohibited_source_ids == (
        "S005",
        "S007",
    )
    assert (
        plan.access_policy.held_out_parsed_document_access_authorized
        is False
    )
    assert plan.access_policy.held_out_annotation_access_authorized is False
    assert plan.access_policy.gold_labels_as_prompt_input_authorized is False
    assert (
        plan.partial_failure_policy
        .attempt_without_cache_is_not_retryable_in_v0_1
        is True
    )
    assert (
        plan.partial_failure_policy
        .automatic_retry_or_overwrite_is_forbidden
        is True
    )


def test_frozen_execution_plan_rejects_tampering() -> None:
    payload = json.loads(_artifact_bytes())
    payload["execution_plan_sha256"] = "F" * 64

    with pytest.raises(ValidationError, match="execution_plan_sha256"):
        OpenAIDevelopmentExecutionPlanV01.model_validate(payload)

    payload = json.loads(_artifact_bytes())
    payload["invocations"][0]["attempt_marker_relative_path"] = (
        "reports/unsafe.attempt.json"
    )

    with pytest.raises(ValidationError, match="attempt marker path"):
        OpenAIDevelopmentExecutionPlanV01.model_validate(payload)
