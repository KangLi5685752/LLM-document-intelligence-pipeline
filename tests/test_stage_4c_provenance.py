"""Stage 4C provenance and deterministic report contract tests."""

from __future__ import annotations

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
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ValidationStatus,
    build_mock_run_report,
    mock_run_report_bytes,
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


def test_invocation_provenance_is_complete_and_separates_cache_parse_event() -> None:
    fresh = _provenance()
    cached = _provenance(hit=True)

    assert fresh.provider_call_performed is True
    assert cached.provider_call_performed is False
    assert cached.attempts == ()
    assert cached.original_attempts == fresh.original_attempts
    assert cached.original_provider_call_timestamp == CALL_TIME
    assert cached.local_parse_event_timestamp > cached.original_provider_call_timestamp


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
