"""Offline regressions for the additive v0.3 alias-safe provider boundary."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import document_intelligence.llm_extraction as facade
from document_intelligence.extraction.models import CandidateEntity
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction.cache import (
    V0_3_OPENAI_CACHE_ROOT,
    CacheIdentityV02,
    CacheIdentityV03,
    cache_identity_from_request,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID_V0_3,
    PROMPT_VERSION_V0_3,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequestV02,
    LLMExtractionRequestV03,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION,
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_RESPONSE_SCHEMA_NAME_V0_3,
    audit_openai_strict_schema,
    build_openai_candidate_schema,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope_v0_2,
    build_request_envelope_v0_3,
    canonical_json_bytes,
    load_prompt_assets,
    uppercase_sha256_bytes,
)


LEGACY_STRICT_SCHEMA_SHA256 = (
    "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
)
V0_3_STRICT_SCHEMA_SHA256 = (
    "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
)
V0_2_PROMPT_SHA256 = (
    "36C8FEDAB242A03B83D877F9F0BBA1A14D83930B8E1B9E0F1072433E2CF857F2"
)
V0_2_REQUEST_SHA256 = (
    "4323D4D07BB41D7093BE3DA3E0DFE42DB33F37EE1DFECDDEC32A3082F167620B"
)
V0_2_PROVIDER_PAYLOAD_SHA256 = (
    "AFB7C696D2971B5AD6F7D4D163CAC5236B627817C73D341AEA8E19543BBB6298"
)
V0_2_CACHE_IDENTITY_SHA256 = (
    "71AEE524A991423772DFEEDD4A8A1F29E2604E82F666D7A980D056D79195534E"
)
V0_3_PROMPT_SHA256 = (
    "95163E9AE3E561A389E24F019590923BAE41BCA24BB7515F218A63C4ECD8A00F"
)
V0_3_REQUEST_SHA256 = (
    "F0EBD035AC762E89025F1DF1905A27E699501A4ACF0042189CF6469B97DDED5F"
)
V0_3_PROVIDER_PAYLOAD_SHA256 = (
    "79C6364D27FBE903E45E14D82FBDE1C3A27B67FD5CD46E4028019BCFD6FEECAA"
)
V0_3_CACHE_IDENTITY_SHA256 = (
    "CEF9B5099E74716ED113011CFDFEF6BB6725A5BBA129650817ACDF70D4D69103"
)


def _block(version: str) -> ApprovedEvidenceBlock:
    return ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id=(
            f"llm-evidence-v{version}-S001-fictional-block-001"
        ),
        block_id="fictional-block-001",
        sequence=1,
        text="A fictional initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )


def _request_v0_2() -> LLMExtractionRequestV02:
    return build_request_envelope_v0_2(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.2-S001-primary-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=(_block("0.2"),),
    )


def _request_v0_3() -> LLMExtractionRequestV03:
    return build_request_envelope_v0_3(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.3-S001-primary-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        evidence_blocks=(_block("0.3"),),
    )


def _candidate_entity(*, aliases: list[str]) -> CandidateEntity:
    return CandidateEntity(
        entity_id="fictional-entity-001",
        canonical_name="Straße",
        entity_type="initiative",
        aliases=aliases,
        source_ids=["S001"],
    )


def test_package_facade_exposes_additive_v0_3_contracts() -> None:
    assert facade.EXPERIMENT_ID_V0_3 == "llm-extraction-baseline-v0.3"
    assert facade.PROMPT_VERSION_V0_3 == "0.3"
    assert facade.LLMExtractionRequestV03 is LLMExtractionRequestV03
    assert facade.CacheIdentityV03 is CacheIdentityV03
    assert facade.V0_3_OPENAI_CACHE_ROOT == (
        ".cache/llm_extraction/llm-extraction-baseline-v0.3/openai/"
    )
    assert facade.build_request_envelope_v0_3 is build_request_envelope_v0_3


def test_candidate_entity_local_alias_contract_remains_unchanged() -> None:
    assert _candidate_entity(aliases=[]).aliases == []
    assert _candidate_entity(aliases=["Delivery Programme"]).aliases == [
        "Delivery Programme"
    ]

    with pytest.raises(
        ValidationError,
        match="alias cannot equal canonical_name after casefold",
    ):
        _candidate_entity(aliases=["STRASSE"])


def test_legacy_schema_is_byte_stable_and_not_mutated_by_v0_3() -> None:
    legacy_before = build_openai_candidate_schema()
    legacy_aliases = legacy_before["$defs"]["CandidateEntity"]["properties"][
        "aliases"
    ]

    build_openai_candidate_schema_v0_3()
    legacy_after = build_openai_candidate_schema()

    assert legacy_before == legacy_after
    assert "maxItems" not in legacy_aliases
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(legacy_after))
        == LEGACY_STRICT_SCHEMA_SHA256
    )


def test_v0_3_schema_adds_only_the_empty_aliases_boundary() -> None:
    legacy = build_openai_candidate_schema()
    expected = deepcopy(legacy)
    expected["$defs"]["CandidateEntity"]["properties"]["aliases"][
        "maxItems"
    ] = 0

    schema = build_openai_candidate_schema_v0_3()
    entity_schema = schema["$defs"]["CandidateEntity"]
    aliases_schema = entity_schema["properties"]["aliases"]

    audit_openai_strict_schema(schema)
    assert schema == expected
    assert aliases_schema["type"] == "array"
    assert aliases_schema["maxItems"] == 0
    assert "aliases" in entity_schema["required"]
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(schema))
        == V0_3_STRICT_SCHEMA_SHA256
    )


def test_v0_3_request_uses_exact_additive_identities() -> None:
    request = _request_v0_3()

    assert request.experiment_id == EXPERIMENT_ID_V0_3
    assert request.prompt_version == PROMPT_VERSION_V0_3
    assert request.request_id == "llm-v0.3-S001-primary-001"
    assert request.evidence_blocks[0].evidence_id == (
        "llm-evidence-v0.3-S001-fictional-block-001"
    )


def test_request_versions_cannot_consume_each_others_identities() -> None:
    request_v0_2 = _request_v0_2()
    request_v0_3 = _request_v0_3()

    with pytest.raises(ValidationError):
        LLMExtractionRequestV03.model_validate(
            request_v0_2.model_dump(mode="python")
        )
    with pytest.raises(ValidationError):
        LLMExtractionRequestV02.model_validate(
            request_v0_3.model_dump(mode="python")
        )

    wrong_v0_3_identity = request_v0_3.model_dump(mode="python")
    wrong_v0_3_identity["request_id"] = "llm-v0.2-S001-primary-001"
    wrong_v0_3_identity["evidence_blocks"][0]["evidence_id"] = (
        "llm-evidence-v0.2-S001-fictional-block-001"
    )
    with pytest.raises(ValidationError, match="v0.3 identity template"):
        LLMExtractionRequestV03.model_validate(wrong_v0_3_identity)


def test_v0_3_installed_prompt_assets_are_deterministic_and_alias_safe() -> None:
    first = load_prompt_assets("0.3")
    second = load_prompt_assets("0.3")
    text = first.extraction_prompt_bytes.decode("utf-8")
    request = _request_v0_3()

    assert first == second
    assert "every entity MUST emit aliases as []" in text
    assert "Alternative-name extraction is intentionally deferred" in text
    assert "Do not invent placeholder aliases" in text
    assert "does not globally forbid aliases" in text
    assert "post-output repair" not in text
    assert request.prompt_sha256 == V0_3_PROMPT_SHA256
    assert request.canonical_request_sha256 == V0_3_REQUEST_SHA256


def test_v0_3_provider_payload_uses_only_the_alias_safe_configuration() -> None:
    payload = build_openai_responses_payload(
        _request_v0_3(),
        DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    )
    output_format = payload["text"]["format"]
    aliases_schema = output_format["schema"]["$defs"]["CandidateEntity"][
        "properties"
    ]["aliases"]

    assert DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3.provider_configuration_id == (
        "openai-responses-text-strict-json-v0.2"
    )
    assert DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3.model_configuration_id == (
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    )
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["max_output_tokens"] == 4096
    assert payload["reasoning"] == {"effort": "none"}
    assert output_format["name"] == OPENAI_RESPONSE_SCHEMA_NAME_V0_3
    assert output_format["strict"] is True
    assert aliases_schema["maxItems"] == 0
    assert payload["store"] is False
    assert payload["stream"] is False
    assert payload["background"] is False
    assert payload["tools"] == []
    assert payload["tool_choice"] == "none"
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(payload))
        == V0_3_PROVIDER_PAYLOAD_SHA256
    )


def test_provider_configuration_and_request_version_mismatch_fails_closed() -> None:
    with pytest.raises(Stage4BError) as v0_3_with_legacy:
        build_openai_responses_payload(
            _request_v0_3(), DEFAULT_OPENAI_RESPONSES_CONFIGURATION
        )
    with pytest.raises(Stage4BError) as v0_2_with_v0_3:
        build_openai_responses_payload(
            _request_v0_2(), DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3
        )

    assert v0_3_with_legacy.value.code is (
        Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH
    )
    assert v0_2_with_v0_3.value.code is (
        Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH
    )


def test_v0_2_fictional_compatibility_anchors_remain_exact() -> None:
    request = _request_v0_2()
    payload = build_openai_responses_payload(request)
    identity = cache_identity_from_request(request)

    assert request.prompt_sha256 == V0_2_PROMPT_SHA256
    assert request.canonical_request_sha256 == V0_2_REQUEST_SHA256
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(payload))
        == V0_2_PROVIDER_PAYLOAD_SHA256
    )
    assert cache_identity_sha256(identity) == V0_2_CACHE_IDENTITY_SHA256


def test_v0_3_cache_identity_and_root_are_additive() -> None:
    identity_v0_2 = cache_identity_from_request(_request_v0_2())
    identity_v0_3 = cache_identity_from_request(_request_v0_3())

    assert isinstance(identity_v0_2, CacheIdentityV02)
    assert isinstance(identity_v0_3, CacheIdentityV03)
    assert V0_3_OPENAI_CACHE_ROOT == (
        ".cache/llm_extraction/llm-extraction-baseline-v0.3/openai/"
    )
    assert cache_identity_sha256(identity_v0_3) == V0_3_CACHE_IDENTITY_SHA256
    assert cache_identity_sha256(identity_v0_2) != cache_identity_sha256(
        identity_v0_3
    )
    with pytest.raises(ValidationError):
        CacheIdentityV03.model_validate(identity_v0_2.model_dump(mode="python"))
    with pytest.raises(ValidationError):
        CacheIdentityV02.model_validate(identity_v0_3.model_dump(mode="python"))
