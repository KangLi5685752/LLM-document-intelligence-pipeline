"""Append-only Stage 4C cache tests with temporary fictional records."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import document_intelligence.llm_extraction.cache as cache_module
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    AttemptProvenance,
    CacheIdentity,
    DeterministicMockProvider,
    InvocationRole,
    LLMProviderResponse,
    MockResponseFixture,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ResponseCache,
    Stage4BError,
    Stage4BErrorCode,
    build_cache_record,
    build_request_envelope,
    cache_record_bytes,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.openai_preflight import (
    ProviderVersionIdentifier,
)


NOW = datetime(2026, 8, 3, 1, 2, 3, tzinfo=timezone.utc)


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symbolic links are unavailable on this platform: {error}")


def _request(role: InvocationRole = InvocationRole.PRIMARY):
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text="A fictional programme has no supported candidate.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )
    return build_request_envelope(
        invocation_role=role,
        request_id=f"fictional-{role.value}-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        evidence_blocks=(block,),
    )


def _raw(batch_id: str = "fictional-batch-001") -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": batch_id,
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _record(
    role: InvocationRole = InvocationRole.PRIMARY,
    *,
    batch_id: str = "fictional-batch-001",
):
    request = _request(role)
    response = DeterministicMockProvider(
        {
            request.canonical_request_sha256: MockResponseFixture(
                terminal_status=ProviderTerminalStatus.SUCCESS,
                raw_response=_raw(batch_id),
                latency_ms=4,
            )
        }
    ).generate(request)
    attempt = AttemptProvenance(
        attempt_number=1,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        provider_call_performed=True,
        response_sha256=response.raw_response_sha256,
        latency_ms=response.latency_ms,
    )
    return build_cache_record(
        identity=CacheIdentity.from_request(request),
        response=response,
        original_provider_call_timestamp=NOW,
        original_attempts=(attempt,),
        estimated_cost_usd=Decimal("0.25"),
    )


def _record_with_provider_metadata():
    base = _record()
    response_payload = base.response.model_dump(mode="python")
    response_payload.update(
        {
            "provider_identifier": "openai",
            "model_identifier": "gpt-5.4-mini-fictional-snapshot",
            "provider_request_id": "req_fictional_001",
            "provider_response_id": "resp_fictional_001",
            "provider_sdk_version": "2.46.0",
            "token_usage": ProviderTokenUsage(input_tokens=23, output_tokens=11),
            "latency_ms": 125,
        }
    )
    return build_cache_record(
        identity=base.identity,
        response=LLMProviderResponse.model_validate(response_payload),
        original_provider_call_timestamp=base.original_provider_call_timestamp,
        original_attempts=base.original_attempts,
        estimated_cost_usd=base.estimated_cost_usd,
    )


def _openai_original_call_provenance(response: LLMProviderResponse):
    field_path = "response.metadata.snapshot_id"
    value = "fictional-snapshot-2099-01-01"
    projection = {
        "response.id": response.provider_response_id,
        "response.model": response.model_identifier,
        "response._request_id": response.provider_request_id,
        "sdk.version": response.provider_sdk_version,
        field_path: value,
    }
    return cache_module.OpenAIOriginalCallProvenanceV01(
        model_version_or_snapshot_provenance=(
            ProviderVersionIdentifier(field_name=field_path, value=value),
        ),
        version_provenance_source_response_id=response.provider_response_id,
        provider_public_metadata_sha256=uppercase_sha256_bytes(
            canonical_json_bytes(projection)
        ),
        provider_public_metadata_field_paths=tuple(projection),
        observed_from_same_provider_call=True,
    )


def _legacy_cache_bytes() -> tuple[CacheIdentity, bytes]:
    identity = CacheIdentity.from_request(_request())
    raw_response = _raw()
    response_sha256 = uppercase_sha256_bytes(raw_response.encode("utf-8"))
    payload = {
        "cache_schema_version": "0.1",
        "identity": identity.model_dump(mode="json"),
        "response": {
            "request_id": identity.request_id,
            "provider_identifier": "stage4b-deterministic-mock-provider",
            "model_identifier": "stage4b-deterministic-mock-model",
            "terminal_status": "success",
            "raw_response": raw_response,
            "raw_response_sha256": response_sha256,
            "token_usage": None,
            "latency_ms": 4,
            "retry_count": 0,
            "warning_codes": [],
            "failure_codes": [],
        },
        "original_provider_call_timestamp": "2026-08-03T01:02:03Z",
        "original_attempts": [
            {
                "attempt_number": 1,
                "terminal_status": "success",
                "provider_call_performed": True,
                "response_sha256": response_sha256,
                "latency_ms": 4,
                "retry_reason": None,
                "failure_code": None,
            }
        ],
        "estimated_cost_usd": "0.25",
    }
    payload["cache_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )
    return identity, canonical_json_bytes(payload)


def test_cache_miss_is_explicit(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    with pytest.raises(Stage4BError) as captured:
        cache.read(CacheIdentity.from_request(_request()))
    assert captured.value.code is Stage4BErrorCode.CACHE_MISS


def test_cache_append_and_read_preserve_exact_original_record(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()

    installed = cache.append(record)
    loaded = cache.read(record.identity)

    assert installed == record
    assert loaded == record
    assert cache.path_for(record.identity).read_bytes() == cache_record_bytes(record)
    assert loaded.original_provider_call_timestamp == NOW
    assert loaded.response.raw_response == _raw()


def test_pre_metadata_legacy_cache_record_remains_hash_valid(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    identity, legacy_bytes = _legacy_cache_bytes()
    target = cache.path_for(identity)
    target.write_bytes(legacy_bytes)

    loaded = cache.read(identity)

    assert loaded.response.provider_request_id is None
    assert loaded.response.provider_response_id is None
    assert loaded.response.provider_sdk_version is None
    assert cache_record_bytes(loaded) == legacy_bytes
    assert b"openai_original_call_provenance" not in legacy_bytes


def test_cache_preserves_additive_provider_metadata_exactly(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record_with_provider_metadata()

    cache.append(record)
    loaded = cache.read(record.identity)

    assert loaded == record
    assert loaded.response.provider_request_id == "req_fictional_001"
    assert loaded.response.provider_response_id == "resp_fictional_001"
    assert loaded.response.provider_sdk_version == "2.46.0"
    assert loaded.response.token_usage == ProviderTokenUsage(
        input_tokens=23, output_tokens=11
    )
    assert loaded.response.latency_ms == 125


def test_cache_preserves_typed_openai_original_call_provenance(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    base = _record_with_provider_metadata()
    provenance = _openai_original_call_provenance(base.response)
    record = build_cache_record(
        identity=base.identity,
        response=base.response,
        original_provider_call_timestamp=base.original_provider_call_timestamp,
        original_attempts=base.original_attempts,
        estimated_cost_usd=base.estimated_cost_usd,
        openai_original_call_provenance=provenance,
    )

    cache.append(record)
    loaded = cache.read(record.identity)

    assert loaded.openai_original_call_provenance == provenance
    assert cache_record_bytes(loaded) == cache.path_for(record.identity).read_bytes()
    assert b"fictional-snapshot-2099-01-01" in cache_record_bytes(loaded)


def test_rehashed_cache_cannot_contradict_original_version_provenance(
    tmp_path,
) -> None:
    cache = ResponseCache(tmp_path / "cache")
    base = _record_with_provider_metadata()
    record = build_cache_record(
        identity=base.identity,
        response=base.response,
        original_provider_call_timestamp=base.original_provider_call_timestamp,
        original_attempts=base.original_attempts,
        estimated_cost_usd=base.estimated_cost_usd,
        openai_original_call_provenance=(
            _openai_original_call_provenance(base.response)
        ),
    )
    cache.append(record)
    target = cache.path_for(record.identity)
    payload = json.loads(target.read_bytes())
    payload["openai_original_call_provenance"][
        "model_version_or_snapshot_provenance"
    ] = "unavailable"
    payload_without_hash = dict(payload)
    payload_without_hash.pop("cache_record_sha256")
    payload["cache_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(payload_without_hash)
    )
    target.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)
    assert captured.value.code is Stage4BErrorCode.CACHE_RECORD_INVALID


@pytest.mark.parametrize(
    "field_name",
    ("provider_request_id", "provider_response_id", "provider_sdk_version"),
)
def test_present_provider_metadata_is_covered_by_cache_hash(
    tmp_path, field_name: str
) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record_with_provider_metadata()
    cache.append(record)
    target = cache.path_for(record.identity)
    payload = json.loads(target.read_bytes())
    payload["response"][field_name] = f"tampered-{field_name}"
    target.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)

    assert captured.value.code is Stage4BErrorCode.CACHE_HASH_MISMATCH


def test_identical_append_is_a_read_without_rewrite(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    cache.append(record)
    target = cache.path_for(record.identity)
    before = target.stat().st_mtime_ns

    assert cache.append(record) == record
    assert target.stat().st_mtime_ns == before


def test_conflicting_overwrite_is_rejected(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    first = _record()
    cache.append(first)
    conflict = _record(batch_id="fictional-different-batch")

    with pytest.raises(Stage4BError) as captured:
        cache.append(conflict)
    assert captured.value.code is Stage4BErrorCode.CACHE_CONFLICT
    assert cache.read(first.identity) == first


def test_truncated_cache_record_fails_closed(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    cache.append(record)
    cache.path_for(record.identity).write_bytes(b'{"cache_schema_version":')

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)
    assert captured.value.code is Stage4BErrorCode.CACHE_RECORD_INVALID


def test_response_hash_mismatch_fails_closed(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    cache.append(record)
    target = cache.path_for(record.identity)
    payload = json.loads(target.read_bytes())
    payload["response"]["raw_response"] = "tampered fictional response"
    target.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)
    assert captured.value.code is Stage4BErrorCode.CACHE_HASH_MISMATCH


def test_cache_record_hash_mismatch_fails_closed(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    cache.append(record)
    target = cache.path_for(record.identity)
    payload = json.loads(target.read_bytes())
    payload["cache_record_sha256"] = "F" * 64
    target.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)
    assert captured.value.code is Stage4BErrorCode.CACHE_HASH_MISMATCH


@pytest.mark.parametrize(
    "relative_path",
    ("../escape.json", "nested/escape.json", r"C:\escape.json", "/escape.json"),
)
def test_cache_path_escape_is_rejected(tmp_path, relative_path: str) -> None:
    with pytest.raises(Stage4BError) as captured:
        cache_module.safe_cache_path(tmp_path, relative_path)
    assert captured.value.code is Stage4BErrorCode.CACHE_PATH_ESCAPE


def test_cache_rejects_symlink_in_existing_ancestor_component(tmp_path) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    _symlink_or_skip(linked_parent, real_parent, target_is_directory=True)

    with pytest.raises(Stage4BError) as captured:
        ResponseCache(linked_parent / "nested-cache")

    assert captured.value.code is Stage4BErrorCode.CACHE_PATH_ESCAPE
    assert not (real_parent / "nested-cache").exists()


def test_cache_rejects_path_escape_through_unsafe_component(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    cache_parent = tmp_path / "cache-parent"
    cache_parent.mkdir()
    unsafe_component = cache_parent / "unsafe"
    _symlink_or_skip(unsafe_component, outside, target_is_directory=True)

    with pytest.raises(Stage4BError) as captured:
        ResponseCache(unsafe_component / "escaped-cache")

    assert captured.value.code is Stage4BErrorCode.CACHE_PATH_ESCAPE
    assert not (outside / "escaped-cache").exists()


def test_cache_rejects_symlink_at_final_entry_path(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    target = cache.path_for(record.identity)
    outside = tmp_path / "outside.json"
    outside.write_bytes(cache_record_bytes(record))
    _symlink_or_skip(target, outside)

    with pytest.raises(Stage4BError) as captured:
        cache.read(record.identity)

    assert captured.value.code is Stage4BErrorCode.CACHE_PATH_ESCAPE


def test_cache_rejects_broken_symlink_at_final_entry_without_partial_file(
    tmp_path,
) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()
    target = cache.path_for(record.identity)
    missing_target = tmp_path / "missing.json"
    _symlink_or_skip(target, missing_target)

    with pytest.raises(Stage4BError) as captured:
        cache.append(record)

    assert captured.value.code is Stage4BErrorCode.CACHE_PATH_ESCAPE
    assert os.path.lexists(target)
    assert not missing_target.exists()
    assert not any(path.name.endswith(".tmp") for path in cache.root.iterdir())


def test_safe_nested_cache_root_append_and_read(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "safe" / "nested" / "cache")
    record = _record()

    assert cache.append(record) == record
    assert cache.read(record.identity) == record


def test_primary_and_repeat_cache_entries_are_separate(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    primary = _record(InvocationRole.PRIMARY)
    repeat = _record(InvocationRole.REPEAT)

    cache.append(primary)
    cache.append(repeat)

    assert cache.path_for(primary.identity) != cache.path_for(repeat.identity)
    assert cache.read(primary.identity).identity.invocation_role is InvocationRole.PRIMARY
    assert cache.read(repeat.identity).identity.invocation_role is InvocationRole.REPEAT


def test_failed_atomic_install_removes_temporary_and_final_files(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ResponseCache(tmp_path / "cache")
    record = _record()

    def fail_install(temporary, target) -> None:
        raise OSError("fictional atomic-install failure")

    monkeypatch.setattr(cache_module, "_install_atomic", fail_install)
    with pytest.raises(Stage4BError) as captured:
        cache.append(record)

    assert captured.value.code is Stage4BErrorCode.CACHE_WRITE_FAILED
    assert not cache.path_for(record.identity).exists()
    assert list(cache.root.iterdir()) == []


def test_cache_serialization_contains_no_root_path_or_secret_fields(tmp_path) -> None:
    cache = ResponseCache(tmp_path / "fictional-machine-cache")
    record = _record()
    raw = cache_record_bytes(cache.append(record))

    assert str(tmp_path).encode() not in raw
    assert b"api_key" not in raw
    assert b"authorization" not in raw
    assert b"environment" not in raw
