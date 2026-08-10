"""Default-deny execution boundary for the additive v0.4 preflight."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from openai import APIStatusError
from pydantic import BaseModel, Field, ValidationError, model_validator

from document_intelligence.llm_extraction import (
    openai_preflight_execution as v0_1_execution,
)
from document_intelligence.llm_extraction import (
    openai_preflight_execution_v0_2 as v0_2_execution,
)
from document_intelligence.llm_extraction.contracts import LLMExtractionRequestV03
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_preflight_bridge import (
    OpenAIResponsesPreflightBridge,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    PREFLIGHT_INPUT_CLASSIFICATION,
    OpenAIPreflightAuthorizationV04,
    OpenAIPreflightPostResponseFailureV04,
    OpenAIPreflightPostResponseMetadataV04,
    OpenAIPreflightRecordV04,
    build_synthetic_openai_preflight_request_v0_4,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_API_SURFACE,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OpenAIProviderFailure,
    OpenAIProviderFailureDiagnostics,
    OpenAIResponsesProvider,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


EXECUTION_CONFIRMATION = "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_4"
EXECUTION_PLAN_SCHEMA_VERSION: Literal["0.4"] = "0.4"
ATTEMPT_MARKER_SCHEMA_VERSION: Literal["0.4"] = "0.4"
FAILURE_RECORD_SCHEMA_VERSION: Literal["0.4"] = "0.4"
OUTPUT_DIRECTORY = PurePosixPath("reports/llm_extraction/openai_preflight")
ATTEMPT_MARKER_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4.attempt.json"
)
SUCCESSFUL_RECORD_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4.record.json"
)
FAILURE_RECORD_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4.failure.json"
)


class OpenAIPreflightExecutionPlanV04(v0_2_execution.OpenAIPreflightExecutionPlanV02):
    """Immutable non-sensitive identity for the v0.4 boundary."""

    execution_plan_schema_version: Literal["0.4"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.4"]
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.4"]
    attempt_marker_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.4.attempt.json"
    ]
    successful_record_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.4.record.json"
    ]
    failure_record_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.4.failure.json"
    ]

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightExecutionPlanV04:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"execution_plan_sha256"})
            )
        )
        if self.execution_plan_sha256 != expected:
            raise ValueError("execution_plan_sha256 does not match plan identity")
        return self


def _derive_execution_plan_anchors() -> v0_2_execution._ExecutionPlanAnchors:
    return _derive_execution_plan_anchors_for_request(
        build_synthetic_openai_preflight_request_v0_4()
    )


def _derive_execution_plan_anchors_for_request(
    request: LLMExtractionRequestV03,
) -> v0_2_execution._ExecutionPlanAnchors:
    """Bind a V03 request to the alias-safe schema and exact V03 configuration."""
    if not isinstance(request, LLMExtractionRequestV03):
        raise TypeError("v0.4 preflight request must use LLMExtractionRequestV03")
    validate_request_identity(request)
    schema = build_openai_candidate_schema_v0_3()
    payload = build_openai_responses_payload(
        request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3
    )
    request_bytes = canonical_json_bytes(
        request.model_dump(mode="json", exclude={"canonical_request_sha256"})
    )
    return v0_2_execution._ExecutionPlanAnchors(
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        prompt_sha256=request.prompt_sha256,
        synthetic_document_sha256=request.document_sha256,
        strict_schema_sha256=uppercase_sha256_bytes(canonical_json_bytes(schema)),
        provider_payload_sha256=uppercase_sha256_bytes(canonical_json_bytes(payload)),
    )


def _build_execution_plan(
    anchors: v0_2_execution._ExecutionPlanAnchors,
) -> OpenAIPreflightExecutionPlanV04:
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
    return OpenAIPreflightExecutionPlanV04.model_validate(
        {
            **values,
            "execution_plan_sha256": uppercase_sha256_bytes(
                canonical_json_bytes(values)
            ),
        }
    )


def build_openai_preflight_execution_plan() -> OpenAIPreflightExecutionPlanV04:
    """Build the deterministic v0.4 plan without credential or client access."""
    return _build_execution_plan(_derive_execution_plan_anchors())


@dataclass
class _ProviderCallCounter:
    count: int = 0
    response_returned: bool = False


@dataclass(frozen=True)
class _CountingResponsesResource:
    delegate: object
    counter: _ProviderCallCounter
    credential: str

    def create(self, **kwargs: Any) -> object:
        if self.counter.count != 0:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
                "v0.4 provider call budget has already been consumed",
            )
        self.counter.count = 1
        create = getattr(self.delegate, "create")
        failure: OpenAIProviderFailure | None = None
        response: object | None = None
        try:
            response = create(**kwargs)
        except APIStatusError as error:
            failure = v0_2_execution._credential_scrubbed_status_failure(
                error,
                self.credential,
            )
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
        configured = getattr(self.delegate, "with_options")(
            max_retries=max_retries,
            timeout=timeout,
        )
        return _CountingConfiguredClient(
            responses=_CountingResponsesResource(
                delegate=getattr(configured, "responses"),
                counter=self.counter,
                credential=self.credential,
            )
        )


@dataclass(frozen=True)
class _PlanBoundPreflightProvider:
    plan: OpenAIPreflightExecutionPlanV04
    delegate: OpenAIResponsesPreflightBridge

    def generate_preflight(self, request: LLMExtractionRequestV03) -> object:
        try:
            anchors = _derive_execution_plan_anchors_for_request(request)
        except Exception:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                "provider-entry request could not be bound to the v0.4 plan",
            ) from None
        v0_2_execution._require_plan_anchor_match(self.plan, anchors)
        return self.delegate.generate_preflight(request)


class OpenAIPreflightAttemptMarkerV04(
    v0_2_execution.OpenAIPreflightAttemptMarkerV02
):
    """Permanent evidence that the separate v0.4 call may have started."""

    marker_schema_version: Literal["0.4"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.4"]
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.4"]

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightAttemptMarkerV04:
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
    authorization: OpenAIPreflightAuthorizationV04,
    plan: OpenAIPreflightExecutionPlanV04,
    timestamp: datetime,
) -> OpenAIPreflightAttemptMarkerV04:
    values = {
        "marker_schema_version": ATTEMPT_MARKER_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_id": authorization.authorization_id,
        "authorization_scope": authorization.scope,
        "execution_plan_sha256": plan.execution_plan_sha256,
        "attempt_timestamp_utc": timestamp,
        "maximum_provider_calls": 1,
        "state": "provider_call_may_have_started",
    }
    return OpenAIPreflightAttemptMarkerV04.model_validate(
        {
            **values,
            "marker_sha256": uppercase_sha256_bytes(
                canonical_json_bytes(
                    OpenAIPreflightAttemptMarkerV04.model_construct(
                        **values,
                        marker_sha256="0" * 64,
                    ).model_dump(mode="json", exclude={"marker_sha256"})
                )
            ),
        }
    )


def attempt_marker_bytes(marker: OpenAIPreflightAttemptMarkerV04) -> bytes:
    validated = OpenAIPreflightAttemptMarkerV04.model_validate(
        marker.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


FailureStage = v0_2_execution.FailureStage


class OpenAIPreflightFailureRecordV04(
    v0_2_execution.OpenAIPreflightFailureRecordV02
):
    """Sanitized self-hashed evidence for one post-marker v0.4 failure."""

    failure_record_schema_version: Literal["0.4"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.4"]
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.4"]
    post_response_metadata: OpenAIPreflightPostResponseMetadataV04 | None = None

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightFailureRecordV04:
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
        if self.post_response_metadata is not None:
            if self.provider_call_count != 1:
                raise ValueError("post-response metadata requires one provider call")
            if self.failure_stage not in {
                "post_provider_validation",
                "record_validation",
                "successful_record_write",
            }:
                raise ValueError("post-response metadata requires a returned response")
        return self


def _build_failure_record(
    *,
    readiness: OpenAIPreflightReadinessV04,
    attempt_marker_sha256: str,
    failure_timestamp: datetime,
    failure_stage: FailureStage,
    error: Stage4BError,
    diagnostics: OpenAIProviderFailureDiagnostics | None,
    post_response_metadata: OpenAIPreflightPostResponseMetadataV04 | None,
    provider_call_count: int,
) -> OpenAIPreflightFailureRecordV04:
    values = {
        "failure_record_schema_version": FAILURE_RECORD_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_id": readiness.inputs.authorization.authorization_id,
        "authorization_scope": readiness.inputs.authorization.scope,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "attempt_marker_sha256": attempt_marker_sha256,
        "failure_timestamp_utc": failure_timestamp,
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
        "post_response_metadata": post_response_metadata,
    }
    provisional = OpenAIPreflightFailureRecordV04.model_construct(
        **values,
        failure_record_sha256="0" * 64,
    )
    record_hash = uppercase_sha256_bytes(
        canonical_json_bytes(
            provisional.model_dump(
                mode="json",
                exclude={"failure_record_sha256"},
            )
        )
    )
    return OpenAIPreflightFailureRecordV04.model_validate(
        {**values, "failure_record_sha256": record_hash}
    )


def failure_record_bytes(record: OpenAIPreflightFailureRecordV04) -> bytes:
    validated = OpenAIPreflightFailureRecordV04.model_validate(
        record.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


def validate_failure_record_payload(
    payload: dict[str, Any],
) -> OpenAIPreflightFailureRecordV04:
    values = dict(payload)
    claimed_hash = values.pop("failure_record_sha256", None)
    try:
        expected_hash = uppercase_sha256_bytes(canonical_json_bytes(values))
    except (TypeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            "v0.4 failure record is not canonical JSON",
        ) from error
    if type(claimed_hash) is not str or claimed_hash != expected_hash:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_FAILURE_RECORD_HASH_MISMATCH,
            "failure_record_sha256 does not match canonical record bytes",
        )
    try:
        return OpenAIPreflightFailureRecordV04.model_validate(payload)
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            "v0.4 failure record does not satisfy its frozen contract",
        ) from error


def load_openai_preflight_failure_record(
    path: Path,
) -> OpenAIPreflightFailureRecordV04:
    payload = v0_1_execution._read_json_object(path, label="v0.4 failure record")
    return validate_failure_record_payload(payload)


@dataclass(frozen=True)
class OpenAIPreflightInputsV04:
    authorization: OpenAIPreflightAuthorizationV04
    pricing_observation: OpenAIPricingObservation
    data_controls_observation: OpenAIDataControlsObservation


@dataclass(frozen=True)
class OpenAIPreflightReadinessV04:
    plan: OpenAIPreflightExecutionPlanV04
    inputs: OpenAIPreflightInputsV04
    execution_timestamp_utc: datetime
    repository_root: Path
    attempt_marker_path: Path
    successful_record_path: Path
    failure_record_path: Path


@dataclass(frozen=True)
class OpenAIPreflightExecutionResultV04:
    plan: OpenAIPreflightExecutionPlanV04
    marker: OpenAIPreflightAttemptMarkerV04
    record: OpenAIPreflightRecordV04
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
) -> OpenAIPreflightInputsV04:
    paths = (authorization_path, pricing_path, data_controls_path)
    protected_roots = {
        v0_1_execution._absolute_lexical_path(repository_root),
        v0_1_execution._absolute_lexical_path(_installed_repository_root()),
    }
    for path in paths:
        for protected_root in protected_roots:
            v0_1_execution._reject_protected_repository_input(path, protected_root)
    authorization = _validate_input_model(
        authorization_path,
        label="authorization",
        model_type=OpenAIPreflightAuthorizationV04,
    )
    pricing = _validate_input_model(
        pricing_path,
        label="pricing observation",
        model_type=OpenAIPricingObservation,
    )
    controls = _validate_input_model(
        data_controls_path,
        label="data-controls observation",
        model_type=OpenAIDataControlsObservation,
    )
    assert isinstance(authorization, OpenAIPreflightAuthorizationV04)
    assert isinstance(pricing, OpenAIPricingObservation)
    assert isinstance(controls, OpenAIDataControlsObservation)
    return OpenAIPreflightInputsV04(authorization, pricing, controls)


def _validate_loaded_inputs(
    inputs: OpenAIPreflightInputsV04,
    timestamp: datetime,
) -> OpenAIPreflightInputsV04:
    try:
        authorization = OpenAIPreflightAuthorizationV04.model_validate(
            inputs.authorization.model_dump(mode="python")
        )
        pricing = OpenAIPricingObservation.model_validate(
            inputs.pricing_observation.model_dump(mode="python")
        )
        controls = OpenAIDataControlsObservation.model_validate(
            inputs.data_controls_observation.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "v0.4 authorization or terms evidence is invalid",
        ) from error
    if authorization.authorized_at_utc > timestamp:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "authorization timestamp must not postdate execution",
        )
    if (
        pricing.observed_at_utc.date() != timestamp.date()
        or controls.observed_at_utc.date() != timestamp.date()
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "pricing and data-control observations must use the execution UTC date",
        )
    return OpenAIPreflightInputsV04(authorization, pricing, controls)


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
            "the fixed v0.4 preflight attempt marker already exists",
        )
    if os.path.lexists(success) or os.path.lexists(failure):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
            "a fixed v0.4 preflight outcome artifact already exists",
        )


def _validate_openai_preflight_readiness(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    clock: Callable[[], datetime],
) -> OpenAIPreflightReadinessV04:
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
        (marker, "v0.4 preflight attempt marker"),
        (success, "v0.4 preflight successful record"),
        (failure, "v0.4 preflight failure record"),
    ):
        v0_1_execution._validate_path_chain(path, label=label)
    _require_artifacts_absent(marker, success, failure)
    return OpenAIPreflightReadinessV04(
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
    """Bind v0.4 production execution to its installed local checkout."""
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
) -> OpenAIPreflightReadinessV04:
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


validate_openai_api_key_shape = v0_2_execution.validate_openai_api_key_shape


def _require_record_matches_plan(
    record: OpenAIPreflightRecordV04,
    plan: OpenAIPreflightExecutionPlanV04,
) -> None:
    if not isinstance(record, OpenAIPreflightRecordV04):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "preflight runner did not return the v0.4 record contract",
        )
    for field_name, expected in {
        "canonical_request_sha256": plan.canonical_request_sha256,
        "prompt_sha256": plan.prompt_sha256,
        "document_sha256": plan.synthetic_document_sha256,
        "strict_schema_sha256": plan.strict_schema_sha256,
        "provider_payload_sha256": plan.provider_payload_sha256,
    }.items():
        if getattr(record, field_name) != expected:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                f"returned record {field_name} differs from the readiness plan",
            )


def _post_response_metadata_from_record(
    record: OpenAIPreflightRecordV04,
) -> OpenAIPreflightPostResponseMetadataV04:
    return OpenAIPreflightPostResponseMetadataV04(
        returned_model_identifier=record.returned_model_identifier,
        model_version_or_snapshot_provenance=(
            record.model_version_or_snapshot_provenance
        ),
        version_provenance_source_response_id=(
            record.version_provenance_source_response_id
        ),
        provider_public_metadata_sha256=record.provider_public_metadata_sha256,
        provider_public_metadata_field_paths=(
            record.provider_public_metadata_field_paths
        ),
        version_provenance_observed_from_same_provider_call=(
            record.version_provenance_observed_from_same_provider_call
        ),
        provider_request_id=record.provider_request_id,
        provider_response_id=record.provider_response_id,
        provider_sdk_version=record.provider_sdk_version,
        raw_response_sha256=record.raw_response_sha256,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        latency_ms=record.latency_ms,
        retry_count=record.retry_count,
    )


def _sanitized_post_marker_failure(
    error: Exception,
    credential: str,
) -> tuple[
    Stage4BError,
    OpenAIProviderFailureDiagnostics | None,
    OpenAIPreflightPostResponseMetadataV04 | None,
]:
    if isinstance(error, OpenAIPreflightPostResponseFailureV04):
        return (
            Stage4BError(
                error.code,
                "OpenAI v0.4 response failed technical validation",
            ),
            None,
            OpenAIPreflightPostResponseMetadataV04.model_validate(
                error.safe_metadata.model_dump(mode="python")
            ),
        )
    if isinstance(error, OpenAIProviderFailure):
        diagnostics = v0_2_execution._credential_scrubbed_diagnostics(
            error.diagnostics,
            credential,
        )
        sanitized = OpenAIProviderFailure(error.code, diagnostics)
        return sanitized, sanitized.diagnostics, None
    if isinstance(error, Stage4BError):
        return (
            Stage4BError(
                error.code,
                "OpenAI v0.4 synthetic preflight failed after marker creation",
            ),
            None,
            None,
        )
    return (
        Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "OpenAI v0.4 synthetic preflight failed after marker creation",
        ),
        None,
        None,
    )


def _write_failure_record_exclusive(
    *,
    readiness: OpenAIPreflightReadinessV04,
    attempt_marker_sha256: str,
    failure_timestamp: datetime,
    failure_stage: FailureStage,
    error: Stage4BError,
    diagnostics: OpenAIProviderFailureDiagnostics | None,
    post_response_metadata: OpenAIPreflightPostResponseMetadataV04 | None,
    provider_call_count: int,
) -> OpenAIPreflightFailureRecordV04:
    if not os.path.lexists(readiness.attempt_marker_path):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "v0.4 failure record requires an existing attempt marker",
        )
    if os.path.lexists(readiness.successful_record_path):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "v0.4 failure record cannot coexist with a successful record",
        )
    record = _build_failure_record(
        readiness=readiness,
        attempt_marker_sha256=attempt_marker_sha256,
        failure_timestamp=failure_timestamp,
        failure_stage=failure_stage,
        error=error,
        diagnostics=diagnostics,
        post_response_metadata=post_response_metadata,
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
) -> OpenAIPreflightExecutionResultV04:
    if execute_real_preflight is not True:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "explicit real-preflight execution flag is required",
        )
    if confirmation != EXECUTION_CONFIRMATION:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "exact v0.4 real-preflight confirmation phrase is required",
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
    post_response_metadata: OpenAIPreflightPostResponseMetadataV04 | None = None
    record: OpenAIPreflightRecordV04 | None = None

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
                    ),
                    configuration=DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
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
                "successful record cannot coexist with a v0.4 failure record",
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
        (
            sanitized_failure,
            diagnostics,
            post_response_metadata,
        ) = _sanitized_post_marker_failure(error, api_key)
        if post_response_metadata is None and record is not None:
            post_response_metadata = _post_response_metadata_from_record(record)

    if sanitized_failure is not None:
        failure_timestamp = v0_1_execution._validated_timestamp(clock)
        _write_failure_record_exclusive(
            readiness=readiness,
            attempt_marker_sha256=attempt_marker_sha256,
            failure_timestamp=failure_timestamp,
            failure_stage=failure_stage,
            error=sanitized_failure,
            diagnostics=diagnostics,
            post_response_metadata=post_response_metadata,
            provider_call_count=counter.count,
        )
        raise sanitized_failure

    if record is None:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "v0.4 preflight produced no successful record",
        )
    return OpenAIPreflightExecutionResultV04(
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
) -> OpenAIPreflightExecutionResultV04:
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
    "OpenAIPreflightAttemptMarkerV04",
    "OpenAIPreflightExecutionPlanV04",
    "OpenAIPreflightExecutionResultV04",
    "OpenAIPreflightFailureRecordV04",
    "OpenAIPreflightInputsV04",
    "OpenAIPreflightReadinessV04",
    "SUCCESSFUL_RECORD_RELATIVE_PATH",
    "attempt_marker_bytes",
    "build_openai_preflight_execution_plan",
    "execute_openai_synthetic_preflight",
    "failure_record_bytes",
    "load_openai_preflight_failure_record",
    "validate_failure_record_payload",
    "validate_openai_api_key_shape",
    "validate_openai_preflight_readiness",
]
