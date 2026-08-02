"""Determinism and isolation tests for the offline Stage 4B mock."""

from __future__ import annotations

import json
import socket
import time

import pytest

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    DeterministicMockProvider,
    InvocationRole,
    LLMProvider,
    MockResponseFixture,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    Stage4BError,
    Stage4BErrorCode,
    build_request_envelope,
)


def _request():
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text="A fictional programme is active.",
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


def _abstention_json() -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-batch-001",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_mock_success_response_is_byte_stable_and_protocol_compatible() -> None:
    request = _request()
    fixture = MockResponseFixture(
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=_abstention_json(),
        token_usage=ProviderTokenUsage(input_tokens=20, output_tokens=10),
        latency_ms=7,
    )
    provider = DeterministicMockProvider(
        {request.canonical_request_sha256: fixture}
    )

    assert isinstance(provider, LLMProvider)
    first = provider.generate(request)
    second = provider.generate(request)
    assert first == second
    assert first.model_dump_json().encode("utf-8") == second.model_dump_json().encode(
        "utf-8"
    )
    assert first.raw_response == _abstention_json()


@pytest.mark.parametrize(
    "raw_response",
    (
        "{not-json",
        '{"schema_version":"0.1","source_ids":["S001"]}',
    ),
)
def test_mock_preserves_invalid_json_and_schema_invalid_success_fixtures(
    raw_response: str,
) -> None:
    request = _request()
    provider = DeterministicMockProvider(
        {
            request.canonical_request_sha256: MockResponseFixture(
                terminal_status=ProviderTerminalStatus.SUCCESS,
                raw_response=raw_response,
            )
        }
    )

    assert provider.generate(request).raw_response == raw_response


@pytest.mark.parametrize(
    ("status", "failure_code"),
    (
        (ProviderTerminalStatus.FAILURE, "fictional_provider_failure"),
        (ProviderTerminalStatus.TIMEOUT, "fictional_timeout"),
    ),
)
def test_mock_supports_explicit_terminal_failures(
    status: ProviderTerminalStatus,
    failure_code: str,
) -> None:
    request = _request()
    provider = DeterministicMockProvider(
        {
            request.canonical_request_sha256: MockResponseFixture(
                terminal_status=status,
                raw_response="",
                failure_codes=(failure_code,),
            )
        }
    )

    response = provider.generate(request)
    assert response.terminal_status is status
    assert response.failure_codes == (failure_code,)


def test_unknown_mock_request_fails_closed() -> None:
    with pytest.raises(Stage4BError) as captured:
        DeterministicMockProvider({}).generate(_request())

    assert captured.value.code is Stage4BErrorCode.MOCK_RESPONSE_NOT_FOUND


def test_mock_provider_attempts_no_network_sleep_or_environment_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    provider = DeterministicMockProvider(
        {
            request.canonical_request_sha256: MockResponseFixture(
                terminal_status=ProviderTerminalStatus.SUCCESS,
                raw_response=_abstention_json(),
            )
        }
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("deterministic mock attempted a forbidden runtime side effect")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(time, "sleep", forbidden)
    assert provider.generate(request).terminal_status is ProviderTerminalStatus.SUCCESS
