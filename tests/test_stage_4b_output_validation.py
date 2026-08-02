"""Fail-closed structured output tests using fictional Stage 4B data."""

from __future__ import annotations

import copy
import json

import pytest

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMProviderResponse,
    ProviderTerminalStatus,
    Stage4BError,
    Stage4BErrorCode,
    build_request_envelope,
    validate_provider_output,
)
from document_intelligence.llm_extraction.contracts import uppercase_sha256


def _request():
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text="The fictional delivery initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="fictional-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        evidence_blocks=(block,),
    )


def _payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "batch_id": "fictional-batch-001",
        "source_ids": ["S001"],
        "entities": [],
        "evidence_references": [
            {
                "evidence_id": "fictional-evidence-001",
                "source_id": "S001",
                "block_id": "fictional-block-001",
                "location_type": "page",
                "location_value": "1",
                "text_excerpt": "The fictional delivery initiative is active.",
                "evidence_status": "supported",
            }
        ],
        "candidate_facts": [
            {
                "candidate_id": "fictional-candidate-001",
                "source_id": "S001",
                "document_family": "fictional_delivery_note",
                "subject_text": "fictional delivery initiative",
                "subject_type": "initiative",
                "predicate": "status",
                "raw_value": "active",
                "normalized_value": "active",
                "value_type": "status",
                "qualifiers": {},
                "evidence_ids": ["fictional-evidence-001"],
                "confidence": 0.8,
                "review_status": "not_required",
                "extraction_method": "llm",
                "warnings": [],
            }
        ],
        "warnings": [],
    }


def _response(
    raw_response: str,
    *,
    status: ProviderTerminalStatus = ProviderTerminalStatus.SUCCESS,
    request_id: str = "fictional-request-001",
) -> LLMProviderResponse:
    return LLMProviderResponse(
        request_id=request_id,
        provider_identifier="stage4b-deterministic-mock-provider",
        model_identifier="stage4b-deterministic-mock-model",
        terminal_status=status,
        raw_response=raw_response,
        raw_response_sha256=uppercase_sha256(raw_response),
        latency_ms=0,
        retry_count=0,
        failure_codes=() if status is ProviderTerminalStatus.SUCCESS else ("failure",),
    )


def _json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _assert_error(
    expected: Stage4BErrorCode,
    raw_response: str,
    *,
    request=None,
    response_status: ProviderTerminalStatus = ProviderTerminalStatus.SUCCESS,
) -> None:
    with pytest.raises(Stage4BError) as captured:
        validate_provider_output(
            request or _request(),
            _response(raw_response, status=response_status),
        )
    assert captured.value.code is expected


def test_valid_structured_candidate_is_accepted_and_preserved() -> None:
    validated = validate_provider_output(_request(), _response(_json(_payload())))

    assert validated.source_id == "S001"
    assert validated.candidate_result.source_ids == ["S001"]
    assert validated.candidate_result.candidate_facts[0].predicate == "status"
    assert validated.candidate_result.candidate_facts[0].evidence_ids == [
        "fictional-evidence-001"
    ]
    assert validated.candidate_result.evidence_references[0].block_id == (
        "fictional-block-001"
    )
    assert len(validated.canonical_output_sha256) == 64


def test_review_required_candidate_and_explicit_abstention_are_preserved() -> None:
    review_payload = _payload()
    review_payload["candidate_facts"][0]["review_status"] = "required"  # type: ignore[index]
    review_payload["candidate_facts"][0]["warnings"] = [  # type: ignore[index]
        "fictional_uncertainty"
    ]
    reviewed = validate_provider_output(
        _request(), _response(_json(review_payload))
    )
    assert reviewed.candidate_result.candidate_facts[0].review_status.value == "required"

    abstention_payload = _payload()
    abstention_payload["evidence_references"] = []
    abstention_payload["candidate_facts"] = []
    abstention_payload["warnings"] = ["abstained_no_supported_candidate"]
    abstained = validate_provider_output(
        _request(), _response(_json(abstention_payload))
    )
    assert abstained.candidate_result.candidate_facts == []
    assert abstained.candidate_result.warnings == [
        "abstained_no_supported_candidate"
    ]


@pytest.mark.parametrize("raw_response", ("{not-json", '{"value":NaN}', '{"x":1,"x":2}'))
def test_malformed_or_non_strict_json_is_rejected(raw_response: str) -> None:
    _assert_error(Stage4BErrorCode.INVALID_JSON, raw_response)


@pytest.mark.parametrize("payload", ([], "text", 7, None))
def test_wrong_top_level_json_type_is_rejected(payload: object) -> None:
    _assert_error(Stage4BErrorCode.INVALID_OUTPUT_SHAPE, _json(payload))


def test_schema_invalid_candidate_is_rejected() -> None:
    payload = _payload()
    del payload["candidate_facts"][0]["confidence"]  # type: ignore[index]
    _assert_error(Stage4BErrorCode.SCHEMA_INVALID, _json(payload))


def test_unknown_predicate_is_rejected_without_coercion() -> None:
    payload = _payload()
    payload["candidate_facts"][0]["predicate"] = "fictional_unknown"  # type: ignore[index]
    _assert_error(Stage4BErrorCode.INVALID_PREDICATE, _json(payload))


def test_invalid_qualifier_is_rejected_without_repair() -> None:
    payload = _payload()
    payload["candidate_facts"][0]["qualifiers"] = {  # type: ignore[index]
        "fictional_undeclared": "value"
    }
    _assert_error(Stage4BErrorCode.INVALID_QUALIFIER, _json(payload))


def test_response_source_mismatch_is_rejected() -> None:
    payload = _payload()
    payload["source_ids"] = ["S002"]
    _assert_error(Stage4BErrorCode.SOURCE_MISMATCH, _json(payload))


def test_unknown_evidence_reference_is_rejected() -> None:
    payload = _payload()
    payload["evidence_references"][0]["evidence_id"] = "fictional-evidence-999"  # type: ignore[index]
    payload["evidence_references"][0]["block_id"] = "fictional-block-999"  # type: ignore[index]
    payload["candidate_facts"][0]["evidence_ids"] = [  # type: ignore[index]
        "fictional-evidence-999"
    ]
    _assert_error(Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE, _json(payload))


def test_cross_source_evidence_reference_is_rejected() -> None:
    payload = _payload()
    payload["evidence_references"][0]["source_id"] = "S002"  # type: ignore[index]
    _assert_error(Stage4BErrorCode.CROSS_SOURCE_EVIDENCE_REFERENCE, _json(payload))


def test_empty_evidence_reference_is_rejected() -> None:
    payload = _payload()
    payload["candidate_facts"][0]["evidence_ids"] = []  # type: ignore[index]
    _assert_error(Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE, _json(payload))


def test_prompt_hash_mismatch_is_rejected_before_output_parsing() -> None:
    request = _request().model_copy(update={"prompt_sha256": "F" * 64})
    _assert_error(
        Stage4BErrorCode.PROMPT_HASH_MISMATCH,
        _json(_payload()),
        request=request,
    )


@pytest.mark.parametrize(
    "status", (ProviderTerminalStatus.FAILURE, ProviderTerminalStatus.TIMEOUT)
)
def test_provider_terminal_failure_is_rejected(
    status: ProviderTerminalStatus,
) -> None:
    _assert_error(
        Stage4BErrorCode.PROVIDER_NOT_SUCCESSFUL,
        "",
        response_status=status,
    )


def test_response_request_mismatch_is_rejected() -> None:
    with pytest.raises(Stage4BError) as captured:
        validate_provider_output(
            _request(),
            _response(_json(_payload()), request_id="fictional-request-other"),
        )
    assert captured.value.code is Stage4BErrorCode.RESPONSE_REQUEST_MISMATCH


def test_invalid_evidence_location_and_non_llm_method_are_rejected() -> None:
    location_payload = _payload()
    location_payload["evidence_references"][0]["location_value"] = "2"  # type: ignore[index]
    _assert_error(
        Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE, _json(location_payload)
    )

    method_payload = copy.deepcopy(_payload())
    method_payload["candidate_facts"][0]["extraction_method"] = "deterministic"  # type: ignore[index]
    _assert_error(Stage4BErrorCode.SCHEMA_INVALID, _json(method_payload))
