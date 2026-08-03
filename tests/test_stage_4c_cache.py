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
    MockResponseFixture,
    ProviderTerminalStatus,
    ResponseCache,
    Stage4BError,
    Stage4BErrorCode,
    build_cache_record,
    build_request_envelope,
    cache_record_bytes,
)
from document_intelligence.llm_extraction.prompting import canonical_json_bytes


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
