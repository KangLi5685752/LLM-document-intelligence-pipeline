"""Offline tests for the Stage 4D-2A synthetic preflight contract."""

from __future__ import annotations

import ast
import inspect
import json
import os
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import openai
import pytest
from pydantic import ValidationError

import document_intelligence.llm_extraction.openai_preflight as preflight_module
from document_intelligence.llm_extraction.contracts import (
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    PREFLIGHT_SCHEMA_VERSION,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightProviderObservation,
    OpenAIPreflightRecord,
    OpenAIPricingObservation,
    ProviderPublicMetadataEntry,
    ProviderVersionIdentifier,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


NOW = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


class FakeProvider:
    """Return one same-call observation or error and count exact calls."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[Any] = []

    def generate_preflight(self, request):
        self.calls.append(request)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if callable(self.outcome):
            return self.outcome(request)
        return self.outcome


def _authorization(
    *, authorized_at: datetime = NOW - timedelta(minutes=5)
) -> OpenAIPreflightAuthorization:
    return OpenAIPreflightAuthorization(
        authorization_id="fictional-synthetic-preflight-authorization",
        authorized_by="Fictional Project Owner",
        authorized_at_utc=authorized_at,
        scope=PREFLIGHT_AUTHORIZATION_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )


def _pricing(
    *, observed_at: datetime = NOW
) -> OpenAIPricingObservation:
    return OpenAIPricingObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed pricing page",
        source_url="https://example.invalid/fictional-pricing",
        input_usd_per_million_tokens=Decimal("1.2500"),
        output_usd_per_million_tokens=Decimal("5.5000"),
        currency="USD",
    )


def _data_controls(
    *, observed_at: datetime = NOW
) -> OpenAIDataControlsObservation:
    return OpenAIDataControlsObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed data-control terms",
        source_url="https://example.invalid/fictional-data-controls",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary=(
            "Fictional terms state that store false is required but is not a "
            "zero-retention guarantee."
        ),
    )


def _abstention_payload(request) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "batch_id": "synthetic-preflight-batch-v0.1",
        "source_ids": [request.source_id],
        "entities": [],
        "evidence_references": [],
        "candidate_facts": [],
        "warnings": ["abstained_no_supported_candidate"],
    }


def _raw(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _response(
    request,
    *,
    raw_response: str | None = None,
    input_tokens: int | None = 100,
    output_tokens: int | None = 25,
) -> LLMProviderResponse:
    raw = raw_response or _raw(_abstention_payload(request))
    return LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier=OPENAI_PROVIDER_IDENTIFIER,
        model_identifier="gpt-5.4-mini-fictional-returned-id",
        provider_request_id="req_fictional_preflight_001",
        provider_response_id="resp_fictional_preflight_001",
        provider_sdk_version=OPENAI_INSTALLED_SDK_VERSION,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256(raw),
        token_usage=ProviderTokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        latency_ms=37,
        retry_count=0,
    )


def _public_metadata_entries(
    response: LLMProviderResponse,
    version_provenance: object,
) -> tuple[ProviderPublicMetadataEntry, ...]:
    entries = [
        ProviderPublicMetadataEntry(
            field_path="response.id", value=response.provider_response_id
        ),
        ProviderPublicMetadataEntry(
            field_path="response.model", value=response.model_identifier
        ),
        ProviderPublicMetadataEntry(
            field_path="response._request_id", value=response.provider_request_id
        ),
        ProviderPublicMetadataEntry(
            field_path="sdk.version", value=response.provider_sdk_version
        ),
    ]
    if isinstance(version_provenance, tuple):
        entries.extend(
            ProviderPublicMetadataEntry(
                field_path=identifier.field_name,
                value=identifier.value,
            )
            for identifier in version_provenance
            if isinstance(identifier, ProviderVersionIdentifier)
        )
    return tuple(entries)


def _observation(
    request,
    *,
    response: LLMProviderResponse | None = None,
    version_provenance: object = "unavailable",
    source_response_id: str | None = None,
    metadata_entries: tuple[ProviderPublicMetadataEntry, ...] | None = None,
) -> OpenAIPreflightProviderObservation:
    selected_response = response or _response(request)
    return OpenAIPreflightProviderObservation(
        response=selected_response,
        model_version_or_snapshot_provenance=version_provenance,
        version_provenance_source_response_id=(
            source_response_id or selected_response.provider_response_id
        ),
        observed_from_same_provider_call=True,
        provider_public_metadata_entries=(
            metadata_entries
            if metadata_entries is not None
            else _public_metadata_entries(selected_response, version_provenance)
        ),
    )


def _unchecked_observation(
    request,
    *,
    response: LLMProviderResponse | None = None,
    version_provenance: object = "unavailable",
    source_response_id: str | None = None,
    metadata_entries: object | None = None,
) -> OpenAIPreflightProviderObservation:
    selected_response = response or _response(request)
    return OpenAIPreflightProviderObservation.model_construct(
        response=selected_response,
        model_version_or_snapshot_provenance=version_provenance,
        version_provenance_source_response_id=(
            source_response_id or selected_response.provider_response_id
        ),
        observed_from_same_provider_call=True,
        provider_public_metadata_entries=(
            _public_metadata_entries(selected_response, version_provenance)
            if metadata_entries is None
            else metadata_entries
        ),
    )


def _replace_metadata_value(
    entries: tuple[ProviderPublicMetadataEntry, ...],
    field_path: str,
    value: object,
) -> tuple[ProviderPublicMetadataEntry, ...]:
    return tuple(
        entry.model_copy(update={"value": value})
        if entry.field_path == field_path
        else entry
        for entry in entries
    )


def _run(
    provider: FakeProvider | None = None,
    *,
    authorization: OpenAIPreflightAuthorization | None = None,
    pricing: OpenAIPricingObservation | None = None,
    data_controls: OpenAIDataControlsObservation | None = None,
    clock=lambda: NOW,
) -> tuple[OpenAIPreflightRecord, FakeProvider]:
    selected_provider = provider or FakeProvider(_observation)
    record = run_openai_synthetic_preflight(
        provider=selected_provider,
        authorization=authorization or _authorization(),
        pricing_observation=pricing or _pricing(),
        data_controls_observation=data_controls or _data_controls(),
        clock=clock,
    )
    return record, selected_provider


def _record_payload_with_recomputed_hash(
    record: OpenAIPreflightRecord,
    **changes: object,
) -> dict[str, Any]:
    payload = json.loads(preflight_record_bytes(record))
    payload.update(changes)
    hash_payload = dict(payload)
    hash_payload.pop("preflight_record_sha256", None)
    payload["preflight_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(hash_payload)
    )
    return payload


def test_fixed_preflight_identities_are_exact() -> None:
    assert PREFLIGHT_SCHEMA_VERSION == "0.1"
    assert PREFLIGHT_ID == "openai-gpt-5.4-mini-synthetic-preflight-v0.1"
    assert PREFLIGHT_AUTHORIZATION_SCOPE == (
        "single-synthetic-openai-preflight-v0.1"
    )


def test_synthetic_request_is_deterministic_and_uses_existing_contracts() -> None:
    first = build_synthetic_openai_preflight_request()
    second = build_synthetic_openai_preflight_request()

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.request_id == "synthetic-preflight-request-v0.1"
    assert first.source_id == "S001"
    assert first.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID
    assert first.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID
    assert first.document_sha256 == uppercase_sha256_bytes(
        first.evidence_blocks[0].text.encode("utf-8")
    )
    assert first.prompt_sha256.isupper()
    assert first.canonical_request_sha256.isupper()


def test_synthetic_request_contains_no_development_document_content() -> None:
    request = build_synthetic_openai_preflight_request()
    text = request.evidence_blocks[0].text

    assert "No development-document content is present" in text
    assert "no real-world fact is asserted" in text
    assert request.evidence_blocks[0].evidence_id.startswith("synthetic-preflight")
    assert request.evidence_blocks[0].block_id.startswith("synthetic-preflight")


def test_request_construction_reads_only_installed_prompt_package_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_open = Path.open
    observed_paths: list[Path] = []
    prompt_root = Path(preflight_module.__file__).parent / "prompts"
    allowed_paths = {
        (prompt_root / "system_v0_1.txt").resolve(),
        (prompt_root / "extraction_v0_1.txt").resolve(),
    }

    def guarded_open(path: Path, *args: object, **kwargs: object):
        resolved = Path(path).resolve()
        observed_paths.append(resolved)
        if resolved not in allowed_paths:
            pytest.fail(f"unexpected synthetic request file access: {resolved}")
        return original_open(path, *args, **kwargs)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("synthetic request attempted environment, network, or client access")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(openai, "OpenAI", forbidden)

    request = build_synthetic_openai_preflight_request()

    assert request.source_id == "S001"
    assert observed_paths
    assert set(observed_paths) == allowed_paths


def test_preflight_uses_complete_production_schema_and_deterministic_hashes() -> None:
    request = build_synthetic_openai_preflight_request()
    schema = build_openai_candidate_schema()
    payload = build_openai_responses_payload(request)
    record, _ = _run()

    assert payload["text"]["format"]["schema"] == schema
    assert record.strict_schema_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(schema)
    )
    assert record.provider_payload_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )


def test_authorization_is_required_before_provider_access() -> None:
    provider = FakeProvider(_observation)

    with pytest.raises(Stage4BError) as captured:
        run_openai_synthetic_preflight(
            provider=provider,
            authorization=None,  # type: ignore[arg-type]
            pricing_observation=_pricing(),
            data_controls_observation=_data_controls(),
            clock=lambda: NOW,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID
    assert provider.calls == []


def test_invalid_or_future_authorization_reaches_no_provider() -> None:
    provider = FakeProvider(_observation)
    invalid = OpenAIPreflightAuthorization.model_construct(
        authorization_id="fictional-invalid",
        authorized_by="Fictional Project Owner",
        authorized_at_utc=NOW,
        scope=PREFLIGHT_AUTHORIZATION_SCOPE,
        maximum_provider_calls=2,
        real_provider_preflight_authorized=False,
    )

    with pytest.raises(Stage4BError) as captured:
        run_openai_synthetic_preflight(
            provider=provider,
            authorization=invalid,
            pricing_observation=_pricing(),
            data_controls_observation=_data_controls(),
            clock=lambda: NOW,
        )
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID
    assert provider.calls == []

    with pytest.raises(Stage4BError) as captured:
        _run(provider, authorization=_authorization(authorized_at=NOW + timedelta(seconds=1)))
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID
    assert provider.calls == []


def test_authorization_timestamp_must_be_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _authorization(authorized_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="UTC"):
        _authorization(
            authorized_at=NOW.astimezone(timezone(timedelta(hours=8)))
        )


def test_pricing_is_explicit_positive_and_stably_serialized() -> None:
    observation = _pricing()
    payload = observation.model_dump(mode="json")

    assert payload["input_usd_per_million_tokens"] == "1.25"
    assert payload["output_usd_per_million_tokens"] == "5.5"
    assert payload["currency"] == "USD"
    assert canonical_json_bytes(payload) == canonical_json_bytes(
        observation.model_dump(mode="json")
    )


@pytest.mark.parametrize("field_name", ("input_usd_per_million_tokens", "output_usd_per_million_tokens"))
def test_pricing_rejects_nonpositive_values(field_name: str) -> None:
    payload = _pricing().model_dump(mode="python")
    payload[field_name] = Decimal("0")
    with pytest.raises(ValidationError):
        OpenAIPricingObservation.model_validate(payload)


def test_observation_dates_must_match_execution_date_before_provider_access() -> None:
    provider = FakeProvider(_observation)

    with pytest.raises(Stage4BError) as pricing_error:
        _run(provider, pricing=_pricing(observed_at=NOW - timedelta(days=1)))
    assert pricing_error.value.code is Stage4BErrorCode.PREFLIGHT_TERMS_INVALID
    assert provider.calls == []

    with pytest.raises(Stage4BError) as controls_error:
        _run(
            provider,
            data_controls=_data_controls(observed_at=NOW - timedelta(days=1)),
        )
    assert controls_error.value.code is Stage4BErrorCode.PREFLIGHT_TERMS_INVALID
    assert provider.calls == []


def test_data_controls_forbid_false_store_requirement_or_zero_retention_claim() -> None:
    payload = _data_controls().model_dump(mode="python")
    payload["store_false_required"] = False
    with pytest.raises(ValidationError):
        OpenAIDataControlsObservation.model_validate(payload)

    payload = _data_controls().model_dump(mode="python")
    payload["zero_retention_claimed"] = True
    with pytest.raises(ValidationError):
        OpenAIDataControlsObservation.model_validate(payload)


def test_runner_does_not_accept_standalone_version_provenance() -> None:
    signature = inspect.signature(run_openai_synthetic_preflight)

    assert "model_version_or_snapshot_provenance" not in signature.parameters


def test_same_call_observation_accepts_unavailable_and_multiple_identifiers() -> None:
    unavailable, unavailable_provider = _run(
        FakeProvider(
            lambda request: _observation(
                request, version_provenance="unavailable"
            )
        )
    )
    identifiers = (
        ProviderVersionIdentifier(
            field_name="response.model_version", value="fictional-version-001"
        ),
        ProviderVersionIdentifier(
            field_name="response.snapshot_name", value="fictional-snapshot-001"
        ),
    )
    multiple, multiple_provider = _run(
        FakeProvider(
            lambda request: _observation(
                request, version_provenance=identifiers
            )
        )
    )

    assert unavailable.model_version_or_snapshot_provenance == "unavailable"
    assert multiple.model_version_or_snapshot_provenance == identifiers
    assert len(unavailable_provider.calls) == 1
    assert len(multiple_provider.calls) == 1


@pytest.mark.parametrize(
    "field_path",
    (
        "response.snapshot_name",
        "response.model_version",
        "response.revision_id",
        "Response.SNAPSHOT-NAME",
        "response.MODEL-VERSION",
        "response.Revision-ID",
        "response.snapshot",
        "response.version-id",
    ),
)
def test_unavailable_provenance_rejects_version_metadata(
    field_path: str,
) -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    entries = _public_metadata_entries(response, "unavailable") + (
        ProviderPublicMetadataEntry(
            field_path=field_path,
            value="fictional-separate-version",
        ),
    )
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=response,
            version_provenance="unavailable",
            metadata_entries=entries,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


def test_unavailable_provenance_allows_sdk_version_and_standard_identity() -> None:
    record, provider = _run()

    assert record.model_version_or_snapshot_provenance == "unavailable"
    assert record.provider_public_metadata_field_paths == (
        "response.id",
        "response.model",
        "response._request_id",
        "sdk.version",
    )
    assert len(provider.calls) == 1


def test_explicit_hyphenated_snapshot_metadata_with_matching_provenance_is_valid() -> None:
    identifier = ProviderVersionIdentifier(
        field_name="Response.SNAPSHOT-NAME",
        value="fictional-snapshot-hyphenated",
    )
    record, provider = _run(
        FakeProvider(
            lambda request: _observation(
                request,
                version_provenance=(identifier,),
            )
        )
    )

    assert record.model_version_or_snapshot_provenance == (identifier,)
    assert "Response.SNAPSHOT-NAME" in record.provider_public_metadata_field_paths
    assert len(provider.calls) == 1


@pytest.mark.parametrize("mode", ("missing", "mismatched"))
def test_explicit_version_provenance_must_reconcile_with_metadata(mode: str) -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    identifiers = (
        ProviderVersionIdentifier(
            field_name="response.snapshot_name",
            value="fictional-snapshot-001",
        ),
    )
    entries = _public_metadata_entries(response, identifiers)
    if mode == "missing":
        entries = tuple(
            entry
            for entry in entries
            if entry.field_path != "response.snapshot_name"
        )
    else:
        entries = _replace_metadata_value(
            entries,
            "response.snapshot_name",
            "fictional-different-snapshot",
        )
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=response,
            version_provenance=identifiers,
            metadata_entries=entries,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


def test_version_provenance_cannot_be_added_after_metadata_derivation() -> None:
    request = build_synthetic_openai_preflight_request()
    observation = _observation(request, version_provenance="unavailable")
    original_hash = observation.provider_public_metadata_sha256
    identifiers = (
        ProviderVersionIdentifier(
            field_name="response.snapshot_name",
            value="fictional-snapshot-added-later",
        ),
    )
    tampered = observation.model_copy(
        update={"model_version_or_snapshot_provenance": identifiers}
    )
    provider = FakeProvider(tampered)

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert tampered.provider_public_metadata_sha256 == original_hash
    assert len(provider.calls) == 1


def test_empty_or_case_insensitive_duplicate_version_provenance_fails_closed() -> None:
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request, version_provenance=()
        )
    )
    with pytest.raises(Stage4BError) as empty_error:
        _run(provider)
    assert empty_error.value.code is (
        Stage4BErrorCode.PREFLIGHT_VERSION_PROVENANCE_INVALID
    )
    assert len(provider.calls) == 1

    duplicate = (
        ProviderVersionIdentifier(field_name="snapshot_name", value="fictional-a"),
        ProviderVersionIdentifier(field_name="SNAPSHOT_NAME", value="fictional-b"),
    )
    duplicate_provider = FakeProvider(
        lambda request: _unchecked_observation(
            request, version_provenance=duplicate
        )
    )
    with pytest.raises(Stage4BError) as duplicate_error:
        _run(duplicate_provider)
    assert duplicate_error.value.code is (
        Stage4BErrorCode.PREFLIGHT_VERSION_PROVENANCE_INVALID
    )
    assert len(duplicate_provider.calls) == 1


@pytest.mark.parametrize(
    "field_name",
    (
        "model",
        "model_alias",
        "model_id",
        "returned_model_identifier",
        "id",
        "response_id",
        "provider_response_id",
        "request_id",
        "provider_request_id",
        "_request_id",
        "created",
        "created_at",
        "created_timestamp",
        "response.model",
        "response.id",
        "response.created_at",
        "response.model-id",
        "response.request-id",
        "response.created-at",
        "Response.MODEL-ID",
        "Response.REQUEST-ID",
        "Response.CREATED-AT",
        "sdk.version",
        "sdk_version",
        "provider_sdk_version",
        "response.provider_sdk_version",
        "SDK.VERSION",
        "response.provider-sdk-version",
    ),
)
def test_version_provenance_rejects_inferred_identity_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError, match="not separate version provenance"):
        ProviderVersionIdentifier(
            field_name=field_name,
            value="fictional-not-version-provenance",
        )


def test_provider_is_called_exactly_once_and_metadata_is_preserved() -> None:
    record, provider = _run()

    assert len(provider.calls) == 1
    assert record.provider_call_count == 1
    assert record.returned_model_identifier == "gpt-5.4-mini-fictional-returned-id"
    assert record.provider_request_id == "req_fictional_preflight_001"
    assert record.provider_response_id == "resp_fictional_preflight_001"
    assert (
        record.version_provenance_source_response_id
        == record.provider_response_id
    )
    assert record.version_provenance_observed_from_same_provider_call is True
    assert record.provider_public_metadata_field_paths == (
        "response.id",
        "response.model",
        "response._request_id",
        "sdk.version",
    )
    assert record.provider_public_metadata_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(
            {
                "response.id": "resp_fictional_preflight_001",
                "response.model": "gpt-5.4-mini-fictional-returned-id",
                "response._request_id": "req_fictional_preflight_001",
                "sdk.version": OPENAI_INSTALLED_SDK_VERSION,
            }
        )
    )
    assert record.provider_sdk_version == OPENAI_INSTALLED_SDK_VERSION
    assert record.input_tokens == 100
    assert record.output_tokens == 25
    assert record.latency_ms == 37
    assert record.retry_count == 0


def test_mismatched_version_source_response_id_fails_closed() -> None:
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            source_response_id="resp_fictional_different_call",
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


def test_metadata_hash_and_paths_cannot_be_supplied_independently() -> None:
    request = build_synthetic_openai_preflight_request()
    payload = _observation(request).model_dump(mode="python")

    assert "provider_public_metadata_sha256" not in payload
    assert "provider_public_metadata_field_paths" not in payload
    for forbidden_field, value in (
        ("provider_public_metadata_sha256", "A" * 64),
        ("provider_public_metadata_field_paths", ("response.id",)),
    ):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            OpenAIPreflightProviderObservation.model_validate(
                {**payload, forbidden_field: value}
            )


def test_metadata_hash_and_paths_are_derived_from_canonical_entries() -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    entries = _public_metadata_entries(response, "unavailable")
    observation = _observation(request, response=response, metadata_entries=entries)
    projection = {entry.field_path: entry.value for entry in entries}

    assert observation.provider_public_metadata_field_paths == tuple(projection)
    assert observation.provider_public_metadata_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(projection)
    )

    changed_entries = entries + (
        ProviderPublicMetadataEntry(
            field_path="response.service_tier",
            value="fictional-service-tier-a",
        ),
    )
    changed = _observation(
        request,
        response=response,
        metadata_entries=changed_entries,
    )
    changed_again = _observation(
        request,
        response=response,
        metadata_entries=_replace_metadata_value(
            changed_entries,
            "response.service_tier",
            "fictional-service-tier-b",
        ),
    )

    assert changed.provider_public_metadata_sha256 != (
        changed_again.provider_public_metadata_sha256
    )


@pytest.mark.parametrize(
    ("field_path", "response_attribute"),
    (
        ("response.id", "provider_response_id"),
        ("response.model", "model_identifier"),
        ("response._request_id", "provider_request_id"),
        ("sdk.version", "provider_sdk_version"),
    ),
)
def test_standard_public_metadata_must_reconcile_with_response(
    field_path: str,
    response_attribute: str,
) -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    assert getattr(response, response_attribute) is not None
    entries = _replace_metadata_value(
        _public_metadata_entries(response, "unavailable"),
        field_path,
        "fictional-mismatch",
    )
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=response,
            metadata_entries=entries,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "missing_path",
    ("response.id", "response.model", "response._request_id", "sdk.version"),
)
def test_missing_standard_public_metadata_fails_closed(missing_path: str) -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    entries = tuple(
        entry
        for entry in _public_metadata_entries(response, "unavailable")
        if entry.field_path != missing_path
    )
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=response,
            metadata_entries=entries,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "extra_paths",
    (
        ("RESPONSE.ID",),
        ("response.service-tier", "response.service_tier"),
    ),
)
def test_normalized_duplicate_metadata_paths_fail_closed(
    extra_paths: tuple[str, ...],
) -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    entries = _public_metadata_entries(response, "unavailable") + tuple(
        ProviderPublicMetadataEntry(
            field_path=field_path,
            value="fictional-duplicate-value",
        )
        for field_path in extra_paths
    )
    provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=response,
            metadata_entries=entries,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "field_path",
    (
        "response.raw_response",
        "response.output_text",
        "request.prompt",
        "request.evidence_text",
        "request.headers",
        "request.authorization_header",
        "request.credentials",
        "request.api-key",
    ),
)
def test_sensitive_public_metadata_paths_remain_rejected(field_path: str) -> None:
    with pytest.raises(ValidationError):
        ProviderPublicMetadataEntry(field_path=field_path, value="fictional")


@pytest.mark.parametrize("value", ("fictional", 7, True, False, None))
def test_public_metadata_values_accept_only_safe_scalars(value: object) -> None:
    entry = ProviderPublicMetadataEntry(
        field_path="response.fictional_scalar",
        value=value,  # type: ignore[arg-type]
    )

    assert entry.value == value
    assert type(entry.value) is type(value)


@pytest.mark.parametrize(
    "value",
    (
        "   ",
        1.5,
        b"fictional-binary",
        ["fictional-array"],
        {"fictional": "object"},
        ("fictional-tuple",),
    ),
)
def test_public_metadata_values_reject_unsafe_content(value: object) -> None:
    with pytest.raises(ValidationError):
        ProviderPublicMetadataEntry(
            field_path="response.fictional_unsafe",
            value=value,  # type: ignore[arg-type]
        )


def test_provider_error_is_not_retried_or_converted_to_success() -> None:
    provider = FakeProvider(
        Stage4BError(Stage4BErrorCode.TIMEOUT, "fictional provider timeout")
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is Stage4BErrorCode.TIMEOUT
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "field_name",
    ("provider_request_id", "provider_response_id", "provider_sdk_version"),
)
def test_missing_provider_metadata_fails_closed(field_name: str) -> None:
    def incomplete(request):
        response = _response(request).model_copy(update={field_name: None})
        return _unchecked_observation(request, response=response)

    provider = FakeProvider(incomplete)
    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )
    assert len(provider.calls) == 1


def test_wrong_provider_or_missing_token_usage_fails_closed() -> None:
    wrong_provider = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=_response(request).model_copy(
                update={"provider_identifier": "fictional-provider"}
            ),
        )
    )
    with pytest.raises(Stage4BError) as captured:
        _run(wrong_provider)
    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )

    missing_usage = FakeProvider(
        lambda request: _unchecked_observation(
            request,
            response=_response(request).model_copy(update={"token_usage": None}),
        )
    )
    with pytest.raises(Stage4BError) as captured:
        _run(missing_usage)
    assert captured.value.code is (
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    )


def test_malformed_output_fails_through_authoritative_existing_validator() -> None:
    provider = FakeProvider(
        lambda request: _observation(
            request,
            response=_response(request, raw_response="{not-json"),
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is Stage4BErrorCode.INVALID_JSON
    assert len(provider.calls) == 1


def _non_abstaining_payload(request, kind: str) -> dict[str, Any]:
    payload = _abstention_payload(request)
    evidence = {
        "evidence_id": request.evidence_blocks[0].evidence_id,
        "source_id": request.source_id,
        "block_id": request.evidence_blocks[0].block_id,
        "location_type": "document_metadata",
        "location_value": "synthetic-preflight",
        "text_excerpt": "Synthetic preflight only.",
        "evidence_status": "supported",
    }
    if kind in {"evidence", "candidate"}:
        payload["evidence_references"] = [evidence]
    if kind == "entity":
        payload["entities"] = [
            {
                "entity_id": "synthetic-preflight-entity",
                "canonical_name": "fictional synthetic subject",
                "entity_type": "other",
                "aliases": [],
                "source_ids": [request.source_id],
            }
        ]
    if kind == "candidate":
        payload["candidate_facts"] = [
            {
                "candidate_id": "synthetic-preflight-candidate",
                "source_id": request.source_id,
                "document_family": "synthetic_preflight",
                "subject_text": "fictional synthetic subject",
                "subject_type": "other",
                "predicate": "status",
                "raw_value": "fictional",
                "normalized_value": "fictional",
                "value_type": "status",
                "qualifiers": {},
                "evidence_ids": [request.evidence_blocks[0].evidence_id],
                "confidence": 0.5,
                "review_status": "not_required",
                "extraction_method": "llm",
                "warnings": [],
            }
        ]
    return payload


@pytest.mark.parametrize("kind", ("candidate", "entity", "evidence"))
def test_any_nonempty_synthetic_output_collection_fails_closed(kind: str) -> None:
    provider = FakeProvider(
        lambda request: _observation(
            request,
            response=_response(
                request,
                raw_response=_raw(_non_abstaining_payload(request, kind)),
            ),
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _run(provider)

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_OUTPUT_INVALID
    assert len(provider.calls) == 1


def test_valid_abstention_produces_reconciled_passed_record() -> None:
    record, _ = _run()

    assert record.preflight_status == "passed"
    assert record.strict_schema_compatible is True
    assert record.local_output_validation_status == "valid"
    assert record.store_requested is False
    assert record.streaming_enabled is False
    assert record.background_enabled is False
    assert record.tools_enabled is False
    assert record.estimated_actual_cost_usd == Decimal("0.0002625")


def test_record_bytes_and_hash_are_deterministic() -> None:
    first, _ = _run()
    second, _ = _run()

    assert first == second
    assert preflight_record_bytes(first) == preflight_record_bytes(second)
    assert OpenAIPreflightRecord.model_validate_json(
        preflight_record_bytes(first)
    ) == first
    payload = json.loads(preflight_record_bytes(first))
    hash_payload = dict(payload)
    del hash_payload["preflight_record_sha256"]
    assert first.preflight_record_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(hash_payload)
    )


@pytest.mark.parametrize(
    "case",
    (
        "explicit_sdk_version",
        "explicit_provider_sdk_version",
        "unavailable_snapshot_path",
        "explicit_snapshot_missing_path",
        "missing_required_standard_path",
    ),
)
def test_recomputed_record_hash_does_not_bypass_path_semantics(case: str) -> None:
    record, _ = _run()
    paths = list(record.provider_public_metadata_field_paths)
    changes: dict[str, object]
    if case == "explicit_sdk_version":
        changes = {
            "model_version_or_snapshot_provenance": [
                {
                    "field_name": "sdk.version",
                    "value": OPENAI_INSTALLED_SDK_VERSION,
                }
            ]
        }
    elif case == "explicit_provider_sdk_version":
        changes = {
            "model_version_or_snapshot_provenance": [
                {
                    "field_name": "response.provider_sdk_version",
                    "value": OPENAI_INSTALLED_SDK_VERSION,
                }
            ],
            "provider_public_metadata_field_paths": [
                *paths,
                "response.provider_sdk_version",
            ],
        }
    elif case == "unavailable_snapshot_path":
        changes = {
            "provider_public_metadata_field_paths": [
                *paths,
                "response.snapshot_name",
            ]
        }
    elif case == "explicit_snapshot_missing_path":
        changes = {
            "model_version_or_snapshot_provenance": [
                {
                    "field_name": "response.snapshot_name",
                    "value": "fictional-missing-snapshot",
                }
            ]
        }
    else:
        changes = {
            "provider_public_metadata_field_paths": [
                path for path in paths if path != "response.model"
            ]
        }
    payload = _record_payload_with_recomputed_hash(record, **changes)
    hash_payload = dict(payload)
    del hash_payload["preflight_record_sha256"]

    assert payload["preflight_record_sha256"] == uppercase_sha256_bytes(
        canonical_json_bytes(hash_payload)
    )
    with pytest.raises((ValidationError, Stage4BError)) as captured:
        OpenAIPreflightRecord.model_validate(payload)
    assert "does not match canonical record bytes" not in str(captured.value)


def test_valid_semantically_consistent_recomputed_record_validates() -> None:
    record, _ = _run()
    authorization = record.authorization.model_dump(mode="json")
    authorization["authorization_id"] = (
        "fictional-synthetic-preflight-authorization-rehashed"
    )
    payload = _record_payload_with_recomputed_hash(
        record,
        authorization=authorization,
    )

    validated = OpenAIPreflightRecord.model_validate(payload)

    assert validated.authorization.authorization_id.endswith("-rehashed")
    assert validated.preflight_record_sha256 == payload["preflight_record_sha256"]


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("request_id",), "tampered-request"),
        (("returned_model_identifier",), "tampered-model"),
        (("provider_request_id",), "tampered-provider-request"),
        (
            ("model_version_or_snapshot_provenance",),
            [
                {
                    "field_name": "response.snapshot_name",
                    "value": "tampered-snapshot",
                }
            ],
        ),
        (
            ("version_provenance_source_response_id",),
            "resp_fictional_different_call",
        ),
        (("provider_public_metadata_sha256",), "A" * 64),
        (
            ("provider_public_metadata_field_paths",),
            [
                "response.id",
                "response.model",
                "response._request_id",
                "sdk.version",
                "response.snapshot_name",
            ],
        ),
        (("pricing_observation", "source_title"), "tampered pricing"),
        (
            ("data_controls_observation", "source_title"),
            "tampered controls",
        ),
    ),
)
def test_tampering_identity_terms_or_provider_fields_invalidates_record(
    path: tuple[str, ...], value: object
) -> None:
    record, _ = _run()
    payload = json.loads(preflight_record_bytes(record))
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises((ValidationError, Stage4BError)):
        OpenAIPreflightRecord.model_validate(payload)


def test_serialized_record_contains_no_sensitive_or_raw_request_material() -> None:
    record, _ = _run()
    raw = preflight_record_bytes(record)
    synthetic_text = build_synthetic_openai_preflight_request().evidence_blocks[0].text

    for forbidden in (
        synthetic_text.encode("utf-8"),
        b"Ordered evidence blocks",
        b"api_key",
        b"authorization_header",
        b"OPENAI_API_KEY",
        b"C:\\",
        b"/Users/",
    ):
        assert forbidden not in raw


def test_metadata_values_are_not_serialized_in_final_record() -> None:
    request = build_synthetic_openai_preflight_request()
    response = _response(request)
    private_projection_value = "fictional-transient-public-metadata-value"
    entries = _public_metadata_entries(response, "unavailable") + (
        ProviderPublicMetadataEntry(
            field_path="response.fictional_region",
            value=private_projection_value,
        ),
    )
    record, _ = _run(
        FakeProvider(
            lambda request: _observation(
                request,
                response=response,
                metadata_entries=entries,
            )
        )
    )
    raw = preflight_record_bytes(record)

    assert b"provider_public_metadata_entries" not in raw
    assert private_projection_value.encode("utf-8") not in raw
    assert b"response.fictional_region" in raw
    assert record.provider_public_metadata_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(
            {entry.field_path: entry.value for entry in entries}
        )
    )


def test_runner_uses_no_network_environment_or_default_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("offline preflight attempted a forbidden runtime side effect")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(openai, "OpenAI", forbidden)

    record, provider = _run()

    assert record.preflight_status == "passed"
    assert len(provider.calls) == 1


def test_preflight_module_implements_no_environment_access() -> None:
    source = Path(preflight_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "os" not in imported_roots
    assert "OPENAI_API_KEY" not in source
    assert "getenv" not in source
    assert "environ" not in source
    assert "OpenAIResponsesProvider(" not in source
    for forbidden in (
        "cache",
        "development_document",
        "gold",
        "manifest",
        "matching",
        "ParsedDocument",
    ):
        assert not any(forbidden in module for module in imported_modules)


def test_runner_creates_no_preflight_artifact_or_transaction_residue(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    record, _ = _run()

    assert record.preflight_status == "passed"
    assert list(tmp_path.iterdir()) == []
