"""Offline regressions for the frozen Stage 4D v0.3 execution plan."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.openai_development_execution_plan_v0_2 import (
    EXPECTED_EXECUTION_PLAN_SHA256 as V0_2_EXECUTION_PLAN_SHA256,
    load_development_execution_plan_v0_2,
)
from document_intelligence.llm_extraction.openai_development_execution_plan_v0_3 import (
    ATTEMPT_MARKER_ROOT,
    AUTHORIZATION_SCOPE,
    EXECUTION_ID,
    EXECUTION_PLAN_SCHEMA_VERSION,
    EXECUTION_RECORD_PATH,
    EXPECTED_EXECUTION_PLAN_ARTIFACT_BYTES,
    EXPECTED_EXECUTION_PLAN_OUTER_SHA256,
    EXPECTED_EXECUTION_PLAN_SHA256,
    FAILURE_RECORD_ROOT,
    MANIFEST_ARTIFACT_BYTES,
    MANIFEST_CANONICAL_LF_SHA256,
    MANIFEST_RELATIVE_PATH,
    MANIFEST_SELF_SHA256,
    OpenAIDevelopmentExecutionPlanV03,
    build_openai_development_execution_plan_v0_3,
    build_plan_from_frozen_manifest_v0_3,
    development_execution_plan_bytes_v0_3,
    load_development_execution_plan_v0_3,
    write_development_execution_plan_v0_3,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentManifestV02,
    OpenAIDevelopmentManifestV03,
    canonical_lf_json_bytes,
    load_development_manifest_v0_3,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / MANIFEST_RELATIVE_PATH
PLAN_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_execution_plan/"
    "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.3.json"
)
V0_2_MANIFEST_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
)
V0_2_PLAN_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_execution_plan/"
    "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.2.json"
)

EXPECTED_REQUEST_IDS = [
    "llm-v0.3-S001-primary-001",
    "llm-v0.3-S002-primary-001",
    "llm-v0.3-S003-primary-001",
    "llm-v0.3-S004-primary-001",
    "llm-v0.3-S004-primary-002",
    "llm-v0.3-S004-primary-003",
    "llm-v0.3-S006-primary-001",
    "llm-v0.3-S004-repeat-001",
]
EXPECTED_PAYLOAD_BYTES = [
    106660,
    84200,
    74123,
    197889,
    196624,
    99320,
    181579,
    197889,
]


def _manifest() -> OpenAIDevelopmentManifestV03:
    return load_development_manifest_v0_3(MANIFEST_PATH)


def _plan() -> OpenAIDevelopmentExecutionPlanV03:
    return build_openai_development_execution_plan_v0_3(_manifest())


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


def test_plan_binds_exact_frozen_v0_3_manifest() -> None:
    raw = MANIFEST_PATH.read_bytes()
    canonical = canonical_lf_json_bytes(raw)
    manifest = _manifest()
    plan = _plan()

    assert len(canonical) == MANIFEST_ARTIFACT_BYTES == 90686
    assert uppercase_sha256_bytes(canonical) == MANIFEST_CANONICAL_LF_SHA256
    assert manifest.manifest_sha256 == MANIFEST_SELF_SHA256
    assert plan.manifest_binding.relative_path == MANIFEST_RELATIVE_PATH
    assert plan.manifest_binding.manifest_sha256 == MANIFEST_SELF_SHA256
    assert plan.manifest_binding.canonical_lf_content_sha256 == (
        MANIFEST_CANONICAL_LF_SHA256
    )
    assert plan.manifest_binding.artifact_bytes == MANIFEST_ARTIFACT_BYTES


def test_plan_binds_exact_alias_safe_provider_model_and_schema() -> None:
    binding = _plan().provider_binding

    assert binding.provider_identifier == "openai"
    assert binding.requested_model_alias == "gpt-5.4-mini"
    assert binding.returned_preflight_model_identifier == (
        "gpt-5.4-mini-2026-03-17"
    )
    assert binding.model_version_or_snapshot_provenance == "unavailable"
    assert binding.provider_sdk_version == "2.46.0"
    assert binding.provider_configuration_id == (
        "openai-responses-text-strict-json-v0.2"
    )
    assert binding.model_configuration_id == (
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    )
    assert binding.output_contract_id == "candidate-extraction-result-0.1"
    assert binding.response_schema_name == (
        "candidate_extraction_result_0_1_aliases_empty_v0_3"
    )
    assert binding.strict_schema_sha256 == (
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    )


def test_plan_freezes_exact_execution_controls_and_cost_cap() -> None:
    controls = _plan().execution_controls

    assert controls.maximum_provider_calls == 8
    assert controls.maximum_total_attempts == 8
    assert controls.maximum_retries_per_invocation == 0
    assert controls.maximum_transaction_retries == 0
    assert controls.provider_side_retries == 0
    assert controls.response_timeout_seconds == 120
    assert controls.maximum_output_tokens_per_invocation == 4096
    assert controls.maximum_output_token_budget == 32768
    assert controls.aggregate_conservative_cost_ceiling_usd == Decimal(
        "1.001169"
    )
    assert controls.planned_authorization_cap_usd == Decimal("1.25")
    assert controls.aggregate_conservative_cost_ceiling_usd < (
        controls.planned_authorization_cap_usd
    )
    assert controls.same_day_pricing_review_required is True
    assert controls.same_day_data_controls_review_required is True


def test_plan_freezes_cache_artifact_failure_and_authorization_boundaries() -> None:
    plan = _plan()

    assert plan.execution_plan_schema_version == EXECUTION_PLAN_SCHEMA_VERSION
    assert plan.execution_id == EXECUTION_ID
    assert plan.authorization_scope == AUTHORIZATION_SCOPE
    assert plan.cache_policy.relative_cache_root == (
        ".cache/llm_extraction/llm-extraction-baseline-v0.3/openai/"
    )
    assert plan.cache_policy.read_before_attempt_marker is True
    assert plan.cache_policy.append_only is True
    assert plan.cache_policy.cache_replacement_allowed is False
    assert plan.cache_policy.cache_bypass_allowed is False
    assert plan.cache_policy.successful_responses_only is True
    assert plan.artifact_policy.attempt_marker_root == ATTEMPT_MARKER_ROOT
    assert plan.artifact_policy.failure_record_root == FAILURE_RECORD_ROOT
    assert plan.artifact_policy.execution_record_path == EXECUTION_RECORD_PATH
    assert plan.artifact_policy.attempt_marker_installed_before_client_construction
    assert plan.artifact_policy.attempt_marker_installed_before_credential_access
    assert (
        plan.artifact_policy
        .provider_response_cache_installed_before_local_validation
    )
    assert plan.artifact_policy.failure_record_sanitized_and_self_hashed
    assert (
        plan.artifact_policy
        .execution_record_installed_only_after_all_invocations_valid
    )
    assert plan.artifact_policy.execution_record_installed_exclusively_and_last
    assert plan.partial_failure_policy.stop_after_first_provider_or_local_failure
    assert plan.partial_failure_policy.completed_cache_records_are_preserved
    assert (
        plan.partial_failure_policy
        .attempt_without_cache_is_not_retryable_in_v0_3
    )
    assert plan.partial_failure_policy.cache_after_local_parse_failure_is_reusable
    assert plan.partial_failure_policy.automatic_retry_or_overwrite_is_forbidden
    assert plan.authorization_binding.explicit_project_owner_authorization_required
    assert (
        plan.authorization_binding
        .authorization_must_bind_execution_plan_sha256
    )
    assert plan.authorization_binding.authorization_must_bind_manifest_sha256
    assert (
        plan.authorization_binding.authorization_must_bind_maximum_provider_calls
        == 8
    )
    assert (
        plan.authorization_binding.authorization_must_bind_maximum_total_attempts
        == 8
    )
    assert plan.authorization_binding.authorization_must_bind_cost_cap_usd == (
        Decimal("1.25")
    )
    assert plan.authorization_binding.authorization_not_created_by_readiness


def test_plan_has_exact_order_role_distribution_and_payload_inventory() -> None:
    invocations = _plan().invocations
    primary = [item for item in invocations if item.invocation_role == "primary"]

    assert len(invocations) == 8
    assert [item.invocation_order for item in invocations] == list(range(1, 9))
    assert [item.request_id for item in invocations] == EXPECTED_REQUEST_IDS
    assert [item.provider_payload_bytes for item in invocations] == (
        EXPECTED_PAYLOAD_BYTES
    )
    assert [item.source_id for item in primary] == [
        "S001",
        "S002",
        "S003",
        "S004",
        "S004",
        "S004",
        "S006",
    ]
    assert [item.invocation_role for item in invocations] == [
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
        "primary",
        "repeat",
    ]
    assert invocations[-1].repeated_primary_request_id == (
        "llm-v0.3-S004-primary-001"
    )
    assert sum(
        item.conservative_call_ceiling_usd for item in invocations
    ) == Decimal("1.001169")


def test_plan_copies_every_required_invocation_identity_from_manifest() -> None:
    manifest = _manifest()
    plan = _plan()

    for planned, frozen in zip(plan.invocations, manifest.invocations, strict=True):
        assert planned.source_id == frozen.source_id
        assert planned.invocation_role == frozen.invocation_role.value
        assert planned.request_id == frozen.request_id
        assert planned.repeated_primary_request_id == (
            frozen.repeated_primary_request_id
        )
        assert planned.canonical_request_sha256 == frozen.canonical_request_sha256
        assert planned.prompt_sha256 == frozen.prompt_sha256
        assert planned.strict_schema_sha256 == frozen.strict_schema_sha256
        assert planned.provider_payload_sha256 == frozen.provider_payload_sha256
        assert planned.cache_identity_sha256 == frozen.cache_identity_sha256
        assert planned.provider_payload_bytes == frozen.provider_payload_bytes
        assert planned.maximum_output_tokens == frozen.maximum_output_tokens
        assert planned.conservative_call_ceiling_usd == (
            frozen.conservative_call_ceiling_usd
        )


def test_attempt_and_failure_paths_are_derived_from_cache_identities() -> None:
    invocations = _plan().invocations

    assert len({item.cache_identity_sha256 for item in invocations}) == 8
    for item in invocations:
        assert item.attempt_marker_relative_path == (
            f"{ATTEMPT_MARKER_ROOT}/"
            f"{item.cache_identity_sha256}.attempt.json"
        )
        assert item.failure_record_relative_path == (
            f"{FAILURE_RECORD_ROOT}/"
            f"{item.cache_identity_sha256}.failure.json"
        )


def test_plan_keeps_held_out_sources_and_semantics_denied() -> None:
    plan = _plan()
    identities = [
        (item.source_id, item.request_id) for item in plan.invocations
    ]

    assert all(source_id not in {"S005", "S007"} for source_id, _ in identities)
    assert all("S005" not in request_id for _, request_id in identities)
    assert all("S007" not in request_id for _, request_id in identities)
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
    assert plan.access_policy.held_out_parsed_document_access_authorized is False
    assert plan.access_policy.held_out_annotation_access_authorized is False
    assert plan.access_policy.gold_labels_as_prompt_input_authorized is False
    assert plan.access_policy.owner_outcomes_as_prompt_input_authorized is False


def test_frozen_plan_is_canonical_self_hashed_and_byte_exact() -> None:
    raw = PLAN_PATH.read_bytes()
    plan = load_development_execution_plan_v0_3(PLAN_PATH)

    assert len(raw) == EXPECTED_EXECUTION_PLAN_ARTIFACT_BYTES == 13077
    assert hashlib.sha256(raw).hexdigest().upper() == (
        EXPECTED_EXECUTION_PLAN_OUTER_SHA256
    )
    assert raw == development_execution_plan_bytes_v0_3(plan)
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert plan.execution_plan_sha256 == EXPECTED_EXECUTION_PLAN_SHA256
    assert plan.execution_plan_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(
            plan.model_dump(mode="json", exclude={"execution_plan_sha256"})
        )
    )


def test_plan_is_hash_only_and_contains_no_raw_document_or_prompt_content() -> None:
    payload = json.loads(PLAN_PATH.read_bytes())
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
            "prompt_text",
            "provider_request_body",
            "provider_response",
            "raw_prompt",
            "raw_response",
            "source_text",
            "text",
        }
    )


def test_regeneration_from_exact_frozen_manifest_is_byte_identical() -> None:
    first = build_plan_from_frozen_manifest_v0_3(MANIFEST_PATH)
    second = build_plan_from_frozen_manifest_v0_3(MANIFEST_PATH)

    assert development_execution_plan_bytes_v0_3(first) == PLAN_PATH.read_bytes()
    assert development_execution_plan_bytes_v0_3(second) == PLAN_PATH.read_bytes()


def test_tampered_plan_and_manifest_fail_closed(tmp_path: Path) -> None:
    plan_payload = _plan().model_dump(mode="json")
    plan_payload["execution_plan_sha256"] = "F" * 64
    with pytest.raises(ValidationError, match="execution_plan_sha256"):
        OpenAIDevelopmentExecutionPlanV03.model_validate(plan_payload)

    plan_payload = _plan().model_dump(mode="json")
    plan_payload["invocations"][0]["attempt_marker_relative_path"] = (
        "reports/unsafe.attempt.json"
    )
    with pytest.raises(ValidationError, match="attempt marker path"):
        OpenAIDevelopmentExecutionPlanV03.model_validate(plan_payload)

    manifest_payload = _manifest().model_dump(mode="json")
    manifest_payload["invocations"][0]["provider_payload_bytes"] += 1
    tampered_manifest = tmp_path / "tampered-manifest.json"
    tampered_manifest.write_bytes(canonical_json_bytes(manifest_payload) + b"\n")
    with pytest.raises(ValueError, match="frozen v0.3 development manifest"):
        build_plan_from_frozen_manifest_v0_3(tampered_manifest)


def test_loader_accepts_lf_and_crlf_and_writer_is_exclusive(tmp_path: Path) -> None:
    canonical = development_execution_plan_bytes_v0_3(_plan())
    lf_path = tmp_path / "plan-lf.json"
    crlf_path = tmp_path / "plan-crlf.json"
    output = tmp_path / "written" / "plan.json"
    output.parent.mkdir()
    lf_path.write_bytes(canonical)
    crlf_path.write_bytes(canonical.replace(b"\n", b"\r\n"))

    assert load_development_execution_plan_v0_3(lf_path) == _plan()
    assert load_development_execution_plan_v0_3(crlf_path) == _plan()
    write_development_execution_plan_v0_3(output, _plan())
    assert output.read_bytes() == canonical
    with pytest.raises(FileExistsError):
        write_development_execution_plan_v0_3(output, _plan())
    assert output.read_bytes() == canonical


def test_v0_2_manifest_and_execution_plan_families_remain_unchanged() -> None:
    v0_2_manifest = OpenAIDevelopmentManifestV02.model_validate_json(
        V0_2_MANIFEST_PATH.read_bytes()
    )
    v0_2_plan = load_development_execution_plan_v0_2(V0_2_PLAN_PATH)
    v0_2_canonical = canonical_lf_json_bytes(V0_2_PLAN_PATH.read_bytes())

    assert V0_2_EXECUTION_PLAN_SHA256 == (
        "25588680A1362AC0192A378CD54288AA2DF5584F4C6108E3467BA06DA68AACE9"
    )
    assert v0_2_plan.execution_plan_sha256 == V0_2_EXECUTION_PLAN_SHA256
    assert len(v0_2_canonical) == 13064
    assert uppercase_sha256_bytes(v0_2_canonical) == (
        "DA00997E1045DF20FC9755C17C5DF5FFA1AF9195F3B6B79BAD849E03F4B1AD2D"
    )
    with pytest.raises(ValueError, match="development manifest is invalid"):
        build_openai_development_execution_plan_v0_3(v0_2_manifest)  # type: ignore[arg-type]
