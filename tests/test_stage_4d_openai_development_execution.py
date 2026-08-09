"""Offline tests for the bounded Stage 4D OpenAI development transaction."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    openai_development_execution as execution,
)
from document_intelligence.llm_extraction.cache import (
    CacheIdentity,
    ResponseCache,
    build_cache_record,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    ApprovedEvidenceBlock,
    LLMExtractionRequest,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ValidatedCandidateOutput,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_development_execution import (
    EXECUTION_CONFIRMATION,
    OpenAIDevelopmentExecutionAuthorizationV01,
    OpenAIDevelopmentExecutionRecordV01,
    PreparedDevelopmentInvocation,
    development_authorization_bytes,
    execution_record_bytes,
    load_development_attempt_marker,
    load_development_execution_record,
    load_development_failure_record,
)
from document_intelligence.llm_extraction.openai_development_execution_plan import (
    OpenAIDevelopmentExecutionPlanV01,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentManifestV01,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
    ProviderPublicMetadataEntry,
    ProviderVersionIdentifier,
)
from document_intelligence.llm_extraction.openai_provider import (
    OpenAIProviderFailure,
    OpenAIProviderFailureDiagnostics,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.provenance import AttemptProvenance


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLAN_SOURCE = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_execution_plan/"
    "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.1.json"
)
MANIFEST_SOURCE = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
)
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
FICTIONAL_CREDENTIAL = "sk-" + "FictionalProjectCredential_" * 6


def _frozen_models() -> tuple[
    OpenAIDevelopmentExecutionPlanV01,
    OpenAIDevelopmentManifestV01,
]:
    return (
        OpenAIDevelopmentExecutionPlanV01.model_validate_json(
            PLAN_SOURCE.read_bytes()
        ),
        OpenAIDevelopmentManifestV01.model_validate_json(
            MANIFEST_SOURCE.read_bytes()
        ),
    )


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "fictional-repository"
    plan_target = root.joinpath(*execution.EXECUTION_PLAN_RELATIVE_PATH.parts)
    manifest_target = root.joinpath(
        *Path(execution.MANIFEST_RELATIVE_PATH).parts
    )
    plan_target.parent.mkdir(parents=True)
    manifest_target.parent.mkdir(parents=True)
    shutil.copyfile(PLAN_SOURCE, plan_target)
    shutil.copyfile(MANIFEST_SOURCE, manifest_target)
    return root


def _authorization(**updates: Any) -> OpenAIDevelopmentExecutionAuthorizationV01:
    values = {
        "authorization_schema_version": "0.1",
        "authorization_id": "fictional-development-authorization-001",
        "execution_id": execution.EXECUTION_ID,
        "authorization_scope": execution.AUTHORIZATION_SCOPE,
        "execution_plan_sha256": execution.EXPECTED_EXECUTION_PLAN_SHA256,
        "manifest_sha256": execution.MANIFEST_SELF_SHA256,
        "maximum_provider_calls": 8,
        "maximum_total_attempts": 8,
        "cost_cap_usd": Decimal("1.25"),
        "real_development_execution_authorized": True,
        "project_owner_identity": "Fictional Project Owner",
        "authorized_at_utc": NOW,
        **updates,
    }
    provisional = OpenAIDevelopmentExecutionAuthorizationV01.model_construct(
        **values,
        authorization_sha256="0" * 64,
    )
    return OpenAIDevelopmentExecutionAuthorizationV01.model_validate(
        {
            **values,
            "authorization_sha256": execution._canonical_hash(
                provisional, "authorization_sha256"
            ),
        }
    )


def _pricing(*, observed_at: datetime = NOW, input_price: str = "0.75"):
    return OpenAIPricingObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed pricing",
        source_url="https://example.invalid/fictional-pricing",
        input_usd_per_million_tokens=Decimal(input_price),
        output_usd_per_million_tokens=Decimal("4.50"),
        currency="USD",
    )


def _controls(*, observed_at: datetime = NOW):
    return OpenAIDataControlsObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed data controls",
        source_url="https://example.invalid/fictional-controls",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary=(
            "Fictional terms preserve provider retention limitations."
        ),
    )


def _write_model(path: Path, model: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(model.model_dump(mode="json")) + b"\n")


def _inputs(
    tmp_path: Path,
    *,
    authorization: OpenAIDevelopmentExecutionAuthorizationV01 | None = None,
    pricing: OpenAIPricingObservation | None = None,
    controls: OpenAIDataControlsObservation | None = None,
) -> tuple[Path, Path, Path]:
    root = tmp_path / "fictional-inputs"
    authorization_path = root / "authorization.json"
    pricing_path = root / "pricing.json"
    controls_path = root / "controls.json"
    authorization_path.parent.mkdir(parents=True, exist_ok=True)
    authorization_path.write_bytes(
        development_authorization_bytes(authorization or _authorization())
    )
    _write_model(pricing_path, pricing or _pricing())
    _write_model(controls_path, controls or _controls())
    return authorization_path, pricing_path, controls_path


def _prepared_invocations(
    _root: Path,
    plan: OpenAIDevelopmentExecutionPlanV01,
    manifest: OpenAIDevelopmentManifestV01,
) -> tuple[PreparedDevelopmentInvocation, ...]:
    prepared: list[PreparedDevelopmentInvocation] = []
    for plan_item, manifest_item in zip(
        plan.invocations, manifest.invocations, strict=True
    ):
        block = ApprovedEvidenceBlock(
            source_id=plan_item.source_id,
            evidence_id=f"fictional-{plan_item.request_id}-evidence",
            block_id=f"fictional-{plan_item.request_id}-block",
            sequence=1,
            text="Fictional offline transaction text.",
            location=SourceLocation(
                location_type=LocationType.PAGE,
                location_value="1",
                page_number=1,
            ),
        )
        request = LLMExtractionRequest.model_construct(
            experiment_id=EXPERIMENT_ID,
            invocation_role=manifest_item.invocation_role,
            request_id=plan_item.request_id,
            source_id=plan_item.source_id,
            document_sha256=manifest_item.document_sha256,
            prompt_version="0.1",
            prompt_sha256=plan_item.prompt_sha256,
            canonical_request_sha256=plan_item.canonical_request_sha256,
            provider_configuration_id=execution.OPENAI_PROVIDER_CONFIGURATION_ID,
            model_configuration_id=execution.OPENAI_MODEL_CONFIGURATION_ID,
            output_contract_id="candidate-extraction-result-0.1",
            evidence_blocks=(block,),
        )
        identity = CacheIdentity.from_request(request)
        assert cache_identity_sha256(identity) == plan_item.cache_identity_sha256
        prepared.append(
            PreparedDevelopmentInvocation(
                plan=plan_item,
                manifest_identity=manifest_item,
                request=request,
                cache_identity=identity,
            )
        )
    return tuple(prepared)


def _readiness(tmp_path: Path):
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    readiness = execution._validate_openai_development_execution_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=root,
        clock=lambda: NOW,
        reconstructor=_prepared_invocations,
    )
    return root, paths, readiness


def _candidate_output(
    request: LLMExtractionRequest,
    _response: LLMProviderResponse,
) -> ValidatedCandidateOutput:
    result = CandidateExtractionResult(
        schema_version="0.1",
        batch_id=f"fictional-{request.request_id}",
        source_ids=[request.source_id],
        entities=[],
        evidence_references=[],
        candidate_facts=[],
        warnings=["abstained_no_supported_candidate"],
    )
    return ValidatedCandidateOutput(
        request_id=request.request_id,
        source_id=request.source_id,
        candidate_result=result,
        canonical_output_sha256=uppercase_sha256_bytes(
            canonical_json_bytes(result.model_dump(mode="json"))
        ),
    )


def _observation(
    request: LLMExtractionRequest,
    *,
    input_tokens: int = 100,
    output_tokens: int = 10,
    version_field_path: str | None = None,
    version_value: str | None = None,
) -> OpenAIPreflightProviderObservation:
    raw = json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": f"fictional-{request.request_id}",
            "source_ids": [request.source_id],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    response_id = f"resp_{request.request_id}"
    provider_request_id = f"req_{request.request_id}"
    response = LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="openai",
        model_identifier="gpt-5.4-mini-2026-03-17",
        provider_request_id=provider_request_id,
        provider_response_id=response_id,
        provider_sdk_version="2.46.0",
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256(raw),
        token_usage=ProviderTokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        latency_ms=5,
        retry_count=0,
    )
    metadata_entries = [
        ProviderPublicMetadataEntry(field_path="response.id", value=response_id),
        ProviderPublicMetadataEntry(
            field_path="response.model",
            value="gpt-5.4-mini-2026-03-17",
        ),
        ProviderPublicMetadataEntry(
            field_path="response._request_id",
            value=provider_request_id,
        ),
        ProviderPublicMetadataEntry(field_path="sdk.version", value="2.46.0"),
    ]
    version_provenance: object = "unavailable"
    if version_field_path is not None:
        assert version_value is not None
        metadata_entries.append(
            ProviderPublicMetadataEntry(
                field_path=version_field_path,
                value=version_value,
            )
        )
        version_provenance = (
            ProviderVersionIdentifier(
                field_name=version_field_path,
                value=version_value,
            ),
        )
    return OpenAIPreflightProviderObservation(
        response=response,
        model_version_or_snapshot_provenance=version_provenance,
        version_provenance_source_response_id=response_id,
        observed_from_same_provider_call=True,
        provider_public_metadata_entries=tuple(metadata_entries),
    )


def _execute(
    root: Path,
    paths: tuple[Path, Path, Path],
    *,
    api_key_reader=lambda: FICTIONAL_CREDENTIAL,
    client_factory=lambda _credential: object(),
    provider_observation=lambda _client, request: _observation(request),
    local_validator=_candidate_output,
    clock=lambda: NOW,
):
    return execution._execute_openai_development_transaction(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=root,
        execute_real_development=True,
        confirmation=EXECUTION_CONFIRMATION,
        clock=clock,
        api_key_reader=api_key_reader,
        client_factory=client_factory,
        reconstructor=_prepared_invocations,
        provider_observation=provider_observation,
        local_validator=local_validator,
    )


def _prepopulate_cache(readiness: Any) -> None:
    cache = ResponseCache(readiness.cache_root)
    for invocation in readiness.invocations:
        observation = _observation(invocation.request)
        response = observation.response
        attempt = AttemptProvenance(
            attempt_number=1,
            terminal_status=ProviderTerminalStatus.SUCCESS,
            provider_call_performed=True,
            response_sha256=response.raw_response_sha256,
            latency_ms=response.latency_ms,
            retry_reason=None,
            failure_code=None,
        )
        cache.append(
            build_cache_record(
                identity=invocation.cache_identity,
                response=response,
                original_provider_call_timestamp=NOW,
                original_attempts=(attempt,),
                estimated_cost_usd=execution._estimated_cost(
                    response.token_usage,
                    readiness.inputs.pricing_observation,
                ),
                openai_original_call_provenance=(
                    execution._original_call_provenance(observation)
                ),
            )
        )


def test_readiness_loads_exact_frozen_plan_manifest_without_side_effects(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    before = sorted(path.relative_to(root) for path in root.rglob("*"))
    counters = {"key": 0, "client": 0, "provider": 0}

    readiness = execution._validate_openai_development_execution_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=root,
        clock=lambda: NOW,
        reconstructor=_prepared_invocations,
    )

    assert readiness.plan.execution_plan_sha256 == (
        execution.EXPECTED_EXECUTION_PLAN_SHA256
    )
    assert readiness.manifest.manifest_sha256 == execution.MANIFEST_SELF_SHA256
    assert len(readiness.invocations) == 8
    assert sorted(path.relative_to(root) for path in root.rglob("*")) == before
    assert counters == {"key": 0, "client": 0, "provider": 0}


@pytest.mark.parametrize("artifact", ("plan", "manifest"))
def test_readiness_rejects_frozen_artifact_tampering(
    tmp_path: Path,
    artifact: str,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    target = (
        root.joinpath(*execution.EXECUTION_PLAN_RELATIVE_PATH.parts)
        if artifact == "plan"
        else root.joinpath(*Path(execution.MANIFEST_RELATIVE_PATH).parts)
    )
    raw = bytearray(target.read_bytes())
    raw[10] ^= 1
    target.write_bytes(bytes(raw))

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=_prepared_invocations,
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID


def test_authorization_duplicate_json_key_fails_closed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    raw = paths[0].read_bytes()
    paths[0].write_bytes(b'{"authorization_id":"duplicate",' + raw[1:])

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=lambda *_args: (_ for _ in ()).throw(AssertionError),
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID


def test_authorization_symlink_fails_before_reconstruction(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    linked = tmp_path / "fictional-authorization-link.json"
    try:
        linked.symlink_to(paths[0])
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable on this platform: {error}")

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=linked,
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=lambda *_args: (_ for _ in ()).throw(AssertionError),
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID


@pytest.mark.parametrize(
    ("update", "code"),
    (
        (
            {"authorization_scope": "single-synthetic-openai-preflight-v0.3"},
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        ),
        (
            {"execution_plan_sha256": "F" * 64},
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        ),
        (
            {"manifest_sha256": "E" * 64},
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        ),
        (
            {"maximum_provider_calls": 7},
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        ),
        (
            {"cost_cap_usd": "1.24"},
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
        ),
    ),
)
def test_authorization_drift_fails_closed(
    tmp_path: Path,
    update: dict[str, object],
    code: Stage4BErrorCode,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    payload = json.loads(paths[0].read_bytes())
    payload.update(update)
    payload["authorization_sha256"] = "0" * 64
    paths[0].write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=_prepared_invocations,
        )
    assert captured.value.code is code


@pytest.mark.parametrize("stale_input", ("pricing", "data_controls"))
def test_stale_pricing_and_data_controls_fail_before_reconstruction(
    tmp_path: Path,
    stale_input: str,
) -> None:
    root = _repository(tmp_path)
    stale = datetime(2026, 8, 7, tzinfo=timezone.utc)
    paths = _inputs(
        tmp_path,
        pricing=_pricing(observed_at=stale if stale_input == "pricing" else NOW),
        controls=_controls(
            observed_at=stale if stale_input == "data_controls" else NOW
        ),
    )
    calls = 0

    def forbidden(*_args: Any):
        nonlocal calls
        calls += 1
        raise AssertionError

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=forbidden,
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID
    assert calls == 0


@pytest.mark.parametrize("future_input", ("pricing", "data_controls"))
def test_same_day_future_terms_observation_fails_before_reconstruction(
    tmp_path: Path,
    future_input: str,
) -> None:
    root = _repository(tmp_path)
    future = datetime(2026, 8, 8, 12, 1, tzinfo=timezone.utc)
    paths = _inputs(
        tmp_path,
        pricing=_pricing(observed_at=future if future_input == "pricing" else NOW),
        controls=_controls(
            observed_at=future if future_input == "data_controls" else NOW
        ),
    )

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=lambda *_args: (_ for _ in ()).throw(AssertionError),
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID


def test_pricing_drift_invalidates_frozen_cost_model(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path, pricing=_pricing(input_price="0.76"))
    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=_prepared_invocations,
        )
    assert captured.value.code is Stage4BErrorCode.COST_BUDGET_EXCEEDED


@pytest.mark.parametrize("source_id", ("S005", "S007"))
def test_prohibited_source_fails_before_path_access(
    tmp_path: Path,
    source_id: str,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    touched = False

    def prohibited(*_args: Any):
        nonlocal touched
        execution.validate_development_source_id(source_id)
        touched = True
        raise AssertionError

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=prohibited,
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert touched is False


def test_missing_execution_gate_fails_before_key_client_or_artifact(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    counters = {"key": 0, "client": 0}

    for flag, phrase in ((False, None), (True, "WRONG")):
        with pytest.raises(Stage4BError):
            execution._execute_openai_development_transaction(
                authorization_path=paths[0],
                pricing_path=paths[1],
                data_controls_path=paths[2],
                repository_root=root,
                execute_real_development=flag,
                confirmation=phrase,
                clock=lambda: NOW,
                api_key_reader=lambda: counters.__setitem__("key", 1),
                client_factory=lambda _key: counters.__setitem__("client", 1),
                reconstructor=_prepared_invocations,
                provider_observation=lambda _client, request: _observation(request),
                local_validator=_candidate_output,
            )
    assert counters == {"key": 0, "client": 0}
    assert not root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts).exists()


def test_cache_hits_perform_no_key_client_provider_or_marker_work(
    tmp_path: Path,
) -> None:
    root, paths, readiness = _readiness(tmp_path)
    _prepopulate_cache(readiness)
    counters = {"key": 0, "client": 0, "provider": 0}

    result = _execute(
        root,
        paths,
        api_key_reader=lambda: counters.__setitem__("key", 1),
        client_factory=lambda _key: counters.__setitem__("client", 1),
        provider_observation=lambda _client, _request: counters.__setitem__(
            "provider", 1
        ),
    )

    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert result.record.provider_call_count == 0
    assert result.record.cache_hit_count == 8
    assert not root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts).exists()


def test_cached_cost_must_reconcile_with_provider_usage(tmp_path: Path) -> None:
    root, paths, readiness = _readiness(tmp_path)
    invocation = readiness.invocations[0]
    observation = _observation(invocation.request)
    response = observation.response
    attempt = AttemptProvenance(
        attempt_number=1,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        provider_call_performed=True,
        response_sha256=response.raw_response_sha256,
        latency_ms=response.latency_ms,
        retry_reason=None,
        failure_code=None,
    )
    ResponseCache(readiness.cache_root).append(
        build_cache_record(
            identity=invocation.cache_identity,
            response=response,
            original_provider_call_timestamp=NOW,
            original_attempts=(attempt,),
            estimated_cost_usd=Decimal("0.99"),
            openai_original_call_provenance=(
                execution._original_call_provenance(observation)
            ),
        )
    )

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            api_key_reader=lambda: (_ for _ in ()).throw(AssertionError),
            client_factory=lambda _key: (_ for _ in ()).throw(AssertionError),
            provider_observation=lambda *_args: (_ for _ in ()).throw(
                AssertionError
            ),
        )
    assert captured.value.code is Stage4BErrorCode.CACHE_RECORD_INVALID
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()


def test_legacy_cache_without_original_call_provenance_fails_closed(
    tmp_path: Path,
) -> None:
    root, paths, readiness = _readiness(tmp_path)
    invocation = readiness.invocations[0]
    response = _observation(invocation.request).response
    attempt = AttemptProvenance(
        attempt_number=1,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        provider_call_performed=True,
        response_sha256=response.raw_response_sha256,
        latency_ms=response.latency_ms,
        retry_reason=None,
        failure_code=None,
    )
    ResponseCache(readiness.cache_root).append(
        build_cache_record(
            identity=invocation.cache_identity,
            response=response,
            original_provider_call_timestamp=NOW,
            original_attempts=(attempt,),
            estimated_cost_usd=execution._estimated_cost(
                response.token_usage,
                readiness.inputs.pricing_observation,
            ),
        )
    )
    counters = {"key": 0, "client": 0, "provider": 0}

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            api_key_reader=lambda: counters.__setitem__("key", 1),
            client_factory=lambda _key: counters.__setitem__("client", 1),
            provider_observation=lambda *_args: counters.__setitem__("provider", 1),
        )

    assert captured.value.code is Stage4BErrorCode.CACHE_RECORD_INVALID
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert not root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts).exists()


def test_cache_miss_orders_marker_before_client_call_cache_and_parse(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    plan, _ = _frozen_models()
    events: list[str] = []
    provider_calls = 0

    def key_reader() -> str:
        events.append("credential")
        return FICTIONAL_CREDENTIAL

    def client_factory(_credential: str) -> object:
        marker_dir = root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts)
        assert len(list(marker_dir.glob("*.attempt.json"))) == provider_calls + 1
        events.append("client")
        return object()

    def provider(_client: object, request: LLMExtractionRequest):
        nonlocal provider_calls
        events.append("provider")
        provider_calls += 1
        return _observation(request)

    def local(request: LLMExtractionRequest, response: LLMProviderResponse):
        identity = CacheIdentity.from_request(request)
        cache_path = root.joinpath(
            *Path(plan.cache_policy.relative_cache_root).parts
        ) / (
            f"{cache_identity_sha256(identity)}.json"
        )
        assert cache_path.is_file()
        events.append("parse")
        return _candidate_output(request, response)

    result = _execute(
        root,
        paths,
        api_key_reader=key_reader,
        client_factory=client_factory,
        provider_observation=provider,
        local_validator=local,
    )

    assert result.record.provider_call_count == 8
    assert result.record.provider_attempt_count == 8
    assert result.record.retry_count == 0
    assert provider_calls == 8
    assert events == ["credential", "client", "provider", "parse"] * 8


def test_attempt_marker_without_cache_permanently_blocks_retry(tmp_path: Path) -> None:
    root, paths, readiness = _readiness(tmp_path)
    invocation = readiness.invocations[0]
    marker = execution._build_marker(
        readiness=readiness,
        invocation=invocation,
        timestamp=NOW,
    )
    marker_path = root.joinpath(
        *Path(invocation.plan.attempt_marker_relative_path).parts
    )
    execution._write_exclusive(
        marker_path, execution.attempt_marker_bytes(marker), marker=True
    )
    calls = 0
    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            api_key_reader=lambda: (_ for _ in ()).throw(AssertionError),
            client_factory=lambda _key: (_ for _ in ()).throw(AssertionError),
            provider_observation=lambda _client, _request: (_ for _ in ()).throw(
                AssertionError
            ),
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
    assert calls == 0
    assert load_development_attempt_marker(marker_path) == marker


def test_losing_exclusive_marker_install_creates_no_failure_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, paths, readiness = _readiness(tmp_path)
    invocation = readiness.invocations[0]
    marker_path = root.joinpath(
        *Path(invocation.plan.attempt_marker_relative_path).parts
    )
    failure_path = root.joinpath(
        *Path(invocation.plan.failure_record_relative_path).parts
    )
    competing_marker = execution._build_marker(
        readiness=readiness,
        invocation=invocation,
        timestamp=NOW + timedelta(seconds=1),
    )
    original_build_marker = execution._build_marker
    original_write_exclusive = execution._write_exclusive
    pending_markers: list[
        execution.OpenAIDevelopmentInvocationAttemptMarkerV01
    ] = []
    counters = {"key": 0, "client": 0, "provider": 0}

    def tracking_build_marker(**kwargs: Any):
        pending_marker = original_build_marker(**kwargs)
        pending_markers.append(pending_marker)
        return pending_marker

    def racing_write_exclusive(path: Path, payload: bytes, *, marker: bool) -> None:
        if marker and path == marker_path:
            assert len(pending_markers) == 1
            assert payload == execution.attempt_marker_bytes(pending_markers[0])
            original_write_exclusive(
                marker_path,
                execution.attempt_marker_bytes(competing_marker),
                marker=True,
            )
        original_write_exclusive(path, payload, marker=marker)

    def key_reader() -> str:
        counters["key"] += 1
        return FICTIONAL_CREDENTIAL

    def client_factory(_credential: str) -> object:
        counters["client"] += 1
        return object()

    def provider(_client: object, request: LLMExtractionRequest):
        counters["provider"] += 1
        return _observation(request)

    monkeypatch.setattr(execution, "_build_marker", tracking_build_marker)
    monkeypatch.setattr(execution, "_write_exclusive", racing_write_exclusive)

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            api_key_reader=key_reader,
            client_factory=client_factory,
            provider_observation=provider,
        )

    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
    assert len(pending_markers) == 1
    assert pending_markers[0].marker_sha256 != competing_marker.marker_sha256
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert load_development_attempt_marker(marker_path) == competing_marker
    assert not failure_path.exists()
    with pytest.raises(Stage4BError) as cache_miss:
        ResponseCache(readiness.cache_root).read(invocation.cache_identity)
    assert cache_miss.value.code is Stage4BErrorCode.CACHE_MISS

    monkeypatch.setattr(execution, "_build_marker", original_build_marker)
    monkeypatch.setattr(execution, "_write_exclusive", original_write_exclusive)
    with pytest.raises(Stage4BError) as retry:
        _execute(
            root,
            paths,
            api_key_reader=key_reader,
            client_factory=client_factory,
            provider_observation=provider,
        )
    assert retry.value.code is Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert load_development_attempt_marker(marker_path) == competing_marker
    assert not failure_path.exists()


@pytest.mark.parametrize(
    ("field_name", "conflicting_value", "cache_present"),
    (
        ("authorization_sha256", "F" * 64, False),
        ("invocation_order", 2, True),
    ),
)
def test_canonical_conflicting_marker_fails_before_provider_boundaries(
    tmp_path: Path,
    field_name: str,
    conflicting_value: object,
    cache_present: bool,
) -> None:
    root, paths, readiness = _readiness(tmp_path)
    if cache_present:
        _prepopulate_cache(readiness)
    invocation = readiness.invocations[0]
    marker = execution._build_marker(
        readiness=readiness,
        invocation=invocation,
        timestamp=NOW,
    )
    values = marker.model_dump(mode="python", exclude={"marker_sha256"})
    values[field_name] = conflicting_value
    provisional = execution.OpenAIDevelopmentInvocationAttemptMarkerV01.model_construct(
        **values,
        marker_sha256="0" * 64,
    )
    conflicting = (
        execution.OpenAIDevelopmentInvocationAttemptMarkerV01.model_validate(
            {
                **values,
                "marker_sha256": execution._canonical_hash(
                    provisional, "marker_sha256"
                ),
            }
        )
    )
    marker_path = root.joinpath(
        *Path(invocation.plan.attempt_marker_relative_path).parts
    )
    execution._write_exclusive(
        marker_path,
        execution.attempt_marker_bytes(conflicting),
        marker=True,
    )
    counters = {"key": 0, "client": 0, "provider": 0}

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            api_key_reader=lambda: counters.__setitem__("key", 1),
            client_factory=lambda _key: counters.__setitem__("client", 1),
            provider_observation=lambda *_args: counters.__setitem__("provider", 1),
        )

    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
    assert counters == {"key": 0, "client": 0, "provider": 0}


def test_provider_failure_stops_transaction_and_preserves_partial_cache(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    count = 0

    def provider(_client: object, request: LLMExtractionRequest):
        nonlocal count
        count += 1
        if count == 3:
            raise Stage4BError(Stage4BErrorCode.TRANSPORT_ERROR, "fictional")
        return _observation(request)

    with pytest.raises(Stage4BError) as captured:
        _execute(root, paths, provider_observation=provider)
    assert captured.value.code is Stage4BErrorCode.TRANSPORT_ERROR
    assert count == 3

    _, plan_manifest = _frozen_models()
    plan, _ = _frozen_models()
    prepared = _prepared_invocations(root, plan, plan_manifest)
    cache = ResponseCache(
        root.joinpath(*Path(plan.cache_policy.relative_cache_root).parts)
    )
    assert cache.read(prepared[0].cache_identity)
    assert cache.read(prepared[1].cache_identity)
    with pytest.raises(Stage4BError) as miss:
        cache.read(prepared[2].cache_identity)
    assert miss.value.code is Stage4BErrorCode.CACHE_MISS
    assert root.joinpath(
        *Path(plan.invocations[2].attempt_marker_relative_path).parts
    ).is_file()
    assert root.joinpath(
        *Path(plan.invocations[2].failure_record_relative_path).parts
    ).is_file()
    assert not root.joinpath(
        *Path(plan.invocations[3].attempt_marker_relative_path).parts
    ).exists()
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()


def test_client_construction_failure_preserves_marker_and_creates_no_cache(
    tmp_path: Path,
) -> None:
    root, paths, readiness = _readiness(tmp_path)
    provider_calls = 0

    def client_failure(_credential: str) -> object:
        raise RuntimeError("fictional client construction failure")

    def provider(*_args: object) -> object:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            client_factory=client_failure,
            provider_observation=provider,
        )

    invocation = readiness.invocations[0]
    marker_path = root.joinpath(
        *Path(invocation.plan.attempt_marker_relative_path).parts
    )
    failure_path = root.joinpath(
        *Path(invocation.plan.failure_record_relative_path).parts
    )
    assert captured.value.code is Stage4BErrorCode.EXECUTION_FAILED
    assert provider_calls == 0
    assert load_development_attempt_marker(marker_path)
    assert load_development_failure_record(failure_path).failure_stage == (
        "client_construction"
    )
    with pytest.raises(Stage4BError) as miss:
        ResponseCache(readiness.cache_root).read(invocation.cache_identity)
    assert miss.value.code is Stage4BErrorCode.CACHE_MISS


def test_runtime_usage_over_conservative_call_ceiling_fails_closed(
    tmp_path: Path,
) -> None:
    root, paths, readiness = _readiness(tmp_path)

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            provider_observation=lambda _client, request: _observation(
                request, input_tokens=1_000_000, output_tokens=4096
            ),
        )

    assert captured.value.code is Stage4BErrorCode.COST_BUDGET_EXCEEDED
    invocation = readiness.invocations[0]
    with pytest.raises(Stage4BError) as miss:
        ResponseCache(readiness.cache_root).read(invocation.cache_identity)
    assert miss.value.code is Stage4BErrorCode.CACHE_MISS
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()


def test_cache_install_conflict_stops_without_local_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    parse_calls = 0

    def conflict(_self: ResponseCache, _record: object) -> object:
        raise Stage4BError(Stage4BErrorCode.CACHE_CONFLICT, "fictional conflict")

    def local(*_args: object) -> object:
        nonlocal parse_calls
        parse_calls += 1
        raise AssertionError

    monkeypatch.setattr(ResponseCache, "append", conflict)
    with pytest.raises(Stage4BError) as captured:
        _execute(root, paths, local_validator=local)

    assert captured.value.code is Stage4BErrorCode.CACHE_CONFLICT
    assert parse_calls == 0
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()


def test_local_parse_failure_preserves_cache_and_reprocesses_without_calls(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    parse_count = 0

    def fails_last(request: LLMExtractionRequest, response: LLMProviderResponse):
        nonlocal parse_count
        parse_count += 1
        if parse_count == 8:
            raise Stage4BError(Stage4BErrorCode.SCHEMA_INVALID, "fictional")
        return _candidate_output(request, response)

    with pytest.raises(Stage4BError) as captured:
        _execute(root, paths, local_validator=fails_last)
    assert captured.value.code is Stage4BErrorCode.SCHEMA_INVALID
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()

    calls = {"key": 0, "client": 0, "provider": 0}
    result = _execute(
        root,
        paths,
        api_key_reader=lambda: calls.__setitem__("key", 1),
        client_factory=lambda _key: calls.__setitem__("client", 1),
        provider_observation=lambda _client, _request: calls.__setitem__(
            "provider", 1
        ),
        local_validator=_candidate_output,
    )
    assert calls == {"key": 0, "client": 0, "provider": 0}
    assert result.record.cache_hit_count == 8


@pytest.mark.parametrize("exposes_snapshot", (True, False))
def test_cache_recovery_preserves_exact_original_same_call_provenance(
    tmp_path: Path,
    exposes_snapshot: bool,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    parse_count = 0
    field_path = "response.model_details.snapshot_id"
    value = "fictional-snapshot-2099-01-01"

    def observation(_client: object, request: LLMExtractionRequest):
        return _observation(
            request,
            version_field_path=field_path if exposes_snapshot else None,
            version_value=value if exposes_snapshot else None,
        )

    def fail_last(request: LLMExtractionRequest, response: LLMProviderResponse):
        nonlocal parse_count
        parse_count += 1
        if parse_count == 8:
            raise Stage4BError(Stage4BErrorCode.SCHEMA_INVALID, "fictional")
        return _candidate_output(request, response)

    with pytest.raises(Stage4BError):
        _execute(
            root,
            paths,
            provider_observation=observation,
            local_validator=fail_last,
        )
    marker_root = root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts)
    marker_snapshot = {
        path.name: path.read_bytes() for path in marker_root.glob("*.attempt.json")
    }
    assert len(marker_snapshot) == 8

    counters = {"key": 0, "client": 0, "provider": 0}
    result = _execute(
        root,
        paths,
        api_key_reader=lambda: counters.__setitem__("key", 1),
        client_factory=lambda _key: counters.__setitem__("client", 1),
        provider_observation=lambda *_args: counters.__setitem__("provider", 1),
    )

    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert result.record.provider_call_count == 0
    assert result.record.cache_hit_count == 8
    assert marker_snapshot == {
        path.name: path.read_bytes() for path in marker_root.glob("*.attempt.json")
    }
    prepared = result.readiness.invocations[-1]
    expected = _observation(
        prepared.request,
        version_field_path=field_path if exposes_snapshot else None,
        version_value=value if exposes_snapshot else None,
    )
    outcome = result.record.ordered_invocation_outcomes[-1]
    assert outcome.model_version_or_snapshot_provenance == (
        expected.model_version_or_snapshot_provenance
    )
    assert outcome.provider_public_metadata_sha256 == (
        expected.provider_public_metadata_sha256
    )
    assert outcome.provider_public_metadata_field_paths == (
        expected.provider_public_metadata_field_paths
    )
    if exposes_snapshot:
        assert outcome.model_version_or_snapshot_provenance == (
            ProviderVersionIdentifier(field_name=field_path, value=value),
        )
        assert field_path in outcome.provider_public_metadata_field_paths
    else:
        assert outcome.model_version_or_snapshot_provenance == "unavailable"


def test_utc_date_rollover_before_first_miss_stops_before_marker_and_provider(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    next_day = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)
    timestamps = iter((NOW, next_day, next_day))
    counters = {"key": 0, "client": 0, "provider": 0}

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            clock=lambda: next(timestamps, next_day),
            api_key_reader=lambda: counters.__setitem__("key", 1),
            client_factory=lambda _key: counters.__setitem__("client", 1),
            provider_observation=lambda *_args: counters.__setitem__("provider", 1),
        )

    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID
    assert counters == {"key": 0, "client": 0, "provider": 0}
    assert not root.joinpath(*Path(execution.ATTEMPT_MARKER_ROOT).parts).exists()
    plan, _ = _frozen_models()
    first_failure_path = root.joinpath(
        *Path(plan.invocations[0].failure_record_relative_path).parts
    )
    assert not first_failure_path.exists()

    reviewed_at = datetime(2026, 8, 9, 0, 1, tzinfo=timezone.utc)
    next_day_paths = _inputs(
        tmp_path,
        pricing=_pricing(observed_at=reviewed_at),
        controls=_controls(observed_at=reviewed_at),
    )
    recovery_counters = {"key": 0, "client": 0, "provider": 0}

    def recovery_key_reader() -> str:
        recovery_counters["key"] += 1
        return FICTIONAL_CREDENTIAL

    def recovery_client(_key: str) -> object:
        recovery_counters["client"] += 1
        return object()

    def recovery_provider(_client: object, request: LLMExtractionRequest):
        recovery_counters["provider"] += 1
        return _observation(request)

    recovered = _execute(
        root,
        next_day_paths,
        clock=lambda: reviewed_at,
        api_key_reader=recovery_key_reader,
        client_factory=recovery_client,
        provider_observation=recovery_provider,
    )

    assert recovery_counters == {"key": 8, "client": 8, "provider": 8}
    assert recovered.record.provider_call_count == 8
    assert recovered.record.cache_hit_count == 0
    assert not first_failure_path.exists()


def test_utc_date_rollover_between_misses_stops_next_invocation_before_marker(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    next_day = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)
    timestamps = iter((NOW, NOW, NOW, next_day, next_day))
    counters = {"key": 0, "client": 0, "provider": 0}

    def key_reader() -> str:
        counters["key"] += 1
        return FICTIONAL_CREDENTIAL

    def client_factory(_key: str) -> object:
        counters["client"] += 1
        return object()

    def observation(_client: object, request: LLMExtractionRequest):
        counters["provider"] += 1
        return _observation(request)

    with pytest.raises(Stage4BError) as captured:
        _execute(
            root,
            paths,
            clock=lambda: next(timestamps, next_day),
            api_key_reader=key_reader,
            client_factory=client_factory,
            provider_observation=observation,
        )

    plan, _ = _frozen_models()
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID
    assert counters == {"key": 1, "client": 1, "provider": 1}
    assert root.joinpath(
        *Path(plan.invocations[0].attempt_marker_relative_path).parts
    ).is_file()
    assert not root.joinpath(
        *Path(plan.invocations[1].attempt_marker_relative_path).parts
    ).exists()
    second_failure_path = root.joinpath(
        *Path(plan.invocations[1].failure_record_relative_path).parts
    )
    assert not second_failure_path.exists()
    assert not root.joinpath(*Path(execution.EXECUTION_RECORD_PATH).parts).exists()

    reviewed_at = datetime(2026, 8, 9, 0, 1, tzinfo=timezone.utc)
    next_day_paths = _inputs(
        tmp_path,
        pricing=_pricing(observed_at=reviewed_at),
        controls=_controls(observed_at=reviewed_at),
    )
    recovery_counters = {"key": 0, "client": 0, "provider": 0}

    def recovery_key_reader() -> str:
        recovery_counters["key"] += 1
        return FICTIONAL_CREDENTIAL

    def recovery_client(_key: str) -> object:
        recovery_counters["client"] += 1
        return object()

    def recovery_provider(_client: object, request: LLMExtractionRequest):
        recovery_counters["provider"] += 1
        return _observation(request)

    recovered = _execute(
        root,
        next_day_paths,
        clock=lambda: reviewed_at,
        api_key_reader=recovery_key_reader,
        client_factory=recovery_client,
        provider_observation=recovery_provider,
    )

    assert recovery_counters == {"key": 7, "client": 7, "provider": 7}
    assert recovered.record.provider_call_count == 7
    assert recovered.record.cache_hit_count == 1
    assert recovered.record.ordered_invocation_outcomes[0].response_source == (
        "cache_hit"
    )
    assert not second_failure_path.exists()


def test_failure_record_and_raised_error_scrub_credential_fragments(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    fragment = FICTIONAL_CREDENTIAL[20:45]

    def failure(_client: object, _request: LLMExtractionRequest):
        raise OpenAIProviderFailure(
            Stage4BErrorCode.PROVIDER_API_FAILURE,
            OpenAIProviderFailureDiagnostics(
                http_status_code=401,
                provider_error_type=fragment,
                provider_error_code="invalid_api_key",
                provider_request_id="req_fictional_001",
            ),
        )

    with pytest.raises(Stage4BError) as captured:
        _execute(root, paths, provider_observation=failure)
    plan, _ = _frozen_models()
    failure_path = root.joinpath(
        *Path(plan.invocations[0].failure_record_relative_path).parts
    )
    raw = failure_path.read_bytes()
    record = load_development_failure_record(failure_path)
    assert record.provider_error_type is None
    assert record.provider_error_code == "invalid_api_key"
    assert FICTIONAL_CREDENTIAL.encode() not in raw
    assert fragment.encode() not in raw
    assert FICTIONAL_CREDENTIAL not in str(captured.value)
    assert fragment not in str(captured.value)


def test_eight_valid_invocations_install_one_canonical_final_record(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    result = _execute(root, paths)
    record = result.record

    assert record.provider_call_count == 8
    assert record.provider_attempt_count == 8
    assert record.cache_hit_count == 0
    assert record.aggregate_output_tokens == 80
    assert record.aggregate_new_cost_usd <= Decimal("1.25")
    assert all(
        item.model_version_or_snapshot_provenance == "unavailable"
        for item in record.ordered_invocation_outcomes
    )
    assert [item.request_id for item in record.ordered_invocation_outcomes] == [
        "llm-v0.1-S001-primary-001",
        "llm-v0.1-S002-primary-001",
        "llm-v0.1-S003-primary-001",
        "llm-v0.1-S004-primary-001",
        "llm-v0.1-S004-primary-002",
        "llm-v0.1-S004-primary-003",
        "llm-v0.1-S006-primary-001",
        "llm-v0.1-S004-repeat-001",
    ]
    raw = result.execution_record_path.read_bytes()
    assert raw == execution_record_bytes(record)
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert load_development_execution_record(result.execution_record_path) == record
    assert b"raw_response" not in raw
    assert b"candidate_facts" not in raw
    assert FICTIONAL_CREDENTIAL.encode() not in raw


def test_existing_valid_final_record_is_idempotent_without_provider_work(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    first = _execute(root, paths)
    calls = {"key": 0, "client": 0, "provider": 0}
    second = _execute(
        root,
        paths,
        api_key_reader=lambda: calls.__setitem__("key", 1),
        client_factory=lambda _key: calls.__setitem__("client", 1),
        provider_observation=lambda _client, _request: calls.__setitem__(
            "provider", 1
        ),
    )
    assert second.record == first.record
    assert calls == {"key": 0, "client": 0, "provider": 0}


def test_final_record_hash_tamper_fails_closed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    result = _execute(root, paths)
    payload = json.loads(result.execution_record_path.read_bytes())
    payload["execution_record_sha256"] = "F" * 64
    result.execution_record_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=_prepared_invocations,
        )
    assert captured.value.code is (
        Stage4BErrorCode.DEVELOPMENT_EXECUTION_RECORD_HASH_MISMATCH
    )


def test_recomputed_final_hash_cannot_hide_contradictory_version_provenance(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    result = _execute(root, paths)
    payload = json.loads(result.execution_record_path.read_bytes())
    paths_payload = payload["ordered_invocation_outcomes"][0][
        "provider_public_metadata_field_paths"
    ]
    paths_payload.append("response.snapshot_name")
    hash_payload = dict(payload)
    hash_payload.pop("execution_record_sha256")
    payload["execution_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(hash_payload)
    )
    result.execution_record_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        load_development_execution_record(result.execution_record_path)
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID


def test_valid_but_conflicting_final_record_fails_closed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)
    result = _execute(root, paths)
    payload = json.loads(result.execution_record_path.read_bytes())
    payload["ordered_invocation_outcomes"][0]["cache_identity_sha256"] = "F" * 64
    hash_payload = dict(payload)
    hash_payload.pop("execution_record_sha256")
    payload["execution_record_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(hash_payload)
    )
    result.execution_record_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        execution._validate_openai_development_execution_readiness(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=root,
            clock=lambda: NOW,
            reconstructor=_prepared_invocations,
        )
    assert captured.value.code is Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID


def test_failure_record_hash_tamper_has_stable_error(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    paths = _inputs(tmp_path)

    with pytest.raises(Stage4BError):
        _execute(
            root,
            paths,
            client_factory=lambda _credential: (_ for _ in ()).throw(
                RuntimeError("fictional")
            ),
        )
    plan, _ = _frozen_models()
    failure_path = root.joinpath(
        *Path(plan.invocations[0].failure_record_relative_path).parts
    )
    payload = json.loads(failure_path.read_bytes())
    payload["failure_record_sha256"] = "F" * 64
    failure_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        load_development_failure_record(failure_path)
    assert captured.value.code is (
        Stage4BErrorCode.DEVELOPMENT_FAILURE_RECORD_HASH_MISMATCH
    )


def test_public_execution_api_exposes_no_root_provider_or_cache_bypass() -> None:
    import inspect

    assert tuple(inspect.signature(execution.execute_openai_development).parameters) == (
        "authorization_path",
        "pricing_path",
        "data_controls_path",
        "execute_real_development",
        "confirmation",
    )
    source = Path(execution.__file__).read_text(encoding="utf-8")
    assert "held_out" not in source
    assert "S005" not in source
    assert "S007" not in source
    assert "gold" not in source.casefold()
