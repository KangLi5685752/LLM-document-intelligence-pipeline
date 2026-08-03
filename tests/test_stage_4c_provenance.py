"""Stage 4C provenance and deterministic report contract tests."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction import (
    AttemptProvenance,
    CacheStatus,
    InvocationProvenance,
    InvocationRole,
    MockRunReport,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ValidationStatus,
    build_mock_run_report,
    mock_run_report_bytes,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


CALL_TIME = datetime(2026, 8, 3, 2, 0, tzinfo=timezone.utc)
PARSE_TIME = datetime(2026, 8, 3, 2, 1, tzinfo=timezone.utc)


def _attempt() -> AttemptProvenance:
    return AttemptProvenance(
        attempt_number=1,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        provider_call_performed=True,
        response_sha256="A" * 64,
        latency_ms=5,
    )


def _provenance(*, hit: bool = False) -> InvocationProvenance:
    attempt = _attempt()
    return InvocationProvenance(
        manifest_sha256="B" * 64,
        request_id="fictional-request-hit" if hit else "fictional-request-fresh",
        invocation_role=InvocationRole.REPEAT if hit else InvocationRole.PRIMARY,
        source_id="S001",
        provider_identifier="stage4b-deterministic-mock-provider",
        model_identifier="stage4b-deterministic-mock-model",
        canonical_request_sha256="C" * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        prompt_sha256="D" * 64,
        document_sha256="E" * 64,
        cache_status=CacheStatus.HIT if hit else CacheStatus.MISS,
        provider_call_performed=not hit,
        attempts=() if hit else (attempt,),
        original_attempts=(attempt,),
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response_sha256="A" * 64,
        parsed_output_sha256="F" * 64,
        validation_status=ValidationStatus.VALID,
        warning_codes=("fictional_warning",),
        token_usage=ProviderTokenUsage(input_tokens=10, output_tokens=4),
        estimated_cost_usd=Decimal("0.50"),
        latency_ms=5,
        original_provider_call_timestamp=CALL_TIME,
        local_parse_event_timestamp=(
            PARSE_TIME + timedelta(minutes=1) if hit else PARSE_TIME
        ),
        candidate_count=0,
        review_required_candidate_count=0,
        abstained=True,
    )


def _provenance_with_provider_metadata() -> InvocationProvenance:
    payload = _provenance().model_dump(mode="python")
    payload.update(
        {
            "provider_identifier": "openai",
            "model_identifier": "gpt-5.4-mini-fictional-snapshot",
            "provider_request_id": "req_fictional_001",
            "provider_response_id": "resp_fictional_001",
            "provider_sdk_version": "2.46.0",
        }
    )
    return InvocationProvenance.model_validate(payload)


def _legacy_report_bytes() -> bytes:
    legacy_invocation = _provenance().model_dump(
        mode="json",
        exclude={
            "provider_request_id",
            "provider_response_id",
            "provider_sdk_version",
        },
    )
    assert not {
        "provider_request_id",
        "provider_response_id",
        "provider_sdk_version",
    } & set(legacy_invocation)
    payload = {
        "report_schema_version": "0.1",
        "experiment_id": "llm-extraction-baseline-v0.1",
        "manifest_sha256": "B" * 64,
        "invocation_total": 1,
        "primary_invocation_count": 1,
        "repeat_invocation_count": 0,
        "cache_hit_count": 0,
        "cache_miss_count": 1,
        "provider_call_count": 1,
        "attempt_count": 1,
        "successful_terminal_response_count": 1,
        "provider_failure_count": 0,
        "timeout_outcome_count": 0,
        "validation_success_count": 1,
        "validation_failure_count": 0,
        "abstention_count": 1,
        "review_required_output_count": 0,
        "total_reported_input_tokens": 10,
        "total_reported_output_tokens": 4,
        "total_estimated_cost_usd": "0.50",
        "ordered_invocation_provenance": [legacy_invocation],
    }
    payload["report_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )
    return canonical_json_bytes(payload)


def test_invocation_provenance_is_complete_and_separates_cache_parse_event() -> None:
    fresh = _provenance()
    cached = _provenance(hit=True)

    assert fresh.provider_call_performed is True
    assert cached.provider_call_performed is False
    assert cached.attempts == ()
    assert cached.original_attempts == fresh.original_attempts
    assert cached.original_provider_call_timestamp == CALL_TIME
    assert cached.local_parse_event_timestamp > cached.original_provider_call_timestamp


def test_provenance_serializes_explicit_provider_identity_metadata() -> None:
    provenance = _provenance_with_provider_metadata()
    report = build_mock_run_report(
        manifest_sha256="B" * 64, invocations=(provenance,)
    )
    raw = mock_run_report_bytes(report)

    assert provenance.provider_request_id == "req_fictional_001"
    assert provenance.provider_response_id == "resp_fictional_001"
    assert provenance.provider_sdk_version == "2.46.0"
    assert b'"provider_request_id":"req_fictional_001"' in raw
    assert b'"provider_response_id":"resp_fictional_001"' in raw
    assert b'"provider_sdk_version":"2.46.0"' in raw


def test_pre_metadata_legacy_report_remains_hash_valid() -> None:
    legacy_bytes = _legacy_report_bytes()

    report = MockRunReport.model_validate_json(legacy_bytes)
    provenance = report.ordered_invocation_provenance[0]

    assert provenance.provider_request_id is None
    assert provenance.provider_response_id is None
    assert provenance.provider_sdk_version is None
    assert mock_run_report_bytes(report) == legacy_bytes


@pytest.mark.parametrize(
    "field_name",
    ("provider_request_id", "provider_response_id", "provider_sdk_version"),
)
def test_present_provider_metadata_is_covered_by_report_hash(
    field_name: str,
) -> None:
    report = build_mock_run_report(
        manifest_sha256="B" * 64,
        invocations=(_provenance_with_provider_metadata(),),
    )
    payload = json.loads(mock_run_report_bytes(report))
    payload["ordered_invocation_provenance"][0][field_name] = (
        f"tampered-{field_name}"
    )

    with pytest.raises(ValidationError, match="report_sha256"):
        MockRunReport.model_validate_json(canonical_json_bytes(payload))


@pytest.mark.parametrize(
    "timestamp",
    (
        datetime(2026, 8, 3, 2, 0),
        datetime(2026, 8, 3, 10, 0, tzinfo=timezone(timedelta(hours=8))),
    ),
)
def test_provenance_rejects_non_utc_timestamps(timestamp: datetime) -> None:
    payload = _provenance().model_dump(mode="python")
    payload["local_parse_event_timestamp"] = timestamp
    with pytest.raises(ValidationError, match="must"):
        InvocationProvenance.model_validate(payload)


def test_report_reconciles_calls_attempts_tokens_cost_and_outcomes() -> None:
    report = build_mock_run_report(
        manifest_sha256="B" * 64,
        invocations=(_provenance(), _provenance(hit=True)),
    )

    assert report.invocation_total == 2
    assert report.primary_invocation_count == 1
    assert report.repeat_invocation_count == 1
    assert report.cache_hit_count == 1
    assert report.cache_miss_count == 1
    assert report.provider_call_count == 1
    assert report.attempt_count == 1
    assert report.validation_success_count == 2
    assert report.abstention_count == 2
    assert report.total_reported_input_tokens == 20
    assert report.total_reported_output_tokens == 8
    assert report.total_estimated_cost_usd == Decimal("0.50")


def test_report_bytes_and_hash_are_deterministic() -> None:
    invocations = (_provenance(), _provenance(hit=True))
    first = build_mock_run_report(
        manifest_sha256="B" * 64, invocations=invocations
    )
    second = build_mock_run_report(
        manifest_sha256="B" * 64, invocations=invocations
    )

    assert mock_run_report_bytes(first) == mock_run_report_bytes(second)
    assert re.fullmatch(r"[0-9A-F]{64}", first.report_sha256)


def test_report_rejects_count_or_hash_drift() -> None:
    report = build_mock_run_report(
        manifest_sha256="B" * 64, invocations=(_provenance(),)
    )
    payload = report.model_dump(mode="python")
    payload["provider_call_count"] = 9
    with pytest.raises(ValidationError, match="does not reconcile"):
        type(report).model_validate(payload)

    payload = report.model_dump(mode="python")
    payload["report_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="report_sha256"):
        type(report).model_validate(payload)


def test_provenance_contains_no_owner_metrics_paths_or_secrets() -> None:
    report = build_mock_run_report(
        manifest_sha256="B" * 64, invocations=(_provenance(),)
    )
    raw = mock_run_report_bytes(report)

    for forbidden in (
        b"precision",
        b"recall",
        b"f1",
        b'"true_positive"',
        b"owner_judgment",
        b"gold",
        b"api_key",
        b"authorization",
        b"C:\\",
        b"/Users/",
    ):
        assert forbidden not in raw
