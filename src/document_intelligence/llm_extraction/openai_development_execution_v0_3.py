"""Default-deny transaction for the frozen Stage 4D v0.3 execution."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.extraction.models import CandidateReviewStatus
from document_intelligence.llm_extraction import (
    openai_development_manifest as manifest_module,
)
from document_intelligence.llm_extraction import (
    openai_preflight_execution as preflight_execution,
)
from document_intelligence.llm_extraction import (
    openai_preflight_execution_v0_2 as credential_safety,
)
from document_intelligence.llm_extraction.cache import (
    CacheIdentityV03,
    CacheRecord,
    OpenAIOriginalCallProvenanceV01,
    ResponseCache,
    build_cache_record,
    cache_identity_sha256,
    cache_record_bytes,
)
from document_intelligence.llm_extraction.contracts import (
    InvocationRole,
    LLMExtractionRequestV03,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    SHA256_PATTERN,
    ValidatedCandidateOutput,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_development_execution_plan_v0_3 import (
    ATTEMPT_MARKER_ROOT,
    AUTHORIZATION_SCOPE,
    EXECUTION_ID,
    EXECUTION_RECORD_PATH,
    EXPECTED_EXECUTION_PLAN_SHA256,
    FAILURE_RECORD_ROOT,
    MANIFEST_ARTIFACT_BYTES,
    MANIFEST_CANONICAL_LF_SHA256,
    MANIFEST_RELATIVE_PATH,
    MANIFEST_SELF_SHA256,
    DevelopmentExecutionInvocationPlanV03,
    OpenAIDevelopmentExecutionPlanV03,
    development_execution_plan_bytes_v0_3,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentInvocationIdentityV03,
    OpenAIDevelopmentManifestV03,
    canonical_lf_json_bytes,
    development_manifest_bytes_v0_3,
    load_approved_parsed_document,
    prepare_openai_development_manifest_v0_3,
)
from document_intelligence.llm_extraction.openai_preflight import (
    ModelVersionOrSnapshotProvenance,
    OpenAIDataControlsObservation,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
    _validate_provenance_path_inventory,
)
from document_intelligence.llm_extraction.openai_preflight_bridge import (
    OpenAIResponsesPreflightBridge,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUIRED_SDK_VERSION,
    OPENAI_RESPONSE_SCHEMA_NAME_V0_3,
    OpenAIProviderFailure,
    OpenAIProviderFailureDiagnostics,
    OpenAIResponsesProvider,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.provenance import AttemptProvenance
from document_intelligence.llm_extraction.validation import validate_provider_output


EXECUTION_PLAN_RELATIVE_PATH = PurePosixPath(
    "reports/llm_extraction/openai_development_execution_plan/"
    "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.3.json"
)
EXECUTION_PLAN_OUTER_SHA256 = (
    "0F567327922CE7C9609CA41C8500AD39BFB3A8F09E8FD0E5BEC4F96E325F38B6"
)
EXECUTION_PLAN_ARTIFACT_BYTES = 13077
EXECUTION_CONFIRMATION = "EXECUTE_BOUNDED_FIVE_SOURCE_OPENAI_DEVELOPMENT_V0_3"
AUTHORIZATION_SCHEMA_VERSION: Literal["0.1"] = "0.1"
ATTEMPT_MARKER_SCHEMA_VERSION: Literal["0.1"] = "0.1"
FAILURE_RECORD_SCHEMA_VERSION: Literal["0.1"] = "0.1"
EXECUTION_RECORD_SCHEMA_VERSION: Literal["0.1"] = "0.1"
MAXIMUM_PROVIDER_CALLS = 8
MAXIMUM_TOTAL_ATTEMPTS = 8
MAXIMUM_AGGREGATE_OUTPUT_TOKENS = 32768
AUTHORIZATION_CAP_USD = Decimal("1.25")
CONSERVATIVE_COST_CEILING_USD = Decimal("1.001169")
EXPECTED_RETURNED_MODEL_IDENTIFIER = "gpt-5.4-mini-2026-03-17"
_MILLION = Decimal("1000000")


def _require_trimmed(value: str, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be trimmed and nonblank")
    return value


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use timezone-aware UTC")
    return value


def _canonical_hash(model: BaseModel, hash_field: str) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(model.model_dump(mode="json", exclude={hash_field}))
    )


def _canonical_model_bytes(model: BaseModel) -> bytes:
    return canonical_json_bytes(model.model_dump(mode="json")) + b"\n"


class OpenAIDevelopmentExecutionAuthorizationV03(BaseModel):
    """Explicit project-owner authority for this transaction only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_schema_version: Literal["0.1"] = AUTHORIZATION_SCHEMA_VERSION
    authorization_id: str
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.3"
    ] = EXECUTION_ID
    authorization_scope: Literal[
        "bounded-five-source-openai-development-execution-v0.3"
    ] = AUTHORIZATION_SCOPE
    execution_plan_sha256: Literal[
        "12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A"
    ] = EXPECTED_EXECUTION_PLAN_SHA256
    manifest_sha256: Literal[
        "D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327"
    ] = MANIFEST_SELF_SHA256
    maximum_provider_calls: Literal[8] = MAXIMUM_PROVIDER_CALLS
    maximum_total_attempts: Literal[8] = MAXIMUM_TOTAL_ATTEMPTS
    cost_cap_usd: Decimal
    real_development_execution_authorized: Literal[True]
    project_owner_identity: str
    authorized_at_utc: datetime
    authorization_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("authorization_id", "project_owner_identity")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _require_trimmed(value, info.field_name)

    @field_validator("authorized_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "authorized_at_utc")

    @field_serializer("authorized_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @field_serializer("cost_cap_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_authorization(self) -> OpenAIDevelopmentExecutionAuthorizationV03:
        if self.cost_cap_usd != AUTHORIZATION_CAP_USD:
            raise ValueError("development authorization must bind exactly USD 1.25")
        if self.authorization_sha256 != _canonical_hash(
            self, "authorization_sha256"
        ):
            raise ValueError("authorization_sha256 does not match canonical content")
        return self


def development_authorization_bytes_v0_3(
    authorization: OpenAIDevelopmentExecutionAuthorizationV03,
) -> bytes:
    validated = OpenAIDevelopmentExecutionAuthorizationV03.model_validate(
        authorization.model_dump(mode="python")
    )
    return _canonical_model_bytes(validated)


class OpenAIDevelopmentInvocationAttemptMarkerV03(BaseModel):
    """Permanent pre-client marker for one exact cache-miss invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    marker_schema_version: Literal["0.1"] = ATTEMPT_MARKER_SCHEMA_VERSION
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.3"
    ] = EXECUTION_ID
    execution_plan_sha256: Literal[
        "12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A"
    ] = EXPECTED_EXECUTION_PLAN_SHA256
    manifest_sha256: Literal[
        "D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327"
    ] = MANIFEST_SELF_SHA256
    authorization_sha256: str = Field(pattern=SHA256_PATTERN)
    invocation_order: int = Field(gt=0, le=8)
    request_id: str
    cache_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    attempt_marker_relative_path: str
    attempt_timestamp_utc: datetime
    state: Literal["provider_call_may_have_started"]
    marker_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("request_id", "attempt_marker_relative_path")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _require_trimmed(value, info.field_name)

    @field_validator("attempt_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "attempt_timestamp_utc")

    @field_serializer("attempt_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def validate_marker(self) -> OpenAIDevelopmentInvocationAttemptMarkerV03:
        expected_path = (
            f"{ATTEMPT_MARKER_ROOT}/{self.cache_identity_sha256}.attempt.json"
        )
        if self.attempt_marker_relative_path != expected_path:
            raise ValueError("attempt marker path does not match cache identity")
        if self.marker_sha256 != _canonical_hash(self, "marker_sha256"):
            raise ValueError("marker_sha256 does not match canonical content")
        return self


DevelopmentFailureStage: TypeAlias = Literal[
    "cache_read",
    "artifact_state",
    "credential_access",
    "client_construction",
    "provider_call",
    "provider_response_validation",
    "cache_install",
    "local_parse",
    "final_record_write",
]


class OpenAIDevelopmentInvocationFailureRecordV03(BaseModel):
    """Sanitized immutable failure evidence for one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    failure_record_schema_version: Literal["0.1"] = FAILURE_RECORD_SCHEMA_VERSION
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.3"
    ] = EXECUTION_ID
    execution_plan_sha256: Literal[
        "12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A"
    ] = EXPECTED_EXECUTION_PLAN_SHA256
    manifest_sha256: Literal[
        "D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327"
    ] = MANIFEST_SELF_SHA256
    authorization_sha256: str = Field(pattern=SHA256_PATTERN)
    invocation_order: int = Field(gt=0, le=8)
    request_id: str
    source_id: Literal["S001", "S002", "S003", "S004", "S006"]
    cache_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    attempt_marker_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    failure_timestamp_utc: datetime
    failure_stage: DevelopmentFailureStage
    local_error_code: Stage4BErrorCode
    cache_present: bool
    provider_call_occurred: bool
    cache_install_completed: bool
    local_parse_started: bool
    local_parse_completed: Literal[False]
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    provider_error_type: str | None = None
    provider_error_code: str | None = None
    provider_request_id: str | None = None
    retry_count: Literal[0] = 0
    failure_record_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return _require_trimmed(value, "request_id")

    @field_validator("source_id")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return validate_development_source_id(value)

    @field_validator("failure_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "failure_timestamp_utc")

    @field_serializer("failure_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def validate_failure(self) -> OpenAIDevelopmentInvocationFailureRecordV03:
        if self.cache_install_completed and not self.cache_present:
            raise ValueError("completed cache installation requires cache presence")
        if self.local_parse_started and not self.cache_present:
            raise ValueError("local parsing requires a verified cache response")
        if self.failure_record_sha256 != _canonical_hash(
            self, "failure_record_sha256"
        ):
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_FAILURE_RECORD_HASH_MISMATCH,
                "failure record hash does not match canonical content",
            )
        return self


class OpenAIDevelopmentInvocationOutcomeV03(BaseModel):
    """Hash-only successful outcome for one ordered invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_order: int = Field(gt=0, le=8)
    request_id: str
    source_id: Literal["S001", "S002", "S003", "S004", "S006"]
    invocation_role: InvocationRole
    cache_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    response_source: Literal["provider_call", "cache_hit"]
    attempt_marker_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    cache_record_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_response_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_output_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_identifier: Literal["openai"]
    returned_model_identifier: str
    provider_request_id: str
    provider_response_id: str
    provider_sdk_version: Literal["2.46.0"]
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    provider_public_metadata_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_public_metadata_field_paths: tuple[str, ...] = Field(min_length=4)
    version_provenance_observed_from_same_provider_call: Literal[True] = True
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0, le=4096)
    latency_ms: int = Field(ge=0)
    newly_incurred_cost_usd: Decimal = Field(ge=0)
    historical_cached_cost_usd: Decimal = Field(ge=0)
    candidate_count: int = Field(ge=0)
    review_required_candidate_count: int = Field(ge=0)
    retry_count: Literal[0] = 0

    @field_serializer(
        "newly_incurred_cost_usd",
        "historical_cached_cost_usd",
        when_used="json",
    )
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_outcome(self) -> OpenAIDevelopmentInvocationOutcomeV03:
        for field_name in (
            "request_id",
            "returned_model_identifier",
            "provider_request_id",
            "provider_response_id",
            "version_provenance_source_response_id",
        ):
            _require_trimmed(getattr(self, field_name), field_name)
        if self.version_provenance_source_response_id != self.provider_response_id:
            raise ValueError(
                "version provenance source response ID must equal provider response ID"
            )
        try:
            _validate_provenance_path_inventory(
                self.model_version_or_snapshot_provenance,
                self.provider_public_metadata_field_paths,
            )
        except Stage4BError as error:
            raise ValueError(error.message) from error
        metadata_projection: dict[str, object] = {
            "response.id": self.provider_response_id,
            "response.model": self.returned_model_identifier,
            "response._request_id": self.provider_request_id,
            "sdk.version": self.provider_sdk_version,
        }
        if self.model_version_or_snapshot_provenance != "unavailable":
            metadata_projection.update(
                (identifier.field_name, identifier.value)
                for identifier in self.model_version_or_snapshot_provenance
            )
        if (
            self.provider_public_metadata_field_paths != tuple(metadata_projection)
            or self.provider_public_metadata_sha256
            != uppercase_sha256_bytes(canonical_json_bytes(metadata_projection))
        ):
            raise ValueError(
                "provider public metadata identity does not reconcile with provenance"
            )
        if self.review_required_candidate_count > self.candidate_count:
            raise ValueError("review-required count exceeds candidate count")
        if self.response_source == "provider_call":
            if self.attempt_marker_sha256 is None:
                raise ValueError("provider-call outcome requires an attempt marker")
            if self.historical_cached_cost_usd != 0:
                raise ValueError("fresh provider outcome cannot claim cached cost")
        else:
            if self.attempt_marker_sha256 is not None:
                raise ValueError("cache-hit outcome cannot claim a new marker")
            if self.newly_incurred_cost_usd != 0:
                raise ValueError("cache hit cannot claim newly incurred cost")
        return self


class OpenAIDevelopmentExecutionRecordV03(BaseModel):
    """Final append-only record installed only after all eight outputs validate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_record_schema_version: Literal["0.1"] = EXECUTION_RECORD_SCHEMA_VERSION
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.3"
    ] = EXECUTION_ID
    execution_plan_sha256: Literal[
        "12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A"
    ] = EXPECTED_EXECUTION_PLAN_SHA256
    manifest_sha256: Literal[
        "D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327"
    ] = MANIFEST_SELF_SHA256
    authorization_id: str
    authorization_sha256: str = Field(pattern=SHA256_PATTERN)
    execution_started_at_utc: datetime
    execution_completed_at_utc: datetime
    ordered_invocation_outcomes: tuple[
        OpenAIDevelopmentInvocationOutcomeV03, ...
    ] = Field(min_length=8, max_length=8)
    provider_call_count: int = Field(ge=0, le=8)
    provider_attempt_count: int = Field(ge=0, le=8)
    cache_hit_count: int = Field(ge=0, le=8)
    aggregate_new_cost_usd: Decimal = Field(ge=0, le=AUTHORIZATION_CAP_USD)
    aggregate_historical_cached_cost_usd: Decimal = Field(ge=0)
    aggregate_input_tokens: int = Field(ge=0)
    aggregate_output_tokens: int = Field(ge=0, le=32768)
    retry_count: Literal[0] = 0
    completion_status: Literal["passed"] = "passed"
    execution_record_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("authorization_id")
    @classmethod
    def validate_authorization_id(cls, value: str) -> str:
        return _require_trimmed(value, "authorization_id")

    @field_validator("execution_started_at_utc", "execution_completed_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime, info: Any) -> datetime:
        return _require_utc(value, info.field_name)

    @field_serializer(
        "execution_started_at_utc",
        "execution_completed_at_utc",
        when_used="json",
    )
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @field_serializer(
        "aggregate_new_cost_usd",
        "aggregate_historical_cached_cost_usd",
        when_used="json",
    )
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_record(self) -> OpenAIDevelopmentExecutionRecordV03:
        outcomes = self.ordered_invocation_outcomes
        if [item.invocation_order for item in outcomes] != list(range(1, 9)):
            raise ValueError("final outcomes must use invocation order 1..8")
        if self.execution_completed_at_utc < self.execution_started_at_utc:
            raise ValueError("execution completion must not predate its start")
        expected = {
            "provider_call_count": sum(
                item.response_source == "provider_call" for item in outcomes
            ),
            "provider_attempt_count": sum(
                item.response_source == "provider_call" for item in outcomes
            ),
            "cache_hit_count": sum(
                item.response_source == "cache_hit" for item in outcomes
            ),
            "aggregate_new_cost_usd": sum(
                (item.newly_incurred_cost_usd for item in outcomes), Decimal("0")
            ),
            "aggregate_historical_cached_cost_usd": sum(
                (item.historical_cached_cost_usd for item in outcomes), Decimal("0")
            ),
            "aggregate_input_tokens": sum(item.input_tokens for item in outcomes),
            "aggregate_output_tokens": sum(item.output_tokens for item in outcomes),
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"{field_name} does not reconcile with outcomes")
        if self.execution_record_sha256 != _canonical_hash(
            self, "execution_record_sha256"
        ):
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_EXECUTION_RECORD_HASH_MISMATCH,
                "execution record hash does not match canonical content",
            )
        return self


def attempt_marker_bytes_v0_3(marker: OpenAIDevelopmentInvocationAttemptMarkerV03) -> bytes:
    validated = OpenAIDevelopmentInvocationAttemptMarkerV03.model_validate(
        marker.model_dump(mode="python")
    )
    return _canonical_model_bytes(validated)


def failure_record_bytes_v0_3(
    record: OpenAIDevelopmentInvocationFailureRecordV03,
) -> bytes:
    validated = OpenAIDevelopmentInvocationFailureRecordV03.model_validate(
        record.model_dump(mode="python")
    )
    return _canonical_model_bytes(validated)


def execution_record_bytes_v0_3(record: OpenAIDevelopmentExecutionRecordV03) -> bytes:
    validated = OpenAIDevelopmentExecutionRecordV03.model_validate(
        record.model_dump(mode="python")
    )
    return _canonical_model_bytes(validated)


@dataclass(frozen=True)
class PreparedDevelopmentInvocationV03:
    plan: DevelopmentExecutionInvocationPlanV03
    manifest_identity: OpenAIDevelopmentInvocationIdentityV03
    request: LLMExtractionRequestV03
    cache_identity: CacheIdentityV03


@dataclass(frozen=True)
class OpenAIDevelopmentExecutionInputsV03:
    authorization: OpenAIDevelopmentExecutionAuthorizationV03
    pricing_observation: OpenAIPricingObservation
    data_controls_observation: OpenAIDataControlsObservation


@dataclass(frozen=True)
class OpenAIDevelopmentExecutionReadinessV03:
    plan: OpenAIDevelopmentExecutionPlanV03
    manifest: OpenAIDevelopmentManifestV03
    inputs: OpenAIDevelopmentExecutionInputsV03
    execution_timestamp_utc: datetime
    repository_root: Path
    invocations: tuple[PreparedDevelopmentInvocationV03, ...]
    cache_root: Path
    execution_record_path: Path
    existing_execution_record: OpenAIDevelopmentExecutionRecordV03 | None


@dataclass(frozen=True)
class OpenAIDevelopmentExecutionResultV03:
    readiness: OpenAIDevelopmentExecutionReadinessV03
    record: OpenAIDevelopmentExecutionRecordV03
    execution_record_path: Path


def _strict_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        canonical = canonical_lf_json_bytes(raw)
        payload = json.loads(canonical)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
            f"{label} must be strict canonical UTF-8 JSON",
        ) from error
    if not isinstance(payload, dict):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
            f"{label} must contain one JSON object",
        )
    return payload


def _load_frozen_plan(repository_root: Path) -> OpenAIDevelopmentExecutionPlanV03:
    path = repository_root.joinpath(*EXECUTION_PLAN_RELATIVE_PATH.parts)
    try:
        raw = preflight_execution._read_validated_descriptor(
            path, label="frozen development execution plan"
        )
    except Stage4BError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development execution plan could not be read safely",
        ) from error
    canonical_raw = canonical_lf_json_bytes(raw)
    if (
        len(canonical_raw) != EXECUTION_PLAN_ARTIFACT_BYTES
        or uppercase_sha256_bytes(canonical_raw) != EXECUTION_PLAN_OUTER_SHA256
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development execution plan file identity differs",
        )
    try:
        plan = OpenAIDevelopmentExecutionPlanV03.model_validate(
            _strict_json_object(
                canonical_raw, label="frozen development execution plan"
            )
        )
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development execution plan contract is invalid",
        ) from error
    if development_execution_plan_bytes_v0_3(plan) != canonical_raw:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development execution plan bytes are not canonical",
        )
    return plan


def _load_frozen_manifest(
    repository_root: Path,
    plan: OpenAIDevelopmentExecutionPlanV03,
) -> OpenAIDevelopmentManifestV03:
    path = repository_root.joinpath(*PurePosixPath(MANIFEST_RELATIVE_PATH).parts)
    try:
        target = manifest_module._safe_existing_file(
            repository_root, MANIFEST_RELATIVE_PATH
        )
        raw = manifest_module._read_validated_regular_file(target)
    except Stage4BError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development manifest could not be read safely",
        ) from error
    if path != target:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development manifest path differs",
        )
    canonical_raw = canonical_lf_json_bytes(raw)
    if (
        len(canonical_raw) != MANIFEST_ARTIFACT_BYTES
        or uppercase_sha256_bytes(canonical_raw)
        != MANIFEST_CANONICAL_LF_SHA256
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development manifest file identity differs",
        )
    try:
        manifest = OpenAIDevelopmentManifestV03.model_validate(
            _strict_json_object(canonical_raw, label="frozen development manifest")
        )
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development manifest contract is invalid",
        ) from error
    if (
        manifest.manifest_sha256 != plan.manifest_binding.manifest_sha256
        or development_manifest_bytes_v0_3(manifest) != canonical_raw
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen development manifest does not reconcile with the plan",
        )
    return manifest


def _load_input_model(
    path: Path,
    *,
    label: str,
    model_type: type[BaseModel],
    repository_root: Path,
    error_code: Stage4BErrorCode = Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
) -> BaseModel:
    try:
        for protected_root in {
            preflight_execution._absolute_lexical_path(repository_root),
            preflight_execution._absolute_lexical_path(
                preflight_execution._installed_repository_root()
            ),
        }:
            preflight_execution._reject_protected_repository_input(
                path, protected_root
            )
        return model_type.model_validate(
            preflight_execution._read_json_object(path, label=label)
        )
    except Stage4BError as error:
        raise Stage4BError(
            error_code,
            f"{label} could not be loaded safely",
        ) from error
    except ValidationError as error:
        raise Stage4BError(
            error_code,
            f"{label} does not satisfy its strict contract",
        ) from error


def _validated_timestamp(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
        if not isinstance(value, datetime):
            raise TypeError
        return _require_utc(value, "execution_timestamp_utc")
    except (TypeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "execution clock must return timezone-aware UTC",
        ) from error


def _validate_current_terms_gate(
    *,
    pricing: OpenAIPricingObservation,
    data_controls: OpenAIDataControlsObservation,
    gate_timestamp: datetime,
) -> None:
    if (
        pricing.observed_at_utc.date() != gate_timestamp.date()
        or data_controls.observed_at_utc.date() != gate_timestamp.date()
        or pricing.observed_at_utc > gate_timestamp
        or data_controls.observed_at_utc > gate_timestamp
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "pricing and data-controls reviews must be complete on the current "
            "execution UTC date before a provider attempt",
        )


def _validate_inputs(
    *,
    authorization: OpenAIDevelopmentExecutionAuthorizationV03,
    pricing: OpenAIPricingObservation,
    data_controls: OpenAIDataControlsObservation,
    manifest: OpenAIDevelopmentManifestV03,
    timestamp: datetime,
) -> OpenAIDevelopmentExecutionInputsV03:
    if (
        authorization.authorized_at_utc > timestamp
        or authorization.authorized_at_utc.date() != timestamp.date()
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
            "development authorization must be issued on the current UTC "
            "execution date and must not postdate execution",
        )
    _validate_current_terms_gate(
        pricing=pricing,
        data_controls=data_controls,
        gate_timestamp=timestamp,
    )
    frozen_pricing = manifest.pricing_observation
    if (
        pricing.input_usd_per_million_tokens
        != frozen_pricing.input_usd_per_million_tokens
        or pricing.output_usd_per_million_tokens
        != frozen_pricing.output_usd_per_million_tokens
        or pricing.currency != frozen_pricing.currency
    ):
        raise Stage4BError(
            Stage4BErrorCode.COST_BUDGET_EXCEEDED,
            "current reviewed pricing differs from the frozen cost model",
        )
    if (
        data_controls.store_false_required is not True
        or data_controls.zero_retention_claimed is not False
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "current data controls do not preserve the frozen request boundary",
        )
    return OpenAIDevelopmentExecutionInputsV03(authorization, pricing, data_controls)


def _reconstruct_invocations(
    repository_root: Path,
    plan: OpenAIDevelopmentExecutionPlanV03,
    manifest: OpenAIDevelopmentManifestV03,
) -> tuple[PreparedDevelopmentInvocationV03, ...]:
    if (
        manifest.provider_configuration_id
        != OPENAI_PROVIDER_CONFIGURATION_ID_V0_3
        or manifest.model_configuration_id
        != OPENAI_MODEL_CONFIGURATION_ID_V0_3
        or manifest.response_schema_name != OPENAI_RESPONSE_SCHEMA_NAME_V0_3
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "frozen manifest does not use the exact v0.3 provider boundary",
        )
    documents: dict[str, Any] = {}
    for route in manifest.source_routes:
        source_id = validate_development_source_id(route.source_id)
        documents[source_id] = load_approved_parsed_document(
            repository_root=repository_root,
            requested_source_id=source_id,
            route=route,
        )
    preparation = prepare_openai_development_manifest_v0_3(
        source_routes=manifest.source_routes,
        parsed_documents=documents,
        partition_policy=manifest.partition_policy,
        pricing_observation=manifest.pricing_observation,
        pricing_review=manifest.pricing_review,
        data_controls_observation=manifest.data_controls_observation,
        data_controls_review=manifest.data_controls_review,
        context_limit_observation=manifest.context_limit_observation,
    )
    if preparation.manifest != manifest:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "reconstructed requests do not reproduce the frozen manifest",
        )

    primary: list[tuple[LLMExtractionRequestV03, str]] = []
    for route in manifest.source_routes:
        primary.extend(
            (request, route.parsed_document_canonical_sha256)
            for request in manifest_module._partition_primary_requests_v0_3(
                document=documents[route.source_id],
                policy=manifest.partition_policy,
            )
        )
    repeat, repeated_primary_id = manifest_module._repeat_request_v0_3(
        [request for request, _ in primary]
    )
    repeat_route_hash = next(
        route_hash
        for request, route_hash in primary
        if request.request_id == repeated_primary_id
    )
    ordered = (*primary, (repeat, repeat_route_hash))
    if len(ordered) != 8:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "reconstruction did not produce exactly eight invocations",
        )

    prepared: list[PreparedDevelopmentInvocationV03] = []
    for index, ((request, route_hash), plan_item, manifest_item) in enumerate(
        zip(ordered, plan.invocations, manifest.invocations, strict=True),
        start=1,
    ):
        identity = manifest_module.build_hash_only_invocation_identity_v0_3(
            request=request,
            invocation_order=index,
            parsed_document_canonical_sha256=route_hash,
            pricing_observation=manifest.pricing_observation,
            repeated_primary_request_id=(
                repeated_primary_id
                if request.invocation_role is InvocationRole.REPEAT
                else None
            ),
        )
        cache_identity = CacheIdentityV03.from_request(request)
        payload = canonical_json_bytes(
            build_openai_responses_payload(
                request,
                configuration=DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
            )
        )
        schema_hash = uppercase_sha256_bytes(
            canonical_json_bytes(build_openai_candidate_schema_v0_3())
        )
        if (
            identity != manifest_item
            or plan_item.request_id != request.request_id
            or plan_item.canonical_request_sha256
            != request.canonical_request_sha256
            or plan_item.prompt_sha256 != request.prompt_sha256
            or plan_item.provider_payload_sha256
            != uppercase_sha256_bytes(payload)
            or plan_item.provider_payload_bytes != len(payload)
            or plan_item.strict_schema_sha256 != schema_hash
            or plan_item.cache_identity_sha256
            != cache_identity_sha256(cache_identity)
        ):
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
                "reconstructed invocation differs from frozen identities",
            )
        prepared.append(
            PreparedDevelopmentInvocationV03(
                plan=plan_item,
                manifest_identity=manifest_item,
                request=request,
                cache_identity=cache_identity,
            )
        )
    return tuple(prepared)


RequestReconstructor: TypeAlias = Callable[
    [Path, OpenAIDevelopmentExecutionPlanV03, OpenAIDevelopmentManifestV03],
    tuple[PreparedDevelopmentInvocationV03, ...],
]


def _artifact_path(repository_root: Path, relative_path: str, *, label: str) -> Path:
    path = repository_root.joinpath(*PurePosixPath(relative_path).parts)
    candidate = preflight_execution._validate_path_chain(path, label=label)
    try:
        candidate.relative_to(repository_root)
    except ValueError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            f"{label} escapes the repository root",
        ) from error
    return candidate


def _parse_canonical_artifact(
    path: Path,
    *,
    label: str,
    model_type: type[BaseModel],
    hash_field: str | None = None,
    hash_error_code: Stage4BErrorCode | None = None,
) -> BaseModel:
    try:
        preflight_execution._validate_path_chain(path, label=label)
        raw = manifest_module._read_validated_regular_file(path)
        payload = _strict_json_object(raw, label=label)
        if hash_field is not None:
            claimed_hash = payload.get(hash_field)
            hash_payload = dict(payload)
            hash_payload.pop(hash_field, None)
            expected_hash = uppercase_sha256_bytes(
                canonical_json_bytes(hash_payload)
            )
            if type(claimed_hash) is not str or claimed_hash != expected_hash:
                assert hash_error_code is not None
                raise Stage4BError(
                    hash_error_code,
                    f"{hash_field} does not match canonical content",
                )
        model = model_type.model_validate(payload)
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
            f"{label} does not satisfy its strict contract",
        ) from error
    if _canonical_model_bytes(model) != raw:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_INPUT_FILE_INVALID,
            f"{label} bytes are not canonical",
        )
    return model


def load_development_attempt_marker_v0_3(
    path: Path,
) -> OpenAIDevelopmentInvocationAttemptMarkerV03:
    model = _parse_canonical_artifact(
        path,
        label="development attempt marker",
        model_type=OpenAIDevelopmentInvocationAttemptMarkerV03,
    )
    assert isinstance(model, OpenAIDevelopmentInvocationAttemptMarkerV03)
    return model


def load_development_failure_record_v0_3(
    path: Path,
) -> OpenAIDevelopmentInvocationFailureRecordV03:
    model = _parse_canonical_artifact(
        path,
        label="development failure record",
        model_type=OpenAIDevelopmentInvocationFailureRecordV03,
        hash_field="failure_record_sha256",
        hash_error_code=Stage4BErrorCode.DEVELOPMENT_FAILURE_RECORD_HASH_MISMATCH,
    )
    assert isinstance(model, OpenAIDevelopmentInvocationFailureRecordV03)
    return model


def load_development_execution_record_v0_3(
    path: Path,
) -> OpenAIDevelopmentExecutionRecordV03:
    model = _parse_canonical_artifact(
        path,
        label="development execution record",
        model_type=OpenAIDevelopmentExecutionRecordV03,
        hash_field="execution_record_sha256",
        hash_error_code=Stage4BErrorCode.DEVELOPMENT_EXECUTION_RECORD_HASH_MISMATCH,
    )
    assert isinstance(model, OpenAIDevelopmentExecutionRecordV03)
    return model


def _validate_existing_marker(
    marker: OpenAIDevelopmentInvocationAttemptMarkerV03,
    *,
    readiness: OpenAIDevelopmentExecutionReadinessV03,
    invocation: PreparedDevelopmentInvocationV03,
) -> OpenAIDevelopmentInvocationAttemptMarkerV03:
    expected = {
        "execution_id": readiness.plan.execution_id,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "manifest_sha256": readiness.manifest.manifest_sha256,
        "authorization_sha256": (
            readiness.inputs.authorization.authorization_sha256
        ),
        "invocation_order": invocation.plan.invocation_order,
        "request_id": invocation.plan.request_id,
        "cache_identity_sha256": invocation.plan.cache_identity_sha256,
        "attempt_marker_relative_path": (
            invocation.plan.attempt_marker_relative_path
        ),
    }
    if any(
        getattr(marker, field_name) != value
        for field_name, value in expected.items()
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
            "existing attempt marker conflicts with current authorization or invocation",
        )
    return marker


def _validate_existing_record(
    record: OpenAIDevelopmentExecutionRecordV03,
    *,
    authorization: OpenAIDevelopmentExecutionAuthorizationV03,
    plan: OpenAIDevelopmentExecutionPlanV03,
) -> None:
    plan_pairs = tuple(
        (
            item.invocation_order,
            item.request_id,
            item.source_id,
            item.invocation_role,
            item.cache_identity_sha256,
        )
        for item in plan.invocations
    )
    outcome_pairs = tuple(
        (
            item.invocation_order,
            item.request_id,
            item.source_id,
            item.invocation_role,
            item.cache_identity_sha256,
        )
        for item in record.ordered_invocation_outcomes
    )
    if (
        record.execution_plan_sha256 != plan.execution_plan_sha256
        or record.manifest_sha256 != plan.manifest_binding.manifest_sha256
        or record.authorization_id != authorization.authorization_id
        or record.authorization_sha256 != authorization.authorization_sha256
        or outcome_pairs != plan_pairs
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "existing execution record conflicts with current frozen inputs",
        )


def _validate_openai_development_execution_readiness_v0_3(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    clock: Callable[[], datetime],
    reconstructor: RequestReconstructor = _reconstruct_invocations,
) -> OpenAIDevelopmentExecutionReadinessV03:
    root = preflight_execution._validate_path_chain(
        repository_root, label="development repository root"
    )
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            raise OSError
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "development repository root must be a safe local directory",
        ) from error
    plan = _load_frozen_plan(root)
    manifest = _load_frozen_manifest(root, plan)

    authorization = _load_input_model(
        authorization_path,
        label="development authorization",
        model_type=OpenAIDevelopmentExecutionAuthorizationV03,
        repository_root=root,
        error_code=Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
    )
    pricing = _load_input_model(
        pricing_path,
        label="current pricing observation",
        model_type=OpenAIPricingObservation,
        repository_root=root,
    )
    controls = _load_input_model(
        data_controls_path,
        label="current data-controls observation",
        model_type=OpenAIDataControlsObservation,
        repository_root=root,
    )
    assert isinstance(authorization, OpenAIDevelopmentExecutionAuthorizationV03)
    assert isinstance(pricing, OpenAIPricingObservation)
    assert isinstance(controls, OpenAIDataControlsObservation)
    timestamp = _validated_timestamp(clock)
    inputs = _validate_inputs(
        authorization=authorization,
        pricing=pricing,
        data_controls=controls,
        manifest=manifest,
        timestamp=timestamp,
    )
    if (
        plan.execution_controls.aggregate_conservative_cost_ceiling_usd
        != CONSERVATIVE_COST_CEILING_USD
        or plan.execution_controls.aggregate_conservative_cost_ceiling_usd
        >= authorization.cost_cap_usd
    ):
        raise Stage4BError(
            Stage4BErrorCode.COST_BUDGET_EXCEEDED,
            "frozen conservative budget does not fit the authorization cap",
        )
    invocations = reconstructor(root, plan, manifest)
    if (
        len(invocations) != 8
        or tuple(item.plan for item in invocations) != plan.invocations
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "prepared invocation inventory differs from the frozen plan",
        )

    cache_root = _artifact_path(
        root, plan.cache_policy.relative_cache_root.rstrip("/"), label="cache root"
    )
    for invocation in invocations:
        _artifact_path(
            root,
            invocation.plan.attempt_marker_relative_path,
            label="development attempt marker",
        )
        _artifact_path(
            root,
            invocation.plan.failure_record_relative_path,
            label="development failure record",
        )
    final_path = _artifact_path(
        root, plan.artifact_policy.execution_record_path, label="execution record"
    )
    existing: OpenAIDevelopmentExecutionRecordV03 | None = None
    if os.path.lexists(final_path):
        existing = load_development_execution_record_v0_3(final_path)
        _validate_existing_record(existing, authorization=authorization, plan=plan)
    return OpenAIDevelopmentExecutionReadinessV03(
        plan=plan,
        manifest=manifest,
        inputs=inputs,
        execution_timestamp_utc=timestamp,
        repository_root=root,
        invocations=invocations,
        cache_root=cache_root,
        execution_record_path=final_path,
        existing_execution_record=existing,
    )


def _installed_repository_root() -> Path:
    return Path(__file__).parents[3]


def resolve_production_repository_root(launch_directory: Path | None = None) -> Path:
    root = preflight_execution._validate_project_repository_identity(
        _installed_repository_root()
    )
    selected = Path.cwd() if launch_directory is None else launch_directory
    try:
        launch = preflight_execution._validate_path_chain(
            selected, label="launch directory"
        )
        launch.relative_to(root)
        if not stat.S_ISDIR(os.lstat(launch).st_mode):
            raise OSError
    except (OSError, ValueError, Stage4BError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "command must run from this verified project repository",
        ) from error
    return root


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_openai_development_execution_readiness_v0_3(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
) -> OpenAIDevelopmentExecutionReadinessV03:
    root = resolve_production_repository_root(Path.cwd())
    return _validate_openai_development_execution_readiness_v0_3(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        clock=_utc_now,
    )


def _build_marker(
    *,
    readiness: OpenAIDevelopmentExecutionReadinessV03,
    invocation: PreparedDevelopmentInvocationV03,
    timestamp: datetime,
) -> OpenAIDevelopmentInvocationAttemptMarkerV03:
    values = {
        "marker_schema_version": ATTEMPT_MARKER_SCHEMA_VERSION,
        "execution_id": EXECUTION_ID,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "manifest_sha256": readiness.manifest.manifest_sha256,
        "authorization_sha256": (
            readiness.inputs.authorization.authorization_sha256
        ),
        "invocation_order": invocation.plan.invocation_order,
        "request_id": invocation.plan.request_id,
        "cache_identity_sha256": invocation.plan.cache_identity_sha256,
        "attempt_marker_relative_path": (
            invocation.plan.attempt_marker_relative_path
        ),
        "attempt_timestamp_utc": timestamp,
        "state": "provider_call_may_have_started",
    }
    provisional = OpenAIDevelopmentInvocationAttemptMarkerV03.model_construct(
        **values, marker_sha256="0" * 64
    )
    return OpenAIDevelopmentInvocationAttemptMarkerV03.model_validate(
        {**values, "marker_sha256": _canonical_hash(provisional, "marker_sha256")}
    )


def _ensure_directory(path: Path, *, label: str) -> Path:
    candidate = preflight_execution._validate_path_chain(path, label=label)
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        candidate = preflight_execution._validate_path_chain(candidate, label=label)
        if not stat.S_ISDIR(os.lstat(candidate).st_mode):
            raise OSError
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
            f"{label} could not be created safely",
        ) from error
    return candidate


def _write_exclusive(path: Path, payload: bytes, *, marker: bool) -> None:
    parent = _ensure_directory(path.parent, label="development artifact directory")
    preflight_execution._validate_path_chain(path, label="development artifact")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor_open = False
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        preflight_execution._validate_path_chain(
            temporary, label="temporary development artifact"
        )
        preflight_execution._validate_path_chain(path, label="development artifact")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            code = (
                Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS
                if marker
                else Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED
            )
            raise Stage4BError(
                code,
                "immutable development artifact already exists",
            ) from error
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
                "exclusive development artifact installation failed",
            ) from error
        if manifest_module._read_validated_regular_file(path) != payload:
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
                "installed development artifact failed read-back verification",
            )
    finally:
        if descriptor_open:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _estimated_cost(
    usage: ProviderTokenUsage,
    pricing: OpenAIPricingObservation,
) -> Decimal:
    if usage.input_tokens is None or usage.output_tokens is None:
        raise Stage4BError(
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
            "development response requires exact provider token usage",
        )
    cost = (
        Decimal(usage.input_tokens) * pricing.input_usd_per_million_tokens
        + Decimal(usage.output_tokens) * pricing.output_usd_per_million_tokens
    ) / _MILLION
    return Decimal("0") if cost == 0 else cost.normalize()


def _validate_provider_observation(
    observation: object,
    invocation: PreparedDevelopmentInvocationV03,
    pricing: OpenAIPricingObservation,
) -> tuple[OpenAIPreflightProviderObservation, Decimal]:
    try:
        validated = OpenAIPreflightProviderObservation.model_validate(
            observation.model_dump(mode="python")  # type: ignore[union-attr]
        )
    except (AttributeError, ValidationError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
            "same-call development response metadata is invalid",
        ) from error
    response = validated.response
    if (
        response.request_id != invocation.request.request_id
        or response.provider_identifier != OPENAI_PROVIDER_IDENTIFIER
        or response.model_identifier != EXPECTED_RETURNED_MODEL_IDENTIFIER
        or response.provider_sdk_version != OPENAI_REQUIRED_SDK_VERSION
        or response.provider_sdk_version != OPENAI_INSTALLED_SDK_VERSION
        or response.terminal_status is not ProviderTerminalStatus.SUCCESS
        or response.retry_count != 0
        or response.token_usage is None
    ):
        raise Stage4BError(
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
            "development response metadata differs from frozen provider controls",
        )
    usage = response.token_usage
    if (
        usage.input_tokens is None
        or usage.output_tokens is None
        or usage.output_tokens > OPENAI_MAX_OUTPUT_TOKENS
    ):
        raise Stage4BError(
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
            "development response token usage is missing or exceeds its cap",
        )
    return validated, _estimated_cost(usage, pricing)


def _production_provider_observation(
    client: object,
    request: LLMExtractionRequestV03,
) -> OpenAIPreflightProviderObservation:
    return OpenAIResponsesPreflightBridge(
        provider=OpenAIResponsesProvider(  # type: ignore[arg-type]
            client=client,
            configuration=DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
        )
    ).generate_preflight(request)


ProviderObservation: TypeAlias = Callable[
    [object, LLMExtractionRequestV03], OpenAIPreflightProviderObservation
]
LocalValidator: TypeAlias = Callable[
    [LLMExtractionRequestV03, LLMProviderResponse], ValidatedCandidateOutput
]


def _original_call_provenance(
    observation: OpenAIPreflightProviderObservation,
) -> OpenAIOriginalCallProvenanceV01:
    return OpenAIOriginalCallProvenanceV01(
        model_version_or_snapshot_provenance=(
            observation.model_version_or_snapshot_provenance
        ),
        version_provenance_source_response_id=(
            observation.version_provenance_source_response_id
        ),
        provider_public_metadata_sha256=(
            observation.provider_public_metadata_sha256
        ),
        provider_public_metadata_field_paths=(
            observation.provider_public_metadata_field_paths
        ),
        observed_from_same_provider_call=True,
    )


def _sanitized_failure(
    error: Exception,
    credential: str | None,
) -> tuple[Stage4BError, OpenAIProviderFailureDiagnostics | None]:
    if isinstance(error, OpenAIProviderFailure):
        diagnostics = (
            credential_safety._credential_scrubbed_diagnostics(
                error.diagnostics, credential
            )
            if credential is not None
            else OpenAIProviderFailureDiagnostics()
        )
        sanitized = OpenAIProviderFailure(error.code, diagnostics)
        return sanitized, sanitized.diagnostics
    code = error.code if isinstance(error, Stage4BError) else Stage4BErrorCode.EXECUTION_FAILED
    return (
        Stage4BError(code, "bounded OpenAI development invocation failed"),
        None,
    )


def _build_failure_record(
    *,
    readiness: OpenAIDevelopmentExecutionReadinessV03,
    invocation: PreparedDevelopmentInvocationV03,
    marker: OpenAIDevelopmentInvocationAttemptMarkerV03 | None,
    timestamp: datetime,
    stage: DevelopmentFailureStage,
    error: Stage4BError,
    diagnostics: OpenAIProviderFailureDiagnostics | None,
    cache_present: bool,
    provider_call_occurred: bool,
    cache_install_completed: bool,
    local_parse_started: bool,
) -> OpenAIDevelopmentInvocationFailureRecordV03:
    values = {
        "failure_record_schema_version": FAILURE_RECORD_SCHEMA_VERSION,
        "execution_id": EXECUTION_ID,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "manifest_sha256": readiness.manifest.manifest_sha256,
        "authorization_sha256": readiness.inputs.authorization.authorization_sha256,
        "invocation_order": invocation.plan.invocation_order,
        "request_id": invocation.plan.request_id,
        "source_id": invocation.plan.source_id,
        "cache_identity_sha256": invocation.plan.cache_identity_sha256,
        "attempt_marker_sha256": marker.marker_sha256 if marker else None,
        "failure_timestamp_utc": timestamp,
        "failure_stage": stage,
        "local_error_code": error.code,
        "cache_present": cache_present,
        "provider_call_occurred": provider_call_occurred,
        "cache_install_completed": cache_install_completed,
        "local_parse_started": local_parse_started,
        "local_parse_completed": False,
        "http_status_code": diagnostics.http_status_code if diagnostics else None,
        "provider_error_type": diagnostics.provider_error_type if diagnostics else None,
        "provider_error_code": diagnostics.provider_error_code if diagnostics else None,
        "provider_request_id": diagnostics.provider_request_id if diagnostics else None,
        "retry_count": 0,
    }
    provisional = OpenAIDevelopmentInvocationFailureRecordV03.model_construct(
        **values, failure_record_sha256="0" * 64
    )
    return OpenAIDevelopmentInvocationFailureRecordV03.model_validate(
        {
            **values,
            "failure_record_sha256": _canonical_hash(
                provisional, "failure_record_sha256"
            ),
        }
    )


def _cache_response_metadata(
    record: CacheRecord,
    pricing: OpenAIPricingObservation,
) -> tuple[ProviderTokenUsage, Decimal, OpenAIOriginalCallProvenanceV01]:
    response = record.response
    if (
        response.provider_identifier != OPENAI_PROVIDER_IDENTIFIER
        or response.model_identifier != EXPECTED_RETURNED_MODEL_IDENTIFIER
        or response.provider_sdk_version != OPENAI_REQUIRED_SDK_VERSION
        or response.terminal_status is not ProviderTerminalStatus.SUCCESS
        or response.retry_count != 0
        or response.token_usage is None
        or response.token_usage.input_tokens is None
        or response.token_usage.output_tokens is None
        or response.token_usage.output_tokens > OPENAI_MAX_OUTPUT_TOKENS
        or response.provider_request_id is None
        or response.provider_response_id is None
        or record.openai_original_call_provenance is None
    ):
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cached development response lacks required OpenAI provenance",
        )
    expected_cost = _estimated_cost(response.token_usage, pricing)
    if record.estimated_cost_usd != expected_cost:
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cached development response cost does not reconcile with token usage",
        )
    return response.token_usage, expected_cost, record.openai_original_call_provenance


def _outcome(
    *,
    invocation: PreparedDevelopmentInvocationV03,
    cached: CacheRecord,
    validated: ValidatedCandidateOutput,
    marker: OpenAIDevelopmentInvocationAttemptMarkerV03 | None,
    fresh_cost: Decimal,
    pricing: OpenAIPricingObservation,
) -> OpenAIDevelopmentInvocationOutcomeV03:
    response = cached.response
    usage, historical_cost, provenance = _cache_response_metadata(cached, pricing)
    assert usage.input_tokens is not None
    assert usage.output_tokens is not None
    assert response.provider_request_id is not None
    assert response.provider_response_id is not None
    assert response.provider_sdk_version is not None
    fresh = marker is not None
    candidate_count = len(validated.candidate_result.candidate_facts)
    review_count = sum(
        fact.review_status is CandidateReviewStatus.REQUIRED
        for fact in validated.candidate_result.candidate_facts
    )
    return OpenAIDevelopmentInvocationOutcomeV03(
        invocation_order=invocation.plan.invocation_order,
        request_id=invocation.plan.request_id,
        source_id=invocation.plan.source_id,
        invocation_role=invocation.request.invocation_role,
        cache_identity_sha256=invocation.plan.cache_identity_sha256,
        response_source="provider_call" if fresh else "cache_hit",
        attempt_marker_sha256=marker.marker_sha256 if marker else None,
        cache_record_sha256=cached.cache_record_sha256,
        provider_response_sha256=response.raw_response_sha256,
        candidate_output_sha256=validated.canonical_output_sha256,
        provider_identifier="openai",
        returned_model_identifier=response.model_identifier,
        provider_request_id=response.provider_request_id,
        provider_response_id=response.provider_response_id,
        provider_sdk_version=response.provider_sdk_version,
        model_version_or_snapshot_provenance=(
            provenance.model_version_or_snapshot_provenance
        ),
        version_provenance_source_response_id=(
            provenance.version_provenance_source_response_id
        ),
        provider_public_metadata_sha256=provenance.provider_public_metadata_sha256,
        provider_public_metadata_field_paths=(
            provenance.provider_public_metadata_field_paths
        ),
        version_provenance_observed_from_same_provider_call=True,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=response.latency_ms,
        newly_incurred_cost_usd=fresh_cost if fresh else Decimal("0"),
        historical_cached_cost_usd=(
            Decimal("0") if fresh else historical_cost
        ),
        candidate_count=candidate_count,
        review_required_candidate_count=review_count,
        retry_count=0,
    )


def _build_execution_record(
    *,
    readiness: OpenAIDevelopmentExecutionReadinessV03,
    started: datetime,
    completed: datetime,
    outcomes: tuple[OpenAIDevelopmentInvocationOutcomeV03, ...],
) -> OpenAIDevelopmentExecutionRecordV03:
    values = {
        "execution_record_schema_version": EXECUTION_RECORD_SCHEMA_VERSION,
        "execution_id": EXECUTION_ID,
        "execution_plan_sha256": readiness.plan.execution_plan_sha256,
        "manifest_sha256": readiness.manifest.manifest_sha256,
        "authorization_id": readiness.inputs.authorization.authorization_id,
        "authorization_sha256": readiness.inputs.authorization.authorization_sha256,
        "execution_started_at_utc": started,
        "execution_completed_at_utc": completed,
        "ordered_invocation_outcomes": outcomes,
        "provider_call_count": sum(
            item.response_source == "provider_call" for item in outcomes
        ),
        "provider_attempt_count": sum(
            item.response_source == "provider_call" for item in outcomes
        ),
        "cache_hit_count": sum(
            item.response_source == "cache_hit" for item in outcomes
        ),
        "aggregate_new_cost_usd": sum(
            (item.newly_incurred_cost_usd for item in outcomes), Decimal("0")
        ),
        "aggregate_historical_cached_cost_usd": sum(
            (item.historical_cached_cost_usd for item in outcomes), Decimal("0")
        ),
        "aggregate_input_tokens": sum(item.input_tokens for item in outcomes),
        "aggregate_output_tokens": sum(item.output_tokens for item in outcomes),
        "retry_count": 0,
        "completion_status": "passed",
    }
    provisional = OpenAIDevelopmentExecutionRecordV03.model_construct(
        **values, execution_record_sha256="0" * 64
    )
    return OpenAIDevelopmentExecutionRecordV03.model_validate(
        {
            **values,
            "execution_record_sha256": _canonical_hash(
                provisional, "execution_record_sha256"
            ),
        }
    )


def _openai_api_key_from_environment() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def _production_openai_client_factory(api_key: str) -> object:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _execute_openai_development_transaction_v0_3(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    execute_real_development: bool,
    confirmation: str | None,
    clock: Callable[[], datetime],
    api_key_reader: Callable[[], str | None],
    client_factory: Callable[[str], object],
    reconstructor: RequestReconstructor = _reconstruct_invocations,
    provider_observation: ProviderObservation = _production_provider_observation,
    local_validator: LocalValidator = validate_provider_output,
) -> OpenAIDevelopmentExecutionResultV03:
    if execute_real_development is not True or confirmation != EXECUTION_CONFIRMATION:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "explicit real-development flag and exact confirmation are required",
        )
    readiness = _validate_openai_development_execution_readiness_v0_3(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=repository_root,
        clock=clock,
        reconstructor=reconstructor,
    )
    if readiness.existing_execution_record is not None:
        return OpenAIDevelopmentExecutionResultV03(
            readiness=readiness,
            record=readiness.existing_execution_record,
            execution_record_path=readiness.execution_record_path,
        )

    _ensure_directory(readiness.cache_root, label="development cache root")
    cache = ResponseCache(readiness.cache_root)
    outcomes: list[OpenAIDevelopmentInvocationOutcomeV03] = []
    provider_calls = 0
    attempts = 0
    output_tokens = 0
    new_cost = Decimal("0")
    started = readiness.execution_timestamp_utc

    for invocation in readiness.invocations:
        marker_path = _artifact_path(
            readiness.repository_root,
            invocation.plan.attempt_marker_relative_path,
            label="development attempt marker",
        )
        failure_path = _artifact_path(
            readiness.repository_root,
            invocation.plan.failure_record_relative_path,
            label="development failure record",
        )
        marker: OpenAIDevelopmentInvocationAttemptMarkerV03 | None = None
        observation: OpenAIPreflightProviderObservation | None = None
        credential: str | None = None
        stage: DevelopmentFailureStage = "cache_read"
        cache_present = False
        provider_call_occurred = False
        cache_install_completed = False
        local_parse_started = False
        cached: CacheRecord | None = None
        fresh_cost = Decimal("0")

        try:
            try:
                cached = cache.read(invocation.cache_identity)
            except Stage4BError as error:
                if error.code is not Stage4BErrorCode.CACHE_MISS:
                    raise
            else:
                cache_present = True

            if cached is None:
                stage = "artifact_state"
                if os.path.lexists(marker_path):
                    _validate_existing_marker(
                        load_development_attempt_marker_v0_3(marker_path),
                        readiness=readiness,
                        invocation=invocation,
                    )
                    raise Stage4BError(
                        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                        "attempt marker without cache permanently blocks v0.3 retry",
                    )
                if os.path.lexists(failure_path):
                    load_development_failure_record_v0_3(failure_path)
                    raise Stage4BError(
                        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                        "failure artifact without cache blocks v0.3 execution",
                    )
                if (
                    provider_calls + 1 > MAXIMUM_PROVIDER_CALLS
                    or attempts + 1 > MAXIMUM_TOTAL_ATTEMPTS
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.ATTEMPT_BUDGET_EXCEEDED,
                        "next invocation would exceed the frozen call budget",
                    )
                if (
                    new_cost + invocation.plan.conservative_call_ceiling_usd
                    > readiness.inputs.authorization.cost_cap_usd
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.COST_BUDGET_EXCEEDED,
                        "next invocation would exceed the authorized spend cap",
                    )
                attempt_gate_timestamp = _validated_timestamp(clock)
                _validate_current_terms_gate(
                    pricing=readiness.inputs.pricing_observation,
                    data_controls=readiness.inputs.data_controls_observation,
                    gate_timestamp=attempt_gate_timestamp,
                )
                pending_marker = _build_marker(
                    readiness=readiness,
                    invocation=invocation,
                    timestamp=attempt_gate_timestamp,
                )
                _write_exclusive(
                    marker_path,
                    attempt_marker_bytes_v0_3(pending_marker),
                    marker=True,
                )
                marker = pending_marker
                attempts += 1

                stage = "credential_access"
                try:
                    supplied = api_key_reader()
                except Exception:
                    raise Stage4BError(
                        Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
                        "OPENAI_API_KEY could not be read at the gated boundary",
                    ) from None
                credential = credential_safety.validate_openai_api_key_shape(
                    supplied
                )
                stage = "client_construction"
                client = client_factory(credential)
                stage = "provider_call"
                provider_call_occurred = True
                provider_calls += 1
                observation = provider_observation(client, invocation.request)
                stage = "provider_response_validation"
                observation, fresh_cost = _validate_provider_observation(
                    observation,
                    invocation,
                    readiness.inputs.pricing_observation,
                )
                response = observation.response
                assert response.token_usage is not None
                assert response.token_usage.output_tokens is not None
                if (
                    new_cost + fresh_cost > readiness.inputs.authorization.cost_cap_usd
                    or output_tokens + response.token_usage.output_tokens
                    > MAXIMUM_AGGREGATE_OUTPUT_TOKENS
                    or fresh_cost > invocation.plan.conservative_call_ceiling_usd
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.COST_BUDGET_EXCEEDED,
                        "provider usage exceeds the frozen execution budget",
                    )
                attempt = AttemptProvenance(
                    attempt_number=1,
                    terminal_status=ProviderTerminalStatus.SUCCESS,
                    provider_call_performed=True,
                    response_sha256=response.raw_response_sha256,
                    latency_ms=response.latency_ms,
                    retry_reason=None,
                    failure_code=None,
                )
                record = build_cache_record(
                    identity=invocation.cache_identity,
                    response=response,
                    original_provider_call_timestamp=_validated_timestamp(clock),
                    original_attempts=(attempt,),
                    estimated_cost_usd=fresh_cost,
                    openai_original_call_provenance=(
                        _original_call_provenance(observation)
                    ),
                )
                stage = "cache_install"
                cached = cache.append(record)
                cached = cache.read(invocation.cache_identity)
                cache_present = True
                cache_install_completed = True
                new_cost += fresh_cost
                output_tokens += response.token_usage.output_tokens
            else:
                if os.path.lexists(marker_path):
                    _validate_existing_marker(
                        load_development_attempt_marker_v0_3(marker_path),
                        readiness=readiness,
                        invocation=invocation,
                    )

            if cached is None:
                raise Stage4BError(
                    Stage4BErrorCode.EXECUTION_FAILED,
                    "development invocation produced no verified cache record",
                )
            usage, reconciled_cost, _ = _cache_response_metadata(
                cached, readiness.inputs.pricing_observation
            )
            if reconciled_cost > invocation.plan.conservative_call_ceiling_usd:
                raise Stage4BError(
                    Stage4BErrorCode.COST_BUDGET_EXCEEDED,
                    "cached provider usage exceeds the frozen invocation budget",
                )
            assert usage.output_tokens is not None
            stage = "local_parse"
            local_parse_started = True
            validated = local_validator(invocation.request, cached.response)
            outcome = _outcome(
                invocation=invocation,
                cached=cached,
                validated=validated,
                marker=marker,
                fresh_cost=fresh_cost,
                pricing=readiness.inputs.pricing_observation,
            )
            outcomes.append(outcome)
        except Exception as error:
            sanitized, diagnostics = _sanitized_failure(error, credential)
            durable_invocation_state = (
                marker is not None
                or cache_present
                or provider_call_occurred
                or local_parse_started
            )
            if durable_invocation_state:
                failure = _build_failure_record(
                    readiness=readiness,
                    invocation=invocation,
                    marker=marker,
                    timestamp=_validated_timestamp(clock),
                    stage=stage,
                    error=sanitized,
                    diagnostics=diagnostics,
                    cache_present=cache_present,
                    provider_call_occurred=provider_call_occurred,
                    cache_install_completed=cache_install_completed,
                    local_parse_started=local_parse_started,
                )
                if not os.path.lexists(failure_path):
                    _write_exclusive(
                        failure_path, failure_record_bytes_v0_3(failure), marker=False
                    )
            raise sanitized from None

    if len(outcomes) != 8:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "all eight development invocations must validate before completion",
        )
    completed = _validated_timestamp(clock)
    record = _build_execution_record(
        readiness=readiness,
        started=started,
        completed=completed,
        outcomes=tuple(outcomes),
    )
    try:
        _write_exclusive(
            readiness.execution_record_path,
            execution_record_bytes_v0_3(record),
            marker=False,
        )
    except Stage4BError:
        if os.path.lexists(readiness.execution_record_path):
            existing = load_development_execution_record_v0_3(
                readiness.execution_record_path
            )
            if existing == record:
                record = existing
            else:
                raise
        else:
            raise
    return OpenAIDevelopmentExecutionResultV03(
        readiness=readiness,
        record=record,
        execution_record_path=readiness.execution_record_path,
    )


def execute_openai_development_v0_3(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    execute_real_development: bool,
    confirmation: str | None,
) -> OpenAIDevelopmentExecutionResultV03:
    root = resolve_production_repository_root(Path.cwd())
    return _execute_openai_development_transaction_v0_3(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        execute_real_development=execute_real_development,
        confirmation=confirmation,
        clock=_utc_now,
        api_key_reader=_openai_api_key_from_environment,
        client_factory=_production_openai_client_factory,
    )


__all__ = [
    "AUTHORIZATION_CAP_USD",
    "CONSERVATIVE_COST_CEILING_USD",
    "EXECUTION_CONFIRMATION",
    "EXECUTION_PLAN_ARTIFACT_BYTES",
    "EXECUTION_PLAN_OUTER_SHA256",
    "EXECUTION_PLAN_RELATIVE_PATH",
    "OpenAIDevelopmentExecutionAuthorizationV03",
    "OpenAIDevelopmentExecutionReadinessV03",
    "OpenAIDevelopmentExecutionRecordV03",
    "OpenAIDevelopmentExecutionResultV03",
    "OpenAIDevelopmentInvocationAttemptMarkerV03",
    "OpenAIDevelopmentInvocationFailureRecordV03",
    "OpenAIDevelopmentInvocationOutcomeV03",
    "PreparedDevelopmentInvocationV03",
    "attempt_marker_bytes_v0_3",
    "development_authorization_bytes_v0_3",
    "execute_openai_development_v0_3",
    "execution_record_bytes_v0_3",
    "failure_record_bytes_v0_3",
    "load_development_attempt_marker_v0_3",
    "load_development_execution_record_v0_3",
    "load_development_failure_record_v0_3",
    "validate_openai_development_execution_readiness_v0_3",
]
