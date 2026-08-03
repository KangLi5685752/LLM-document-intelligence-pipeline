"""Mock-only Stage 4C runner tests with fictional in-memory evidence."""

from __future__ import annotations

import ast
import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    CacheIdentity,
    DeterministicMockProvider,
    ExecutionBudget,
    InvocationRole,
    LLMProviderResponse,
    MockResponseFixture,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ResponseCache,
    Stage4BError,
    Stage4BErrorCode,
    ValidationStatus,
    build_request_envelope,
    build_request_manifest,
    mock_run_report_bytes,
    run_mock_development,
)
from document_intelligence.llm_extraction.prompting import canonical_json_bytes


NOW = datetime(2026, 8, 3, 3, 0, tzinfo=timezone.utc)


def _request(
    request_id: str = "fictional-request-001",
    *,
    source_id: str = "S001",
    role: InvocationRole = InvocationRole.PRIMARY,
):
    block = ApprovedEvidenceBlock(
        source_id=source_id,
        evidence_id=f"fictional-evidence-{request_id}",
        block_id=f"fictional-block-{request_id}",
        sequence=1,
        text="The fictional delivery initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )
    return build_request_envelope(
        invocation_role=role,
        request_id=request_id,
        source_id=source_id,
        document_sha256=("A" if source_id == "S001" else "B") * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        evidence_blocks=(block,),
    )


def _payload(request, *, review_required: bool = False) -> dict[str, object]:
    evidence = request.evidence_blocks[0]
    return {
        "schema_version": "0.1",
        "batch_id": f"fictional-batch-{request.request_id}",
        "source_ids": [request.source_id],
        "entities": [],
        "evidence_references": [
            {
                "evidence_id": evidence.evidence_id,
                "source_id": request.source_id,
                "block_id": evidence.block_id,
                "location_type": "page",
                "location_value": "1",
                "text_excerpt": "The fictional delivery initiative is active.",
                "evidence_status": "supported",
            }
        ],
        "candidate_facts": [
            {
                "candidate_id": f"fictional-candidate-{request.request_id}",
                "source_id": request.source_id,
                "document_family": "fictional_delivery_note",
                "subject_text": "fictional delivery initiative",
                "subject_type": "initiative",
                "predicate": "status",
                "raw_value": "active",
                "normalized_value": "active",
                "value_type": "status",
                "qualifiers": {},
                "evidence_ids": [evidence.evidence_id],
                "confidence": 0.7,
                "review_status": "required" if review_required else "not_required",
                "extraction_method": "llm",
                "warnings": ["fictional_uncertainty"] if review_required else [],
            }
        ],
        "warnings": [],
    }


def _abstention(request) -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": f"fictional-batch-{request.request_id}",
            "source_ids": [request.source_id],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _provider(request, raw_response: str, **fixture_values):
    fixture = MockResponseFixture(
        terminal_status=fixture_values.pop(
            "terminal_status", ProviderTerminalStatus.SUCCESS
        ),
        raw_response=raw_response,
        **fixture_values,
    )
    return DeterministicMockProvider({request.canonical_request_sha256: fixture})


def _clock() -> datetime:
    return NOW


def test_successful_mock_execution_reconciles_report_and_provenance(tmp_path) -> None:
    request = _request()
    provider = _provider(
        request,
        _json(_payload(request, review_required=True)),
        token_usage=ProviderTokenUsage(input_tokens=12, output_tokens=6),
        latency_ms=8,
    )
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=provider,
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
        budget=ExecutionBudget(estimated_cost_per_attempt_usd=Decimal("0.10")),
    )

    assert report.invocation_total == 1
    assert report.cache_miss_count == 1
    assert report.provider_call_count == 1
    assert report.attempt_count == 1
    assert report.validation_success_count == 1
    assert report.review_required_output_count == 1
    assert report.total_reported_input_tokens == 12
    assert report.total_estimated_cost_usd == Decimal("0.10")
    provenance = report.ordered_invocation_provenance[0]
    assert provenance.validation_status is ValidationStatus.VALID
    assert provenance.provider_call_performed is True
    assert provenance.candidate_count == 1
    assert provenance.provider_identifier == "stage4b-deterministic-mock-provider"
    assert provenance.model_identifier == "stage4b-deterministic-mock-model"


def test_cache_miss_then_hit_performs_no_second_provider_call(tmp_path) -> None:
    request = _request()
    manifest = build_request_manifest((request,))
    cache = ResponseCache(tmp_path / "cache")
    first = run_mock_development(
        manifest=manifest,
        provider=_provider(request, _abstention(request)),
        cache=cache,
        clock=_clock,
    )
    second = run_mock_development(
        manifest=manifest,
        provider=DeterministicMockProvider({}),
        cache=cache,
        clock=lambda: NOW + timedelta(minutes=1),
    )

    assert first.cache_miss_count == 1
    assert second.cache_hit_count == 1
    assert second.provider_call_count == 0
    assert second.attempt_count == 0
    cached = second.ordered_invocation_provenance[0]
    assert cached.provider_call_performed is False
    assert cached.original_provider_call_timestamp == NOW
    assert cached.local_parse_event_timestamp == NOW + timedelta(minutes=1)
    assert cached.original_attempts == first.ordered_invocation_provenance[0].attempts


def test_cache_hit_retains_openai_style_metadata_without_provider_call(
    tmp_path,
) -> None:
    request = _request()
    base_response = _provider(request, _abstention(request)).generate(request)
    response_payload = base_response.model_dump(mode="python")
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

    class CountingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, generated_request):
            self.calls += 1
            assert generated_request == request
            return LLMProviderResponse.model_validate(response_payload)

    provider = CountingProvider()
    manifest = build_request_manifest((request,))
    cache = ResponseCache(tmp_path / "cache")
    first = run_mock_development(
        manifest=manifest,
        provider=provider,
        cache=cache,
        clock=_clock,
        budget=ExecutionBudget(estimated_cost_per_attempt_usd=Decimal("0.10")),
    )
    second = run_mock_development(
        manifest=manifest,
        provider=provider,
        cache=cache,
        clock=lambda: NOW + timedelta(minutes=1),
        budget=ExecutionBudget(estimated_cost_per_attempt_usd=Decimal("0.10")),
    )

    fresh = first.ordered_invocation_provenance[0]
    cached = second.ordered_invocation_provenance[0]
    assert provider.calls == 1
    assert fresh.provider_request_id == cached.provider_request_id == "req_fictional_001"
    assert fresh.provider_response_id == cached.provider_response_id == "resp_fictional_001"
    assert fresh.provider_sdk_version == cached.provider_sdk_version == "2.46.0"
    assert fresh.token_usage == cached.token_usage == ProviderTokenUsage(
        input_tokens=23, output_tokens=11
    )
    assert fresh.latency_ms == cached.latency_ms == 125
    assert cached.original_provider_call_timestamp == NOW
    assert cached.local_parse_event_timestamp == NOW + timedelta(minutes=1)
    assert cached.provider_call_performed is False
    assert cached.attempts == ()
    assert cached.original_attempts == fresh.attempts
    assert second.provider_call_count == 0
    assert second.attempt_count == 0
    assert second.total_estimated_cost_usd == Decimal("0")


def test_provider_failure_is_preserved_without_candidate_output(tmp_path) -> None:
    request = _request()
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(
            request,
            "",
            terminal_status=ProviderTerminalStatus.FAILURE,
            failure_codes=("fictional_terminal_failure",),
        ),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )

    assert report.provider_failure_count == 1
    assert report.validation_success_count == 0
    provenance = report.ordered_invocation_provenance[0]
    assert provenance.validation_status is ValidationStatus.NOT_ATTEMPTED
    assert provenance.parsed_output_sha256 is None
    assert provenance.candidate_count == 0


def test_timeout_is_explicit_and_can_be_configured_without_retry(tmp_path) -> None:
    request = _request()
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(
            request,
            "",
            terminal_status=ProviderTerminalStatus.TIMEOUT,
            failure_codes=("timeout",),
        ),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
        budget=ExecutionBudget(max_retries_per_invocation=0),
    )

    assert report.timeout_outcome_count == 1
    assert report.provider_call_count == 1


def test_typed_timeout_exception_is_counted_without_adapter_side_retry(
    tmp_path,
) -> None:
    request = _request()

    class TimeoutProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, generated_request):
            self.calls += 1
            assert generated_request == request
            raise Stage4BError(Stage4BErrorCode.TIMEOUT, "fictional timeout")

    provider = TimeoutProvider()
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=provider,
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
        budget=ExecutionBudget(max_retries_per_invocation=0),
    )

    provenance = report.ordered_invocation_provenance[0]
    assert provider.calls == 1
    assert report.timeout_outcome_count == 1
    assert report.provider_call_count == 1
    assert provenance.terminal_status is ProviderTerminalStatus.TIMEOUT
    assert provenance.attempts[0].terminal_status is ProviderTerminalStatus.TIMEOUT
    assert provenance.failure_codes == (Stage4BErrorCode.TIMEOUT.value,)


def test_one_retry_is_permitted_and_a_second_retry_never_occurs(tmp_path) -> None:
    request = _request()
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(
            request,
            "",
            terminal_status=ProviderTerminalStatus.TIMEOUT,
            failure_codes=("timeout",),
        ),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )

    provenance = report.ordered_invocation_provenance[0]
    assert report.provider_call_count == 2
    assert report.attempt_count == 2
    assert [item.attempt_number for item in provenance.attempts] == [1, 2]
    assert provenance.attempts[1].retry_reason == "timeout"


@pytest.mark.parametrize(
    ("raw_response", "expected_code"),
    (
        ("{not-json", Stage4BErrorCode.INVALID_JSON),
        ("{}", Stage4BErrorCode.SCHEMA_INVALID),
    ),
)
def test_invalid_json_and_schema_invalid_outputs_are_not_retried(
    tmp_path, raw_response: str, expected_code: Stage4BErrorCode
) -> None:
    request = _request()
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(request, raw_response),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )

    provenance = report.ordered_invocation_provenance[0]
    assert report.provider_call_count == 1
    assert report.validation_failure_count == 1
    assert provenance.failure_codes == (expected_code.value,)
    assert provenance.parsed_output_sha256 is None


def test_source_mismatch_is_preserved_without_retry(tmp_path) -> None:
    request = _request()
    payload = _payload(request)
    payload["source_ids"] = ["S002"]
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(request, _json(payload)),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )

    provenance = report.ordered_invocation_provenance[0]
    assert report.provider_call_count == 1
    assert provenance.failure_codes == (Stage4BErrorCode.SOURCE_MISMATCH.value,)


def test_unknown_evidence_reference_is_preserved_without_retry(tmp_path) -> None:
    request = _request()
    payload = _payload(request)
    payload["candidate_facts"] = []
    payload["evidence_references"][0]["evidence_id"] = "fictional-unknown"  # type: ignore[index]
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(request, _json(payload)),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )

    provenance = report.ordered_invocation_provenance[0]
    assert report.provider_call_count == 1
    assert provenance.failure_codes == (
        Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE.value,
    )


def test_cost_budget_stops_before_provider_or_cache_write(tmp_path) -> None:
    request = _request()
    cache = ResponseCache(tmp_path / "cache")
    with pytest.raises(Stage4BError) as captured:
        run_mock_development(
            manifest=build_request_manifest((request,)),
            provider=DeterministicMockProvider({}),
            cache=cache,
            clock=_clock,
            budget=ExecutionBudget(
                max_total_estimated_cost_usd=Decimal("25"),
                estimated_cost_per_attempt_usd=Decimal("26"),
            ),
        )

    assert captured.value.code is Stage4BErrorCode.COST_BUDGET_EXCEEDED
    assert list(cache.root.iterdir()) == []


@pytest.mark.parametrize(
    ("budget", "expected_code"),
    (
        (
            ExecutionBudget(max_primary_invocations=0),
            Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
        ),
        (
            ExecutionBudget(max_total_attempts=0),
            Stage4BErrorCode.ATTEMPT_BUDGET_EXCEEDED,
        ),
    ),
)
def test_request_and_attempt_budgets_stop_before_provider_call(
    tmp_path, budget: ExecutionBudget, expected_code: Stage4BErrorCode
) -> None:
    request = _request()
    cache = ResponseCache(tmp_path / expected_code.value)
    with pytest.raises(Stage4BError) as captured:
        run_mock_development(
            manifest=build_request_manifest((request,)),
            provider=DeterministicMockProvider({}),
            cache=cache,
            clock=_clock,
            budget=budget,
        )

    assert captured.value.code is expected_code
    assert list(cache.root.iterdir()) == []


def test_provider_side_retry_is_rejected(tmp_path) -> None:
    request = _request()
    with pytest.raises(Stage4BError) as captured:
        run_mock_development(
            manifest=build_request_manifest((request,)),
            provider=_provider(
                request,
                _abstention(request),
                retry_count=1,
            ),
            cache=ResponseCache(tmp_path / "cache"),
            clock=_clock,
        )

    assert captured.value.code is Stage4BErrorCode.RETRY_NOT_PERMITTED


def test_cache_integrity_failure_stops_before_provider_invocation(tmp_path) -> None:
    request = _request()
    manifest = build_request_manifest((request,))
    cache = ResponseCache(tmp_path / "cache")
    run_mock_development(
        manifest=manifest,
        provider=_provider(request, _abstention(request)),
        cache=cache,
        clock=_clock,
    )
    target = cache.path_for(CacheIdentity.from_request(request))
    payload = json.loads(target.read_bytes())
    payload["response"]["raw_response"] = "tampered"
    target.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        run_mock_development(
            manifest=manifest,
            provider=DeterministicMockProvider({}),
            cache=cache,
            clock=_clock,
        )
    assert captured.value.code is Stage4BErrorCode.CACHE_HASH_MISMATCH


def test_identical_fictional_execution_produces_identical_report_bytes(
    tmp_path,
) -> None:
    request = _request()
    manifest = build_request_manifest((request,))
    first = run_mock_development(
        manifest=manifest,
        provider=_provider(request, _abstention(request)),
        cache=ResponseCache(tmp_path / "first-cache"),
        clock=_clock,
    )
    second = run_mock_development(
        manifest=manifest,
        provider=_provider(request, _abstention(request)),
        cache=ResponseCache(tmp_path / "second-cache"),
        clock=_clock,
    )

    assert mock_run_report_bytes(first) == mock_run_report_bytes(second)
    assert first.abstention_count == 1


def test_runner_uses_no_network(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Stage 4C mock execution attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    report = run_mock_development(
        manifest=build_request_manifest((request,)),
        provider=_provider(request, _abstention(request)),
        cache=ResponseCache(tmp_path / "cache"),
        clock=_clock,
    )
    assert report.successful_terminal_response_count == 1


def test_stage_4c_modules_import_no_gold_matcher_or_document_execution() -> None:
    root = Path(__file__).parents[1] / "src/document_intelligence/llm_extraction"
    modules = ("manifest.py", "cache.py", "provenance.py", "runner.py")
    imported: set[str] = set()
    for name in modules:
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imported.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        imported.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

    assert not any(
        forbidden in module
        for module in imported
        for forbidden in (
            "annotations",
            "matching",
            "baseline_gold",
            "ParsedDocument",
            "deterministic",
        )
    )
