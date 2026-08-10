"""Offline regressions for the frozen Stage 4D development manifest v0.3."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.cache import (
    CacheIdentityV03,
    V0_3_OPENAI_CACHE_ROOT,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.contracts import InvocationRole
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
import document_intelligence.llm_extraction.openai_development_manifest as manifest_module
from document_intelligence.llm_extraction.openai_development_manifest import (
    APPROVED_SOURCE_ORDER,
    OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3,
    PARTITION_POLICY_ID_V0_3,
    REPEAT_SELECTION_POLICY_ID_V0_3,
    OpenAIDevelopmentManifestV01,
    OpenAIDevelopmentManifestV02,
    OpenAIDevelopmentManifestV03,
    OpenAIDevelopmentPartitionPolicyV03,
    approved_parsed_document_relative_path,
    build_reviewed_observation_binding,
    canonical_lf_json_bytes,
    development_manifest_bytes,
    development_manifest_bytes_v0_2,
    development_manifest_bytes_v0_3,
    load_approved_parsed_document,
    load_development_manifest_v0_2,
    load_development_manifest_v0_3,
    prepare_openai_development_manifest_v0_3,
    validate_successful_preflight_evidence_v0_4,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    OpenAIPreflightRecordV04,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_RESPONSE_SCHEMA_NAME_V0_3,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest"
)
V0_1_MANIFEST_PATH = MANIFEST_ROOT / (
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
)
V0_2_MANIFEST_PATH = MANIFEST_ROOT / (
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
)
V0_3_MANIFEST_PATH = MANIFEST_ROOT / (
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.3.json"
)
V0_4_ATTEMPT_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_preflight/"
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4.attempt.json"
)
V0_4_RECORD_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_preflight/"
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4.record.json"
)
EXACT_DEVELOPMENT_PARSED_DOCUMENT_PATHS = tuple(
    REPOSITORY_ROOT
    / "artifacts/stage_3b/v0_2_development_input/parsed"
    / f"{source_id}.json"
    for source_id in ("S001", "S002", "S003", "S004", "S006")
)
EXACT_DEVELOPMENT_PARSED_DOCUMENTS_AVAILABLE = all(
    path.is_file() for path in EXACT_DEVELOPMENT_PARSED_DOCUMENT_PATHS
)

EXPECTED_V0_1_OUTER_SHA256 = (
    "15DF5E959040B399EDF8CA5455B5060EF71B6672C97D9901E6DB084FE9ACC069"
)
EXPECTED_V0_2_CANONICAL_LF_SHA256 = (
    "04FF2499BF346D8CB73B2DC03196E7FEE74B5DFF601F79CAC86F4C7B84D3BA3B"
)
EXPECTED_V0_3_OUTER_SHA256 = (
    "EE634214A296D4CB18687F48FD241E4A64B8848C2AD80FC697F797FE527AEB6E"
)
EXPECTED_V0_3_SELF_HASH = (
    "D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327"
)
EXPECTED_V0_4_PLAN_SHA256 = (
    "F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E"
)
EXPECTED_PAYLOAD_BYTES = {
    "llm-v0.3-S001-primary-001": 106660,
    "llm-v0.3-S002-primary-001": 84200,
    "llm-v0.3-S003-primary-001": 74123,
    "llm-v0.3-S004-primary-001": 197889,
    "llm-v0.3-S004-primary-002": 196624,
    "llm-v0.3-S004-primary-003": 99320,
    "llm-v0.3-S006-primary-001": 181579,
    "llm-v0.3-S004-repeat-001": 197889,
}


def _outer_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_manifest() -> OpenAIDevelopmentManifestV03:
    return load_development_manifest_v0_3(V0_3_MANIFEST_PATH)


def _regenerate_manifest() -> OpenAIDevelopmentManifestV03:
    historical = load_development_manifest_v0_2(V0_2_MANIFEST_PATH)
    documents = {
        route.source_id: load_approved_parsed_document(
            repository_root=REPOSITORY_ROOT,
            requested_source_id=route.source_id,
            route=route,
        )
        for route in historical.source_routes
    }
    record = OpenAIPreflightRecordV04.model_validate_json(
        V0_4_RECORD_PATH.read_bytes()
    )
    pricing_review = build_reviewed_observation_binding(
        observation_kind="pricing",
        evidence_id="OPENAI-PRICING-OBSERVATION-V0.4-SUCCESS-RECORD",
        reviewed_by=record.authorization.authorized_by,
        reviewed_at_utc=record.authorization.authorized_at_utc,
        observation=record.pricing_observation,
    )
    data_controls_review = build_reviewed_observation_binding(
        observation_kind="data_controls",
        evidence_id="OPENAI-DATA-CONTROLS-OBSERVATION-V0.4-SUCCESS-RECORD",
        reviewed_by=record.authorization.authorized_by,
        reviewed_at_utc=record.authorization.authorized_at_utc,
        observation=record.data_controls_observation,
    )
    preparation = prepare_openai_development_manifest_v0_3(
        source_routes=historical.source_routes,
        parsed_documents=documents,
        partition_policy=OpenAIDevelopmentPartitionPolicyV03(),
        pricing_observation=record.pricing_observation,
        pricing_review=pricing_review,
        data_controls_observation=record.data_controls_observation,
        data_controls_review=data_controls_review,
        context_limit_observation=historical.context_limit_observation,
    )
    assert preparation.readiness_status == "eligible_for_independent_review"
    assert preparation.manifest is not None
    return preparation.manifest


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


def test_historical_v0_1_v0_2_manifest_bytes_and_models_are_unchanged() -> None:
    v0_1_bytes = V0_1_MANIFEST_PATH.read_bytes()
    v0_2_bytes = V0_2_MANIFEST_PATH.read_bytes()
    v0_1 = OpenAIDevelopmentManifestV01.model_validate_json(v0_1_bytes)
    v0_2 = OpenAIDevelopmentManifestV02.model_validate_json(v0_2_bytes)
    v0_2_canonical_lf_bytes = canonical_lf_json_bytes(v0_2_bytes)

    assert hashlib.sha256(v0_1_bytes).hexdigest().upper() == (
        EXPECTED_V0_1_OUTER_SHA256
    )
    assert hashlib.sha256(v0_2_canonical_lf_bytes).hexdigest().upper() == (
        EXPECTED_V0_2_CANONICAL_LF_SHA256
    )
    assert development_manifest_bytes(v0_1) == v0_1_bytes
    assert development_manifest_bytes_v0_2(v0_2) == v0_2_canonical_lf_bytes


def test_actual_v0_3_manifest_exact_bytes_hashes_and_canonical_round_trip() -> None:
    raw_bytes = V0_3_MANIFEST_PATH.read_bytes()
    manifest = _load_manifest()

    assert V0_3_MANIFEST_PATH.is_file()
    assert not V0_3_MANIFEST_PATH.is_symlink()
    assert len(raw_bytes) == 90686
    assert raw_bytes.endswith(b"\n")
    assert not raw_bytes.endswith(b"\n\n")
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw_bytes
    assert _outer_sha256(V0_3_MANIFEST_PATH) == EXPECTED_V0_3_OUTER_SHA256
    assert manifest.manifest_sha256 == EXPECTED_V0_3_SELF_HASH
    assert development_manifest_bytes_v0_3(manifest) == raw_bytes


@pytest.mark.skipif(
    not EXACT_DEVELOPMENT_PARSED_DOCUMENTS_AVAILABLE,
    reason=(
        "exact ignored five-source development ParsedDocument artifacts "
        "are unavailable"
    ),
)
def test_actual_v0_3_regeneration_is_byte_identical() -> None:
    regenerated = _regenerate_manifest()
    assert development_manifest_bytes_v0_3(regenerated) == (
        V0_3_MANIFEST_PATH.read_bytes()
    )


def test_v0_3_exact_provider_prompt_schema_and_cache_identities() -> None:
    manifest = _load_manifest()

    assert manifest.experiment_id == "llm-extraction-baseline-v0.3"
    assert manifest.prompt_version == "0.3"
    assert manifest.provider_identifier == "openai"
    assert manifest.requested_model_alias == "gpt-5.4-mini"
    assert manifest.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID_V0_3
    assert manifest.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID_V0_3
    assert manifest.response_schema_name == OPENAI_RESPONSE_SCHEMA_NAME_V0_3
    assert manifest.strict_schema_sha256 == (
        OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3
    )
    assert manifest.partition_policy.policy_id == PARTITION_POLICY_ID_V0_3
    assert manifest.repeat_selection_policy.policy_id == (
        REPEAT_SELECTION_POLICY_ID_V0_3
    )
    assert manifest.cache_policy.relative_cache_root == V0_3_OPENAI_CACHE_ROOT
    for item in manifest.invocations:
        identity = CacheIdentityV03(
            experiment_id=manifest.experiment_id,
            invocation_role=item.invocation_role,
            request_id=item.request_id,
            canonical_request_sha256=item.canonical_request_sha256,
            provider_configuration_id=manifest.provider_configuration_id,
            model_configuration_id=manifest.model_configuration_id,
            prompt_sha256=item.prompt_sha256,
            document_sha256=item.document_sha256,
        )
        assert cache_identity_sha256(identity) == item.cache_identity_sha256


def test_v0_3_binds_only_successful_alias_safe_v0_4_preflight() -> None:
    manifest = _load_manifest()
    binding = manifest.preflight_evidence

    assert binding.preflight_id == "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
    assert binding.preflight_id != "openai-gpt-5.4-mini-synthetic-preflight-v0.3"
    assert binding.execution_plan_sha256 == EXPECTED_V0_4_PLAN_SHA256
    assert binding.attempt_canonical_self_sha256 == (
        "3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A"
    )
    assert binding.success_record_canonical_self_sha256 == (
        "36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF"
    )
    assert binding.attempt_canonical_lf_content_sha256 == (
        "4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B"
    )
    assert binding.success_record_canonical_lf_content_sha256 == (
        "1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6"
    )
    validate_successful_preflight_evidence_v0_4(
        attempt_content=V0_4_ATTEMPT_PATH.read_bytes(),
        success_record_content=V0_4_RECORD_PATH.read_bytes(),
        binding=binding,
    )
    assert manifest.returned_preflight_model_identifier == (
        "gpt-5.4-mini-2026-03-17"
    )
    assert manifest.model_version_or_snapshot_provenance == "unavailable"
    assert manifest.provider_sdk_version == "2.46.0"


def test_v0_3_inventory_partitioning_and_payload_lengths_are_exact() -> None:
    manifest = _load_manifest()
    primary = [
        item
        for item in manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]

    assert tuple(route.source_id for route in manifest.source_routes) == (
        "S001",
        "S002",
        "S003",
        "S004",
        "S006",
    )
    assert len(primary) == 7
    assert Counter(item.source_id for item in primary) == {
        "S001": 1,
        "S002": 1,
        "S003": 1,
        "S004": 3,
        "S006": 1,
    }
    assert len(manifest.invocations) == 8
    assert {item.request_id: item.provider_payload_bytes for item in manifest.invocations} == (
        EXPECTED_PAYLOAD_BYTES
    )
    assert all(
        re.fullmatch(
            r"llm-v0\.3-S00[12346]-(?:primary|repeat)-\d{3}",
            item.request_id,
        )
        for item in manifest.invocations
    )
    assert all(
        item.provider_payload_bytes <= 200000 for item in manifest.invocations
    )


@pytest.mark.skipif(
    not EXACT_DEVELOPMENT_PARSED_DOCUMENTS_AVAILABLE,
    reason=(
        "exact ignored five-source development ParsedDocument artifacts "
        "are unavailable"
    ),
)
def test_v0_3_primary_blocks_are_whole_ordered_and_covered_once() -> None:
    manifest = _load_manifest()
    historical = load_development_manifest_v0_2(V0_2_MANIFEST_PATH)
    primary = [
        item
        for item in manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    for route in historical.source_routes:
        document = load_approved_parsed_document(
            repository_root=REPOSITORY_ROOT,
            requested_source_id=route.source_id,
            route=route,
        )
        observed = [
            identity.block_id
            for item in primary
            if item.source_id == route.source_id
            for identity in item.ordered_evidence_blocks
        ]
        expected = [block.block_id for block in document.blocks if block.text.strip()]
        assert observed == expected
        assert len(observed) == len(set(observed))
        assert all(
            identity.evidence_id
            == f"llm-evidence-v0.3-{route.source_id}-{identity.block_id}"
            for item in primary
            if item.source_id == route.source_id
            for identity in item.ordered_evidence_blocks
        )


def test_v0_3_repeat_is_pre_observation_largest_primary_and_distinct() -> None:
    manifest = _load_manifest()
    primary = [
        item
        for item in manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    repeat = manifest.invocations[-1]
    selected = min(
        primary,
        key=lambda item: (-item.provider_payload_bytes, item.request_id),
    )

    assert repeat.invocation_role is InvocationRole.REPEAT
    assert repeat.request_id == "llm-v0.3-S004-repeat-001"
    assert repeat.repeated_primary_request_id == selected.request_id
    assert selected.request_id == "llm-v0.3-S004-primary-001"
    assert repeat.ordered_evidence_blocks == selected.ordered_evidence_blocks
    assert repeat.provider_payload_bytes == selected.provider_payload_bytes
    assert repeat.provider_payload_sha256 == selected.provider_payload_sha256
    assert repeat.prompt_sha256 == selected.prompt_sha256
    assert repeat.canonical_request_sha256 != selected.canonical_request_sha256
    assert repeat.cache_identity_sha256 != selected.cache_identity_sha256


def test_v0_3_context_cost_and_authorization_boundaries_are_exact() -> None:
    manifest = _load_manifest()
    budget = manifest.execution_budget
    largest = max(item.provider_payload_bytes for item in manifest.invocations)

    assert manifest.context_limit_observation.exact_context_window_tokens == 400000
    assert largest == 197889
    assert largest + 4096 == 201985
    assert largest + 4096 <= 400000
    assert all(
        item.provider_payload_bytes + 4096 <= 400000
        for item in manifest.invocations
    )
    assert budget.primary_request_count == 7
    assert budget.repeat_request_count == 1
    assert budget.maximum_provider_calls == 8
    assert budget.maximum_total_attempts == 8
    assert budget.maximum_retries_per_invocation == 0
    assert budget.provider_side_retries == 0
    assert budget.planning_input_token_budget == 284573
    assert budget.conservative_input_token_budget == 1138284
    assert budget.maximum_output_token_budget == 32768
    assert format(budget.aggregate_planning_cost_usd, "f") == "0.36088575"
    assert format(budget.aggregate_conservative_cost_ceiling_usd, "f") == (
        "1.001169"
    )
    assert format(budget.planned_authorization_cap_usd, "f") == "1.25"
    assert budget.aggregate_conservative_cost_ceiling_usd < (
        budget.planned_authorization_cap_usd
    )
    assert manifest.execution_authorization_required is True
    assert manifest.execution_authorization_status == "not_provided"
    assert manifest.manifest_review_status == "pending_independent_review"


@pytest.mark.parametrize("source_id", ("S005", "S007", "S999"))
def test_v0_3_prohibited_source_fails_before_path_or_filesystem_access(
    source_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path_calls = 0
    filesystem_calls = 0

    def forbidden_path(*args: object, **kwargs: object) -> str:
        nonlocal path_calls
        path_calls += 1
        raise AssertionError("path validation must not occur")

    def forbidden_filesystem(*args: object, **kwargs: object) -> Path:
        nonlocal filesystem_calls
        filesystem_calls += 1
        raise AssertionError("filesystem access must not occur")

    monkeypatch.setattr(
        manifest_module,
        "_validate_repository_relative_path",
        forbidden_path,
    )
    monkeypatch.setattr(manifest_module, "_safe_existing_file", forbidden_filesystem)
    with pytest.raises(Stage4BError) as captured:
        approved_parsed_document_relative_path(
            source_id,
            "fictional/parsed/source.json",
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    with pytest.raises(Stage4BError) as captured:
        load_approved_parsed_document(
            repository_root=REPOSITORY_ROOT,
            requested_source_id=source_id,
            route=object(),  # type: ignore[arg-type]
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert path_calls == 0
    assert filesystem_calls == 0


def test_v0_3_manifest_rejects_recomputed_self_hash_drift() -> None:
    manifest = _load_manifest()
    payload = manifest.model_dump(mode="json")
    payload["manifest_sha256"] = "F" * 64
    with pytest.raises(ValidationError, match="manifest_sha256"):
        OpenAIDevelopmentManifestV03.model_validate(payload)


def test_v0_3_manifest_contains_only_hash_inventory_and_safe_provenance() -> None:
    raw_bytes = V0_3_MANIFEST_PATH.read_bytes()
    payload = json.loads(raw_bytes)
    keys = _all_mapping_keys(payload)
    lowered = raw_bytes.lower()

    assert str(REPOSITORY_ROOT).encode("utf-8") not in raw_bytes
    assert not {"S005", "S007"}.intersection(
        route["source_id"] for route in payload["source_routes"]
    )
    assert not {"S005", "S007"}.intersection(
        item["source_id"] for item in payload["invocations"]
    )
    assert keys.isdisjoint(
        {
            "api_key",
            "authorization_id",
            "candidate_facts",
            "candidate_output",
            "credential",
            "evaluation",
            "gold",
            "provider_request_body",
            "provider_response",
            "raw_cache",
            "raw_prompt",
            "source_text",
            "text",
        }
    )
    for forbidden_literal in (
        b"sk-",
        b"bearer ",
        b"openai_api_key",
        b"ordered evidence blocks (canonical json)",
    ):
        assert forbidden_literal not in lowered


def test_v0_3_actual_file_inventory_is_exact() -> None:
    names = {
        path.name
        for path in MANIFEST_ROOT.glob(
            "openai-gpt-5.4-mini-five-source-development-manifest-v0.*.json"
        )
    }
    assert names == {
        V0_1_MANIFEST_PATH.name,
        V0_2_MANIFEST_PATH.name,
        V0_3_MANIFEST_PATH.name,
    }
    assert os.path.isfile(V0_3_MANIFEST_PATH)
