"""Offline contract tests for compatibility-first OpenAI preflight v0.4."""

from __future__ import annotations

import inspect
import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequestV03,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import Stage4BErrorCode
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
    ProviderPublicMetadataEntry,
)
from document_intelligence.llm_extraction.openai_preflight_v0_2 import (
    PREFLIGHT_AUTHORIZATION_SCOPE as V0_2_SCOPE,
    PREFLIGHT_ID as V0_2_ID,
    OpenAIPreflightAuthorizationV02,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    EXPECTED_ABSTENTION_WARNING,
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    OpenAIPreflightAuthorizationV04,
    OpenAIPreflightPostResponseFailureV04,
    OpenAIPreflightRecordV04,
    build_synthetic_openai_preflight_request_v0_4,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_INSTALLED_SDK_VERSION,
    build_openai_candidate_schema,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _authorization() -> OpenAIPreflightAuthorizationV04:
    return OpenAIPreflightAuthorizationV04(
        authorization_id="fictional-v0-3-authorization",
        authorized_by="Fictional V0.4 Owner",
        authorized_at_utc=NOW - timedelta(minutes=5),
        scope=PREFLIGHT_AUTHORIZATION_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )


def _pricing() -> OpenAIPricingObservation:
    return OpenAIPricingObservation(
        observed_at_utc=NOW,
        source_title="Fictional v0.4 pricing",
        source_url="https://example.invalid/pricing-v0-3",
        input_usd_per_million_tokens=Decimal("1.25"),
        output_usd_per_million_tokens=Decimal("5.50"),
        currency="USD",
    )


def _controls() -> OpenAIDataControlsObservation:
    return OpenAIDataControlsObservation(
        observed_at_utc=NOW,
        source_title="Fictional v0.4 controls",
        source_url="https://example.invalid/controls-v0-3",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary="Fictional limitations apply.",
    )


def _base_payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "batch_id": "fictional-v0-3-batch",
        "source_ids": ["S001"],
        "entities": [],
        "evidence_references": [],
        "candidate_facts": [],
        "warnings": [EXPECTED_ABSTENTION_WARNING],
    }


def _entity() -> dict[str, object]:
    return {
        "entity_id": "fictional-v0-3-entity",
        "canonical_name": "Fictional delivery initiative",
        "entity_type": "initiative",
        "aliases": [],
        "source_ids": ["S001"],
    }


def _evidence() -> dict[str, object]:
    return {
        "evidence_id": "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4",
        "source_id": "S001",
        "block_id": "synthetic-preflight-block-v0.4",
        "location_type": "document_metadata",
        "location_value": "synthetic-preflight-v0.4",
        "text_excerpt": "This document is a synthetic API preflight fixture.",
        "evidence_status": "supported",
    }


def _fact() -> dict[str, object]:
    return {
        "candidate_id": "fictional-v0-3-candidate",
        "source_id": "S001",
        "document_family": "synthetic_preflight",
        "subject_text": "synthetic API preflight fixture",
        "subject_type": "initiative",
        "predicate": "status",
        "raw_value": "synthetic",
        "normalized_value": "synthetic",
        "value_type": "status",
        "qualifiers": {},
        "evidence_ids": [
            "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4"
        ],
        "confidence": 0.5,
        "review_status": "required",
        "extraction_method": "llm",
        "warnings": ["fictional_semantic_variance"],
    }


def _observation(
    payload: object,
    *,
    raw_response: str | None = None,
) -> OpenAIPreflightProviderObservation:
    request = build_synthetic_openai_preflight_request_v0_4()
    raw = (
        raw_response
        if raw_response is not None
        else json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )
    response = LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="openai",
        model_identifier="gpt-5.4-mini-fictional-v0-3",
        provider_request_id="req_fictional_v0_4",
        provider_response_id="resp_fictional_v0_4",
        provider_sdk_version=OPENAI_INSTALLED_SDK_VERSION,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256(raw),
        token_usage=ProviderTokenUsage(input_tokens=10, output_tokens=5),
        latency_ms=25,
        retry_count=0,
    )
    entries = (
        ProviderPublicMetadataEntry(
            field_path="response.id",
            value=response.provider_response_id,
        ),
        ProviderPublicMetadataEntry(
            field_path="response.model",
            value=response.model_identifier,
        ),
        ProviderPublicMetadataEntry(
            field_path="response._request_id",
            value=response.provider_request_id,
        ),
        ProviderPublicMetadataEntry(
            field_path="sdk.version",
            value=response.provider_sdk_version,
        ),
    )
    return OpenAIPreflightProviderObservation(
        response=response,
        model_version_or_snapshot_provenance="unavailable",
        version_provenance_source_response_id=response.provider_response_id,
        observed_from_same_provider_call=True,
        provider_public_metadata_entries=entries,
    )


class FakeProvider:
    def __init__(self, payload: object, *, raw_response: str | None = None) -> None:
        self.payload = payload
        self.raw_response = raw_response
        self.calls = 0

    def generate_preflight(self, request):
        self.calls += 1
        return _observation(self.payload, raw_response=self.raw_response)


def _run(payload: object) -> tuple[OpenAIPreflightRecordV04, FakeProvider]:
    provider = FakeProvider(payload)
    record = run_openai_synthetic_preflight(
        provider=provider,
        authorization=_authorization(),
        pricing_observation=_pricing(),
        data_controls_observation=_controls(),
        clock=lambda: NOW,
    )
    return record, provider


def _semantic_cases() -> tuple[
    tuple[str, dict[str, object], str, tuple[int, int, int]], ...
]:
    abstention = _base_payload()
    entity = _base_payload()
    entity["entities"] = [_entity()]
    evidence = _base_payload()
    evidence["evidence_references"] = [_evidence()]
    fact = _base_payload()
    fact["evidence_references"] = [_evidence()]
    fact["candidate_facts"] = [_fact()]
    warning = _base_payload()
    warning["warnings"] = ["fictional_alternative_warning"]
    no_warning = _base_payload()
    no_warning["warnings"] = []
    multiple = _base_payload()
    multiple["entities"] = [_entity()]
    multiple["evidence_references"] = [_evidence()]
    multiple["candidate_facts"] = [_fact()]
    multiple["warnings"] = ["fictional_alternative_warning"]
    return (
        ("exact-abstention", abstention, "expected_abstention", (0, 0, 0)),
        ("one-entity", entity, "valid_semantic_variance", (1, 0, 0)),
        ("evidence", evidence, "valid_semantic_variance", (0, 1, 0)),
        ("candidate", fact, "valid_semantic_variance", (0, 1, 1)),
        ("different-warning", warning, "valid_semantic_variance", (0, 0, 0)),
        ("no-warning", no_warning, "valid_semantic_variance", (0, 0, 0)),
        ("multiple", multiple, "valid_semantic_variance", (1, 1, 1)),
    )


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_counts"),
    tuple((item[1], item[2], item[3]) for item in _semantic_cases()),
    ids=tuple(item[0] for item in _semantic_cases()),
)
def test_schema_valid_semantic_variants_are_technical_successes(
    payload: dict[str, object],
    expected_status: str,
    expected_counts: tuple[int, int, int],
) -> None:
    record, provider = _run(payload)
    diagnostic = record.semantic_diagnostic

    assert record.compatibility_status == "passed"
    assert record.preflight_status == "passed"
    assert provider.calls == 1
    assert record.retry_count == 0
    assert diagnostic.semantic_diagnostic_status == expected_status
    assert (
        diagnostic.entity_count,
        diagnostic.evidence_reference_count,
        diagnostic.candidate_fact_count,
    ) == expected_counts
    assert diagnostic.warnings == tuple(sorted(payload["warnings"]))
    assert "raw_response" not in diagnostic.model_dump(mode="json")


def test_schema_valid_non_abstaining_result_must_not_raise_preflight_output_invalid() -> None:
    payload = _base_payload()
    payload["entities"] = [_entity()]
    payload["warnings"] = []

    record, provider = _run(payload)

    assert record.compatibility_status == "passed"
    assert record.semantic_diagnostic.semantic_diagnostic_status == (
        "valid_semantic_variance"
    )
    assert provider.calls == 1


def test_semantic_diagnostic_occurs_after_validation_and_cannot_raise_output_invalid() -> None:
    source = inspect.getsource(run_openai_synthetic_preflight)

    assert source.index("validate_provider_output") < source.index(
        "_build_semantic_diagnostic"
    )
    assert "PREFLIGHT_OUTPUT_INVALID" not in source


def test_invalid_json_preserves_safe_post_response_metadata_without_raw_output() -> None:
    provider = FakeProvider(_base_payload(), raw_response="{not-json")

    with pytest.raises(OpenAIPreflightPostResponseFailureV04) as captured:
        run_openai_synthetic_preflight(
            provider=provider,
            authorization=_authorization(),
            pricing_observation=_pricing(),
            data_controls_observation=_controls(),
            clock=lambda: NOW,
        )

    assert captured.value.code is Stage4BErrorCode.INVALID_JSON
    metadata = captured.value.safe_metadata
    assert metadata.provider_request_id == "req_fictional_v0_4"
    assert metadata.retry_count == 0
    serialized = canonical_json_bytes(metadata.model_dump(mode="json"))
    assert b"not-json" not in serialized


def test_v0_4_identities_and_payload_are_separate_and_safety_controls_are_unchanged() -> None:
    request = build_synthetic_openai_preflight_request_v0_4()
    payload = build_openai_responses_payload(
        request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3
    )
    record, provider = _run(_base_payload())

    assert PREFLIGHT_ID == "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
    assert PREFLIGHT_AUTHORIZATION_SCOPE == "single-synthetic-openai-preflight-v0.4"
    assert PREFLIGHT_ID != V0_2_ID
    assert PREFLIGHT_AUTHORIZATION_SCOPE != V0_2_SCOPE
    assert isinstance(request, LLMExtractionRequestV03)
    assert request.experiment_id == "llm-extraction-baseline-v0.3"
    assert request.prompt_version == "0.3"
    assert request.request_id == "llm-v0.3-S001-primary-999"
    assert request.evidence_blocks[0].evidence_id == (
        "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4"
    )
    assert request.evidence_blocks[0].block_id.endswith("v0.4")
    assert payload["max_output_tokens"] == 4096
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["store"] is False
    assert payload["stream"] is False
    assert payload["background"] is False
    assert payload["tools"] == []
    assert payload["tool_choice"] == "none"
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["name"] == (
        "candidate_extraction_result_0_1_aliases_empty_v0_3"
    )
    assert record.provider_payload_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )
    assert preflight_record_bytes(record).endswith(b"}")
    assert provider.calls == 1
    assert record.provider_configuration_id == (
        "openai-responses-text-strict-json-v0.2"
    )
    assert record.model_configuration_id == (
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    )
    assert "raw_response" not in record.model_dump(mode="json")


def test_v0_4_binds_alias_safe_schema_and_preserves_legacy_schema() -> None:
    alias_safe_schema = build_openai_candidate_schema_v0_3()
    legacy_schema = build_openai_candidate_schema()

    assert uppercase_sha256_bytes(canonical_json_bytes(alias_safe_schema)) == (
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    )
    assert uppercase_sha256_bytes(canonical_json_bytes(legacy_schema)) == (
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    )
    aliases = alias_safe_schema["$defs"]["CandidateEntity"]["properties"]["aliases"]
    assert aliases["type"] == "array"
    assert aliases["maxItems"] == 0
    assert "aliases" in alias_safe_schema["$defs"]["CandidateEntity"]["required"]
    assert DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3.response_schema_name == (
        "candidate_extraction_result_0_1_aliases_empty_v0_3"
    )

    changed = json.loads(json.dumps(alias_safe_schema))
    del changed["$defs"]["CandidateEntity"]["properties"]["aliases"]["maxItems"]
    assert uppercase_sha256_bytes(canonical_json_bytes(changed)) != (
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    )


def test_v0_4_record_rejects_a_rehashed_legacy_schema_anchor() -> None:
    record, _ = _run(_base_payload())
    payload = record.model_dump(mode="json")
    payload["strict_schema_sha256"] = (
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    )
    payload["preflight_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(
            {key: value for key, value in payload.items() if key != "preflight_record_sha256"}
        )
    )

    with pytest.raises(ValidationError, match="strict_schema_sha256"):
        OpenAIPreflightRecordV04.model_validate(payload)


def test_v0_2_authorization_cannot_satisfy_v0_4_scope() -> None:
    v0_2 = OpenAIPreflightAuthorizationV02(
        authorization_id="fictional-v0-2-authorization",
        authorized_by="Fictional V0.2 Owner",
        authorized_at_utc=NOW - timedelta(minutes=5),
        scope=V0_2_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )

    with pytest.raises(ValidationError):
        OpenAIPreflightAuthorizationV04.model_validate(
            v0_2.model_dump(mode="python")
        )


def test_v0_4_contract_uses_no_environment_network_or_default_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("v0.4 contract attempted environment, network or client access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    record, provider = _run(_base_payload())

    assert record.compatibility_status == "passed"
    assert provider.calls == 1
