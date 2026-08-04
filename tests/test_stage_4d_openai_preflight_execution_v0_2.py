"""Offline transaction tests for the separate Stage 4D preflight v0.2."""

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
from openai import APIStatusError

import document_intelligence.llm_extraction.openai_preflight_execution_v0_2 as execution
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_preflight_v0_2 import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    OpenAIPreflightAuthorizationV02,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_MAX_TIMEOUT_SECONDS,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
FICTIONAL_VALID_KEY = "sk-proj-" + "A" * 116


def _write_model(path: Path, model: object) -> None:
    path.write_bytes(
        canonical_json_bytes(model.model_dump(mode="json"))  # type: ignore[attr-defined]
    )


def _input_paths(root: Path) -> tuple[Path, Path, Path]:
    authorization = root / "authorization-v0-2.json"
    pricing = root / "pricing-v0-2.json"
    controls = root / "controls-v0-2.json"
    _write_model(
        authorization,
        OpenAIPreflightAuthorizationV02(
            authorization_id="fictional-v0-2-authorization",
            authorized_by="Fictional V0.2 Owner",
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
            source_title="Fictional v0.2 pricing",
            source_url="https://example.invalid/pricing-v0-2",
            input_usd_per_million_tokens=Decimal("1.25"),
            output_usd_per_million_tokens=Decimal("5.50"),
            currency="USD",
        ),
    )
    _write_model(
        controls,
        OpenAIDataControlsObservation(
            observed_at_utc=NOW,
            source_title="Fictional v0.2 controls",
            source_url="https://example.invalid/controls-v0-2",
            store_false_required=True,
            zero_retention_claimed=False,
            retention_and_abuse_monitoring_summary="Fictional limitations apply.",
        ),
    )
    return authorization, pricing, controls


def _raw_output() -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-v0-2-batch",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class FictionalSDKResponse:
    status = "completed"
    model = "gpt-5.4-mini-fictional-v0-2"
    id = "resp_fictional_v0_2"
    _request_id = "req_fictional_v0_2"
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    output = (
        SimpleNamespace(
            type="message",
            content=(SimpleNamespace(type="output_text", text=_raw_output()),),
        ),
    )

    def model_dump(self, *, mode: str) -> dict[str, str]:
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
        self.option_calls.append(
            {"max_retries": max_retries, "timeout": timeout}
        )
        return self


def _artifact_paths(root: Path) -> tuple[Path, Path, Path, Path]:
    return (
        root.joinpath(*execution.V0_1_ATTEMPT_MARKER_RELATIVE_PATH.parts),
        root.joinpath(*execution.ATTEMPT_MARKER_RELATIVE_PATH.parts),
        root.joinpath(*execution.SUCCESSFUL_RECORD_RELATIVE_PATH.parts),
        root.joinpath(*execution.FAILURE_RECORD_RELATIVE_PATH.parts),
    )


def _execute(
    root: Path,
    *,
    outcome: object | None = None,
    key: object = FICTIONAL_VALID_KEY,
) -> tuple[object, FakeClient]:
    paths = _input_paths(root)
    client = FakeClient(outcome or FictionalSDKResponse())
    result = execution._execute_openai_synthetic_preflight_transaction(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=root,
        execute_real_preflight=True,
        confirmation=execution.EXECUTION_CONFIRMATION,
        clock=lambda: NOW,
        api_key_reader=lambda: key,  # type: ignore[return-value]
        client_factory=lambda supplied: client,
    )
    return result, client


def test_v0_2_plan_uses_exact_separate_identities_and_paths() -> None:
    plan = execution.build_openai_preflight_execution_plan()

    assert plan.preflight_id == PREFLIGHT_ID
    assert plan.authorization_scope == PREFLIGHT_AUTHORIZATION_SCOPE
    assert execution.EXECUTION_CONFIRMATION == (
        "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_2"
    )
    assert "-v0.2.attempt.json" in plan.attempt_marker_path
    assert "-v0.2.record.json" in plan.successful_record_path
    assert "-v0.2.failure.json" in plan.failure_record_path
    assert "v0.1" not in plan.attempt_marker_path
    assert "v0.1" not in plan.successful_record_path
    assert "v0.1" not in plan.failure_record_path


@pytest.mark.parametrize(
    "invalid_key",
    (
        "x",
        "sk-",
        "sk-short",
        "sk-" + "A" * 37,
        "sk-proj-" + "A" * 95,
        " sk-" + "A" * 64,
        "sk-" + "A" * 64 + " ",
        "sk-" + "A" * 20 + "\n" + "B" * 30,
        "sk-" + "A" * 20 + "\x00" + "B" * 30,
        True,
        None,
    ),
)
def test_malformed_credentials_fail_before_output_marker_client_or_provider(
    tmp_path: Path,
    invalid_key: object,
) -> None:
    paths = _input_paths(tmp_path)
    factory_calls = 0

    def forbidden_factory(supplied: str) -> object:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("invalid credential reached client construction")

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: invalid_key,  # type: ignore[return-value]
            client_factory=forbidden_factory,
        )

    _, marker, success, failure = _artifact_paths(tmp_path)
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID
    assert factory_calls == 0
    assert not tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()
    assert not marker.exists()
    assert not success.exists()
    assert not failure.exists()
    assert str(invalid_key) not in str(captured.value)


def test_valid_shaped_fictional_key_reaches_one_injected_fake_call(
    tmp_path: Path,
) -> None:
    result, client = _execute(tmp_path)
    _, marker, success, failure = _artifact_paths(tmp_path)

    assert result.record.preflight_id == PREFLIGHT_ID  # type: ignore[attr-defined]
    assert marker.is_file()
    assert success.is_file()
    assert not failure.exists()
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert len(client.responses.calls) == 1
    exact_payload = build_openai_responses_payload(
        execution.build_synthetic_openai_preflight_request()
    )
    assert client.responses.calls == [exact_payload]
    assert exact_payload["max_output_tokens"] == 4096
    assert exact_payload["reasoning"] == {"effort": "none"}
    assert exact_payload["store"] is False
    assert exact_payload["stream"] is False
    assert exact_payload["background"] is False
    assert exact_payload["tools"] == []
    assert exact_payload["tool_choice"] == "none"


def test_client_construction_failure_records_zero_calls_without_secret(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)

    def failed_factory(supplied: str) -> object:
        raise RuntimeError(f"unsafe client error {supplied}")

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=failed_factory,
        )

    _, marker, success, failure_path = _artifact_paths(tmp_path)
    record = execution.OpenAIPreflightFailureRecordV02.model_validate_json(
        failure_path.read_bytes()
    )
    assert captured.value.code is Stage4BErrorCode.EXECUTION_FAILED
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert record.failure_stage == "client_construction"
    assert record.provider_call_count == 0
    assert record.retry_count == 0
    assert marker.is_file()
    assert not success.exists()
    assert FICTIONAL_VALID_KEY not in failure_path.read_text(encoding="utf-8")
    assert FICTIONAL_VALID_KEY not in str(captured.value)
    assert FICTIONAL_VALID_KEY not in repr(captured.value)


def test_v0_1_marker_is_unchanged_and_does_not_block_v0_2(tmp_path: Path) -> None:
    v0_1_marker, v0_2_marker, success, failure = _artifact_paths(tmp_path)
    v0_1_marker.parent.mkdir(parents=True)
    historical_bytes = b'{"fictional":"immutable-v0.1-evidence"}\n'
    v0_1_marker.write_bytes(historical_bytes)
    before_hash = uppercase_sha256_bytes(historical_bytes)

    result, client = _execute(tmp_path)

    assert result.record.preflight_id == PREFLIGHT_ID  # type: ignore[attr-defined]
    assert v0_1_marker.read_bytes() == historical_bytes
    assert uppercase_sha256_bytes(v0_1_marker.read_bytes()) == before_hash
    assert v0_2_marker.is_file()
    assert success.is_file()
    assert not failure.exists()
    assert len(client.responses.calls) == 1


def test_v0_2_marker_blocks_second_attempt_before_key_client_or_call(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    _, first_client = _execute(tmp_path)
    key_calls = 0
    factory_calls = 0

    def forbidden_key() -> str:
        nonlocal key_calls
        key_calls += 1
        return FICTIONAL_VALID_KEY

    def forbidden_factory(supplied: str) -> object:
        nonlocal factory_calls
        factory_calls += 1
        return FakeClient(FictionalSDKResponse())

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


def _fictional_api_status_error(
    secret: str,
    *,
    provider_type: str = "invalid_request_error",
    provider_code: str = "invalid_api_key",
    request_id: str = "req_fictional_failure_v0_2",
) -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.invalid/v1/responses")
    response = httpx.Response(
        401,
        request=request,
        headers={
            "x-request-id": request_id,
            "authorization": f"Bearer {secret}",
            "x-sensitive": secret,
        },
        content=f'{{"secret":"{secret}"}}'.encode("utf-8"),
    )
    return APIStatusError(
        f"unsafe provider message {secret}",
        response=response,
        body={
            "type": provider_type,
            "code": provider_code,
            "message": secret,
            "prompt": "fictional prompt body",
        },
    )


def test_api_status_failure_writes_sanitized_self_hashed_failure_record(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    client = FakeClient(_fictional_api_status_error(FICTIONAL_VALID_KEY))

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=lambda supplied: client,
        )

    _, marker, success, failure_path = _artifact_paths(tmp_path)
    raw = failure_path.read_bytes()
    payload = json.loads(raw)
    record = execution.OpenAIPreflightFailureRecordV02.model_validate(payload)
    assert captured.value.code is Stage4BErrorCode.PROVIDER_API_FAILURE
    assert marker.is_file()
    assert not success.exists()
    assert failure_path.is_file()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert record.failure_stage == "provider_call"
    assert record.local_error_code is Stage4BErrorCode.PROVIDER_API_FAILURE
    assert record.http_status_code == 401
    assert record.provider_error_type == "invalid_request_error"
    assert record.provider_error_code == "invalid_api_key"
    assert record.provider_request_id == "req_fictional_failure_v0_2"
    assert record.retry_count == 0
    assert record.provider_call_count == 1
    assert record.successful_record_written is False
    assert record.attempt_marker_sha256 == uppercase_sha256_bytes(
        marker.read_bytes()
    )
    assert execution.failure_record_bytes(record) + b"\n" == raw
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert len(client.responses.calls) == 1
    artifact_text = raw.decode("utf-8")
    for forbidden in (
        FICTIONAL_VALID_KEY,
        "unsafe provider message",
        "fictional prompt body",
        "Bearer",
        "x-sensitive",
    ):
        assert forbidden not in artifact_text
        assert forbidden not in str(captured.value)
        assert forbidden not in repr(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    ("record_field", "error_field"),
    (
        ("provider_error_type", "provider_type"),
        ("provider_error_code", "provider_code"),
        ("provider_request_id", "request_id"),
    ),
)
@pytest.mark.parametrize(
    "unsafe_diagnostic",
    (
        FICTIONAL_VALID_KEY,
        "trace-sk-fictional_fragment",
        FICTIONAL_VALID_KEY[:80],
        FICTIONAL_VALID_KEY[-80:],
    ),
    ids=("complete", "sk-fragment", "long-prefix", "long-suffix"),
)
def test_credential_derived_status_diagnostics_are_scrubbed_before_artifact(
    tmp_path: Path,
    record_field: str,
    error_field: str,
    unsafe_diagnostic: str,
) -> None:
    paths = _input_paths(tmp_path)
    overrides = {error_field: unsafe_diagnostic}
    client = FakeClient(
        _fictional_api_status_error(FICTIONAL_VALID_KEY, **overrides)
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
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=lambda supplied: client,
        )

    failure_path = _artifact_paths(tmp_path)[3]
    record = execution.load_openai_preflight_failure_record(failure_path)
    artifact_text = failure_path.read_text(encoding="utf-8")
    assert getattr(record, record_field) is None
    assert record.failure_stage == "provider_call"
    assert record.provider_call_count == 1
    for forbidden in (FICTIONAL_VALID_KEY, unsafe_diagnostic):
        assert forbidden not in artifact_text
        assert forbidden not in str(captured.value)
        assert forbidden not in repr(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_invalid_output_after_response_uses_post_provider_validation_stage(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    response = FictionalSDKResponse()
    response.status = "incomplete"
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
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=lambda supplied: client,
        )

    record = execution.load_openai_preflight_failure_record(
        _artifact_paths(tmp_path)[3]
    )
    assert captured.value.code is Stage4BErrorCode.INCOMPLETE_RESPONSE
    assert record.failure_stage == "post_provider_validation"
    assert record.provider_call_count == 1
    assert len(client.responses.calls) == 1


def test_failure_record_hash_tampering_is_rejected(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    with pytest.raises(Stage4BError):
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=lambda supplied: FakeClient(
                _fictional_api_status_error(FICTIONAL_VALID_KEY)
            ),
        )
    failure_path = _artifact_paths(tmp_path)[3]
    payload = json.loads(failure_path.read_bytes())
    payload["provider_call_count"] = 0
    failure_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_failure_record(failure_path)

    assert (
        captured.value.code
        is Stage4BErrorCode.PREFLIGHT_FAILURE_RECORD_HASH_MISMATCH
    )


def test_failure_record_creation_is_exclusive(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )
    with pytest.raises(Stage4BError):
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_VALID_KEY,
            client_factory=lambda supplied: FakeClient(
                _fictional_api_status_error(FICTIONAL_VALID_KEY)
            ),
        )
    existing = execution.OpenAIPreflightFailureRecordV02.model_validate_json(
        readiness.failure_record_path.read_bytes()
    )

    with pytest.raises(Stage4BError) as captured:
        execution._write_failure_record_exclusive(
            readiness=readiness,
            attempt_marker_sha256=existing.attempt_marker_sha256,
            failure_timestamp=NOW,
            failure_stage="provider_call",
            error=Stage4BError(
                Stage4BErrorCode.PROVIDER_API_FAILURE,
                "fictional safe failure",
            ),
            diagnostics=None,
            provider_call_count=1,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED


def test_failure_record_cannot_coexist_with_success(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )
    result, _ = _execute(tmp_path)

    with pytest.raises(Stage4BError) as captured:
        execution._write_failure_record_exclusive(
            readiness=readiness,
            attempt_marker_sha256=uppercase_sha256_bytes(
                readiness.attempt_marker_path.read_bytes()
            ),
            failure_timestamp=NOW,
            failure_stage="successful_record_write",
            error=Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
                "fictional safe failure",
            ),
            diagnostics=None,
            provider_call_count=1,
        )

    assert result.record.preflight_status == "passed"  # type: ignore[attr-defined]
    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED
    assert not readiness.failure_record_path.exists()


def test_v0_2_execution_uses_no_network_or_real_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("offline v0.2 execution attempted a network operation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    result, client = _execute(tmp_path)

    assert result.record.preflight_status == "passed"  # type: ignore[attr-defined]
    assert len(client.responses.calls) == 1
