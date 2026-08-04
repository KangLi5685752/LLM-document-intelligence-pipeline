"""Offline contract tests for the additive Stage 4D preflight v0.2."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.contracts import (
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE as V0_1_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID as V0_1_PREFLIGHT_ID,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
    ProviderPublicMetadataEntry,
)
from document_intelligence.llm_extraction.openai_preflight_v0_2 import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    OpenAIPreflightAuthorizationV02,
    OpenAIPreflightRecordV02,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_INSTALLED_SDK_VERSION,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def _authorization() -> OpenAIPreflightAuthorizationV02:
    return OpenAIPreflightAuthorizationV02(
        authorization_id="fictional-v0-2-authorization",
        authorized_by="Fictional V0.2 Owner",
        authorized_at_utc=NOW - timedelta(minutes=5),
        scope=PREFLIGHT_AUTHORIZATION_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )


def _pricing() -> OpenAIPricingObservation:
    return OpenAIPricingObservation(
        observed_at_utc=NOW,
        source_title="Fictional v0.2 pricing",
        source_url="https://example.invalid/pricing-v0-2",
        input_usd_per_million_tokens=Decimal("1.25"),
        output_usd_per_million_tokens=Decimal("5.50"),
        currency="USD",
    )


def _data_controls() -> OpenAIDataControlsObservation:
    return OpenAIDataControlsObservation(
        observed_at_utc=NOW,
        source_title="Fictional v0.2 controls",
        source_url="https://example.invalid/controls-v0-2",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary="Fictional limitations apply.",
    )


def _observation(request) -> OpenAIPreflightProviderObservation:
    raw = json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-v0-2-batch",
            "source_ids": [request.source_id],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    response = LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="openai",
        model_identifier="gpt-5.4-mini-fictional-v0-2",
        provider_request_id="req_fictional_v0_2",
        provider_response_id="resp_fictional_v0_2",
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
    def __init__(self) -> None:
        self.calls = 0

    def generate_preflight(self, request):
        self.calls += 1
        return _observation(request)


def test_v0_2_identities_and_request_ids_are_distinct_from_v0_1() -> None:
    request = build_synthetic_openai_preflight_request()

    assert PREFLIGHT_ID == "openai-gpt-5.4-mini-synthetic-preflight-v0.2"
    assert PREFLIGHT_AUTHORIZATION_SCOPE == "single-synthetic-openai-preflight-v0.2"
    assert PREFLIGHT_ID != V0_1_PREFLIGHT_ID
    assert PREFLIGHT_AUTHORIZATION_SCOPE != V0_1_AUTHORIZATION_SCOPE
    assert request.request_id == "synthetic-preflight-request-v0.2"
    assert request.evidence_blocks[0].evidence_id == "synthetic-preflight-evidence-v0.2"
    assert request.evidence_blocks[0].block_id == "synthetic-preflight-block-v0.2"
    assert request.source_id == "S001"
    assert "S005" not in canonical_json_bytes(request.model_dump(mode="json")).decode()
    assert "S007" not in canonical_json_bytes(request.model_dump(mode="json")).decode()


def test_v0_2_runner_produces_one_self_hashed_record_with_unchanged_payload() -> None:
    provider = FakeProvider()

    record = run_openai_synthetic_preflight(
        provider=provider,
        authorization=_authorization(),
        pricing_observation=_pricing(),
        data_controls_observation=_data_controls(),
        clock=lambda: NOW,
    )

    payload = build_openai_responses_payload(
        build_synthetic_openai_preflight_request()
    )
    assert isinstance(record, OpenAIPreflightRecordV02)
    assert record.preflight_id == PREFLIGHT_ID
    assert record.authorization.scope == PREFLIGHT_AUTHORIZATION_SCOPE
    assert provider.calls == 1
    assert payload["max_output_tokens"] == 4096
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["store"] is False
    assert payload["stream"] is False
    assert payload["background"] is False
    assert payload["tools"] == []
    assert payload["tool_choice"] == "none"
    assert record.provider_payload_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )
    assert preflight_record_bytes(record).endswith(b"}")
    assert OpenAIPreflightRecordV02.model_validate(
        record.model_dump(mode="python")
    ) == record


def test_v0_1_authorization_cannot_satisfy_v0_2_scope() -> None:
    v0_1_authorization = OpenAIPreflightAuthorization(
        authorization_id="fictional-v0-1-authorization",
        authorized_by="Fictional V0.1 Owner",
        authorized_at_utc=NOW - timedelta(minutes=5),
        scope=V0_1_AUTHORIZATION_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )

    with pytest.raises(ValidationError):
        OpenAIPreflightAuthorizationV02.model_validate(
            v0_1_authorization.model_dump(mode="python")
        )


def test_v0_2_contract_uses_no_environment_network_or_default_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("v0.2 contract attempted environment, network or client access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    provider = FakeProvider()

    record = run_openai_synthetic_preflight(
        provider=provider,
        authorization=_authorization(),
        pricing_observation=_pricing(),
        data_controls_observation=_data_controls(),
        clock=lambda: NOW,
    )

    assert record.preflight_status == "passed"
    assert provider.calls == 1
