"""Offline regressions for provenance-safe semantic provider output v0.4."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction.contracts import (
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequestV04,
    LLMProviderResponse,
    ProviderTerminalStatus,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4,
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_MODEL_CONFIGURATION_ID_V0_4,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
    OPENAI_RESPONSE_SCHEMA_NAME_V0_4,
    build_openai_candidate_schema_v0_3,
    build_openai_candidate_schema_v0_4,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope_v0_3,
    build_request_envelope_v0_4,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.validation import (
    _hydrate_semantic_result_v0_4,
    validate_provider_output,
    validate_provider_output_v0_4,
)


V0_3_STRICT_SCHEMA_SHA256 = (
    "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
)


def _block(*, version: str, suffix: str, sequence: int, location: str) -> ApprovedEvidenceBlock:
    return ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id=f"llm-evidence-v{version}-S001-DOC-S001-{suffix}",
        block_id=f"DOC-S001-{suffix}",
        sequence=sequence,
        text=(
            f"Visible document page {int(location) - 1} states that the "
            f"fictional {suffix} initiative is active."
        ),
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value=location,
            page_number=int(location),
        ),
    )


def _request_v0_4() -> LLMExtractionRequestV04:
    return build_request_envelope_v0_4(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.4-S001-primary-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_4,
        evidence_blocks=(
            _block(version="0.4", suffix="B0008", sequence=1, location="8"),
            _block(version="0.4", suffix="B0022", sequence=2, location="22"),
        ),
    )


def _semantic_fact(candidate_id: str, evidence_ids: list[str]) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "document_family": "fictional-policy",
        "subject_text": "Fictional initiative",
        "subject_type": "initiative",
        "predicate": "status",
        "raw_value": "active",
        "normalized_value": "active",
        "value_type": "status",
        "qualifiers": {},
        "evidence_ids": evidence_ids,
        "confidence": 0.8,
        "review_status": "required",
        "warnings": [],
    }


def _semantic_payload(*facts: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "batch_id": "fictional-v0.4-batch",
        "entities": [
            {
                "entity_id": "fictional-entity-001",
                "canonical_name": "Fictional initiative",
                "entity_type": "initiative",
                "aliases": [],
            }
        ],
        "candidate_facts": list(facts),
        "warnings": [],
    }


def _response(request: LLMExtractionRequestV04, payload: dict[str, object]) -> LLMProviderResponse:
    raw = canonical_json_bytes(payload).decode("utf-8")
    return LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="fictional-provider",
        model_identifier="fictional-model",
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256(raw),
        latency_ms=1,
        retry_count=0,
    )


def test_v0_4_semantic_output_hydrates_exact_request_provenance() -> None:
    request = _request_v0_4()
    first_id = request.evidence_blocks[0].evidence_id
    second_id = request.evidence_blocks[1].evidence_id
    payload = _semantic_payload(
        _semantic_fact("fictional-candidate-001", [first_id]),
        _semantic_fact("fictional-candidate-002", [second_id]),
    )

    response = _response(request, payload)
    original_raw_response = response.raw_response
    first = validate_provider_output_v0_4(request, response)
    second = validate_provider_output_v0_4(request, _response(request, payload))

    assert first == second
    assert response.raw_response == original_raw_response
    assert first.canonical_output_sha256 == second.canonical_output_sha256
    assert first.candidate_result.source_ids == ["S001"]
    assert first.candidate_result.entities[0].source_ids == ["S001"]
    assert [item.location_value for item in first.candidate_result.evidence_references] == [
        "8",
        "22",
    ]
    assert [item.block_id for item in first.candidate_result.evidence_references] == [
        "DOC-S001-B0008",
        "DOC-S001-B0022",
    ]
    assert all(
        fact.extraction_method.value == "llm"
        for fact in first.candidate_result.candidate_facts
    )


def test_v0_4_hydrated_excerpt_remains_trimmed_after_truncation() -> None:
    text = " \n" + "A" * 239 + " " + "fictional suffix"
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="llm-evidence-v0.4-S001-DOC-S001-B0003",
        block_id="DOC-S001-B0003",
        sequence=1,
        text=text,
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="3",
            page_number=3,
        ),
    )
    request = build_request_envelope_v0_4(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.4-S001-primary-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_4,
        evidence_blocks=(block,),
    )
    payload = _semantic_payload(
        _semantic_fact("fictional-candidate-001", [block.evidence_id])
    )

    result = validate_provider_output_v0_4(request, _response(request, payload))
    excerpt = result.candidate_result.evidence_references[0].text_excerpt

    assert excerpt == text.strip()[:240].rstrip()
    assert excerpt
    assert len(excerpt) <= 240
    assert excerpt == excerpt.strip()


def test_v0_4_unknown_and_blank_evidence_ids_fail_closed() -> None:
    request = _request_v0_4()
    unknown = _semantic_payload(
        _semantic_fact("fictional-candidate-001", ["fictional-unknown-evidence"])
    )
    blank = _semantic_payload(_semantic_fact("fictional-candidate-001", [" "]))

    with pytest.raises(Stage4BError) as unknown_error:
        validate_provider_output_v0_4(request, _response(request, unknown))
    with pytest.raises(Stage4BError) as blank_error:
        validate_provider_output_v0_4(request, _response(request, blank))

    assert unknown_error.value.code is Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE
    assert blank_error.value.code is Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE


def test_v0_4_schema_and_validator_remove_model_control_over_location() -> None:
    request = _request_v0_4()
    evidence_id = request.evidence_blocks[0].evidence_id
    schema = build_openai_candidate_schema_v0_4()
    serialized_schema = canonical_json_bytes(schema)
    payload = _semantic_payload(
        _semantic_fact("fictional-candidate-001", [evidence_id])
    )
    payload["evidence_references"] = [
        {
            "evidence_id": evidence_id,
            "source_id": "S001",
            "block_id": "DOC-S001-B0008",
            "location_type": "page",
            "location_value": "7",
            "text_excerpt": "fictional",
            "evidence_status": "supported",
        }
    ]

    assert b"location_value" not in serialized_schema
    assert b"location_type" not in serialized_schema
    assert b"block_id" not in serialized_schema
    assert b"source_id" not in serialized_schema
    assert b"evidence_references" not in serialized_schema
    with pytest.raises(Stage4BError) as error:
        validate_provider_output_v0_4(request, _response(request, payload))
    assert error.value.code is Stage4BErrorCode.SCHEMA_INVALID


def test_v0_4_hydrates_only_used_evidence_and_deduplicates_shared_selection() -> None:
    request = _request_v0_4()
    evidence_id = request.evidence_blocks[0].evidence_id
    payload = _semantic_payload(
        _semantic_fact("fictional-candidate-001", [evidence_id]),
        _semantic_fact("fictional-candidate-002", [evidence_id]),
    )

    output = validate_provider_output_v0_4(request, _response(request, payload))

    assert [
        reference.evidence_id
        for reference in output.candidate_result.evidence_references
    ] == [evidence_id]
    assert all(
        fact.evidence_ids == [evidence_id]
        for fact in output.candidate_result.candidate_facts
    )


def test_v0_3_page_number_failure_fixture_is_structurally_hydrated_by_v0_4() -> None:
    blocks = (
        _block(version="0.3", suffix="B0008", sequence=1, location="8"),
        _block(version="0.3", suffix="B0022", sequence=2, location="22"),
    )
    request = build_request_envelope_v0_3(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.3-S001-primary-001",
        source_id="S001",
        document_sha256="B" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        evidence_blocks=blocks,
    )
    payload = _semantic_payload(
        _semantic_fact(
            "fictional-candidate-001",
            ["llm-evidence-v0.3-S001-DOC-S001-B0008"],
        ),
        _semantic_fact(
            "fictional-candidate-002",
            ["llm-evidence-v0.3-S001-DOC-S001-B0022"],
        ),
    )

    result = _hydrate_semantic_result_v0_4(request, payload)

    assert [item.location_value for item in result.evidence_references] == ["8", "22"]
    assert all("location_value" not in fact for fact in payload["candidate_facts"])


def test_existing_v0_3_full_provenance_validation_remains_unchanged() -> None:
    block = _block(version="0.3", suffix="B0008", sequence=1, location="8")
    request = build_request_envelope_v0_3(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.3-S001-primary-001",
        source_id="S001",
        document_sha256="C" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        evidence_blocks=(block,),
    )
    legacy_payload = {
        **_semantic_payload(
            _semantic_fact("fictional-candidate-001", [block.evidence_id])
        ),
        "source_ids": ["S001"],
        "evidence_references": [
            {
                "evidence_id": block.evidence_id,
                "source_id": "S001",
                "block_id": block.block_id,
                "location_type": "page",
                "location_value": "7",
                "text_excerpt": "Fictional evidence.",
                "evidence_status": "supported",
            }
        ],
    }
    legacy_payload["entities"][0]["source_ids"] = ["S001"]
    legacy_payload["candidate_facts"][0]["source_id"] = "S001"
    legacy_payload["candidate_facts"][0]["extraction_method"] = "llm"
    raw = canonical_json_bytes(legacy_payload).decode("utf-8")
    response = LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="fictional-provider",
        model_identifier="fictional-model",
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256(raw),
        latency_ms=1,
        retry_count=0,
    )

    with pytest.raises(Stage4BError) as error:
        validate_provider_output(request, response)

    assert error.value.code is Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(build_openai_candidate_schema_v0_3()))
        == V0_3_STRICT_SCHEMA_SHA256
    )


def test_v0_4_provider_payload_uses_only_the_provenance_safe_contract() -> None:
    request = _request_v0_4()
    payload = build_openai_responses_payload(
        request,
        DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4,
    )
    output_format = payload["text"]["format"]

    assert output_format["name"] == OPENAI_RESPONSE_SCHEMA_NAME_V0_4
    assert output_format["strict"] is True
    assert "evidence_references" not in output_format["schema"]["properties"]
    assert payload["max_output_tokens"] == 4096
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["store"] is False
    with pytest.raises(Stage4BError) as v0_4_with_v0_3:
        build_openai_responses_payload(
            request,
            DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
        )
    assert v0_4_with_v0_3.value.code is (
        Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH
    )


def test_v0_4_request_identity_is_additive_and_exact() -> None:
    request = _request_v0_4()
    dumped = request.model_dump(mode="python")

    assert request.experiment_id == "llm-extraction-baseline-v0.4"
    assert request.prompt_version == "0.4"
    assert request.output_contract_id == "semantic-candidate-extraction-result-v0.4"
    assert request.request_id == "llm-v0.4-S001-primary-001"
    assert all("llm-evidence-v0.4-" in block.evidence_id for block in request.evidence_blocks)

    wrong = deepcopy(dumped)
    wrong["request_id"] = "llm-v0.3-S001-primary-001"
    with pytest.raises(ValidationError, match="v0.4 identity template"):
        LLMExtractionRequestV04.model_validate(wrong)
