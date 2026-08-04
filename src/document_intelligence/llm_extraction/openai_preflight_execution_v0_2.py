"""Default-deny transaction boundary for the separate v0.2 preflight."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from openai import APIStatusError, RateLimitError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.llm_extraction import (
    openai_preflight_execution as v0_1_execution,
)
from document_intelligence.llm_extraction.contracts import LLMExtractionRequest
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_preflight_bridge import (
    OpenAIResponsesPreflightBridge,
)
from document_intelligence.llm_extraction.openai_preflight_v0_2 import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    PREFLIGHT_INPUT_CLASSIFICATION,
    OpenAIPreflightAuthorizationV02,
    OpenAIPreflightRecordV02,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_API_SURFACE,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OpenAIProviderFailure,
    OpenAIProviderFailureDiagnostics,
    OpenAIResponsesProvider,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


EXECUTION_CONFIRMATION = "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_2"
EXECUTION_PLAN_SCHEMA_VERSION: Literal["0.2"] = "0.2"
ATTEMPT_MARKER_SCHEMA_VERSION: Literal["0.2"] = "0.2"
FAILURE_RECORD_SCHEMA_VERSION: Literal["0.2"] = "0.2"
OUTPUT_DIRECTORY = PurePosixPath("reports/llm_extraction/openai_preflight")
ATTEMPT_MARKER_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.2.attempt.json"
)
SUCCESSFUL_RECORD_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.2.record.json"
)
FAILURE_RECORD_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.2.failure.json"
)
V0_1_ATTEMPT_MARKER_RELATIVE_PATH = (
    v0_1_execution.ATTEMPT_MARKER_RELATIVE_PATH
)
# Project-scoped keys currently use a long shape. This intentionally conservative
# offline floor rejects plausible partial clipboard values without inspecting a
# real credential or claiming to validate provider authentication.
MINIMUM_API_KEY_LENGTH = 120
MAXIMUM_API_KEY_LENGTH = 512
_API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")
_SAFE_DIAGNOSTIC_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_MINIMUM_MEANINGFUL_CREDENTIAL_FRAGMENT_LENGTH = 12


def _utc_json(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class OpenAIPreflightExecutionPlanV02(BaseModel):
    """Immutable non-sensitive identity for the v0.2 boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_plan_schema_version: Literal["0.2"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.2"]
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.2"]
    provider_identifier: Literal["openai"]
    api_surface: Literal["responses"]
    requested_model_alias: Literal["gpt-5.4-mini"]
    maximum_provider_calls: Literal[1]
    input_classification: Literal["synthetic_preflight_text"]
    canonical_request_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    synthetic_document_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    strict_schema_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    attempt_marker_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.2.attempt.json"
    ]
    successful_record_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.2.record.json"
    ]
    failure_record_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.2.failure.json"
    ]
    execution_plan_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightExecutionPlanV02:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"execution_plan_sha256"})
            )
        )
        if self.execution_plan_sha256 != expected:
            raise ValueError("execution_plan_sha256 does not match plan identity")
        return self


@dataclass(frozen=True)
class _ExecutionPlanAnchors:
    canonical_request_sha256: str
    prompt_sha256: str
    synthetic_document_sha256: str
    strict_schema_sha256: str
    provider_payload_sha256: str


def _derive_execution_plan_anchors() -> _ExecutionPlanAnchors:
    return _derive_execution_plan_anchors_for_request(
        build_synthetic_openai_preflight_request()
    )


def _derive_execution_plan_anchors_for_request(
    request: LLMExtractionRequest,
) -> _ExecutionPlanAnchors:
    if not isinstance(request, LLMExtractionRequest):
        raise TypeError("preflight request must use LLMExtractionRequest")
    validate_request_identity(request)
    request_bytes = canonical_json_bytes(
        request.model_dump(mode="json", exclude={"canonical_request_sha256"})
    )
    schema = build_openai_candidate_schema()
    payload = build_openai_responses_payload(request)
    return _ExecutionPlanAnchors(
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        prompt_sha256=request.prompt_sha256,
        synthetic_document_sha256=request.document_sha256,
        strict_schema_sha256=uppercase_sha256_bytes(canonical_json_bytes(schema)),
        provider_payload_sha256=uppercase_sha256_bytes(
            canonical_json_bytes(payload)
        ),
    )


def _build_execution_plan(
    anchors: _ExecutionPlanAnchors,
) -> OpenAIPreflightExecutionPlanV02:
    values = {
        "execution_plan_schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_scope": PREFLIGHT_AUTHORIZATION_SCOPE,
        "provider_identifier": OPENAI_PROVIDER_IDENTIFIER,
        "api_surface": OPENAI_API_SURFACE,
        "requested_model_alias": OPENAI_REQUESTED_MODEL_ALIAS,
        "maximum_provider_calls": 1,
        "input_classification": PREFLIGHT_INPUT_CLASSIFICATION,
        "canonical_request_sha256": anchors.canonical_request_sha256,
        "prompt_sha256": anchors.prompt_sha256,
        "synthetic_document_sha256": anchors.synthetic_document_sha256,
        "strict_schema_sha256": anchors.strict_schema_sha256,
        "provider_payload_sha256": anchors.provider_payload_sha256,
        "attempt_marker_path": ATTEMPT_MARKER_RELATIVE_PATH.as_posix(),
        "successful_record_path": SUCCESSFUL_RECORD_RELATIVE_PATH.as_posix(),
        "failure_record_path": FAILURE_RECORD_RELATIVE_PATH.as_posix(),
    }
    return OpenAIPreflightExecutionPlanV02.model_validate(
        {
            **values,
            "execution_plan_sha256": uppercase_sha256_bytes(
                canonical_json_bytes(values)
            ),
        }
    )


def build_openai_preflight_execution_plan() -> OpenAIPreflightExecutionPlanV02:
    """Build the deterministic v0.2 plan without credential or client access."""
    return _build_execution_plan(_derive_execution_plan_anchors())


def _require_plan_anchor_match(
    plan: OpenAIPreflightExecutionPlanV02,
    anchors: _ExecutionPlanAnchors,
) -> None:
    for field_name in (
        "canonical_request_sha256",
        "prompt_sha256",
        "synthetic_document_sha256",
        "strict_schema_sha256",
        "provider_payload_sha256",
    ):
        if getattr(plan, field_name) != getattr(anchors, field_name):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                f"provider-entry {field_name} differs from the readiness plan",
            )


@dataclass
class _ProviderCallCounter:
    count: int = 0
    response_returned: bool = False


def _credential_safe_provider_diagnostic(
    value: object,
    credential: str,
) -> str | None:
    if (
        type(value) is not str
        or _SAFE_DIAGNOSTIC_PATTERN.fullmatch(value) is None
        or "sk-" in value.casefold()
    ):
        return None
    normalized_value = value.casefold()
    normalized_credential = credential.casefold()
    if normalized_credential in normalized_value:
        return None
    if (
        len(normalized_value) >= _MINIMUM_MEANINGFUL_CREDENTIAL_FRAGMENT_LENGTH
        and normalized_value in normalized_credential
    ):
        return None
    fragment_length = _MINIMUM_MEANINGFUL_CREDENTIAL_FRAGMENT_LENGTH
    for start in range(len(normalized_credential) - fragment_length + 1):
        if normalized_credential[start : start + fragment_length] in normalized_value:
            return None
    return value


def _credential_scrubbed_diagnostics(
    diagnostics: OpenAIProviderFailureDiagnostics,
    credential: str,
) -> OpenAIProviderFailureDiagnostics:
    return OpenAIProviderFailureDiagnostics(
        http_status_code=diagnostics.http_status_code,
        provider_error_type=_credential_safe_provider_diagnostic(
            diagnostics.provider_error_type,
            credential,
        ),
        provider_error_code=_credential_safe_provider_diagnostic(
            diagnostics.provider_error_code,
            credential,
        ),
        provider_request_id=_credential_safe_provider_diagnostic(
            diagnostics.provider_request_id,
            credential,
        ),
    )


def _credential_scrubbed_status_failure(
    error: APIStatusError,
    credential: str,
) -> OpenAIProviderFailure:
    status = getattr(error, "status_code", None)
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    diagnostics = OpenAIProviderFailureDiagnostics(
        http_status_code=status,
        provider_error_type=_credential_safe_provider_diagnostic(
            getattr(error, "type", None),
            credential,
        ),
        provider_error_code=_credential_safe_provider_diagnostic(
            getattr(error, "code", None),
            credential,
        ),
        provider_request_id=_credential_safe_provider_diagnostic(
            getattr(error, "request_id", None),
            credential,
        ),
    )
    code = (
        Stage4BErrorCode.RATE_LIMIT
        if isinstance(error, RateLimitError)
        else Stage4BErrorCode.PROVIDER_API_FAILURE
    )
    return OpenAIProviderFailure(code, diagnostics)


@dataclass(frozen=True)
class _CountingResponsesResource:
    delegate: object
    counter: _ProviderCallCounter
    credential: str

    def create(self, **kwargs: Any) -> object:
        if self.counter.count != 0:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
                "v0.2 provider call budget has already been consumed",
            )
        self.counter.count = 1
        create = getattr(self.delegate, "create")
        failure: OpenAIProviderFailure | None = None
        response: object | None = None
        try:
            response = create(**kwargs)
        except APIStatusError as error:
            failure = _credential_scrubbed_status_failure(error, self.credential)
        if failure is not None:
            raise failure
        self.counter.response_returned = True
        if response is None:
            raise Stage4BError(
                Stage4BErrorCode.PROVIDER_API_FAILURE,
                "OpenAI Responses call returned no response",
            )
        return response


@dataclass(frozen=True)
class _CountingConfiguredClient:
    responses: _CountingResponsesResource


@dataclass(frozen=True)
class _CountingOpenAIClient:
    delegate: object
    counter: _ProviderCallCounter
    credential: str

    def with_options(
        self,
        *,
        max_retries: int,
        timeout: float,
    ) -> _CountingConfiguredClient:
        with_options = getattr(self.delegate, "with_options")
        configured = with_options(max_retries=max_retries, timeout=timeout)
        return _CountingConfiguredClient(
            responses=_CountingResponsesResource(
                delegate=getattr(configured, "responses"),
                counter=self.counter,
                credential=self.credential,
            )
        )


@dataclass(frozen=True)
class _PlanBoundPreflightProvider:
    plan: OpenAIPreflightExecutionPlanV02
    delegate: OpenAIResponsesPreflightBridge

    def generate_preflight(self, request: LLMExtractionRequest) -> object:
        try:
            anchors = _derive_execution_plan_anchors_for_request(request)
        except Exception:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                "provider-entry request could not be bound to the readiness plan",
            ) from None
        _require_plan_anchor_match(self.plan, anchors)
        return self.delegate.generate_preflight(request)


class OpenAIPreflightAttemptMarkerV02(BaseModel):
    """Permanent evidence that the separate v0.2 call may have started."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    marker_schema_version: Literal["0.2"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.2"]
    authorization_id: str
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.2"]
    execution_plan_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    attempt_timestamp_utc: datetime
    maximum_provider_calls: Literal[1]
    state: Literal["provider_call_may_have_started"]
    marker_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_validator("authorization_id")
    @classmethod
    def validate_authorization_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("authorization_id must be trimmed and nonblank")
        return value

    @field_validator("attempt_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return v0_1_execution._require_utc(value, "attempt_timestamp_utc")

    @field_serializer("attempt_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightAttemptMarkerV02:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"marker_sha256"})
            )
        )
        if self.marker_sha256 != expected:
            raise ValueError("marker_sha256 does not match marker identity")
        return self


def _build_attempt_marker(
    *,
    authorization: OpenAIPreflightAuthorizationV02,
    plan: OpenAIPreflightExecutionPlanV02,
    timestamp: datetime,
) -> OpenAIPreflightAttemptMarkerV02:
    values = {
        "marker_schema_version": ATTEMPT_MARKER_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_id": authorization.authorization_id,
        "authorization_scope": authorization.scope,
        "execution_plan_sha256": plan.execution_plan_sha256,
        "attempt_timestamp_utc": _utc_json(timestamp),
        "maximum_provider_calls": 1,
        "state": "provider_call_may_have_started",
    }
    return OpenAIPreflightAttemptMarkerV02.model_validate(
        {
            **values,
            "marker_sha256": uppercase_sha256_bytes(canonical_json_bytes(values)),
        }
    )


def attempt_marker_bytes(marker: OpenAIPreflightAttemptMarkerV02) -> bytes:
    validated = OpenAIPreflightAttemptMarkerV02.model_validate(
        marker.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


FailureStage = Literal[
    "client_construction",
    "provider_construction",
    "provider_call",
    "post_provider_validation",
    "record_validation",
    "successful_record_write",
]


class OpenAIPreflightFailureRecordV02(BaseModel):
    """Sanitized self-hashed evidence for one post-marker v0.2 failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    failure_record_schema_version: Literal["0.2"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.2"]
    authorization_id: str
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.2"]
    execution_plan_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    attempt_marker_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    failure_timestamp_utc: datetime
    failure_stage: FailureStage
    local_error_code: Stage4BErrorCode
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    provider_error_type: str | None = None
    provider_error_code: str | None = None
    provider_request_id: str | None = None
    retry_count: Literal[0]
    provider_call_count: int = Field(ge=0, le=1)
    successful_record_written: Literal[False]
    failure_record_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_validator("authorization_id")
    @classmethod
    def validate_authorization_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("authorization_id must be trimmed and nonblank")
        return value

    @field_validator("failure_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return v0_1_execution._require_utc(value, "failure_timestamp_utc")

    @field_validator("http_status_code", "provider_call_count", mode="before")
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("failure integer fields must not use booleans")
        return value

    @field_validator(
        "provider_error_type",
        "provider_error_code",
        "provider_request_id",
        mode="before",
    )
    @classmethod
    def validate_diagnostic_text(cls, value: object) -> object:
        if value is None:
            return None
        if type(value) is not str or _SAFE_DIAGNOSTIC_PATTERN.fullmatch(value) is None:
            raise ValueError("failure diagnostic is not safely representable")
        return value

    @field_serializer("failure_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightFailureRecordV02:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"failure_record_sha256"})
            )
        )
        if self.failure_record_sha256 != expected:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_FAILURE_RECORD_HASH_MISMATCH,
                "failure_record_sha256 does not match canonical record bytes",
            )
        return self


def _build_failure_record(
    *,
    readiness: OpenAIPreflightReadinessV02,
    attempt_marker_sha256: str,
    failure_timestamp: datetime,
    failure_stage: FailureStage,
    error: Stage4BError,
    diagnostics: OpenAIProviderFailureDiagnostics | None,
    provider_call_count: int,
) -> OpenAIPreflightFailureRecordV02:
    values = {
        "failure_record_schema_version": FAILURE_RECORD_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_id": readiness.inputs.authorization.authorization_id,
        "authorization_scope": readiness.inputs.authorization.scope,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "attempt_marker_sha256": attempt_marker_sha256,
        "failure_timestamp_utc": _utc_json(failure_timestamp),
        "failure_stage": failure_stage,
        "local_error_code": error.code,
        "http_status_code": (
            diagnostics.http_status_code if diagnostics is not None else None
        ),
        "provider_error_type": (
            diagnostics.provider_error_type if diagnostics is not None else None
        ),
        "provider_error_code": (
            diagnostics.provider_error_code if diagnostics is not None else None
        ),
        "provider_request_id": (
            diagnostics.provider_request_id if diagnostics is not None else None
        ),
        "retry_count": 0,
        "provider_call_count": provider_call_count,
        "successful_record_written": False,
    }
    return OpenAIPreflightFailureRecordV02.model_validate(
        {
            **values,
            "failure_record_sha256": uppercase_sha256_bytes(
                canonical_json_bytes(values)
            ),
        }
    )


def failure_record_bytes(record: OpenAIPreflightFailureRecordV02) -> bytes:
    validated = OpenAIPreflightFailureRecordV02.model_validate(
        record.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


def validate_failure_record_payload(
    payload: dict[str, Any],
) -> OpenAIPreflightFailureRecordV02:
    values = dict(payload)
    claimed_hash = values.pop("failure_record_sha256", None)
    try:
        expected_hash = uppercase_sha256_bytes(canonical_json_bytes(values))
    except (TypeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            "v0.2 failure record is not canonical JSON",
        ) from error
    if type(claimed_hash) is not str or claimed_hash != expected_hash:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_FAILURE_RECORD_HASH_MISMATCH,
            "failure_record_sha256 does not match canonical record bytes",
        )
    try:
        return OpenAIPreflightFailureRecordV02.model_validate(payload)
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            "v0.2 failure record does not satisfy its frozen contract",
        ) from error


def load_openai_preflight_failure_record(
    path: Path,
) -> OpenAIPreflightFailureRecordV02:
    payload = v0_1_execution._read_json_object(path, label="v0.2 failure record")
    return validate_failure_record_payload(payload)


@dataclass(frozen=True)
class OpenAIPreflightInputsV02:
    authorization: OpenAIPreflightAuthorizationV02
    pricing_observation: OpenAIPricingObservation
    data_controls_observation: OpenAIDataControlsObservation


@dataclass(frozen=True)
class OpenAIPreflightReadinessV02:
    plan: OpenAIPreflightExecutionPlanV02
    inputs: OpenAIPreflightInputsV02
    execution_timestamp_utc: datetime
    repository_root: Path
    attempt_marker_path: Path
    successful_record_path: Path
    failure_record_path: Path


@dataclass(frozen=True)
class OpenAIPreflightExecutionResultV02:
    plan: OpenAIPreflightExecutionPlanV02
    marker: OpenAIPreflightAttemptMarkerV02
    record: OpenAIPreflightRecordV02
    attempt_marker_path: Path
    successful_record_path: Path
    failure_record_path: Path


def _validate_input_model(
    path: Path,
    *,
    label: str,
    model_type: type[BaseModel],
) -> BaseModel:
    try:
        return model_type.model_validate(
            v0_1_execution._read_json_object(path, label=label)
        )
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input does not satisfy its frozen contract",
        ) from error


def _load_openai_preflight_inputs(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
) -> OpenAIPreflightInputsV02:
    paths = (authorization_path, pricing_path, data_controls_path)
    protected_roots = {
        v0_1_execution._absolute_lexical_path(repository_root),
        v0_1_execution._absolute_lexical_path(
            v0_1_execution._installed_repository_root()
        ),
    }
    for path in paths:
        for protected_root in protected_roots:
            v0_1_execution._reject_protected_repository_input(path, protected_root)
    authorization = _validate_input_model(
        authorization_path,
        label="authorization",
        model_type=OpenAIPreflightAuthorizationV02,
    )
    pricing = _validate_input_model(
        pricing_path,
        label="pricing observation",
        model_type=OpenAIPricingObservation,
    )
    data_controls = _validate_input_model(
        data_controls_path,
        label="data-controls observation",
        model_type=OpenAIDataControlsObservation,
    )
    assert isinstance(authorization, OpenAIPreflightAuthorizationV02)
    assert isinstance(pricing, OpenAIPricingObservation)
    assert isinstance(data_controls, OpenAIDataControlsObservation)
    return OpenAIPreflightInputsV02(authorization, pricing, data_controls)


def _validate_loaded_inputs(
    inputs: OpenAIPreflightInputsV02,
    execution_timestamp: datetime,
) -> OpenAIPreflightInputsV02:
    try:
        authorization = OpenAIPreflightAuthorizationV02.model_validate(
            inputs.authorization.model_dump(mode="python")
        )
        pricing = OpenAIPricingObservation.model_validate(
            inputs.pricing_observation.model_dump(mode="python")
        )
        data_controls = OpenAIDataControlsObservation.model_validate(
            inputs.data_controls_observation.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "v0.2 authorization or terms evidence is invalid",
        ) from error
    if authorization.authorized_at_utc > execution_timestamp:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "authorization timestamp must not postdate execution",
        )
    if (
        pricing.observed_at_utc.date() != execution_timestamp.date()
        or data_controls.observed_at_utc.date() != execution_timestamp.date()
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "pricing and data-control observations must use the execution UTC date",
        )
    return OpenAIPreflightInputsV02(authorization, pricing, data_controls)


def _fixed_artifact_paths(repository_root: Path) -> tuple[Path, Path, Path, Path]:
    root = v0_1_execution._validate_path_chain(
        repository_root,
        label="repository root",
    )
    try:
        metadata = os.lstat(root)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "repository root must be an existing regular directory",
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "repository root must be an existing regular directory",
        )
    return (
        root.joinpath(*OUTPUT_DIRECTORY.parts),
        root.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parts),
        root.joinpath(*SUCCESSFUL_RECORD_RELATIVE_PATH.parts),
        root.joinpath(*FAILURE_RECORD_RELATIVE_PATH.parts),
    )


def _require_artifacts_absent(marker: Path, success: Path, failure: Path) -> None:
    if os.path.lexists(marker):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
            "the fixed v0.2 preflight attempt marker already exists",
        )
    if os.path.lexists(success) or os.path.lexists(failure):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
            "a fixed v0.2 preflight outcome artifact already exists",
        )


def _validate_openai_preflight_readiness(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    clock: Callable[[], datetime],
) -> OpenAIPreflightReadinessV02:
    inputs = _load_openai_preflight_inputs(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=repository_root,
    )
    timestamp = v0_1_execution._validated_timestamp(clock)
    inputs = _validate_loaded_inputs(inputs, timestamp)
    plan = _build_execution_plan(_derive_execution_plan_anchors())
    output, marker, success, failure = _fixed_artifact_paths(repository_root)
    for path, label in (
        (output, "preflight output"),
        (marker, "v0.2 preflight attempt marker"),
        (success, "v0.2 preflight successful record"),
        (failure, "v0.2 preflight failure record"),
    ):
        v0_1_execution._validate_path_chain(path, label=label)
    _require_artifacts_absent(marker, success, failure)
    return OpenAIPreflightReadinessV02(
        plan=plan,
        inputs=inputs,
        execution_timestamp_utc=timestamp,
        repository_root=v0_1_execution._absolute_lexical_path(repository_root),
        attempt_marker_path=marker,
        successful_record_path=success,
        failure_record_path=failure,
    )


def _installed_repository_root() -> Path:
    return Path(__file__).parents[3]


def resolve_production_repository_root(
    launch_directory: Path | None = None,
) -> Path:
    """Bind v0.2 production execution to its installed local checkout."""
    root = v0_1_execution._validate_project_repository_identity(
        _installed_repository_root()
    )
    selected = launch_directory if launch_directory is not None else Path.cwd()
    try:
        launch = v0_1_execution._validate_path_chain(
            selected,
            label="launch directory",
        )
        launch_status = os.lstat(launch)
        launch.relative_to(root)
    except (OSError, ValueError, Stage4BError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "command must be launched from this verified project repository",
        ) from error
    if not stat.S_ISDIR(launch_status.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "command launch location must be a repository directory",
        )
    return root


def validate_openai_preflight_readiness(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
) -> OpenAIPreflightReadinessV02:
    root = resolve_production_repository_root(Path.cwd())
    return _validate_openai_preflight_readiness(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        clock=_utc_now,
    )


def _create_output_directory(repository_root: Path) -> Path:
    output, _, _, _ = _fixed_artifact_paths(repository_root)
    v0_1_execution._validate_path_chain(output, label="preflight output")
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output directory could not be created",
        ) from error
    output = v0_1_execution._validate_path_chain(output, label="preflight output")
    try:
        metadata = os.lstat(output)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output directory could not be inspected",
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output path is not a directory",
        )
    return output


def validate_openai_api_key_shape(value: object) -> str:
    """Return a valid-shaped key without ever describing its supplied value."""
    if (
        type(value) is not str
        or not MINIMUM_API_KEY_LENGTH <= len(value) <= MAXIMUM_API_KEY_LENGTH
        or not value.startswith("sk-")
        or value != value.strip()
        or any(character.isspace() or not character.isprintable() for character in value)
        or _API_KEY_PATTERN.fullmatch(value) is None
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID,
            "OPENAI_API_KEY has an invalid local shape",
        )
    return value


def _require_record_matches_plan(
    record: OpenAIPreflightRecordV02,
    plan: OpenAIPreflightExecutionPlanV02,
) -> None:
    if not isinstance(record, OpenAIPreflightRecordV02):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "preflight runner did not return the v0.2 record contract",
        )
    expected = {
        "canonical_request_sha256": plan.canonical_request_sha256,
        "prompt_sha256": plan.prompt_sha256,
        "document_sha256": plan.synthetic_document_sha256,
        "strict_schema_sha256": plan.strict_schema_sha256,
        "provider_payload_sha256": plan.provider_payload_sha256,
    }
    for field_name, value in expected.items():
        if getattr(record, field_name) != value:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                f"returned record {field_name} differs from the readiness plan",
            )


def _sanitized_post_marker_failure(
    error: Exception,
    credential: str,
) -> tuple[Stage4BError, OpenAIProviderFailureDiagnostics | None]:
    if isinstance(error, OpenAIProviderFailure):
        diagnostics = _credential_scrubbed_diagnostics(
            error.diagnostics,
            credential,
        )
        sanitized = OpenAIProviderFailure(error.code, diagnostics)
        return sanitized, sanitized.diagnostics
    if isinstance(error, Stage4BError):
        return (
            Stage4BError(
                error.code,
                "OpenAI v0.2 synthetic preflight failed after marker creation",
            ),
            None,
        )
    return (
        Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "OpenAI v0.2 synthetic preflight failed after marker creation",
        ),
        None,
    )


def _write_failure_record_exclusive(
    *,
    readiness: OpenAIPreflightReadinessV02,
    attempt_marker_sha256: str,
    failure_timestamp: datetime,
    failure_stage: FailureStage,
    error: Stage4BError,
    diagnostics: OpenAIProviderFailureDiagnostics | None,
    provider_call_count: int,
) -> OpenAIPreflightFailureRecordV02:
    if not os.path.lexists(readiness.attempt_marker_path):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "v0.2 failure record requires an existing attempt marker",
        )
    if os.path.lexists(readiness.successful_record_path):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "v0.2 failure record cannot coexist with a successful record",
        )
    record = _build_failure_record(
        readiness=readiness,
        attempt_marker_sha256=attempt_marker_sha256,
        failure_timestamp=failure_timestamp,
        failure_stage=failure_stage,
        error=error,
        diagnostics=diagnostics,
        provider_call_count=provider_call_count,
    )
    v0_1_execution._write_exclusive(
        readiness.failure_record_path,
        failure_record_bytes(record),
        marker=False,
    )
    return record


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_production_openai_client_factory = v0_1_execution._production_openai_client_factory
_openai_api_key_from_environment = v0_1_execution._openai_api_key_from_environment


def _execute_openai_synthetic_preflight_transaction(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    execute_real_preflight: bool,
    confirmation: str | None,
    clock: Callable[[], datetime],
    api_key_reader: Callable[[], str | None],
    client_factory: Callable[[str], object],
) -> OpenAIPreflightExecutionResultV02:
    if execute_real_preflight is not True:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "explicit real-preflight execution flag is required",
        )
    if confirmation != EXECUTION_CONFIRMATION:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "exact v0.2 real-preflight confirmation phrase is required",
        )
    readiness = _validate_openai_preflight_readiness(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=repository_root,
        clock=clock,
    )
    try:
        supplied_api_key = api_key_reader()
    except Exception:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
            "OPENAI_API_KEY could not be read at the gated boundary",
        ) from None
    api_key = validate_openai_api_key_shape(supplied_api_key)

    _create_output_directory(readiness.repository_root)
    _require_artifacts_absent(
        readiness.attempt_marker_path,
        readiness.successful_record_path,
        readiness.failure_record_path,
    )
    marker = _build_attempt_marker(
        authorization=readiness.inputs.authorization,
        plan=readiness.plan,
        timestamp=readiness.execution_timestamp_utc,
    )
    marker_payload = attempt_marker_bytes(marker)
    v0_1_execution._write_exclusive(
        readiness.attempt_marker_path,
        marker_payload,
        marker=True,
    )
    attempt_marker_sha256 = uppercase_sha256_bytes(marker_payload + b"\n")
    counter = _ProviderCallCounter()
    failure_stage: FailureStage = "client_construction"
    sanitized_failure: Stage4BError | None = None
    diagnostics: OpenAIProviderFailureDiagnostics | None = None
    record: OpenAIPreflightRecordV02 | None = None

    try:
        client = client_factory(api_key)
        failure_stage = "provider_construction"
        provider = _PlanBoundPreflightProvider(
            plan=readiness.plan,
            delegate=OpenAIResponsesPreflightBridge(
                provider=OpenAIResponsesProvider(
                    client=_CountingOpenAIClient(
                        delegate=client,
                        counter=counter,
                        credential=api_key,
                    )
                )
            ),
        )
        failure_stage = "provider_call"
        record = run_openai_synthetic_preflight(
            provider=provider,
            authorization=readiness.inputs.authorization,
            pricing_observation=readiness.inputs.pricing_observation,
            data_controls_observation=readiness.inputs.data_controls_observation,
            clock=lambda: readiness.execution_timestamp_utc,
        )
        failure_stage = "record_validation"
        _require_record_matches_plan(record, readiness.plan)
        if os.path.lexists(readiness.failure_record_path):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
                "successful record cannot coexist with a v0.2 failure record",
            )
        failure_stage = "successful_record_write"
        v0_1_execution._write_exclusive(
            readiness.successful_record_path,
            preflight_record_bytes(record),
            marker=False,
        )
    except Exception as error:
        if failure_stage == "provider_call":
            if counter.count == 0:
                failure_stage = "provider_construction"
            elif counter.response_returned:
                failure_stage = "post_provider_validation"
        sanitized_failure, diagnostics = _sanitized_post_marker_failure(
            error,
            api_key,
        )

    if sanitized_failure is not None:
        failure_timestamp = v0_1_execution._validated_timestamp(clock)
        _write_failure_record_exclusive(
            readiness=readiness,
            attempt_marker_sha256=attempt_marker_sha256,
            failure_timestamp=failure_timestamp,
            failure_stage=failure_stage,
            error=sanitized_failure,
            diagnostics=diagnostics,
            provider_call_count=counter.count,
        )
        raise sanitized_failure

    if record is None:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "v0.2 preflight produced no successful record",
        )
    return OpenAIPreflightExecutionResultV02(
        plan=readiness.plan,
        marker=marker,
        record=record,
        attempt_marker_path=readiness.attempt_marker_path,
        successful_record_path=readiness.successful_record_path,
        failure_record_path=readiness.failure_record_path,
    )


def execute_openai_synthetic_preflight(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    execute_real_preflight: bool,
    confirmation: str | None,
) -> OpenAIPreflightExecutionResultV02:
    root = resolve_production_repository_root(Path.cwd())
    return _execute_openai_synthetic_preflight_transaction(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        execute_real_preflight=execute_real_preflight,
        confirmation=confirmation,
        clock=_utc_now,
        api_key_reader=_openai_api_key_from_environment,
        client_factory=_production_openai_client_factory,
    )


__all__ = [
    "ATTEMPT_MARKER_RELATIVE_PATH",
    "EXECUTION_CONFIRMATION",
    "FAILURE_RECORD_RELATIVE_PATH",
    "OpenAIPreflightAttemptMarkerV02",
    "OpenAIPreflightExecutionPlanV02",
    "OpenAIPreflightExecutionResultV02",
    "OpenAIPreflightFailureRecordV02",
    "OpenAIPreflightInputsV02",
    "OpenAIPreflightReadinessV02",
    "SUCCESSFUL_RECORD_RELATIVE_PATH",
    "V0_1_ATTEMPT_MARKER_RELATIVE_PATH",
    "attempt_marker_bytes",
    "build_openai_preflight_execution_plan",
    "execute_openai_synthetic_preflight",
    "failure_record_bytes",
    "load_openai_preflight_failure_record",
    "validate_failure_record_payload",
    "validate_openai_api_key_shape",
    "validate_openai_preflight_readiness",
]
