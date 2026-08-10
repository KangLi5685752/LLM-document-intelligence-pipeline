"""Tests for the Stage 4D bounded v0.2 development execution plan."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.openai_development_execution_plan_v0_2 import (
    EXPECTED_EXECUTION_PLAN_SHA256,
    OpenAIDevelopmentExecutionPlanV02,
    build_openai_development_execution_plan_v0_2,
    development_execution_plan_bytes_v0_2,
    load_development_execution_plan_v0_2,
    write_development_execution_plan_v0_2,
)
from document_intelligence.llm_extraction.openai_development_execution_plan import (
    build_openai_development_execution_plan,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentManifestV01,
    OpenAIDevelopmentManifestV02,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
)


def _manifest() -> OpenAIDevelopmentManifestV02:
    return OpenAIDevelopmentManifestV02.model_validate_json(
        MANIFEST_PATH.read_bytes()
    )


def _plan() -> OpenAIDevelopmentExecutionPlanV02:
    return build_openai_development_execution_plan_v0_2(_manifest())


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


def test_execution_plan_has_exact_readiness_identity() -> None:
    plan = _plan()
    raw = development_execution_plan_bytes_v0_2(plan)

    assert plan.execution_plan_sha256 == EXPECTED_EXECUTION_PLAN_SHA256
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert OpenAIDevelopmentExecutionPlanV02.model_validate_json(raw) == plan
    assert hashlib.sha256(raw).hexdigest().upper() == (
        hashlib.sha256(development_execution_plan_bytes_v0_2(plan))
        .hexdigest()
        .upper()
    )


def test_execution_plan_binds_exact_manifest_and_provider() -> None:
    plan = _plan()

    assert plan.manifest_binding.artifact_bytes == 90575
    assert plan.manifest_binding.manifest_sha256 == (
        "16D9524377677F271CE7C33880B3E69E11A0157491FC8218A7666F8C5577D35C"
    )
    assert plan.manifest_binding.canonical_lf_content_sha256 == (
        "04FF2499BF346D8CB73B2DC03196E7FEE74B5DFF601F79CAC86F4C7B84D3BA3B"
    )
    assert plan.provider_binding.provider_identifier == "openai"
    assert plan.provider_binding.requested_model_alias == "gpt-5.4-mini"
    assert plan.provider_binding.returned_preflight_model_identifier == (
        "gpt-5.4-mini-2026-03-17"
    )
    assert plan.provider_binding.model_version_or_snapshot_provenance == (
        "unavailable"
    )
    assert plan.provider_binding.provider_sdk_version == "2.46.0"
    assert plan.provider_binding.output_contract_id == (
        "candidate-extraction-result-0.1"
    )
    assert plan.provider_binding.response_schema_name == (
        "candidate_extraction_result_0_1"
    )


def test_execution_plan_has_exact_invocation_inventory() -> None:
    plan = _plan()
    invocations = plan.invocations

    assert len(invocations) == 8
    assert [item.invocation_order for item in invocations] == list(range(1, 9))
    assert [item.request_id for item in invocations] == [
        "llm-v0.2-S001-primary-001",
        "llm-v0.2-S002-primary-001",
        "llm-v0.2-S003-primary-001",
        "llm-v0.2-S004-primary-001",
        "llm-v0.2-S004-primary-002",
        "llm-v0.2-S004-primary-003",
        "llm-v0.2-S006-primary-001",
        "llm-v0.2-S004-repeat-001",
    ]
    assert [item.provider_payload_bytes for item in invocations] == [
        106610,
        84150,
        74073,
        197839,
        196574,
        99270,
        181529,
        197839,
    ]
    assert invocations[-1].repeated_primary_request_id == (
        "llm-v0.2-S004-primary-001"
    )
    assert len({item.cache_identity_sha256 for item in invocations}) == 8
    assert all(
        item.cache_identity_sha256 in item.attempt_marker_relative_path
        for item in invocations
    )
    assert all(
        item.cache_identity_sha256 in item.failure_record_relative_path
        for item in invocations
    )


def test_execution_plan_freezes_budget_cache_and_failure_boundaries() -> None:
    plan = _plan()
    controls = plan.execution_controls

    assert controls.maximum_provider_calls == 8
    assert controls.maximum_total_attempts == 8
    assert controls.maximum_retries_per_invocation == 0
    assert controls.maximum_transaction_retries == 0
    assert controls.provider_side_retries == 0
    assert controls.response_timeout_seconds == 120
    assert controls.maximum_output_tokens_per_invocation == 4096
    assert controls.maximum_output_token_budget == 32768
    assert controls.aggregate_conservative_cost_ceiling_usd == Decimal(
        "1.000869"
    )
    assert controls.planned_authorization_cap_usd == Decimal("1.25")
    assert controls.same_day_pricing_review_required is True
    assert controls.same_day_data_controls_review_required is True

    assert plan.cache_policy.read_before_attempt_marker is True
    assert plan.cache_policy.append_only is True
    assert plan.cache_policy.cache_replacement_allowed is False
    assert plan.cache_policy.cache_bypass_allowed is False
    assert plan.artifact_policy.attempt_marker_installed_before_credential_access
    assert (
        plan.artifact_policy
        .provider_response_cache_installed_before_local_validation
    )
    assert plan.artifact_policy.execution_record_installed_exclusively_and_last
    assert plan.partial_failure_policy.stop_after_first_provider_or_local_failure
    assert plan.partial_failure_policy.completed_cache_records_are_preserved
    assert (
        plan.partial_failure_policy
        .attempt_without_cache_is_not_retryable_in_v0_2
    )
    assert plan.partial_failure_policy.cache_after_local_parse_failure_is_reusable
    assert (
        plan.partial_failure_policy.automatic_retry_or_overwrite_is_forbidden
    )


def test_execution_plan_preserves_default_deny_access_and_authorization() -> None:
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
        plan.authorization_binding
        .explicit_project_owner_authorization_required
        is True
    )
    assert (
        plan.authorization_binding
        .authorization_not_created_by_readiness
        is True
    )


def test_execution_plan_is_hash_only() -> None:
    payload = json.loads(development_execution_plan_bytes_v0_2(_plan()))
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


def test_execution_plan_rejects_tampering() -> None:
    payload = _plan().model_dump(mode="json")
    payload["execution_plan_sha256"] = "F" * 64

    with pytest.raises(ValidationError, match="execution_plan_sha256"):
        OpenAIDevelopmentExecutionPlanV02.model_validate(payload)

    payload = _plan().model_dump(mode="json")
    payload["invocations"][0]["attempt_marker_relative_path"] = (
        "reports/unsafe.attempt.json"
    )

    with pytest.raises(ValidationError, match="attempt marker path"):
        OpenAIDevelopmentExecutionPlanV02.model_validate(payload)


def test_execution_plan_loader_accepts_lf_and_crlf(tmp_path: Path) -> None:
    canonical = development_execution_plan_bytes_v0_2(_plan())
    lf_path = tmp_path / "plan-lf.json"
    crlf_path = tmp_path / "plan-crlf.json"
    lf_path.write_bytes(canonical)
    crlf_path.write_bytes(canonical.replace(b"\n", b"\r\n"))

    assert load_development_execution_plan_v0_2(lf_path) == _plan()
    assert load_development_execution_plan_v0_2(crlf_path) == _plan()


def test_execution_plan_writer_is_canonical_and_exclusive(tmp_path: Path) -> None:
    output = tmp_path / "plan" / "execution-plan.json"
    output.parent.mkdir()

    write_development_execution_plan_v0_2(output, _plan())

    expected = development_execution_plan_bytes_v0_2(_plan())
    assert output.read_bytes() == expected
    with pytest.raises(FileExistsError):
        write_development_execution_plan_v0_2(output, _plan())
    assert output.read_bytes() == expected


def test_v0_1_and_v0_2_manifest_plan_families_do_not_cross() -> None:
    v0_1_manifest_path = REPOSITORY_ROOT / (
        "reports/llm_extraction/openai_development_manifest/"
        "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
    )
    v0_1_manifest = OpenAIDevelopmentManifestV01.model_validate_json(
        v0_1_manifest_path.read_bytes()
    )

    with pytest.raises(ValueError, match="development manifest is invalid"):
        build_openai_development_execution_plan_v0_2(v0_1_manifest)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="development manifest is invalid"):
        build_openai_development_execution_plan(_manifest())  # type: ignore[arg-type]
