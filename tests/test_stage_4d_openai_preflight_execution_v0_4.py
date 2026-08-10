"""Offline transaction tests for compatibility-first preflight v0.4."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

import document_intelligence.llm_extraction.openai_preflight_execution_v0_4 as execution
import document_intelligence.llm_extraction.openai_preflight_v0_4 as contract
from document_intelligence.llm_extraction import openai_preflight_execution_v0_3
from document_intelligence.llm_extraction.contracts import InvocationRole
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    EXPECTED_ABSTENTION_WARNING,
    PREFLIGHT_AUTHORIZATION_SCOPE,
    OpenAIPreflightAuthorizationV04,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_MAX_TIMEOUT_SECONDS,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope,
    build_request_envelope_v0_3,
    canonical_json_bytes,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
FICTIONAL_KEY = "sk-proj-" + "V" * 116


def _write_model(path: Path, model: object) -> None:
    path.write_bytes(
        canonical_json_bytes(model.model_dump(mode="json"))  # type: ignore[attr-defined]
    )


def _input_paths(root: Path) -> tuple[Path, Path, Path]:
    authorization = root / "authorization-v0-3.json"
    pricing = root / "pricing-v0-3.json"
    controls = root / "controls-v0-3.json"
    _write_model(
        authorization,
        OpenAIPreflightAuthorizationV04(
            authorization_id="fictional-v0-3-authorization",
            authorized_by="Fictional V0.4 Owner",
            authorized_at_utc=NOW - timedelta(minutes=5),
            scope=PREFLIGHT_AUTHORIZATION_SCOPE,
            maximum_provider_calls=1,
            real_provider_preflight_authorized=True,
        ),
    )
    _write_model(
        pricing,
        OpenAIPricingObservation(
            observed_at_utc=NOW,
            source_title="Fictional v0.4 pricing",
            source_url="https://example.invalid/pricing-v0-3",
            input_usd_per_million_tokens=Decimal("1.25"),
            output_usd_per_million_tokens=Decimal("5.50"),
            currency="USD",
        ),
    )
    _write_model(
        controls,
        OpenAIDataControlsObservation(
            observed_at_utc=NOW,
            source_title="Fictional v0.4 controls",
            source_url="https://example.invalid/controls-v0-3",
            store_false_required=True,
            zero_retention_claimed=False,
            retention_and_abuse_monitoring_summary="Fictional limitations apply.",
        ),
    )
    return authorization, pricing, controls


def _base_payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "batch_id": "fictional-v0-3-batch",
        "source_ids": ["S001"],
        "entities": [],
        "evidence_references": [],
        "candidate_facts": [],
        "warnings": [EXPECTED_ABSTENTION_WARNING],
    }


def _entity() -> dict[str, object]:
    return {
        "entity_id": "fictional-v0-3-entity",
        "canonical_name": "Fictional delivery initiative",
        "entity_type": "initiative",
        "aliases": [],
        "source_ids": ["S001"],
    }


def _evidence() -> dict[str, object]:
    return {
        "evidence_id": "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4",
        "source_id": "S001",
        "block_id": "synthetic-preflight-block-v0.4",
        "location_type": "document_metadata",
        "location_value": "synthetic-preflight-v0.4",
        "text_excerpt": "This document is a synthetic API preflight fixture.",
        "evidence_status": "supported",
    }


def _fact() -> dict[str, object]:
    return {
        "candidate_id": "fictional-v0-3-candidate",
        "source_id": "S001",
        "document_family": "synthetic_preflight",
        "subject_text": "synthetic API preflight fixture",
        "subject_type": "initiative",
        "predicate": "status",
        "raw_value": "synthetic",
        "normalized_value": "synthetic",
        "value_type": "status",
        "qualifiers": {},
        "evidence_ids": [
            "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4"
        ],
        "confidence": 0.5,
        "review_status": "required",
        "extraction_method": "llm",
        "warnings": ["fictional_semantic_variance"],
    }


def _semantic_cases() -> tuple[
    tuple[str, dict[str, object], str, tuple[int, int, int]], ...
]:
    abstention = _base_payload()
    entity = _base_payload()
    entity["entities"] = [_entity()]
    evidence = _base_payload()
    evidence["evidence_references"] = [_evidence()]
    fact = _base_payload()
    fact["evidence_references"] = [_evidence()]
    fact["candidate_facts"] = [_fact()]
    warning = _base_payload()
    warning["warnings"] = ["fictional_alternative_warning"]
    no_warning = _base_payload()
    no_warning["warnings"] = []
    multiple = _base_payload()
    multiple["entities"] = [_entity()]
    multiple["evidence_references"] = [_evidence()]
    multiple["candidate_facts"] = [_fact()]
    multiple["warnings"] = ["fictional_alternative_warning"]
    return (
        ("exact-abstention", abstention, "expected_abstention", (0, 0, 0)),
        ("one-entity", entity, "valid_semantic_variance", (1, 0, 0)),
        ("evidence", evidence, "valid_semantic_variance", (0, 1, 0)),
        ("candidate", fact, "valid_semantic_variance", (0, 1, 1)),
        ("different-warning", warning, "valid_semantic_variance", (0, 0, 0)),
        ("no-warning", no_warning, "valid_semantic_variance", (0, 0, 0)),
        ("multiple", multiple, "valid_semantic_variance", (1, 1, 1)),
    )


class FictionalSDKResponse:
    def __init__(
        self,
        *,
        raw_output: str,
        status: str = "completed",
        content_type: str = "output_text",
        request_id: str | None = "req_fictional_v0_4",
        response_id: str | None = "resp_fictional_v0_4",
        model: str | None = "gpt-5.4-mini-fictional-v0-3",
        usage: object | None = None,
    ) -> None:
        self.status = status
        self.model = model
        self.id = response_id
        self._request_id = request_id
        self.usage = usage or SimpleNamespace(input_tokens=10, output_tokens=5)
        self.output = (
            SimpleNamespace(
                type="message",
                content=(SimpleNamespace(type=content_type, text=raw_output),),
            ),
        )

    def model_dump(self, *, mode: str) -> dict[str, object]:
        return {"id": self.id, "model": self.model}


class FakeResponses:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: object) -> None:
        self.responses = FakeResponses(outcome)
        self.option_calls: list[dict[str, object]] = []

    def with_options(self, *, max_retries: int, timeout: float):
        self.option_calls.append({"max_retries": max_retries, "timeout": timeout})
        return self


def _raw(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _artifact_paths(root: Path) -> tuple[Path, Path, Path]:
    return (
        root.joinpath(*execution.ATTEMPT_MARKER_RELATIVE_PATH.parts),
        root.joinpath(*execution.SUCCESSFUL_RECORD_RELATIVE_PATH.parts),
        root.joinpath(*execution.FAILURE_RECORD_RELATIVE_PATH.parts),
    )


def test_v0_4_plan_is_deterministic_alias_safe_and_historically_separate() -> None:
    first = execution.build_openai_preflight_execution_plan()
    second = execution.build_openai_preflight_execution_plan()
    historical = openai_preflight_execution_v0_3.build_openai_preflight_execution_plan()

    assert first == second
    assert first.preflight_id == "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
    assert first.authorization_scope == "single-synthetic-openai-preflight-v0.4"
    assert execution.EXECUTION_CONFIRMATION == (
        "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_4"
    )
    assert first.maximum_provider_calls == 1
    assert first.strict_schema_sha256 == (
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    )
    assert first.execution_plan_sha256 == (
        "F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E"
    )
    assert historical.execution_plan_sha256 == (
        "21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5"
    )
    assert first.preflight_id != historical.preflight_id
    assert first.attempt_marker_path != historical.attempt_marker_path


def test_legacy_default_request_cannot_satisfy_v0_4_provider_entry() -> None:
    request = contract.build_synthetic_openai_preflight_request_v0_4()
    legacy = build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="synthetic-preflight-request-fictional-legacy",
        source_id=request.source_id,
        document_sha256=request.document_sha256,
        provider_configuration_id="openai-responses-text-strict-json-v0.1",
        model_configuration_id="openai-gpt-5.4-mini-text-strict-json-v0.1",
        evidence_blocks=request.evidence_blocks,
    )

    class ForbiddenDelegate:
        def generate_preflight(self, supplied: object) -> object:
            raise AssertionError("legacy request reached provider delegate")

    provider = execution._PlanBoundPreflightProvider(
        plan=execution.build_openai_preflight_execution_plan(),
        delegate=ForbiddenDelegate(),  # type: ignore[arg-type]
    )
    with pytest.raises(Stage4BError) as captured:
        provider.generate_preflight(legacy)  # type: ignore[arg-type]

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID


def _execute(
    root: Path,
    *,
    response: FictionalSDKResponse | None = None,
    outcome: object | None = None,
) -> tuple[execution.OpenAIPreflightExecutionResultV04, FakeClient]:
    paths = _input_paths(root)
    selected = outcome or response or FictionalSDKResponse(raw_output=_raw(_base_payload()))
    client = FakeClient(selected)
    result = execution._execute_openai_synthetic_preflight_transaction(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=root,
        execute_real_preflight=True,
        confirmation=execution.EXECUTION_CONFIRMATION,
        clock=lambda: NOW,
        api_key_reader=lambda: FICTIONAL_KEY,
        client_factory=lambda supplied: client,
    )
    return result, client


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_counts"),
    tuple((item[1], item[2], item[3]) for item in _semantic_cases()),
    ids=tuple(item[0] for item in _semantic_cases()),
)
def test_valid_semantic_variants_install_technical_success_records(
    tmp_path: Path,
    payload: dict[str, object],
    expected_status: str,
    expected_counts: tuple[int, int, int],
) -> None:
    result, client = _execute(
        tmp_path,
        response=FictionalSDKResponse(raw_output=_raw(payload)),
    )
    marker, success, failure = _artifact_paths(tmp_path)
    installed = contract.OpenAIPreflightRecordV04.model_validate_json(
        success.read_bytes()
    )
    diagnostic = installed.semantic_diagnostic

    assert result.record == installed
    assert result.record.compatibility_status == "passed"
    assert result.record.retry_count == 0
    assert marker.is_file()
    assert success.is_file()
    assert not failure.exists()
    assert len(client.responses.calls) == 1
    provider_payload = client.responses.calls[0]
    assert provider_payload["text"]["format"]["name"] == (
        DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3.response_schema_name
    )
    aliases = provider_payload["text"]["format"]["schema"]["$defs"][
        "CandidateEntity"
    ]["properties"]["aliases"]
    assert aliases["maxItems"] == 0
    assert provider_payload["max_output_tokens"] == 4096
    assert provider_payload["reasoning"] == {"effort": "none"}
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert diagnostic.semantic_diagnostic_status == expected_status
    assert (
        diagnostic.entity_count,
        diagnostic.evidence_reference_count,
        diagnostic.candidate_fact_count,
    ) == expected_counts


@pytest.mark.parametrize(
    ("raw_output", "expected_code"),
    (
        ("{not-json", Stage4BErrorCode.INVALID_JSON),
        (
            '{"schema_version":"0.1"}',
            Stage4BErrorCode.SCHEMA_INVALID,
        ),
    ),
)
def test_invalid_json_and_schema_write_safe_post_response_failure(
    tmp_path: Path,
    raw_output: str,
    expected_code: Stage4BErrorCode,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(raw_output=raw_output))

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda supplied: client,
        )

    marker, success, failure = _artifact_paths(tmp_path)
    record = execution.load_openai_preflight_failure_record(failure)
    assert captured.value.code is expected_code
    assert record.local_error_code is expected_code
    assert record.failure_stage == "post_provider_validation"
    assert record.provider_call_count == 1
    assert record.post_response_metadata is not None
    assert record.post_response_metadata.retry_count == 0
    assert raw_output not in failure.read_text(encoding="utf-8")
    assert marker.is_file()
    assert not success.exists()
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    ("response", "expected_code"),
    (
        (
            FictionalSDKResponse(raw_output=_raw(_base_payload()), status="incomplete"),
            Stage4BErrorCode.INCOMPLETE_RESPONSE,
        ),
        (
            FictionalSDKResponse(
                raw_output="fictional refusal",
                content_type="refusal",
            ),
            Stage4BErrorCode.PROVIDER_REFUSAL,
        ),
        (
            FictionalSDKResponse(
                raw_output=_raw(_base_payload()),
                request_id=None,
            ),
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
        ),
    ),
)
def test_genuine_post_response_failures_remain_fail_closed(
    tmp_path: Path,
    response: FictionalSDKResponse,
    expected_code: Stage4BErrorCode,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(response)

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda supplied: client,
        )

    _, success, failure = _artifact_paths(tmp_path)
    record = execution.load_openai_preflight_failure_record(failure)
    assert captured.value.code is expected_code
    assert record.local_error_code is expected_code
    assert record.failure_stage == "post_provider_validation"
    assert record.provider_call_count == 1
    assert not success.exists()
    assert len(client.responses.calls) == 1


def _api_status_failure() -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.invalid/v1/responses")
    response = httpx.Response(
        401,
        request=request,
        headers={"x-request-id": "req_fictional_v0_4_failure"},
    )
    return APIStatusError(
        "fictional provider failure",
        response=response,
        body={"type": "invalid_request_error", "code": "invalid_api_key"},
    )


@pytest.mark.parametrize(
    ("outcome", "expected_code"),
    (
        (_api_status_failure(), Stage4BErrorCode.PROVIDER_API_FAILURE),
        (
            APITimeoutError(
                request=httpx.Request(
                    "POST",
                    "https://api.openai.invalid/v1/responses",
                )
            ),
            Stage4BErrorCode.TIMEOUT,
        ),
    ),
)
def test_provider_api_failure_and_timeout_are_one_call_without_retry(
    tmp_path: Path,
    outcome: BaseException,
    expected_code: Stage4BErrorCode,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(outcome)

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda supplied: client,
        )

    record = execution.load_openai_preflight_failure_record(
        _artifact_paths(tmp_path)[2]
    )
    assert captured.value.code is expected_code
    assert record.failure_stage == "provider_call"
    assert record.provider_call_count == 1
    assert record.retry_count == 0
    assert record.post_response_metadata is None
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize("drift_kind", ("request", "schema", "payload"))
def test_request_schema_or_payload_drift_fails_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_kind: str,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(raw_output=_raw(_base_payload())))

    def install_drift() -> str:
        if drift_kind == "request":
            request = contract.build_synthetic_openai_preflight_request_v0_4()
            drifted = build_request_envelope_v0_3(
                invocation_role=InvocationRole.PRIMARY,
                request_id="llm-v0.3-S001-primary-998",
                source_id=request.source_id,
                document_sha256=request.document_sha256,
                provider_configuration_id=request.provider_configuration_id,
                model_configuration_id=request.model_configuration_id,
                evidence_blocks=request.evidence_blocks,
            )
            monkeypatch.setattr(
                contract,
                "build_synthetic_openai_preflight_request_v0_4",
                lambda: drifted,
            )
        elif drift_kind == "schema":
            original = execution.build_openai_candidate_schema_v0_3

            def changed_schema() -> dict[str, Any]:
                schema = original()
                schema["x-fictional-v0-4-drift"] = True
                return schema

            monkeypatch.setattr(
                execution,
                "build_openai_candidate_schema_v0_3",
                changed_schema,
            )
        else:
            original_payload = execution.build_openai_responses_payload

            def changed_payload(request: object, configuration: object) -> dict[str, Any]:
                payload = original_payload(  # type: ignore[arg-type]
                    request, configuration
                )
                payload["max_output_tokens"] = 4095
                return payload

            monkeypatch.setattr(
                execution,
                "build_openai_responses_payload",
                changed_payload,
            )
        return FICTIONAL_KEY

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=install_drift,
            client_factory=lambda supplied: client,
        )

    record = execution.load_openai_preflight_failure_record(
        _artifact_paths(tmp_path)[2]
    )
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert record.provider_call_count == 0
    assert not _artifact_paths(tmp_path)[1].exists()
    assert client.responses.calls == []


def test_success_record_write_failure_retains_safe_post_response_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(raw_output=_raw(_base_payload())))
    original_write = execution.v0_1_execution._write_exclusive

    def controlled_write(path: Path, payload: bytes, *, marker: bool) -> None:
        if path.name.endswith("v0.4.record.json"):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
                "fictional v0.4 record write failure",
            )
        original_write(path, payload, marker=marker)

    monkeypatch.setattr(
        execution.v0_1_execution,
        "_write_exclusive",
        controlled_write,
    )

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda supplied: client,
        )

    _, success, failure = _artifact_paths(tmp_path)
    record = execution.load_openai_preflight_failure_record(failure)
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED
    assert record.failure_stage == "successful_record_write"
    assert record.post_response_metadata is not None
    assert record.post_response_metadata.provider_response_id == (
        "resp_fictional_v0_4"
    )
    assert not success.exists()
    assert len(client.responses.calls) == 1


def test_second_v0_4_attempt_is_blocked_before_credential_or_client(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    _, first_client = _execute(tmp_path)
    key_calls = 0
    factory_calls = 0

    def forbidden_key() -> str:
        nonlocal key_calls
        key_calls += 1
        return FICTIONAL_KEY

    def forbidden_factory(value: str) -> object:
        nonlocal factory_calls
        factory_calls += 1
        return FakeClient(FictionalSDKResponse(raw_output=_raw(_base_payload())))

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=forbidden_key,
            client_factory=forbidden_factory,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS
    assert key_calls == 0
    assert factory_calls == 0
    assert len(first_client.responses.calls) == 1


def test_malformed_credential_fails_before_v0_4_artifacts_or_client(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    factory_calls = 0

    def forbidden_factory(value: str) -> object:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("partial fictional credential reached client")

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: "sk-proj-" + "P" * 60,
            client_factory=forbidden_factory,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID
    assert factory_calls == 0
    assert not tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()


def test_historical_v0_1_v0_3_files_do_not_block_or_change_v0_4(
    tmp_path: Path,
) -> None:
    historical_root = tmp_path / "reports" / "llm_extraction" / "openai_preflight"
    historical_root.mkdir(parents=True)
    historical = {
        "openai-gpt-5.4-mini-synthetic-preflight-v0.1.attempt.json": b"v0.1\n",
        "openai-gpt-5.4-mini-synthetic-preflight-v0.3.attempt.json": b"v0.3-marker\n",
        "openai-gpt-5.4-mini-synthetic-preflight-v0.3.record.json": b"v0.3-record\n",
    }
    for name, content in historical.items():
        (historical_root / name).write_bytes(content)

    result, client = _execute(tmp_path)

    assert result.record.preflight_id.endswith("v0.4")
    assert len(client.responses.calls) == 1
    for name, content in historical.items():
        assert (historical_root / name).read_bytes() == content


def test_v0_4_readiness_and_fake_execution_use_no_network_or_default_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("v0.4 test attempted a network operation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    paths = _input_paths(tmp_path)
    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )

    assert readiness.plan.preflight_id.endswith("v0.4")
    assert not tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()
    result, client = _execute(tmp_path)
    assert result.record.compatibility_status == "passed"
    assert len(client.responses.calls) == 1
