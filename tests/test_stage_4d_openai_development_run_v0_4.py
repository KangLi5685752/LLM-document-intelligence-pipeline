"""Offline tests for the compact bounded Stage 4D v0.4 development run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
    SourceLocation,
)
from document_intelligence.llm_extraction.cache import (
    V0_3_OPENAI_CACHE_ROOT,
    V0_4_OPENAI_CACHE_ROOT,
    ResponseCache,
    build_cache_record,
    cache_identity_from_request,
)
from document_intelligence.llm_extraction.contracts import (
    InvocationRole,
    LLMExtractionRequestV04,
    LLMProviderResponse,
    OUTPUT_CONTRACT_ID_V0_4,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
from document_intelligence.llm_extraction.openai_development_run_v0_4 import (
    EXECUTION_ARTIFACT_ROOT,
    EXECUTION_CONFIRMATION,
    EXPECTED_REQUEST_IDS,
    MAXIMUM_PROVIDER_CALLS,
    MAXIMUM_RETRIES,
    MAXIMUM_TOTAL_ATTEMPTS,
    authorization_bytes_v0_4,
    build_development_authorization_v0_4,
    build_development_requests_v0_4,
    execute_development_run_v0_4,
    prepare_development_run_v0_4,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.provenance import AttemptProvenance
from document_intelligence.llm_extraction import openai_development_run_v0_4_cli
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_MODEL_CONFIGURATION_ID_V0_4,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
)
from document_intelligence.llm_extraction.validation import (
    validate_provider_output_v0_4,
)


_HEAD = "a" * 40
_SOURCE_BLOCK_COUNTS = {
    "S001": 26,
    "S002": 22,
    "S003": 16,
    "S004": 118,
    "S006": 61,
}


def _document(source_id: str, block_count: int) -> ParsedDocument:
    return ParsedDocument(
        document_id=f"fictional-{source_id}",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=f"fictional-{source_id}.pdf",
        checksum_sha256=(source_id[-1] * 64),
        blocks=[
            DocumentBlock(
                block_id=f"DOC-{source_id}-B{sequence:04d}",
                sequence=sequence,
                block_type=BlockType.PAGE_TEXT,
                text=f"Fictional {source_id} statement {sequence}.",
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value=str(sequence),
                    page_number=sequence,
                ),
            )
            for sequence in range(1, block_count + 1)
        ],
        parse_status=ParseStatus.SUCCESS,
    )


@pytest.fixture
def fictional_documents() -> dict[str, ParsedDocument]:
    return {
        source_id: _document(source_id, block_count)
        for source_id, block_count in _SOURCE_BLOCK_COUNTS.items()
    }


def _semantic_response(
    request: LLMExtractionRequestV04,
    *,
    evidence_id: str | None = None,
) -> LLMProviderResponse:
    selected_evidence_id = evidence_id or request.evidence_blocks[0].evidence_id
    raw_response = json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": f"fictional-{request.request_id}",
            "entities": [],
            "candidate_facts": [
                {
                    "candidate_id": f"candidate-{request.request_id}",
                    "document_family": "fictional-policy",
                    "subject_text": "Fictional programme",
                    "subject_type": "programme",
                    "predicate": "status",
                    "raw_value": "active",
                    "normalized_value": "active",
                    "value_type": "status",
                    "qualifiers": {},
                    "evidence_ids": [selected_evidence_id],
                    "confidence": 0.8,
                    "review_status": "required",
                    "warnings": [],
                }
            ],
            "warnings": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="fictional-provider",
        model_identifier="fictional-model",
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw_response,
        raw_response_sha256=uppercase_sha256(raw_response),
        token_usage=ProviderTokenUsage(input_tokens=100, output_tokens=50),
        latency_ms=1,
        retry_count=0,
    )


def _authorization_path(
    root: Path,
    documents: dict[str, ParsedDocument],
) -> Path:
    readiness = prepare_development_run_v0_4(
        repository_root=root,
        repository_head_sha=_HEAD,
        documents=documents,
    )
    authorization = build_development_authorization_v0_4(
        spec=readiness.spec,
        authorization_id="fictional-owner-authorization-v0.4",
        project_owner_identity="Fictional Project Owner",
    )
    path = root / "fictional-authorization.json"
    path.write_bytes(authorization_bytes_v0_4(authorization))
    return path


def _self_hashed_bytes(payload: dict[str, object], hash_field: str) -> bytes:
    return canonical_json_bytes(
        {
            **payload,
            hash_field: uppercase_sha256_bytes(canonical_json_bytes(payload)),
        }
    )


def _seed_historical_local_failure(
    root: Path,
    documents: dict[str, ParsedDocument],
    *,
    failure_stage: str = "local_validation",
    error_code: str = "schema_invalid",
) -> dict[str, Path]:
    historical = prepare_development_run_v0_4(
        repository_root=root,
        repository_head_sha="b" * 40,
        documents=documents,
    )
    authorization = build_development_authorization_v0_4(
        spec=historical.spec,
        authorization_id="fictional-historical-authorization-v0.4",
        project_owner_identity="Fictional Historical Owner",
    )
    request = historical.requests[0]
    invocation = historical.spec.invocations[0]
    identity = cache_identity_from_request(request)
    response = _semantic_response(request)
    cache = ResponseCache(root / V0_4_OPENAI_CACHE_ROOT)
    record = cache.append(
        build_cache_record(
            identity=identity,
            response=response,
            original_provider_call_timestamp=datetime(
                2026, 8, 11, 10, 0, tzinfo=timezone.utc
            ),
            original_attempts=(
                AttemptProvenance(
                    attempt_number=1,
                    terminal_status=ProviderTerminalStatus.SUCCESS,
                    provider_call_performed=True,
                    response_sha256=response.raw_response_sha256,
                    latency_ms=response.latency_ms,
                ),
            ),
            estimated_cost_usd=Decimal("0.0003"),
        )
    )
    cache_path = cache.path_for(record.identity)
    marker_path = root / EXECUTION_ARTIFACT_ROOT / "attempts" / (
        f"{invocation.cache_identity_sha256}.attempt.json"
    )
    failure_path = root / EXECUTION_ARTIFACT_ROOT / "failures" / (
        f"{invocation.cache_identity_sha256}.failure.json"
    )
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    common = {
        "execution_id": historical.spec.execution_id,
        "run_spec_sha256": historical.spec.run_spec_sha256,
        "authorization_sha256": authorization.authorization_sha256,
        "request_id": request.request_id,
        "cache_identity_sha256": invocation.cache_identity_sha256,
    }
    marker_path.write_bytes(
        _self_hashed_bytes(
            {"marker_schema_version": "0.1", **common},
            "marker_sha256",
        )
    )
    failure_path.write_bytes(
        _self_hashed_bytes(
            {
                "failure_schema_version": "0.1",
                **common,
                "failure_stage": failure_stage,
                "error_code": error_code,
            },
            "failure_sha256",
        )
    )
    return {
        "cache": cache_path,
        "marker": marker_path,
        "failure": failure_path,
    }


def _path_snapshot(path: Path) -> tuple[bool, bytes | None]:
    return path.exists(), path.read_bytes() if path.is_file() else None


def test_exact_seven_primary_v0_4_requests_are_constructed(
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    requests = build_development_requests_v0_4(fictional_documents)

    assert tuple(request.request_id for request in requests) == EXPECTED_REQUEST_IDS
    assert tuple(request.source_id for request in requests) == (
        "S001",
        "S002",
        "S003",
        "S004",
        "S004",
        "S004",
        "S006",
    )
    assert all(type(request) is LLMExtractionRequestV04 for request in requests)
    assert all(request.invocation_role is InvocationRole.PRIMARY for request in requests)
    assert all("repeat" not in request.request_id for request in requests)
    assert all(request.source_id not in {"S005", "S007"} for request in requests)
    assert all(
        request.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID_V0_4
        and request.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID_V0_4
        and request.prompt_version == "0.4"
        and request.output_contract_id == OUTPUT_CONTRACT_ID_V0_4
        for request in requests
    )


def test_offline_readiness_reports_exact_bounded_inventory(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    readiness = prepare_development_run_v0_4(
        repository_root=tmp_path,
        repository_head_sha=_HEAD,
        documents=fictional_documents,
    )
    spec = readiness.spec

    assert spec.repository_head_sha == _HEAD
    assert tuple(item.request_id for item in spec.invocations) == EXPECTED_REQUEST_IDS
    assert all(item.canonical_request_sha256 for item in spec.invocations)
    assert all(item.prompt_sha256 for item in spec.invocations)
    assert all(item.provider_payload_sha256 for item in spec.invocations)
    assert spec.strict_schema_sha256
    assert spec.maximum_provider_calls == MAXIMUM_PROVIDER_CALLS == 7
    assert spec.maximum_total_attempts == MAXIMUM_TOTAL_ATTEMPTS == 7
    assert spec.maximum_retries == MAXIMUM_RETRIES == 0
    assert spec.maximum_output_tokens_per_call == 4096
    assert spec.aggregate_conservative_cost_ceiling_usd <= spec.cost_cap_usd
    assert spec.cache_root == V0_4_OPENAI_CACHE_ROOT
    assert spec.execution_artifact_root == EXECUTION_ARTIFACT_ROOT
    assert "v0.3" not in spec.cache_root
    assert "v0.3" not in spec.execution_artifact_root


def test_default_cli_performs_zero_credential_client_or_provider_activity(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
    capsys: pytest.CaptureFixture[str],
) -> None:
    counters = {"key": 0, "client": 0, "provider": 0}

    def forbidden_key() -> str:
        counters["key"] += 1
        raise AssertionError("credential access is forbidden in readiness")

    def forbidden_client(value: str) -> object:
        del value
        counters["client"] += 1
        raise AssertionError("client construction is forbidden in readiness")

    def forbidden_provider(
        client: object, request: LLMExtractionRequestV04
    ) -> LLMProviderResponse:
        del client, request
        counters["provider"] += 1
        raise AssertionError("provider access is forbidden in readiness")

    result = openai_development_run_v0_4_cli._run_cli(
        ["--repository-root", str(tmp_path)],
        documents=fictional_documents,
        repository_head_sha=_HEAD,
        api_key_reader=forbidden_key,
        client_factory=forbidden_client,
        provider_call=forbidden_provider,
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["mode"] == "readiness"
    assert payload["run_spec"]["maximum_provider_calls"] == 7
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert not (tmp_path / V0_4_OPENAI_CACHE_ROOT).exists()
    assert not (tmp_path / EXECUTION_ARTIFACT_ROOT).exists()


@pytest.mark.parametrize(
    ("execute_real", "confirmation"),
    ((False, EXECUTION_CONFIRMATION), (True, "wrong-confirmation")),
)
def test_real_mode_requires_both_gates_before_credential_access(
    tmp_path: Path,
    execute_real: bool,
    confirmation: str,
) -> None:
    counters = {"key": 0, "client": 0, "provider": 0}

    def forbidden_key() -> str:
        counters["key"] += 1
        raise AssertionError("credential boundary was reached")

    with pytest.raises(Stage4BError) as error:
        execute_development_run_v0_4(
            repository_root=tmp_path,
            authorization_path=None,
            execute_real_development=execute_real,
            confirmation=confirmation,
            api_key_reader=forbidden_key,
            client_factory=lambda value: counters.__setitem__("client", 1),
            provider_call=lambda client, request: counters.__setitem__("provider", 1),  # type: ignore[arg-type,return-value]
        )

    assert error.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert not (tmp_path / V0_4_OPENAI_CACHE_ROOT).exists()
    assert not (tmp_path / EXECUTION_ARTIFACT_ROOT).exists()


def test_authorization_must_bind_exact_run_spec_before_credential_access(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    credential_reads = 0

    def forbidden_key() -> str:
        nonlocal credential_reads
        credential_reads += 1
        raise AssertionError("credential boundary was reached")

    with pytest.raises(Stage4BError) as error:
        execute_development_run_v0_4(
            repository_root=tmp_path,
            authorization_path=authorization_path,
            execute_real_development=True,
            confirmation=EXECUTION_CONFIRMATION,
            repository_head_sha="b" * 40,
            documents=fictional_documents,
            api_key_reader=forbidden_key,
        )

    assert error.value.code is Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID
    assert credential_reads == 0
    assert not (tmp_path / V0_4_OPENAI_CACHE_ROOT).exists()
    assert not (tmp_path / EXECUTION_ARTIFACT_ROOT).exists()


def test_bound_fake_run_hydrates_all_outputs_and_uses_new_cache(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    counters = {"key": 0, "client": 0, "provider": 0}

    def fake_key() -> str:
        counters["key"] += 1
        return "sk-proj-" + "A" * 120

    def fake_client(value: str) -> object:
        assert value.startswith("sk-proj-")
        counters["client"] += 1
        return object()

    def fake_provider(
        client: object, request: LLMExtractionRequestV04
    ) -> LLMProviderResponse:
        assert client is not None
        counters["provider"] += 1
        return _semantic_response(request)

    result = execute_development_run_v0_4(
        repository_root=tmp_path,
        authorization_path=authorization_path,
        execute_real_development=True,
        confirmation=EXECUTION_CONFIRMATION,
        repository_head_sha=_HEAD,
        documents=fictional_documents,
        clock=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        api_key_reader=fake_key,
        client_factory=fake_client,
        provider_call=fake_provider,
    )

    assert result.provider_call_count == 7
    assert result.cache_hit_count == 0
    assert counters == {"key": 7, "client": 7, "provider": 7}
    assert len(result.output_paths) == 7
    for path, request in zip(result.output_paths, result.readiness.requests, strict=True):
        payload = json.loads(path.read_bytes())
        assert payload["source_ids"] == [request.source_id]
        assert payload["candidate_facts"][0]["evidence_ids"] == [
            request.evidence_blocks[0].evidence_id
        ]
        assert payload["evidence_references"][0]["block_id"] == (
            request.evidence_blocks[0].block_id
        )
    assert result.execution_record_path.is_file()
    assert (tmp_path / V0_4_OPENAI_CACHE_ROOT).is_dir()
    assert not (tmp_path / V0_3_OPENAI_CACHE_ROOT).exists()


def test_matching_historical_local_failure_recovers_cache_then_uses_six_calls(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    source_text = "A" * 239 + " " + "fictional suffix"
    fictional_documents["S001"].blocks[0].text = source_text
    historical_paths = _seed_historical_local_failure(
        tmp_path, fictional_documents
    )
    historical_bytes = {
        name: path.read_bytes() for name, path in historical_paths.items()
    }
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    counters = {"key": 0, "client": 0}
    provider_requests: list[str] = []

    def fake_key() -> str:
        counters["key"] += 1
        return "sk-proj-" + "A" * 120

    def fake_client(value: str) -> object:
        assert value.startswith("sk-proj-")
        counters["client"] += 1
        return object()

    def fake_provider(
        client: object, request: LLMExtractionRequestV04
    ) -> LLMProviderResponse:
        assert client is not None
        provider_requests.append(request.request_id)
        return _semantic_response(request)

    result = execute_development_run_v0_4(
        repository_root=tmp_path,
        authorization_path=authorization_path,
        execute_real_development=True,
        confirmation=EXECUTION_CONFIRMATION,
        repository_head_sha=_HEAD,
        documents=fictional_documents,
        clock=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        api_key_reader=fake_key,
        client_factory=fake_client,
        provider_call=fake_provider,
    )

    record = json.loads(result.execution_record_path.read_bytes())
    recovered_output = json.loads(result.output_paths[0].read_bytes())
    excerpt = recovered_output["evidence_references"][0]["text_excerpt"]
    assert result.provider_call_count == 6
    assert result.cache_hit_count == 1
    assert counters == {"key": 6, "client": 6}
    assert provider_requests == list(EXPECTED_REQUEST_IDS[1:])
    assert record["outcomes"][0]["cache_status"] == "recovered_cache"
    assert excerpt == source_text.strip()[:240].rstrip()
    assert excerpt == excerpt.strip()
    assert all(
        path.read_bytes() == historical_bytes[name]
        for name, path in historical_paths.items()
    )


@pytest.mark.parametrize(
    ("failure_stage", "error_code"),
    (
        ("provider_call", "schema_invalid"),
        ("cache_install", "schema_invalid"),
        ("credential_access", "schema_invalid"),
        ("local_validation", "unknown_evidence_reference"),
    ),
)
def test_only_historical_local_validation_schema_failure_is_recoverable(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
    failure_stage: str,
    error_code: str,
) -> None:
    historical_paths = _seed_historical_local_failure(
        tmp_path,
        fictional_documents,
        failure_stage=failure_stage,
        error_code=error_code,
    )
    historical_bytes = {
        name: path.read_bytes() for name, path in historical_paths.items()
    }
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    counters = {"key": 0, "client": 0, "provider": 0}

    with pytest.raises(Stage4BError) as error:
        execute_development_run_v0_4(
            repository_root=tmp_path,
            authorization_path=authorization_path,
            execute_real_development=True,
            confirmation=EXECUTION_CONFIRMATION,
            repository_head_sha=_HEAD,
            documents=fictional_documents,
            api_key_reader=lambda: counters.__setitem__("key", 1),  # type: ignore[arg-type,return-value]
            client_factory=lambda value: counters.__setitem__("client", 1),
            provider_call=lambda client, request: counters.__setitem__("provider", 1),  # type: ignore[arg-type,return-value]
        )

    assert error.value.code is Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert all(
        path.read_bytes() == historical_bytes[name]
        for name, path in historical_paths.items()
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "malformed_marker",
        "mismatched_failure",
        "malformed_cache",
        "missing_marker",
        "missing_cache",
    ),
)
def test_malformed_mismatched_or_incomplete_history_fails_closed(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
    mutation: str,
) -> None:
    historical_paths = _seed_historical_local_failure(
        tmp_path, fictional_documents
    )
    if mutation == "malformed_marker":
        historical_paths["marker"].write_bytes(b"{}")
    elif mutation == "mismatched_failure":
        payload = json.loads(historical_paths["failure"].read_bytes())
        payload.pop("failure_sha256")
        payload["request_id"] = "llm-v0.4-S002-primary-001"
        historical_paths["failure"].write_bytes(
            _self_hashed_bytes(payload, "failure_sha256")
        )
    elif mutation == "malformed_cache":
        historical_paths["cache"].write_bytes(b"{}")
    elif mutation == "missing_marker":
        historical_paths["marker"].unlink()
    else:
        historical_paths["cache"].unlink()
    mutated_state = {
        name: _path_snapshot(path) for name, path in historical_paths.items()
    }
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    counters = {"key": 0, "client": 0, "provider": 0}

    with pytest.raises(Stage4BError):
        execute_development_run_v0_4(
            repository_root=tmp_path,
            authorization_path=authorization_path,
            execute_real_development=True,
            confirmation=EXECUTION_CONFIRMATION,
            repository_head_sha=_HEAD,
            documents=fictional_documents,
            api_key_reader=lambda: counters.__setitem__("key", 1),  # type: ignore[arg-type,return-value]
            client_factory=lambda value: counters.__setitem__("client", 1),
            provider_call=lambda client, request: counters.__setitem__("provider", 1),  # type: ignore[arg-type,return-value]
        )

    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert {
        name: _path_snapshot(path) for name, path in historical_paths.items()
    } == mutated_state


def test_unknown_evidence_is_cached_then_fails_closed_without_second_call(
    tmp_path: Path,
    fictional_documents: dict[str, ParsedDocument],
) -> None:
    authorization_path = _authorization_path(tmp_path, fictional_documents)
    calls: list[str] = []

    def fake_provider(
        client: object, request: LLMExtractionRequestV04
    ) -> LLMProviderResponse:
        del client
        calls.append(request.request_id)
        return _semantic_response(request, evidence_id="fictional-unknown-evidence")

    with pytest.raises(Stage4BError) as error:
        execute_development_run_v0_4(
            repository_root=tmp_path,
            authorization_path=authorization_path,
            execute_real_development=True,
            confirmation=EXECUTION_CONFIRMATION,
            repository_head_sha=_HEAD,
            documents=fictional_documents,
            clock=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
            api_key_reader=lambda: "sk-proj-" + "A" * 120,
            client_factory=lambda value: object(),
            provider_call=fake_provider,
            local_validator=validate_provider_output_v0_4,
        )

    first_request = build_development_requests_v0_4(fictional_documents)[0]
    cached = ResponseCache(tmp_path / V0_4_OPENAI_CACHE_ROOT).read(
        cache_identity_from_request(first_request)
    )
    assert error.value.code is Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE
    assert calls == [EXPECTED_REQUEST_IDS[0]]
    assert cached.response.raw_response_sha256
    assert not list(
        (tmp_path / EXECUTION_ARTIFACT_ROOT / "outputs").glob("*.json")
    )
    assert len(
        list((tmp_path / EXECUTION_ARTIFACT_ROOT / "failures").glob("*.json"))
    ) == 1
