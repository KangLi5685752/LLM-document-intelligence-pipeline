"""Offline-only contracts for a future OpenAI development manifest."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.llm_extraction.cache import (
    CacheIdentity,
    CacheIdentityV02,
    CacheIdentityV03,
    V0_2_OPENAI_CACHE_ROOT,
    V0_3_OPENAI_CACHE_ROOT,
    cache_identity_from_request,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    EXPERIMENT_ID_V0_2,
    EXPERIMENT_ID_V0_3,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
    LLMExtractionRequestAny,
    LLMExtractionRequestV02,
    LLMExtractionRequestV03,
    SHA256_PATTERN,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.manifest import EvidenceBlockIdentity
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_preflight_execution_v0_3 import (
    OpenAIPreflightAttemptMarkerV03,
)
from document_intelligence.llm_extraction.openai_preflight_execution_v0_4 import (
    OpenAIPreflightAttemptMarkerV04,
)
from document_intelligence.llm_extraction.openai_preflight_execution import (
    _identities_differ,
    _open_read_only_descriptor,
)
from document_intelligence.llm_extraction.openai_preflight_v0_3 import (
    OpenAIPreflightRecordV03,
)
from document_intelligence.llm_extraction.openai_preflight_v0_4 import (
    OpenAIPreflightRecordV04,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_RESPONSE_SCHEMA_NAME_V0_3,
    build_openai_candidate_schema,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope,
    build_request_envelope_v0_2,
    build_request_envelope_v0_3,
    canonical_json_bytes,
    canonical_prompt_bytes,
    canonical_request_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


DEVELOPMENT_MANIFEST_SCHEMA_VERSION: Literal["0.1"] = "0.1"
DEVELOPMENT_PREPARATION_SCHEMA_VERSION: Literal["0.1"] = "0.1"
CONTEXT_OBSERVATION_SCHEMA_VERSION: Literal["0.1"] = "0.1"
SOURCE_ROUTE_SCHEMA_VERSION: Literal["0.1"] = "0.1"

OPENAI_RETURNED_PREFLIGHT_MODEL: Literal["gpt-5.4-mini-2026-03-17"] = (
    "gpt-5.4-mini-2026-03-17"
)
OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256: Literal[
    "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
] = "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3: Literal[
    "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
] = "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"

PREFLIGHT_ID: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.3"] = (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.3"
)
PREFLIGHT_EXECUTION_PLAN_SHA256 = (
    "21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5"
)
PREFLIGHT_ATTEMPT_SELF_SHA256 = (
    "7FDEE6CFEFC6A9BAEC59BD702D7B0FBA4265DD049A11F43E5F5F5A4791036848"
)
PREFLIGHT_SUCCESS_SELF_SHA256 = (
    "1849C329F45D5BD0FA3472DB21FFBC60903C7449BC38BE05BFF6C3ACA219F974"
)
PREFLIGHT_ATTEMPT_CANONICAL_LF_SHA256 = (
    "94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119"
)
PREFLIGHT_SUCCESS_CANONICAL_LF_SHA256 = (
    "C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2"
)
PREFLIGHT_ID_V0_4: Literal[
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
] = "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
PREFLIGHT_EXECUTION_PLAN_SHA256_V0_4 = (
    "F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E"
)
PREFLIGHT_ATTEMPT_SELF_SHA256_V0_4 = (
    "3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A"
)
PREFLIGHT_SUCCESS_SELF_SHA256_V0_4 = (
    "36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF"
)
PREFLIGHT_ATTEMPT_CANONICAL_LF_SHA256_V0_4 = (
    "4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B"
)
PREFLIGHT_SUCCESS_CANONICAL_LF_SHA256_V0_4 = (
    "1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6"
)

APPROVED_SOURCE_ORDER = ("S001", "S002", "S003", "S004", "S006")
PROHIBITED_SOURCE_IDS = ("S005", "S007")
PARTITION_POLICY_ID: Literal[
    "provider-payload-whole-block-greedy-v0.1"
] = "provider-payload-whole-block-greedy-v0.1"
PARTITION_POLICY_ID_V0_2: Literal[
    "provider-payload-whole-block-greedy-v0.2"
] = "provider-payload-whole-block-greedy-v0.2"
PARTITION_POLICY_ID_V0_3: Literal[
    "provider-payload-whole-block-greedy-v0.3"
] = "provider-payload-whole-block-greedy-v0.3"
REPEAT_SELECTION_POLICY_ID: Literal[
    "largest-primary-provider-payload-request-id-tiebreak-v0.1"
] = "largest-primary-provider-payload-request-id-tiebreak-v0.1"
REPEAT_SELECTION_POLICY_ID_V0_3: Literal[
    "largest-primary-provider-payload-request-id-tiebreak-v0.3"
] = "largest-primary-provider-payload-request-id-tiebreak-v0.3"
PLANNED_CACHE_ROOT = (
    ".cache/llm_extraction/llm-extraction-baseline-v0.1/openai/"
)
PLANNED_CACHE_ROOT_V0_2 = V0_2_OPENAI_CACHE_ROOT
PLANNED_CACHE_ROOT_V0_3 = V0_3_OPENAI_CACHE_ROOT
PLANNED_AUTHORIZATION_CAP_USD = Decimal("1.25")
BROAD_PROJECT_COST_CEILING_USD = Decimal("25")
MAX_OUTPUT_TOKENS = 4096
CONSERVATIVE_TOKEN_ADMISSION_METHOD: Literal[
    "serialized_utf8_byte_upper_bound"
] = "serialized_utf8_byte_upper_bound"
CONSERVATIVE_CONTEXT_SAFETY_RULE: Literal[
    "one serialized UTF-8 provider-payload byte is admitted as at most one "
    "input token for the context-window safety check"
] = (
    "one serialized UTF-8 provider-payload byte is admitted as at most one "
    "input token for the context-window safety check"
)


def _require_trimmed(value: str, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be trimmed and nonblank")
    return value


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value


def _utc_json(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_model_hash(model: BaseModel, hash_field: str) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(model.model_dump(mode="json", exclude={hash_field}))
        + b"\n"
    )


def _canonical_observation_hash(observation: BaseModel) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(observation.model_dump(mode="json")) + b"\n"
    )


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("canonical JSON content must not contain duplicate keys")
        result[name] = value
    return result


def canonical_lf_json_bytes(content: bytes) -> bytes:
    """Return canonical JSON UTF-8 bytes with one LF, independent of checkout EOL."""
    if content.startswith(b"\xef\xbb\xbf"):
        raise ValueError("canonical JSON content must not contain a UTF-8 BOM")
    try:
        text = content.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("canonical JSON content must not contain non-finite values")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("canonical JSON content is not valid UTF-8 JSON") from error
    return canonical_json_bytes(value) + b"\n"


def canonical_lf_json_sha256(content: bytes) -> str:
    """Hash canonical JSON content with exactly one trailing LF and no BOM."""
    return uppercase_sha256_bytes(canonical_lf_json_bytes(content))


class OpenAIDevelopmentPreflightBindingV01(BaseModel):
    """Exact immutable binding to the successful synthetic preflight evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preflight_id: Literal[
        "openai-gpt-5.4-mini-synthetic-preflight-v0.3"
    ] = PREFLIGHT_ID
    execution_plan_sha256: Literal[
        "21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5"
    ] = PREFLIGHT_EXECUTION_PLAN_SHA256
    attempt_canonical_self_sha256: Literal[
        "7FDEE6CFEFC6A9BAEC59BD702D7B0FBA4265DD049A11F43E5F5F5A4791036848"
    ] = PREFLIGHT_ATTEMPT_SELF_SHA256
    success_record_canonical_self_sha256: Literal[
        "1849C329F45D5BD0FA3472DB21FFBC60903C7449BC38BE05BFF6C3ACA219F974"
    ] = PREFLIGHT_SUCCESS_SELF_SHA256
    attempt_canonical_lf_content_sha256: Literal[
        "94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119"
    ] = PREFLIGHT_ATTEMPT_CANONICAL_LF_SHA256
    success_record_canonical_lf_content_sha256: Literal[
        "C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2"
    ] = PREFLIGHT_SUCCESS_CANONICAL_LF_SHA256


def validate_successful_preflight_evidence(
    *,
    attempt_content: bytes,
    success_record_content: bytes,
    binding: OpenAIDevelopmentPreflightBindingV01 | None = None,
) -> None:
    """Validate exact v0.3 identities without depending on checkout line endings."""
    selected = binding or OpenAIDevelopmentPreflightBindingV01()
    if canonical_lf_json_sha256(attempt_content) != (
        selected.attempt_canonical_lf_content_sha256
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "preflight attempt canonical LF-content SHA-256 does not match",
        )
    if canonical_lf_json_sha256(success_record_content) != (
        selected.success_record_canonical_lf_content_sha256
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "preflight success canonical LF-content SHA-256 does not match",
        )
    try:
        attempt = OpenAIPreflightAttemptMarkerV03.model_validate_json(
            attempt_content
        )
        record = OpenAIPreflightRecordV03.model_validate_json(
            success_record_content
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "successful preflight evidence does not satisfy its production models",
        ) from error
    if (
        attempt.preflight_id != selected.preflight_id
        or attempt.execution_plan_sha256 != selected.execution_plan_sha256
        or attempt.marker_sha256 != selected.attempt_canonical_self_sha256
        or record.preflight_id != selected.preflight_id
        or record.preflight_record_sha256
        != selected.success_record_canonical_self_sha256
        or record.returned_model_identifier != OPENAI_RETURNED_PREFLIGHT_MODEL
        or record.model_version_or_snapshot_provenance != "unavailable"
        or record.provider_sdk_version != "2.46.0"
        or record.provider_call_count != 1
        or record.retry_count != 0
        or record.compatibility_status != "passed"
        or record.preflight_status != "passed"
        or attempt.authorization_id != record.authorization.authorization_id
        or attempt.authorization_scope != record.authorization.scope
        or attempt.maximum_provider_calls
        != record.authorization.maximum_provider_calls
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "successful preflight evidence does not match the development binding",
        )


class OpenAIDevelopmentPreflightBindingV03(BaseModel):
    """Exact immutable binding to the alias-safe v0.4 compatibility evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preflight_id: Literal[
        "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
    ] = PREFLIGHT_ID_V0_4
    execution_plan_sha256: Literal[
        "F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E"
    ] = PREFLIGHT_EXECUTION_PLAN_SHA256_V0_4
    attempt_canonical_self_sha256: Literal[
        "3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A"
    ] = PREFLIGHT_ATTEMPT_SELF_SHA256_V0_4
    success_record_canonical_self_sha256: Literal[
        "36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF"
    ] = PREFLIGHT_SUCCESS_SELF_SHA256_V0_4
    attempt_canonical_lf_content_sha256: Literal[
        "4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B"
    ] = PREFLIGHT_ATTEMPT_CANONICAL_LF_SHA256_V0_4
    success_record_canonical_lf_content_sha256: Literal[
        "1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6"
    ] = PREFLIGHT_SUCCESS_CANONICAL_LF_SHA256_V0_4


def validate_successful_preflight_evidence_v0_4(
    *,
    attempt_content: bytes,
    success_record_content: bytes,
    binding: OpenAIDevelopmentPreflightBindingV03 | None = None,
) -> None:
    """Validate the exact alias-safe v0.4 evidence used by development v0.3."""
    selected = binding or OpenAIDevelopmentPreflightBindingV03()
    if canonical_lf_json_sha256(attempt_content) != (
        selected.attempt_canonical_lf_content_sha256
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.4 preflight attempt canonical LF-content SHA-256 does not match",
        )
    if canonical_lf_json_sha256(success_record_content) != (
        selected.success_record_canonical_lf_content_sha256
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.4 preflight success canonical LF-content SHA-256 does not match",
        )
    try:
        attempt = OpenAIPreflightAttemptMarkerV04.model_validate_json(
            attempt_content
        )
        record = OpenAIPreflightRecordV04.model_validate_json(
            success_record_content
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.4 preflight evidence does not satisfy its production models",
        ) from error
    if (
        attempt.preflight_id != selected.preflight_id
        or attempt.execution_plan_sha256 != selected.execution_plan_sha256
        or attempt.marker_sha256 != selected.attempt_canonical_self_sha256
        or record.preflight_id != selected.preflight_id
        or record.preflight_record_sha256
        != selected.success_record_canonical_self_sha256
        or record.experiment_id != EXPERIMENT_ID_V0_3
        or record.returned_model_identifier != OPENAI_RETURNED_PREFLIGHT_MODEL
        or record.model_version_or_snapshot_provenance != "unavailable"
        or record.provider_sdk_version != "2.46.0"
        or record.provider_call_count != 1
        or record.retry_count != 0
        or record.compatibility_status != "passed"
        or record.preflight_status != "passed"
        or record.strict_schema_compatible is not True
        or record.local_output_validation_status != "valid"
        or record.strict_schema_sha256
        != OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3
        or record.provider_configuration_id
        != OPENAI_PROVIDER_CONFIGURATION_ID_V0_3
        or record.model_configuration_id != OPENAI_MODEL_CONFIGURATION_ID_V0_3
        or attempt.authorization_id != record.authorization.authorization_id
        or attempt.authorization_scope != record.authorization.scope
        or attempt.maximum_provider_calls
        != record.authorization.maximum_provider_calls
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.4 preflight evidence does not match the development-v0.3 binding",
        )


class ReviewedContextLimitObservationV01(BaseModel):
    """Self-hashed reviewed context and token-admission evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_schema_version: Literal["0.1"] = CONTEXT_OBSERVATION_SCHEMA_VERSION
    requested_model_alias: Literal["gpt-5.4-mini"] = "gpt-5.4-mini"
    returned_model_identifier: Literal[
        "gpt-5.4-mini-2026-03-17"
    ] = OPENAI_RETURNED_PREFLIGHT_MODEL
    source_title: str
    source_url: str
    observed_at_utc: datetime
    reviewer: str
    exact_context_window_tokens: int = Field(gt=4096)
    input_output_reasoning_share_context_window: StrictBool
    max_output_tokens_4096_supported: Literal[True]
    reasoning_effort_none_supported: Literal[True]
    token_admission_method: Literal[
        "serialized_utf8_byte_upper_bound"
    ] = CONSERVATIVE_TOKEN_ADMISSION_METHOD
    exact_safety_rule: Literal[
        "one serialized UTF-8 provider-payload byte is admitted as at most one "
        "input token for the context-window safety check"
    ] = CONSERVATIVE_CONTEXT_SAFETY_RULE
    observation_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("source_title", "source_url", "reviewer")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        validated = _require_trimmed(value, info.field_name)
        if info.field_name == "source_url" and not validated.startswith(
            ("https://", "http://")
        ):
            raise ValueError("source_url must be an HTTP(S) reviewed source")
        return validated

    @field_validator("observed_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "observed_at_utc")

    @field_validator("exact_context_window_tokens", mode="before")
    @classmethod
    def validate_exact_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("exact_context_window_tokens must use an integer")
        return value

    @field_serializer("observed_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @model_validator(mode="after")
    def validate_self_hash(self) -> ReviewedContextLimitObservationV01:
        if self.observation_sha256 != _canonical_model_hash(
            self, "observation_sha256"
        ):
            raise ValueError(
                "observation_sha256 does not match the canonical observation"
            )
        return self


def build_reviewed_context_limit_observation(
    *,
    source_title: str,
    source_url: str,
    observed_at_utc: datetime,
    reviewer: str,
    exact_context_window_tokens: int,
    input_output_reasoning_share_context_window: bool,
) -> ReviewedContextLimitObservationV01:
    """Build a fictional-or-later-reviewed observation without provider access."""
    values = {
        "observation_schema_version": CONTEXT_OBSERVATION_SCHEMA_VERSION,
        "requested_model_alias": "gpt-5.4-mini",
        "returned_model_identifier": OPENAI_RETURNED_PREFLIGHT_MODEL,
        "source_title": source_title,
        "source_url": source_url,
        "observed_at_utc": observed_at_utc,
        "reviewer": reviewer,
        "exact_context_window_tokens": exact_context_window_tokens,
        "input_output_reasoning_share_context_window": (
            input_output_reasoning_share_context_window
        ),
        "max_output_tokens_4096_supported": True,
        "reasoning_effort_none_supported": True,
        "token_admission_method": CONSERVATIVE_TOKEN_ADMISSION_METHOD,
        "exact_safety_rule": CONSERVATIVE_CONTEXT_SAFETY_RULE,
    }
    provisional = ReviewedContextLimitObservationV01.model_construct(
        **values, observation_sha256="0" * 64
    )
    return ReviewedContextLimitObservationV01.model_validate(
        {
            **values,
            "observation_sha256": _canonical_model_hash(
                provisional, "observation_sha256"
            ),
        }
    )


def _validate_repository_relative_path(value: str, field_name: str) -> str:
    validated = _require_trimmed(value, field_name)
    if "\\" in validated:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            f"{field_name} must use repository-relative POSIX separators",
        )
    lowered = validated.casefold()
    if lowered.startswith(("//", "\\\\?\\", "\\\\.\\")):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            f"{field_name} must not use UNC or device namespaces",
        )
    posix = PurePosixPath(validated)
    windows = PureWindowsPath(validated)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or not posix.parts
        or any(part in {"", ".", ".."} for part in posix.parts)
        or posix.as_posix() != validated
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            f"{field_name} must be a normalized repository-relative path",
        )
    return validated


def approved_parsed_document_relative_path(
    source_id: str,
    relative_path: str,
) -> str:
    """Validate the source before any path parsing or filesystem activity."""
    validate_development_source_id(source_id)
    return _validate_repository_relative_path(
        relative_path,
        "parsed_document_relative_path",
    )


class OpenAIDevelopmentSourceRouteV01(BaseModel):
    """Self-hashed metadata proof required before a ParsedDocument is opened."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_schema_version: Literal["0.1"] = SOURCE_ROUTE_SCHEMA_VERSION
    source_id: str
    split: Literal["development"]
    corpus_status: Literal["approved"]
    derived_text_allowed: Literal[True]
    ingestion_status: Literal["success"]
    checksum_matches: Literal[True]
    parsed_document_relative_path: str
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_document_canonical_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    parsed_document_schema_version: Literal["0.1"]
    source_format: Literal["PDF"]
    route_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("source_id")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return validate_development_source_id(value)

    @model_validator(mode="after")
    def validate_route(self) -> OpenAIDevelopmentSourceRouteV01:
        approved_parsed_document_relative_path(
            self.source_id,
            self.parsed_document_relative_path,
        )
        if self.route_sha256 != _canonical_model_hash(self, "route_sha256"):
            raise ValueError("route_sha256 does not match the canonical route")
        return self


def build_source_route_identity(
    *,
    source_id: str,
    parsed_document_relative_path: str,
    document_sha256: str,
    parsed_document_canonical_sha256: str,
    parser_commit: str,
) -> OpenAIDevelopmentSourceRouteV01:
    """Build a route from already-reviewed non-semantic source metadata."""
    relative_path = approved_parsed_document_relative_path(
        source_id,
        parsed_document_relative_path,
    )
    values = {
        "route_schema_version": SOURCE_ROUTE_SCHEMA_VERSION,
        "source_id": source_id,
        "split": "development",
        "corpus_status": "approved",
        "derived_text_allowed": True,
        "ingestion_status": "success",
        "checksum_matches": True,
        "parsed_document_relative_path": relative_path,
        "document_sha256": document_sha256,
        "parsed_document_canonical_sha256": parsed_document_canonical_sha256,
        "parser_commit": parser_commit,
        "parsed_document_schema_version": "0.1",
        "source_format": "PDF",
    }
    provisional = OpenAIDevelopmentSourceRouteV01.model_construct(
        **values, route_sha256="0" * 64
    )
    return OpenAIDevelopmentSourceRouteV01.model_validate(
        {
            **values,
            "route_sha256": _canonical_model_hash(provisional, "route_sha256"),
        }
    )


def _is_reparse_or_link(path: Path, result: os.stat_result) -> bool:
    attributes = getattr(result, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(result.st_mode) or bool(attributes & reparse)


def _safe_existing_file(repository_root: Path, relative_path: str) -> Path:
    root = repository_root.absolute()
    root_components: list[Path] = []
    current_root = Path(root.anchor)
    root_components.append(current_root)
    for part in root.parts[1:]:
        current_root /= part
        root_components.append(current_root)
    for component in root_components:
        try:
            root_stat = os.lstat(component)
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "repository root is unavailable",
            ) from error
        if _is_reparse_or_link(component, root_stat):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "repository root path contains an unsafe component",
            )
    if not stat.S_ISDIR(root_stat.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "repository root is not a safe directory",
        )

    target = root.joinpath(*PurePosixPath(relative_path).parts)
    current = root
    target_stat: os.stat_result | None = None
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        try:
            current_stat = os.lstat(current)
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "approved ParsedDocument path is unavailable",
            ) from error
        if _is_reparse_or_link(current, current_stat):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "approved ParsedDocument path contains an unsafe component",
            )
        target_stat = current_stat

    if target_stat is None or not stat.S_ISREG(target_stat.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument path is not a regular file",
        )
    try:
        resolved_root = root.resolve(strict=True)
        resolved_target = target.resolve(strict=True)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument path cannot be resolved safely",
        ) from error
    if not resolved_target.is_relative_to(resolved_root):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument path escapes the repository root",
        )
    return target


def _read_validated_regular_file(target: Path) -> bytes:
    """Read the exact regular-file descriptor checked before and after access."""
    try:
        before = os.lstat(target)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument is unavailable",
        ) from error
    if _is_reparse_or_link(target, before) or not stat.S_ISREG(before.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument is not a safe regular file",
        )
    descriptor: int | None = None
    try:
        descriptor = _open_read_only_descriptor(target)
        opened = os.fstat(descriptor)
        after_open = os.lstat(target)
        if (
            _is_reparse_or_link(target, opened)
            or _is_reparse_or_link(target, after_open)
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(after_open.st_mode)
            or _identities_differ(before, opened)
            or _identities_differ(opened, after_open)
        ):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "approved ParsedDocument changed during validation",
            )
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            content = handle.read()
            opened_after_read = os.fstat(handle.fileno())
            after_read = os.lstat(target)
            if (
                _is_reparse_or_link(target, opened_after_read)
                or _is_reparse_or_link(target, after_read)
                or not stat.S_ISREG(opened_after_read.st_mode)
                or not stat.S_ISREG(after_read.st_mode)
                or _identities_differ(opened, opened_after_read)
                or _identities_differ(opened_after_read, after_read)
            ):
                raise Stage4BError(
                    Stage4BErrorCode.INVALID_MANIFEST,
                    "approved ParsedDocument changed while it was read",
                )
    except Stage4BError:
        raise
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument could not be read safely",
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return content


def _parse_canonical_json(content: bytes) -> Any:
    canonical = canonical_lf_json_bytes(content)
    return json.loads(canonical)


def _document_canonical_sha256(document: ParsedDocument) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(document.model_dump(mode="json"))
    )


def _validate_document_route(
    document: ParsedDocument,
    route: OpenAIDevelopmentSourceRouteV01,
) -> ParsedDocument:
    validated = ParsedDocument.model_validate(document.model_dump(mode="python"))
    if (
        validated.source_id != route.source_id
        or validated.checksum_sha256 != route.document_sha256
        or validated.schema_version != route.parsed_document_schema_version
        or validated.source_format.value != route.source_format
        or validated.parse_status.value != route.ingestion_status
        or _document_canonical_sha256(validated)
        != route.parsed_document_canonical_sha256
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument does not reconcile with its approved source route",
        )
    return validated


def load_approved_parsed_document(
    *,
    repository_root: Path,
    requested_source_id: str,
    route: OpenAIDevelopmentSourceRouteV01,
) -> ParsedDocument:
    """Load one approved route after source denial and path-chain validation."""
    validate_development_source_id(requested_source_id)
    validated_route = OpenAIDevelopmentSourceRouteV01.model_validate(
        route.model_dump(mode="python")
    )
    if validated_route.source_id != requested_source_id:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "requested source does not match the approved route",
        )
    target = _safe_existing_file(
        repository_root, validated_route.parsed_document_relative_path
    )
    try:
        content = _read_validated_regular_file(target)
        payload = _parse_canonical_json(content)
        document = ParsedDocument.model_validate(payload)
    except (OSError, ValueError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved ParsedDocument could not be validated",
        ) from error
    return _validate_document_route(document, validated_route)


class OpenAIDevelopmentPartitionPolicyV01(BaseModel):
    """Source-independent whole-block canonical-payload partition rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: Literal[
        "provider-payload-whole-block-greedy-v0.1"
    ] = PARTITION_POLICY_ID
    maximum_provider_payload_bytes: Literal[200000] = 200000
    preserve_complete_blocks: Literal[True] = True
    preserve_source_sequence: Literal[True] = True
    greedy_maximal_prefix: Literal[True] = True
    omit_blank_text_blocks: Literal[True] = True
    evidence_id_template: Literal[
        "llm-evidence-v0.1-{source_id}-{block_id}"
    ] = "llm-evidence-v0.1-{source_id}-{block_id}"


class OpenAIDevelopmentPartitionPolicyV02(OpenAIDevelopmentPartitionPolicyV01):
    """Additive v0.2 whole-block rule over prompt and request v0.2 bytes."""

    policy_id: Literal[
        "provider-payload-whole-block-greedy-v0.2"
    ] = PARTITION_POLICY_ID_V0_2
    evidence_id_template: Literal[
        "llm-evidence-v0.2-{source_id}-{block_id}"
    ] = "llm-evidence-v0.2-{source_id}-{block_id}"


class OpenAIDevelopmentPartitionPolicyV03(OpenAIDevelopmentPartitionPolicyV01):
    """Additive whole-block rule over alias-safe prompt and payload v0.3 bytes."""

    policy_id: Literal[
        "provider-payload-whole-block-greedy-v0.3"
    ] = PARTITION_POLICY_ID_V0_3
    evidence_id_template: Literal[
        "llm-evidence-v0.3-{source_id}-{block_id}"
    ] = "llm-evidence-v0.3-{source_id}-{block_id}"


class OpenAIDevelopmentRepeatSelectionPolicyV01(BaseModel):
    """Deterministic pre-observation repeat-selection boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: Literal[
        "largest-primary-provider-payload-request-id-tiebreak-v0.1"
    ] = REPEAT_SELECTION_POLICY_ID
    repeat_request_count: Literal[1] = 1
    select_greatest_provider_payload_bytes: Literal[True] = True
    request_id_lexicographic_tiebreak: Literal[True] = True
    repeat_appears_after_all_primaries: Literal[True] = True


class OpenAIDevelopmentRepeatSelectionPolicyV03(
    OpenAIDevelopmentRepeatSelectionPolicyV01
):
    """Explicit repeat identity for the development-v0.3 request family."""

    policy_id: Literal[
        "largest-primary-provider-payload-request-id-tiebreak-v0.3"
    ] = REPEAT_SELECTION_POLICY_ID_V0_3


class OpenAIDevelopmentProviderControlsV01(BaseModel):
    """Fixed paid-request controls already verified by the adapter tests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning_effort: Literal["none"] = "none"
    max_output_tokens: Literal[4096] = 4096
    strict_json_schema: Literal[True] = True
    store: Literal[False] = False
    stream: Literal[False] = False
    background: Literal[False] = False
    tools: tuple[()] = ()
    tool_choice: Literal["none"] = "none"
    provider_side_retries: Literal[0] = 0
    response_timeout_seconds: Literal[120] = 120


class OpenAIDevelopmentCachePolicyV01(BaseModel):
    """Fixed local append-only cache boundary for a later execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_cache_root: str = PLANNED_CACHE_ROOT
    git_ignored_local_only: Literal[True] = True
    append_only: Literal[True] = True
    cache_replacement_allowed: Literal[False] = False
    cache_bypass_allowed: Literal[False] = False
    primary_repeat_identities_distinct: Literal[True] = True
    successful_responses_only: Literal[True] = True

    @field_validator("relative_cache_root")
    @classmethod
    def validate_cache_root(cls, value: str) -> str:
        if not value.endswith("/"):
            raise ValueError("relative_cache_root must end with one slash")
        normalized = _validate_repository_relative_path(
            value[:-1],
            "relative_cache_root",
        )
        return normalized + "/"

    @model_validator(mode="after")
    def validate_fixed_root(self) -> OpenAIDevelopmentCachePolicyV01:
        if self.relative_cache_root != PLANNED_CACHE_ROOT:
            raise ValueError("relative_cache_root differs from the fixed cache policy")
        return self


class OpenAIDevelopmentCachePolicyV02(OpenAIDevelopmentCachePolicyV01):
    """Append-only cache policy isolated under the v0.2 experiment root."""

    relative_cache_root: str = PLANNED_CACHE_ROOT_V0_2

    @model_validator(mode="after")
    def validate_fixed_root(self) -> OpenAIDevelopmentCachePolicyV02:
        if self.relative_cache_root != PLANNED_CACHE_ROOT_V0_2:
            raise ValueError("relative_cache_root differs from the v0.2 cache policy")
        return self


class OpenAIDevelopmentCachePolicyV03(OpenAIDevelopmentCachePolicyV01):
    """Append-only cache policy isolated under the v0.3 experiment root."""

    relative_cache_root: str = PLANNED_CACHE_ROOT_V0_3

    @model_validator(mode="after")
    def validate_fixed_root(self) -> OpenAIDevelopmentCachePolicyV03:
        if self.relative_cache_root != PLANNED_CACHE_ROOT_V0_3:
            raise ValueError("relative_cache_root differs from the v0.3 cache policy")
        return self


class OpenAIDevelopmentAccessPolicyV01(BaseModel):
    """Exact development-only source and semantic-access boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved_source_ids: tuple[
        Literal["S001"],
        Literal["S002"],
        Literal["S003"],
        Literal["S004"],
        Literal["S006"],
    ] = APPROVED_SOURCE_ORDER
    explicitly_prohibited_source_ids: tuple[
        Literal["S005"], Literal["S007"]
    ] = PROHIBITED_SOURCE_IDS
    unknown_sources_prohibited: Literal[True] = True
    route_validation_before_path_construction: Literal[True] = True
    route_validation_before_file_open: Literal[True] = True
    held_out_parsed_document_access_authorized: Literal[False] = False
    held_out_annotation_access_authorized: Literal[False] = False
    gold_labels_as_prompt_input_authorized: Literal[False] = False
    deterministic_candidates_as_prompt_input_authorized: Literal[False] = False
    owner_outcomes_as_prompt_input_authorized: Literal[False] = False


class OpenAIDevelopmentInvocationIdentityV01(BaseModel):
    """Hash-only identity and deterministic cost plan for one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_order: int = Field(gt=0)
    source_id: str
    invocation_role: InvocationRole
    request_id: str
    repeated_primary_request_id: str | None = None
    block_count: int = Field(gt=0)
    ordered_evidence_blocks: tuple[EvidenceBlockIdentity, ...] = Field(
        min_length=1
    )
    total_supplied_text_bytes: int = Field(gt=0)
    canonical_prompt_bytes: int = Field(gt=0)
    canonical_request_bytes: int = Field(gt=0)
    provider_payload_bytes: int = Field(gt=0)
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_document_canonical_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    strict_schema_sha256: Literal[
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    ] = OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256
    provider_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    cache_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    planning_input_token_estimate: int = Field(gt=0)
    conservative_input_token_proxy: int = Field(gt=0)
    maximum_output_tokens: Literal[4096] = MAX_OUTPUT_TOKENS
    maximum_output_cost_usd: Decimal = Field(gt=0)
    planning_cost_ceiling_usd: Decimal = Field(gt=0)
    conservative_call_ceiling_usd: Decimal = Field(gt=0)

    @field_validator("source_id")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return validate_development_source_id(value)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return _require_trimmed(value, "request_id")

    @field_validator(
        "maximum_output_cost_usd",
        "planning_cost_ceiling_usd",
        "conservative_call_ceiling_usd",
    )
    @classmethod
    def normalize_decimal(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_serializer(
        "maximum_output_cost_usd",
        "planning_cost_ceiling_usd",
        "conservative_call_ceiling_usd",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_identity(self) -> OpenAIDevelopmentInvocationIdentityV01:
        if self.block_count != len(self.ordered_evidence_blocks):
            raise ValueError("block_count must match ordered evidence identities")
        if any(
            item.source_id != self.source_id
            for item in self.ordered_evidence_blocks
        ):
            raise ValueError("ordered evidence identities must use one source")
        sequences = [item.sequence for item in self.ordered_evidence_blocks]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("ordered evidence sequences must be unique and increasing")
        block_ids = [item.block_id for item in self.ordered_evidence_blocks]
        evidence_ids = [item.evidence_id for item in self.ordered_evidence_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("ordered block IDs must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("ordered evidence IDs must be unique")
        for item in self.ordered_evidence_blocks:
            expected_evidence_id = (
                f"llm-evidence-v0.1-{self.source_id}-{item.block_id}"
            )
            if item.evidence_id != expected_evidence_id:
                raise ValueError("evidence ID does not match the fixed template")
        if self.invocation_role is InvocationRole.PRIMARY:
            expected_prefix = f"llm-v0.1-{self.source_id}-primary-"
            suffix = self.request_id.removeprefix(expected_prefix)
            if (
                not self.request_id.startswith(expected_prefix)
                or len(suffix) != 3
                or not suffix.isdigit()
                or suffix == "000"
            ):
                raise ValueError("primary request ID does not match the fixed format")
            if self.repeated_primary_request_id is not None:
                raise ValueError("primary invocations cannot repeat another request")
        else:
            if self.request_id != f"llm-v0.1-{self.source_id}-repeat-001":
                raise ValueError("repeat request ID does not match the fixed format")
            if not self.repeated_primary_request_id:
                raise ValueError("repeat invocations require a primary request identity")
        if self.planning_input_token_estimate != (
            self.provider_payload_bytes + 3
        ) // 4:
            raise ValueError("planning input-token estimate does not reconcile")
        if self.conservative_input_token_proxy != self.provider_payload_bytes:
            raise ValueError("conservative input-token proxy does not reconcile")
        if self.planning_cost_ceiling_usd > self.conservative_call_ceiling_usd:
            raise ValueError("planning cost must not exceed the conservative ceiling")
        cache_identity = CacheIdentity(
            experiment_id=EXPERIMENT_ID,
            invocation_role=self.invocation_role,
            request_id=self.request_id,
            canonical_request_sha256=self.canonical_request_sha256,
            provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
            model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
            prompt_sha256=self.prompt_sha256,
            document_sha256=self.document_sha256,
        )
        if self.cache_identity_sha256 != cache_identity_sha256(cache_identity):
            raise ValueError(
                "cache_identity_sha256 does not match the serialized invocation"
            )
        return self


class OpenAIDevelopmentInvocationIdentityV02(
    OpenAIDevelopmentInvocationIdentityV01
):
    """Additive hash-only invocation identity for request/cache family v0.2."""

    @model_validator(mode="after")
    def validate_identity(self) -> OpenAIDevelopmentInvocationIdentityV02:
        if self.block_count != len(self.ordered_evidence_blocks):
            raise ValueError("block_count must match ordered evidence identities")
        if any(
            item.source_id != self.source_id
            for item in self.ordered_evidence_blocks
        ):
            raise ValueError("ordered evidence identities must use one source")
        sequences = [item.sequence for item in self.ordered_evidence_blocks]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("ordered evidence sequences must be unique and increasing")
        block_ids = [item.block_id for item in self.ordered_evidence_blocks]
        evidence_ids = [item.evidence_id for item in self.ordered_evidence_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("ordered block IDs must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("ordered evidence IDs must be unique")
        for item in self.ordered_evidence_blocks:
            expected_evidence_id = (
                f"llm-evidence-v0.2-{self.source_id}-{item.block_id}"
            )
            if item.evidence_id != expected_evidence_id:
                raise ValueError("evidence ID does not match the v0.2 template")
        if self.invocation_role is InvocationRole.PRIMARY:
            expected_prefix = f"llm-v0.2-{self.source_id}-primary-"
            suffix = self.request_id.removeprefix(expected_prefix)
            if (
                not self.request_id.startswith(expected_prefix)
                or len(suffix) != 3
                or not suffix.isdigit()
                or suffix == "000"
            ):
                raise ValueError("primary request ID does not match the v0.2 format")
            if self.repeated_primary_request_id is not None:
                raise ValueError("primary invocations cannot repeat another request")
        else:
            if self.request_id != f"llm-v0.2-{self.source_id}-repeat-001":
                raise ValueError("repeat request ID does not match the v0.2 format")
            if not self.repeated_primary_request_id:
                raise ValueError("repeat invocations require a primary request identity")
        if self.planning_input_token_estimate != (
            self.provider_payload_bytes + 3
        ) // 4:
            raise ValueError("planning input-token estimate does not reconcile")
        if self.conservative_input_token_proxy != self.provider_payload_bytes:
            raise ValueError("conservative input-token proxy does not reconcile")
        if self.planning_cost_ceiling_usd > self.conservative_call_ceiling_usd:
            raise ValueError("planning cost must not exceed the conservative ceiling")
        cache_identity = CacheIdentityV02(
            experiment_id=EXPERIMENT_ID_V0_2,
            invocation_role=self.invocation_role,
            request_id=self.request_id,
            canonical_request_sha256=self.canonical_request_sha256,
            provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
            model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
            prompt_sha256=self.prompt_sha256,
            document_sha256=self.document_sha256,
        )
        if self.cache_identity_sha256 != cache_identity_sha256(cache_identity):
            raise ValueError(
                "cache_identity_sha256 does not match the serialized v0.2 invocation"
            )
        return self


class OpenAIDevelopmentInvocationIdentityV03(
    OpenAIDevelopmentInvocationIdentityV01
):
    """Additive hash-only invocation identity for alias-safe request v0.3."""

    strict_schema_sha256: Literal[
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    ] = OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3

    @model_validator(mode="after")
    def validate_identity(self) -> OpenAIDevelopmentInvocationIdentityV03:
        if self.block_count != len(self.ordered_evidence_blocks):
            raise ValueError("block_count must match ordered evidence identities")
        if any(
            item.source_id != self.source_id
            for item in self.ordered_evidence_blocks
        ):
            raise ValueError("ordered evidence identities must use one source")
        sequences = [item.sequence for item in self.ordered_evidence_blocks]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("ordered evidence sequences must be unique and increasing")
        block_ids = [item.block_id for item in self.ordered_evidence_blocks]
        evidence_ids = [item.evidence_id for item in self.ordered_evidence_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("ordered block IDs must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("ordered evidence IDs must be unique")
        for item in self.ordered_evidence_blocks:
            expected_evidence_id = (
                f"llm-evidence-v0.3-{self.source_id}-{item.block_id}"
            )
            if item.evidence_id != expected_evidence_id:
                raise ValueError("evidence ID does not match the v0.3 template")
        if self.invocation_role is InvocationRole.PRIMARY:
            expected_prefix = f"llm-v0.3-{self.source_id}-primary-"
            suffix = self.request_id.removeprefix(expected_prefix)
            if (
                not self.request_id.startswith(expected_prefix)
                or len(suffix) != 3
                or not suffix.isdigit()
                or suffix == "000"
            ):
                raise ValueError("primary request ID does not match the v0.3 format")
            if self.repeated_primary_request_id is not None:
                raise ValueError("primary invocations cannot repeat another request")
        else:
            if self.request_id != f"llm-v0.3-{self.source_id}-repeat-001":
                raise ValueError("repeat request ID does not match the v0.3 format")
            if not self.repeated_primary_request_id:
                raise ValueError("repeat invocations require a primary request identity")
        if self.planning_input_token_estimate != (
            self.provider_payload_bytes + 3
        ) // 4:
            raise ValueError("planning input-token estimate does not reconcile")
        if self.conservative_input_token_proxy != self.provider_payload_bytes:
            raise ValueError("conservative input-token proxy does not reconcile")
        if self.planning_cost_ceiling_usd > self.conservative_call_ceiling_usd:
            raise ValueError("planning cost must not exceed the conservative ceiling")
        cache_identity = CacheIdentityV03(
            experiment_id=EXPERIMENT_ID_V0_3,
            invocation_role=self.invocation_role,
            request_id=self.request_id,
            canonical_request_sha256=self.canonical_request_sha256,
            provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
            model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
            prompt_sha256=self.prompt_sha256,
            document_sha256=self.document_sha256,
        )
        if self.cache_identity_sha256 != cache_identity_sha256(cache_identity):
            raise ValueError(
                "cache_identity_sha256 does not match the serialized v0.3 invocation"
            )
        return self


def _evidence_identity(block: ApprovedEvidenceBlock) -> EvidenceBlockIdentity:
    return EvidenceBlockIdentity(
        source_id=block.source_id,
        evidence_id=block.evidence_id,
        block_id=block.block_id,
        sequence=block.sequence,
        text_sha256=uppercase_sha256_bytes(block.text.encode("utf-8")),
        location_type=block.location.location_type,
        location_value=block.location.location_value,
    )


def _request_measurements(
    request: LLMExtractionRequestAny,
) -> tuple[bytes, bytes, bytes]:
    validate_request_identity(request)
    prompt = canonical_prompt_bytes(
        evidence_blocks=request.evidence_blocks,
        model_configuration_id=request.model_configuration_id,
        prompt_version=request.prompt_version,
        output_contract_id=request.output_contract_id,
    )
    request_bytes = canonical_request_bytes(request)
    if isinstance(request, LLMExtractionRequestV03):
        payload = build_openai_responses_payload(
            request,
            configuration=DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
        )
    else:
        payload = build_openai_responses_payload(request)
    provider_payload = canonical_json_bytes(payload)
    return prompt, request_bytes, provider_payload


def _token_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    pricing: OpenAIPricingObservation,
) -> Decimal:
    million = Decimal("1000000")
    return (
        Decimal(input_tokens) * pricing.input_usd_per_million_tokens / million
        + Decimal(output_tokens) * pricing.output_usd_per_million_tokens / million
    ).normalize()


def build_hash_only_invocation_identity(
    *,
    request: LLMExtractionRequest,
    invocation_order: int,
    parsed_document_canonical_sha256: str,
    pricing_observation: OpenAIPricingObservation,
    repeated_primary_request_id: str | None = None,
) -> OpenAIDevelopmentInvocationIdentityV01:
    """Derive a reviewable identity without retaining prompt or source text."""
    prompt, request_bytes, provider_payload = _request_measurements(request)
    strict_schema_sha256 = uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_candidate_schema())
    )
    if strict_schema_sha256 != OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "production strict-schema identity differs from the fixed contract",
        )
    payload_bytes = len(provider_payload)
    planning_tokens = (payload_bytes + 3) // 4
    maximum_output_cost = _token_cost(
        input_tokens=0,
        output_tokens=MAX_OUTPUT_TOKENS,
        pricing=pricing_observation,
    )
    cache_identity = CacheIdentity.from_request(request)
    return OpenAIDevelopmentInvocationIdentityV01(
        invocation_order=invocation_order,
        source_id=request.source_id,
        invocation_role=request.invocation_role,
        request_id=request.request_id,
        repeated_primary_request_id=repeated_primary_request_id,
        block_count=len(request.evidence_blocks),
        ordered_evidence_blocks=tuple(
            _evidence_identity(block) for block in request.evidence_blocks
        ),
        total_supplied_text_bytes=sum(
            len(block.text.encode("utf-8")) for block in request.evidence_blocks
        ),
        canonical_prompt_bytes=len(prompt),
        canonical_request_bytes=len(request_bytes),
        provider_payload_bytes=payload_bytes,
        document_sha256=request.document_sha256,
        parsed_document_canonical_sha256=parsed_document_canonical_sha256,
        prompt_sha256=uppercase_sha256_bytes(prompt),
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        strict_schema_sha256=strict_schema_sha256,
        provider_payload_sha256=uppercase_sha256_bytes(provider_payload),
        cache_identity_sha256=cache_identity_sha256(cache_identity),
        planning_input_token_estimate=planning_tokens,
        conservative_input_token_proxy=payload_bytes,
        maximum_output_tokens=MAX_OUTPUT_TOKENS,
        maximum_output_cost_usd=maximum_output_cost,
        planning_cost_ceiling_usd=_token_cost(
            input_tokens=planning_tokens,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
        conservative_call_ceiling_usd=_token_cost(
            input_tokens=payload_bytes,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
    )

def build_hash_only_invocation_identity_v0_2(
    *,
    request: LLMExtractionRequestV02,
    invocation_order: int,
    parsed_document_canonical_sha256: str,
    pricing_observation: OpenAIPricingObservation,
    repeated_primary_request_id: str | None = None,
) -> OpenAIDevelopmentInvocationIdentityV02:
    """Derive one v0.2 hash-only identity without retaining source text."""
    prompt, request_bytes, provider_payload = _request_measurements(request)
    strict_schema_sha256 = uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_candidate_schema())
    )
    if strict_schema_sha256 != OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "production strict-schema identity differs from the fixed contract",
        )
    payload_bytes = len(provider_payload)
    planning_tokens = (payload_bytes + 3) // 4
    maximum_output_cost = _token_cost(
        input_tokens=0,
        output_tokens=MAX_OUTPUT_TOKENS,
        pricing=pricing_observation,
    )
    cache_identity = cache_identity_from_request(request)
    if not isinstance(cache_identity, CacheIdentityV02):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.2 request did not produce a v0.2 cache identity",
        )
    return OpenAIDevelopmentInvocationIdentityV02(
        invocation_order=invocation_order,
        source_id=request.source_id,
        invocation_role=request.invocation_role,
        request_id=request.request_id,
        repeated_primary_request_id=repeated_primary_request_id,
        block_count=len(request.evidence_blocks),
        ordered_evidence_blocks=tuple(
            _evidence_identity(block) for block in request.evidence_blocks
        ),
        total_supplied_text_bytes=sum(
            len(block.text.encode("utf-8")) for block in request.evidence_blocks
        ),
        canonical_prompt_bytes=len(prompt),
        canonical_request_bytes=len(request_bytes),
        provider_payload_bytes=payload_bytes,
        document_sha256=request.document_sha256,
        parsed_document_canonical_sha256=parsed_document_canonical_sha256,
        prompt_sha256=uppercase_sha256_bytes(prompt),
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        strict_schema_sha256=strict_schema_sha256,
        provider_payload_sha256=uppercase_sha256_bytes(provider_payload),
        cache_identity_sha256=cache_identity_sha256(cache_identity),
        planning_input_token_estimate=planning_tokens,
        conservative_input_token_proxy=payload_bytes,
        maximum_output_tokens=MAX_OUTPUT_TOKENS,
        maximum_output_cost_usd=maximum_output_cost,
        planning_cost_ceiling_usd=_token_cost(
            input_tokens=planning_tokens,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
        conservative_call_ceiling_usd=_token_cost(
            input_tokens=payload_bytes,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
    )


def build_hash_only_invocation_identity_v0_3(
    *,
    request: LLMExtractionRequestV03,
    invocation_order: int,
    parsed_document_canonical_sha256: str,
    pricing_observation: OpenAIPricingObservation,
    repeated_primary_request_id: str | None = None,
) -> OpenAIDevelopmentInvocationIdentityV03:
    """Derive one v0.3 hash-only identity without retaining source text."""
    prompt, request_bytes, provider_payload = _request_measurements(request)
    strict_schema_sha256 = uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_candidate_schema_v0_3())
    )
    if strict_schema_sha256 != OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "production alias-safe strict-schema identity differs from v0.3",
        )
    payload_bytes = len(provider_payload)
    planning_tokens = (payload_bytes + 3) // 4
    maximum_output_cost = _token_cost(
        input_tokens=0,
        output_tokens=MAX_OUTPUT_TOKENS,
        pricing=pricing_observation,
    )
    cache_identity = cache_identity_from_request(request)
    if not isinstance(cache_identity, CacheIdentityV03):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.3 request did not produce a v0.3 cache identity",
        )
    return OpenAIDevelopmentInvocationIdentityV03(
        invocation_order=invocation_order,
        source_id=request.source_id,
        invocation_role=request.invocation_role,
        request_id=request.request_id,
        repeated_primary_request_id=repeated_primary_request_id,
        block_count=len(request.evidence_blocks),
        ordered_evidence_blocks=tuple(
            _evidence_identity(block) for block in request.evidence_blocks
        ),
        total_supplied_text_bytes=sum(
            len(block.text.encode("utf-8")) for block in request.evidence_blocks
        ),
        canonical_prompt_bytes=len(prompt),
        canonical_request_bytes=len(request_bytes),
        provider_payload_bytes=payload_bytes,
        document_sha256=request.document_sha256,
        parsed_document_canonical_sha256=parsed_document_canonical_sha256,
        prompt_sha256=uppercase_sha256_bytes(prompt),
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        strict_schema_sha256=strict_schema_sha256,
        provider_payload_sha256=uppercase_sha256_bytes(provider_payload),
        cache_identity_sha256=cache_identity_sha256(cache_identity),
        planning_input_token_estimate=planning_tokens,
        conservative_input_token_proxy=payload_bytes,
        maximum_output_tokens=MAX_OUTPUT_TOKENS,
        maximum_output_cost_usd=maximum_output_cost,
        planning_cost_ceiling_usd=_token_cost(
            input_tokens=planning_tokens,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
        conservative_call_ceiling_usd=_token_cost(
            input_tokens=payload_bytes,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing_observation,
        ),
    )


def _approved_blocks(document: ParsedDocument) -> tuple[ApprovedEvidenceBlock, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    blocks = tuple(
        ApprovedEvidenceBlock(
            source_id=document.source_id,
            evidence_id=(
                f"llm-evidence-v0.1-{document.source_id}-{block.block_id}"
            ),
            block_id=block.block_id,
            sequence=block.sequence,
            text=block.text,
            location=block.location,
        )
        for block in document.blocks
        if block.text.strip()
    )
    if not blocks:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "an approved ParsedDocument requires nonblank text blocks",
        )
    return blocks


def _request(
    *,
    source_id: str,
    document_sha256: str,
    role: InvocationRole,
    ordinal: int,
    blocks: Sequence[ApprovedEvidenceBlock],
) -> LLMExtractionRequest:
    return build_request_envelope(
        invocation_role=role,
        request_id=f"llm-v0.1-{source_id}-{role.value}-{ordinal:03d}",
        source_id=source_id,
        document_sha256=document_sha256,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=blocks,
    )


def _partition_primary_requests(
    *,
    document: ParsedDocument,
    policy: OpenAIDevelopmentPartitionPolicyV01,
) -> tuple[LLMExtractionRequest, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    blocks = _approved_blocks(document)
    partitions: list[tuple[ApprovedEvidenceBlock, ...]] = []
    current: tuple[ApprovedEvidenceBlock, ...] = ()
    for block in blocks:
        trial = (*current, block)
        ordinal = len(partitions) + 1
        trial_request = _request(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=ordinal,
            blocks=trial,
        )
        _, _, payload = _request_measurements(trial_request)
        if len(payload) <= policy.maximum_provider_payload_bytes:
            current = trial
            continue
        if not current:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
        partitions.append(current)
        current = (block,)
        single_request = _request(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=len(partitions) + 1,
            blocks=current,
        )
        _, _, single_payload = _request_measurements(single_request)
        if len(single_payload) > policy.maximum_provider_payload_bytes:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
    if current:
        partitions.append(current)
    return tuple(
        _request(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=index,
            blocks=partition,
        )
        for index, partition in enumerate(partitions, start=1)
    )


def _repeat_request(primary_requests: Sequence[LLMExtractionRequest]) -> tuple[
    LLMExtractionRequest, str
]:
    measured = [
        (len(_request_measurements(request)[2]), request.request_id, request)
        for request in primary_requests
    ]
    _, primary_request_id, selected = min(
        measured, key=lambda item: (-item[0], item[1])
    )
    repeated = _request(
        source_id=selected.source_id,
        document_sha256=selected.document_sha256,
        role=InvocationRole.REPEAT,
        ordinal=1,
        blocks=selected.evidence_blocks,
    )
    return repeated, primary_request_id


def _approved_blocks_v0_2(
    document: ParsedDocument,
) -> tuple[ApprovedEvidenceBlock, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    validate_development_source_id(document.source_id)
    blocks = tuple(
        ApprovedEvidenceBlock(
            source_id=document.source_id,
            evidence_id=(
                f"llm-evidence-v0.2-{document.source_id}-{block.block_id}"
            ),
            block_id=block.block_id,
            sequence=block.sequence,
            text=block.text,
            location=block.location,
        )
        for block in document.blocks
        if block.text.strip()
    )
    if not blocks:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "an approved ParsedDocument requires nonblank text blocks",
        )
    return blocks


def _request_v0_2(
    *,
    source_id: str,
    document_sha256: str,
    role: InvocationRole,
    ordinal: int,
    blocks: Sequence[ApprovedEvidenceBlock],
) -> LLMExtractionRequestV02:
    return build_request_envelope_v0_2(
        invocation_role=role,
        request_id=f"llm-v0.2-{source_id}-{role.value}-{ordinal:03d}",
        source_id=source_id,
        document_sha256=document_sha256,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=blocks,
    )


def _partition_primary_requests_v0_2(
    *,
    document: ParsedDocument,
    policy: OpenAIDevelopmentPartitionPolicyV02,
) -> tuple[LLMExtractionRequestV02, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    blocks = _approved_blocks_v0_2(document)
    partitions: list[tuple[ApprovedEvidenceBlock, ...]] = []
    current: tuple[ApprovedEvidenceBlock, ...] = ()
    for block in blocks:
        trial = (*current, block)
        ordinal = len(partitions) + 1
        trial_request = _request_v0_2(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=ordinal,
            blocks=trial,
        )
        _, _, payload = _request_measurements(trial_request)
        if len(payload) <= policy.maximum_provider_payload_bytes:
            current = trial
            continue
        if not current:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
        partitions.append(current)
        current = (block,)
        single_request = _request_v0_2(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=len(partitions) + 1,
            blocks=current,
        )
        _, _, single_payload = _request_measurements(single_request)
        if len(single_payload) > policy.maximum_provider_payload_bytes:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
    if current:
        partitions.append(current)
    return tuple(
        _request_v0_2(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=index,
            blocks=partition,
        )
        for index, partition in enumerate(partitions, start=1)
    )


def _repeat_request_v0_2(
    primary_requests: Sequence[LLMExtractionRequestV02],
) -> tuple[LLMExtractionRequestV02, str]:
    measured = [
        (len(_request_measurements(request)[2]), request.request_id, request)
        for request in primary_requests
    ]
    _, primary_request_id, selected = min(
        measured, key=lambda item: (-item[0], item[1])
    )
    repeated = _request_v0_2(
        source_id=selected.source_id,
        document_sha256=selected.document_sha256,
        role=InvocationRole.REPEAT,
        ordinal=1,
        blocks=selected.evidence_blocks,
    )
    return repeated, primary_request_id


def _approved_blocks_v0_3(
    document: ParsedDocument,
) -> tuple[ApprovedEvidenceBlock, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    validate_development_source_id(document.source_id)
    blocks = tuple(
        ApprovedEvidenceBlock(
            source_id=document.source_id,
            evidence_id=(
                f"llm-evidence-v0.3-{document.source_id}-{block.block_id}"
            ),
            block_id=block.block_id,
            sequence=block.sequence,
            text=block.text,
            location=block.location,
        )
        for block in document.blocks
        if block.text.strip()
    )
    if not blocks:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "an approved ParsedDocument requires nonblank text blocks",
        )
    return blocks


def _request_v0_3(
    *,
    source_id: str,
    document_sha256: str,
    role: InvocationRole,
    ordinal: int,
    blocks: Sequence[ApprovedEvidenceBlock],
) -> LLMExtractionRequestV03:
    return build_request_envelope_v0_3(
        invocation_role=role,
        request_id=f"llm-v0.3-{source_id}-{role.value}-{ordinal:03d}",
        source_id=source_id,
        document_sha256=document_sha256,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        evidence_blocks=blocks,
    )


def _partition_primary_requests_v0_3(
    *,
    document: ParsedDocument,
    policy: OpenAIDevelopmentPartitionPolicyV03,
) -> tuple[LLMExtractionRequestV03, ...]:
    if document.source_id is None:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "ParsedDocument source identity is required",
        )
    blocks = _approved_blocks_v0_3(document)
    partitions: list[tuple[ApprovedEvidenceBlock, ...]] = []
    current: tuple[ApprovedEvidenceBlock, ...] = ()
    for block in blocks:
        trial = (*current, block)
        ordinal = len(partitions) + 1
        trial_request = _request_v0_3(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=ordinal,
            blocks=trial,
        )
        _, _, payload = _request_measurements(trial_request)
        if len(payload) <= policy.maximum_provider_payload_bytes:
            current = trial
            continue
        if not current:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
        partitions.append(current)
        current = (block,)
        single_request = _request_v0_3(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=len(partitions) + 1,
            blocks=current,
        )
        _, _, single_payload = _request_measurements(single_request)
        if len(single_payload) > policy.maximum_provider_payload_bytes:
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "one complete evidence block exceeds the payload partition limit",
            )
    if current:
        partitions.append(current)
    return tuple(
        _request_v0_3(
            source_id=document.source_id,
            document_sha256=document.checksum_sha256,
            role=InvocationRole.PRIMARY,
            ordinal=index,
            blocks=partition,
        )
        for index, partition in enumerate(partitions, start=1)
    )


def _repeat_request_v0_3(
    primary_requests: Sequence[LLMExtractionRequestV03],
) -> tuple[LLMExtractionRequestV03, str]:
    measured = [
        (len(_request_measurements(request)[2]), request.request_id, request)
        for request in primary_requests
    ]
    _, primary_request_id, selected = min(
        measured, key=lambda item: (-item[0], item[1])
    )
    repeated = _request_v0_3(
        source_id=selected.source_id,
        document_sha256=selected.document_sha256,
        role=InvocationRole.REPEAT,
        ordinal=1,
        blocks=selected.evidence_blocks,
    )
    return repeated, primary_request_id


class ReviewedObservationBindingV01(BaseModel):
    """Review identity bound to one already-dated provider observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_kind: Literal["pricing", "data_controls"]
    evidence_id: str
    reviewed_by: str
    reviewed_at_utc: datetime
    observation_sha256: str = Field(pattern=SHA256_PATTERN)
    review_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("evidence_id", "reviewed_by")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _require_trimmed(value, info.field_name)

    @field_validator("reviewed_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "reviewed_at_utc")

    @field_serializer("reviewed_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @model_validator(mode="after")
    def validate_hash(self) -> ReviewedObservationBindingV01:
        if self.review_sha256 != _canonical_model_hash(self, "review_sha256"):
            raise ValueError("review_sha256 does not match the canonical review")
        return self


def build_reviewed_observation_binding(
    *,
    observation_kind: Literal["pricing", "data_controls"],
    evidence_id: str,
    reviewed_by: str,
    reviewed_at_utc: datetime,
    observation: BaseModel,
) -> ReviewedObservationBindingV01:
    values = {
        "observation_kind": observation_kind,
        "evidence_id": evidence_id,
        "reviewed_by": reviewed_by,
        "reviewed_at_utc": reviewed_at_utc,
        "observation_sha256": _canonical_observation_hash(observation),
    }
    provisional = ReviewedObservationBindingV01.model_construct(
        **values,
        review_sha256="0" * 64,
    )
    return ReviewedObservationBindingV01.model_validate(
        {
            **values,
            "review_sha256": _canonical_model_hash(
                provisional,
                "review_sha256",
            ),
        }
    )


class OpenAIDevelopmentExecutionBudgetV01(BaseModel):
    """Narrow retry-zero token and cost plan derived from the manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_request_count: int = Field(gt=0)
    repeat_request_count: Literal[1]
    maximum_provider_calls: int = Field(gt=0)
    maximum_retries_per_invocation: Literal[0]
    maximum_total_attempts: int = Field(gt=0)
    provider_side_retries: Literal[0]
    response_timeout_seconds: Literal[120]
    planning_input_token_budget: int = Field(gt=0)
    conservative_input_token_budget: int = Field(gt=0)
    maximum_output_token_budget: int = Field(gt=0)
    aggregate_maximum_output_cost_usd: Decimal = Field(gt=0)
    aggregate_planning_cost_usd: Decimal = Field(gt=0)
    aggregate_conservative_cost_ceiling_usd: Decimal = Field(gt=0)
    planned_authorization_cap_usd: Decimal = Field(gt=0)
    broad_project_cost_ceiling_usd: Decimal = Field(gt=0)
    same_day_pricing_review_required: Literal[True]

    @field_validator(
        "primary_request_count",
        "repeat_request_count",
        "maximum_provider_calls",
        "maximum_retries_per_invocation",
        "maximum_total_attempts",
        "provider_side_retries",
        "response_timeout_seconds",
        "planning_input_token_budget",
        "conservative_input_token_budget",
        "maximum_output_token_budget",
        mode="before",
    )
    @classmethod
    def require_integers(cls, value: object, info: Any) -> object:
        if type(value) is not int:
            raise ValueError(f"{info.field_name} must use an integer")
        return value

    @field_validator(
        "aggregate_maximum_output_cost_usd",
        "aggregate_planning_cost_usd",
        "aggregate_conservative_cost_ceiling_usd",
        "planned_authorization_cap_usd",
        "broad_project_cost_ceiling_usd",
    )
    @classmethod
    def normalize_decimal(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_serializer(
        "aggregate_maximum_output_cost_usd",
        "aggregate_planning_cost_usd",
        "aggregate_conservative_cost_ceiling_usd",
        "planned_authorization_cap_usd",
        "broad_project_cost_ceiling_usd",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_fixed_caps(self) -> OpenAIDevelopmentExecutionBudgetV01:
        if self.planned_authorization_cap_usd != PLANNED_AUTHORIZATION_CAP_USD:
            raise ValueError("planned authorization cap must be exactly USD 1.25")
        if self.broad_project_cost_ceiling_usd != BROAD_PROJECT_COST_CEILING_USD:
            raise ValueError("broad project cost ceiling must remain USD 25")
        if not (
            self.aggregate_conservative_cost_ceiling_usd
            <= self.planned_authorization_cap_usd
            < self.broad_project_cost_ceiling_usd
        ):
            raise ValueError("planned cap does not safely bound the manifest cost")
        return self


def _cost_budget(
    *,
    invocations: Sequence[OpenAIDevelopmentInvocationIdentityV01],
    pricing: OpenAIPricingObservation,
) -> OpenAIDevelopmentExecutionBudgetV01:
    primary_count = sum(
        item.invocation_role is InvocationRole.PRIMARY for item in invocations
    )
    repeat_count = len(invocations) - primary_count
    for item in invocations:
        expected_planning_tokens = (item.provider_payload_bytes + 3) // 4
        expected_maximum_output_cost = _token_cost(
            input_tokens=0,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing,
        )
        expected_planning_cost = _token_cost(
            input_tokens=expected_planning_tokens,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing,
        )
        expected_conservative_cost = _token_cost(
            input_tokens=item.provider_payload_bytes,
            output_tokens=MAX_OUTPUT_TOKENS,
            pricing=pricing,
        )
        if (
            item.planning_input_token_estimate != expected_planning_tokens
            or item.conservative_input_token_proxy != item.provider_payload_bytes
            or item.maximum_output_cost_usd != expected_maximum_output_cost
            or item.planning_cost_ceiling_usd != expected_planning_cost
            or item.conservative_call_ceiling_usd != expected_conservative_cost
        ):
            raise ValueError("invocation cost plan does not reconcile with pricing")
    aggregate_planning_cost = sum(
        (item.planning_cost_ceiling_usd for item in invocations),
        Decimal("0"),
    ).normalize()
    aggregate_conservative_cost = sum(
        (item.conservative_call_ceiling_usd for item in invocations),
        Decimal("0"),
    ).normalize()
    if aggregate_conservative_cost > PLANNED_AUTHORIZATION_CAP_USD:
        raise Stage4BError(
            Stage4BErrorCode.COST_BUDGET_EXCEEDED,
            "conservative manifest cost exceeds the planned USD 1.25 cap",
        )
    return OpenAIDevelopmentExecutionBudgetV01(
        primary_request_count=primary_count,
        repeat_request_count=repeat_count,
        maximum_provider_calls=len(invocations),
        maximum_retries_per_invocation=0,
        maximum_total_attempts=len(invocations),
        provider_side_retries=0,
        response_timeout_seconds=120,
        planning_input_token_budget=sum(
            item.planning_input_token_estimate for item in invocations
        ),
        conservative_input_token_budget=sum(
            item.conservative_input_token_proxy for item in invocations
        ),
        maximum_output_token_budget=len(invocations) * MAX_OUTPUT_TOKENS,
        aggregate_maximum_output_cost_usd=sum(
            (item.maximum_output_cost_usd for item in invocations),
            Decimal("0"),
        ).normalize(),
        aggregate_planning_cost_usd=aggregate_planning_cost,
        aggregate_conservative_cost_ceiling_usd=aggregate_conservative_cost,
        planned_authorization_cap_usd=PLANNED_AUTHORIZATION_CAP_USD,
        broad_project_cost_ceiling_usd=BROAD_PROJECT_COST_CEILING_USD,
        same_day_pricing_review_required=True,
    )


def _validate_budget_reconciliation(
    *,
    invocations: Sequence[OpenAIDevelopmentInvocationIdentityV01],
    budget: OpenAIDevelopmentExecutionBudgetV01,
    pricing: OpenAIPricingObservation,
) -> None:
    expected = _cost_budget(invocations=invocations, pricing=pricing)
    if budget != expected:
        raise ValueError("execution budget does not reconcile with invocations")


def _validate_common_inventory(
    *,
    source_routes: Sequence[OpenAIDevelopmentSourceRouteV01],
    partition_policy: OpenAIDevelopmentPartitionPolicyV01,
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV01,
    invocations: Sequence[OpenAIDevelopmentInvocationIdentityV01],
    identity_version: Literal["0.1", "0.2", "0.3"] = "0.1",
) -> None:
    if tuple(route.source_id for route in source_routes) != APPROVED_SOURCE_ORDER:
        raise ValueError("source routes must use the exact approved source order")

    orders = [item.invocation_order for item in invocations]
    if orders != list(range(1, len(invocations) + 1)):
        raise ValueError("invocation order must be exactly 1..N")
    request_ids = [item.request_id for item in invocations]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("manifest request IDs must be globally unique")

    routes_by_source = {route.source_id: route for route in source_routes}
    for invocation in invocations:
        route = routes_by_source.get(invocation.source_id)
        if route is None:
            raise ValueError("invocation source does not have an approved route")
        if invocation.document_sha256 != route.document_sha256:
            raise ValueError("invocation document_sha256 does not match its route")
        if (
            invocation.parsed_document_canonical_sha256
            != route.parsed_document_canonical_sha256
        ):
            raise ValueError(
                "invocation parsed_document_canonical_sha256 does not match its route"
            )
        if (
            invocation.provider_payload_bytes
            > partition_policy.maximum_provider_payload_bytes
        ):
            raise ValueError("invocation exceeds the payload partition limit")

    primary = [
        item
        for item in invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    repeat = [
        item
        for item in invocations
        if item.invocation_role is InvocationRole.REPEAT
    ]
    if {item.source_id for item in primary} != set(APPROVED_SOURCE_ORDER):
        raise ValueError("primary requests must cover every approved source")
    source_rank = {
        source_id: index for index, source_id in enumerate(APPROVED_SOURCE_ORDER)
    }
    expected_primary_order = sorted(
        primary,
        key=lambda item: (
            source_rank[item.source_id],
            int(item.request_id.rsplit("-", 1)[-1]),
        ),
    )
    if primary != expected_primary_order:
        raise ValueError("primary invocation order does not reconcile")

    for source_id in APPROVED_SOURCE_ORDER:
        source_primaries = [
            item for item in primary if item.source_id == source_id
        ]
        expected_request_ids = [
            f"llm-v{identity_version}-{source_id}-primary-{ordinal:03d}"
            for ordinal in range(1, len(source_primaries) + 1)
        ]
        if [item.request_id for item in source_primaries] != expected_request_ids:
            raise ValueError(
                "primary partition ordinals must be exactly 001..N for each source"
            )
        identities = [
            identity
            for invocation in source_primaries
            for identity in invocation.ordered_evidence_blocks
        ]
        block_ids = [identity.block_id for identity in identities]
        evidence_ids = [identity.evidence_id for identity in identities]
        sequences = [identity.sequence for identity in identities]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError(
                "primary partition block IDs must be unique across each source"
            )
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "primary partition evidence IDs must be unique across each source"
            )
        if any(
            current >= following
            for current, following in zip(sequences, sequences[1:])
        ):
            raise ValueError(
                "primary partition sequences must be strictly increasing and unique"
            )

    if len(repeat) != 1 or repeat_selection_policy.repeat_request_count != 1:
        raise ValueError("the development inventory requires exactly one repeat")
    if not invocations or invocations[-1].invocation_role is not InvocationRole.REPEAT:
        raise ValueError("the repeat invocation must appear last")
    primary_by_id = {item.request_id: item for item in primary}
    repeated = primary_by_id.get(repeat[0].repeated_primary_request_id or "")
    if repeated is None:
        raise ValueError("repeat request must reference a manifest primary request")
    expected_repeated = min(
        primary,
        key=lambda item: (-item.provider_payload_bytes, item.request_id),
    )
    if repeated.request_id != expected_repeated.request_id:
        raise ValueError("repeat request must select the largest deterministic primary")
    for field_name in (
        "source_id",
        "block_count",
        "ordered_evidence_blocks",
        "total_supplied_text_bytes",
        "canonical_prompt_bytes",
        "provider_payload_bytes",
        "document_sha256",
        "parsed_document_canonical_sha256",
        "prompt_sha256",
        "strict_schema_sha256",
        "provider_payload_sha256",
        "planning_input_token_estimate",
        "conservative_input_token_proxy",
        "maximum_output_tokens",
        "maximum_output_cost_usd",
        "planning_cost_ceiling_usd",
        "conservative_call_ceiling_usd",
    ):
        if getattr(repeat[0], field_name) != getattr(repeated, field_name):
            raise ValueError(f"repeat {field_name} must match its primary")
    if repeat[0].canonical_request_sha256 == repeated.canonical_request_sha256:
        raise ValueError("repeat and primary canonical requests must be distinct")
    if repeat[0].cache_identity_sha256 == repeated.cache_identity_sha256:
        raise ValueError("repeat and primary cache identities must be distinct")


class OpenAIDevelopmentManifestV01(BaseModel):
    """Final hash-only manifest eligible only for independent review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_schema_version: Literal["0.1"] = DEVELOPMENT_MANIFEST_SCHEMA_VERSION
    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    provider_identifier: Literal["openai"] = "openai"
    requested_model_alias: Literal["gpt-5.4-mini"] = "gpt-5.4-mini"
    returned_preflight_model_identifier: Literal[
        "gpt-5.4-mini-2026-03-17"
    ] = OPENAI_RETURNED_PREFLIGHT_MODEL
    model_version_or_snapshot_provenance: Literal["unavailable"] = "unavailable"
    provider_sdk_version: Literal["2.46.0"] = "2.46.0"
    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.1"
    ] = OPENAI_PROVIDER_CONFIGURATION_ID
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.1"
    ] = OPENAI_MODEL_CONFIGURATION_ID
    strict_schema_sha256: Literal[
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    ] = OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256
    preflight_evidence: OpenAIDevelopmentPreflightBindingV01
    provider_controls: OpenAIDevelopmentProviderControlsV01
    source_routes: tuple[OpenAIDevelopmentSourceRouteV01, ...] = Field(min_length=5)
    partition_policy: OpenAIDevelopmentPartitionPolicyV01
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV01
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV01, ...] = Field(
        min_length=6
    )
    execution_budget: OpenAIDevelopmentExecutionBudgetV01
    pricing_observation: OpenAIPricingObservation
    pricing_review: ReviewedObservationBindingV01
    data_controls_observation: OpenAIDataControlsObservation
    data_controls_review: ReviewedObservationBindingV01
    context_limit_observation: ReviewedContextLimitObservationV01
    cache_policy: OpenAIDevelopmentCachePolicyV01
    access_policy: OpenAIDevelopmentAccessPolicyV01
    manifest_review_status: Literal["pending_independent_review"] = (
        "pending_independent_review"
    )
    execution_authorization_required: Literal[True] = True
    execution_authorization_status: Literal["not_provided"] = "not_provided"
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_manifest(self) -> OpenAIDevelopmentManifestV01:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
        )
        required_tokens = [
            item.provider_payload_bytes + MAX_OUTPUT_TOKENS
            for item in self.invocations
        ]
        if max(required_tokens) > (
            self.context_limit_observation.exact_context_window_tokens
        ):
            raise ValueError("an invocation exceeds the reviewed context boundary")
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.manifest_sha256 != _canonical_model_hash(self, "manifest_sha256"):
            raise ValueError("manifest_sha256 does not match the canonical manifest")
        return self


class OpenAIDevelopmentManifestV02(OpenAIDevelopmentManifestV01):
    """Additive final manifest for the prompt/request/cache v0.2 family."""

    experiment_id: Literal["llm-extraction-baseline-v0.2"] = EXPERIMENT_ID_V0_2
    partition_policy: OpenAIDevelopmentPartitionPolicyV02
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV02, ...] = Field(
        min_length=6
    )
    cache_policy: OpenAIDevelopmentCachePolicyV02

    @model_validator(mode="after")
    def validate_manifest(self) -> OpenAIDevelopmentManifestV02:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
            identity_version="0.2",
        )
        required_tokens = [
            item.provider_payload_bytes + MAX_OUTPUT_TOKENS
            for item in self.invocations
        ]
        if max(required_tokens) > (
            self.context_limit_observation.exact_context_window_tokens
        ):
            raise ValueError("an invocation exceeds the reviewed context boundary")
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.manifest_sha256 != _canonical_model_hash(self, "manifest_sha256"):
            raise ValueError("manifest_sha256 does not match the canonical manifest")
        return self


class OpenAIDevelopmentManifestV03(OpenAIDevelopmentManifestV01):
    """Additive final manifest for alias-safe development request v0.3."""

    experiment_id: Literal["llm-extraction-baseline-v0.3"] = EXPERIMENT_ID_V0_3
    prompt_version: Literal["0.3"] = "0.3"
    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.2"
    ] = OPENAI_PROVIDER_CONFIGURATION_ID_V0_3
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    ] = OPENAI_MODEL_CONFIGURATION_ID_V0_3
    response_schema_name: Literal[
        "candidate_extraction_result_0_1_aliases_empty_v0_3"
    ] = OPENAI_RESPONSE_SCHEMA_NAME_V0_3
    strict_schema_sha256: Literal[
        "C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E"
    ] = OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3
    preflight_evidence: OpenAIDevelopmentPreflightBindingV03
    partition_policy: OpenAIDevelopmentPartitionPolicyV03
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV03
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV03, ...] = Field(
        min_length=6
    )
    cache_policy: OpenAIDevelopmentCachePolicyV03

    @model_validator(mode="after")
    def validate_manifest(self) -> OpenAIDevelopmentManifestV03:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
            identity_version="0.3",
        )
        required_tokens = [
            item.provider_payload_bytes + MAX_OUTPUT_TOKENS
            for item in self.invocations
        ]
        if max(required_tokens) > (
            self.context_limit_observation.exact_context_window_tokens
        ):
            raise ValueError("an invocation exceeds the reviewed context boundary")
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.manifest_sha256 != _canonical_model_hash(self, "manifest_sha256"):
            raise ValueError("manifest_sha256 does not match the canonical manifest")
        return self


_PREPARATION_MANIFEST_SHARED_FIELDS = (
    "source_routes",
    "partition_policy",
    "repeat_selection_policy",
    "invocations",
    "preflight_evidence",
    "provider_controls",
    "execution_budget",
    "pricing_observation",
    "pricing_review",
    "data_controls_observation",
    "data_controls_review",
    "context_limit_observation",
    "cache_policy",
    "access_policy",
)


def _validate_nested_manifest_reconciliation(
    *,
    preparation: BaseModel,
    manifest: OpenAIDevelopmentManifestV01,
) -> None:
    for field_name in _PREPARATION_MANIFEST_SHARED_FIELDS:
        if getattr(preparation, field_name) != getattr(manifest, field_name):
            raise ValueError(
                f"nested manifest {field_name} does not reconcile with preparation"
            )


class OpenAIDevelopmentManifestPreparationV01(BaseModel):
    """Structurally valid no-call preparation, possibly blocked on context review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preparation_schema_version: Literal[
        "0.1"
    ] = DEVELOPMENT_PREPARATION_SCHEMA_VERSION
    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    source_routes: tuple[OpenAIDevelopmentSourceRouteV01, ...]
    partition_policy: OpenAIDevelopmentPartitionPolicyV01
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV01
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV01, ...]
    preflight_evidence: OpenAIDevelopmentPreflightBindingV01
    provider_controls: OpenAIDevelopmentProviderControlsV01
    execution_budget: OpenAIDevelopmentExecutionBudgetV01
    pricing_observation: OpenAIPricingObservation
    pricing_review: ReviewedObservationBindingV01
    data_controls_observation: OpenAIDataControlsObservation
    data_controls_review: ReviewedObservationBindingV01
    cache_policy: OpenAIDevelopmentCachePolicyV01
    access_policy: OpenAIDevelopmentAccessPolicyV01
    context_limit_observation: ReviewedContextLimitObservationV01 | None
    readiness_status: Literal["blocked", "eligible_for_independent_review"]
    blocking_reasons: tuple[str, ...]
    manifest: OpenAIDevelopmentManifestV01 | None
    preparation_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_preparation(self) -> OpenAIDevelopmentManifestPreparationV01:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
        )
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.context_limit_observation is None:
            if (
                self.readiness_status != "blocked"
                or self.blocking_reasons
                != ("reviewed_context_limit_observation_missing",)
                or self.manifest is not None
            ):
                raise ValueError("missing context evidence must block final readiness")
        else:
            if (
                self.readiness_status != "eligible_for_independent_review"
                or self.blocking_reasons
                or self.manifest is None
            ):
                raise ValueError(
                    "complete context evidence must produce a review manifest"
                )
            _validate_nested_manifest_reconciliation(
                preparation=self,
                manifest=self.manifest,
            )
        if self.preparation_sha256 != _canonical_model_hash(
            self, "preparation_sha256"
        ):
            raise ValueError(
                "preparation_sha256 does not match the canonical preparation"
            )
        return self


class OpenAIDevelopmentManifestPreparationV02(
    OpenAIDevelopmentManifestPreparationV01
):
    """Additive no-call preparation for a possible v0.2 review manifest."""

    experiment_id: Literal["llm-extraction-baseline-v0.2"] = EXPERIMENT_ID_V0_2
    partition_policy: OpenAIDevelopmentPartitionPolicyV02
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV02, ...]
    cache_policy: OpenAIDevelopmentCachePolicyV02
    manifest: OpenAIDevelopmentManifestV02 | None

    @model_validator(mode="after")
    def validate_preparation(self) -> OpenAIDevelopmentManifestPreparationV02:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
            identity_version="0.2",
        )
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.context_limit_observation is None:
            if (
                self.readiness_status != "blocked"
                or self.blocking_reasons
                != ("reviewed_context_limit_observation_missing",)
                or self.manifest is not None
            ):
                raise ValueError("missing context evidence must block final readiness")
        else:
            if (
                self.readiness_status != "eligible_for_independent_review"
                or self.blocking_reasons
                or self.manifest is None
            ):
                raise ValueError(
                    "complete context evidence must produce a review manifest"
                )
            _validate_nested_manifest_reconciliation(
                preparation=self,
                manifest=self.manifest,
            )
        if self.preparation_sha256 != _canonical_model_hash(
            self, "preparation_sha256"
        ):
            raise ValueError(
                "preparation_sha256 does not match the canonical preparation"
            )
        return self


class OpenAIDevelopmentManifestPreparationV03(
    OpenAIDevelopmentManifestPreparationV01
):
    """Additive no-call preparation for alias-safe development v0.3."""

    experiment_id: Literal["llm-extraction-baseline-v0.3"] = EXPERIMENT_ID_V0_3
    prompt_version: Literal["0.3"] = "0.3"
    partition_policy: OpenAIDevelopmentPartitionPolicyV03
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV03
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV03, ...]
    preflight_evidence: OpenAIDevelopmentPreflightBindingV03
    cache_policy: OpenAIDevelopmentCachePolicyV03
    manifest: OpenAIDevelopmentManifestV03 | None

    @model_validator(mode="after")
    def validate_preparation(self) -> OpenAIDevelopmentManifestPreparationV03:
        _validate_common_inventory(
            source_routes=self.source_routes,
            partition_policy=self.partition_policy,
            repeat_selection_policy=self.repeat_selection_policy,
            invocations=self.invocations,
            identity_version="0.3",
        )
        _validate_budget_reconciliation(
            invocations=self.invocations,
            budget=self.execution_budget,
            pricing=self.pricing_observation,
        )
        if (
            self.pricing_review.observation_kind != "pricing"
            or self.pricing_review.observation_sha256
            != _canonical_observation_hash(self.pricing_observation)
        ):
            raise ValueError("pricing review does not reconcile")
        if (
            self.data_controls_review.observation_kind != "data_controls"
            or self.data_controls_review.observation_sha256
            != _canonical_observation_hash(self.data_controls_observation)
        ):
            raise ValueError("data-control review does not reconcile")
        if self.context_limit_observation is None:
            if (
                self.readiness_status != "blocked"
                or self.blocking_reasons
                != ("reviewed_context_limit_observation_missing",)
                or self.manifest is not None
            ):
                raise ValueError("missing context evidence must block final readiness")
        else:
            if (
                self.readiness_status != "eligible_for_independent_review"
                or self.blocking_reasons
                or self.manifest is None
            ):
                raise ValueError(
                    "complete context evidence must produce a review manifest"
                )
            _validate_nested_manifest_reconciliation(
                preparation=self,
                manifest=self.manifest,
            )
        if self.preparation_sha256 != _canonical_model_hash(
            self, "preparation_sha256"
        ):
            raise ValueError(
                "preparation_sha256 does not match the canonical preparation"
            )
        return self


def _build_final_manifest(
    *,
    source_routes: tuple[OpenAIDevelopmentSourceRouteV01, ...],
    partition_policy: OpenAIDevelopmentPartitionPolicyV01,
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV01,
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV01, ...],
    execution_budget: OpenAIDevelopmentExecutionBudgetV01,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01,
) -> OpenAIDevelopmentManifestV01:
    values = {
        "manifest_schema_version": DEVELOPMENT_MANIFEST_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "provider_identifier": "openai",
        "requested_model_alias": "gpt-5.4-mini",
        "returned_preflight_model_identifier": OPENAI_RETURNED_PREFLIGHT_MODEL,
        "model_version_or_snapshot_provenance": "unavailable",
        "provider_sdk_version": "2.46.0",
        "provider_configuration_id": OPENAI_PROVIDER_CONFIGURATION_ID,
        "model_configuration_id": OPENAI_MODEL_CONFIGURATION_ID,
        "strict_schema_sha256": OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV01(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "source_routes": source_routes,
        "partition_policy": partition_policy,
        "repeat_selection_policy": repeat_selection_policy,
        "invocations": invocations,
        "execution_budget": execution_budget,
        "pricing_observation": pricing_observation,
        "pricing_review": pricing_review,
        "data_controls_observation": data_controls_observation,
        "data_controls_review": data_controls_review,
        "context_limit_observation": context_limit_observation,
        "cache_policy": OpenAIDevelopmentCachePolicyV01(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "manifest_review_status": "pending_independent_review",
        "execution_authorization_required": True,
        "execution_authorization_status": "not_provided",
    }
    provisional = OpenAIDevelopmentManifestV01.model_construct(
        **values, manifest_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestV01.model_validate(
        {
            **values,
            "manifest_sha256": _canonical_model_hash(
                provisional, "manifest_sha256"
            ),
        }
    )


def prepare_openai_development_manifest(
    *,
    source_routes: Sequence[OpenAIDevelopmentSourceRouteV01],
    parsed_documents: Mapping[str, ParsedDocument],
    partition_policy: OpenAIDevelopmentPartitionPolicyV01,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01 | None = None,
) -> OpenAIDevelopmentManifestPreparationV01:
    """Prepare a no-call hash inventory and block final readiness without context."""
    routes = tuple(
        OpenAIDevelopmentSourceRouteV01.model_validate(
            route.model_dump(mode="python")
        )
        for route in source_routes
    )
    try:
        validated_partition_policy = OpenAIDevelopmentPartitionPolicyV01.model_validate(
            partition_policy.model_dump(mode="python")
        )
        validated_pricing = OpenAIPricingObservation.model_validate(
            pricing_observation.model_dump(mode="python")
        )
        validated_pricing_review = ReviewedObservationBindingV01.model_validate(
            pricing_review.model_dump(mode="python")
        )
        validated_controls = OpenAIDataControlsObservation.model_validate(
            data_controls_observation.model_dump(mode="python")
        )
        validated_controls_review = ReviewedObservationBindingV01.model_validate(
            data_controls_review.model_dump(mode="python")
        )
        validated_context = (
            None
            if context_limit_observation is None
            else ReviewedContextLimitObservationV01.model_validate(
                context_limit_observation.model_dump(mode="python")
            )
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "reviewed manifest inputs do not satisfy their immutable contracts",
        ) from error
    if tuple(route.source_id for route in routes) != APPROVED_SOURCE_ORDER:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "source routes must use the exact approved source order",
        )
    if set(parsed_documents) != set(APPROVED_SOURCE_ORDER):
        raise Stage4BError(
            Stage4BErrorCode.PROHIBITED_SOURCE,
            "preparation requires exactly the approved development sources",
        )

    if (
        validated_pricing_review.observation_kind != "pricing"
        or validated_pricing_review.observation_sha256
        != _canonical_observation_hash(validated_pricing)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "pricing review does not bind the supplied observation",
        )
    if (
        validated_controls_review.observation_kind != "data_controls"
        or validated_controls_review.observation_sha256
        != _canonical_observation_hash(validated_controls)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "data-control review does not bind the supplied observation",
        )

    primary_requests: list[tuple[LLMExtractionRequest, str]] = []
    for route in routes:
        document = _validate_document_route(
            parsed_documents[route.source_id], route
        )
        primary_requests.extend(
            (
                request,
                route.parsed_document_canonical_sha256,
            )
            for request in _partition_primary_requests(
                document=document,
                policy=validated_partition_policy,
            )
        )
    repeated_request, repeated_primary_id = _repeat_request(
        [request for request, _ in primary_requests]
    )
    repeated_route_hash = next(
        route_hash
        for request, route_hash in primary_requests
        if request.request_id == repeated_primary_id
    )
    ordered_requests = (*primary_requests, (repeated_request, repeated_route_hash))
    invocations = tuple(
        build_hash_only_invocation_identity(
            request=request,
            invocation_order=index,
            parsed_document_canonical_sha256=route_hash,
            pricing_observation=validated_pricing,
            repeated_primary_request_id=(
                repeated_primary_id
                if request.invocation_role is InvocationRole.REPEAT
                else None
            ),
        )
        for index, (request, route_hash) in enumerate(ordered_requests, start=1)
    )
    budget = _cost_budget(
        invocations=invocations,
        pricing=validated_pricing,
    )
    manifest = None
    status = "blocked"
    blocking_reasons = ("reviewed_context_limit_observation_missing",)
    if validated_context is not None:
        manifest = _build_final_manifest(
            source_routes=routes,
            partition_policy=validated_partition_policy,
            repeat_selection_policy=OpenAIDevelopmentRepeatSelectionPolicyV01(),
            invocations=invocations,
            execution_budget=budget,
            pricing_observation=validated_pricing,
            pricing_review=validated_pricing_review,
            data_controls_observation=validated_controls,
            data_controls_review=validated_controls_review,
            context_limit_observation=validated_context,
        )
        status = "eligible_for_independent_review"
        blocking_reasons = ()

    values = {
        "preparation_schema_version": DEVELOPMENT_PREPARATION_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "source_routes": routes,
        "partition_policy": validated_partition_policy,
        "repeat_selection_policy": OpenAIDevelopmentRepeatSelectionPolicyV01(),
        "invocations": invocations,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV01(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "execution_budget": budget,
        "pricing_observation": validated_pricing,
        "pricing_review": validated_pricing_review,
        "data_controls_observation": validated_controls,
        "data_controls_review": validated_controls_review,
        "cache_policy": OpenAIDevelopmentCachePolicyV01(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "context_limit_observation": validated_context,
        "readiness_status": status,
        "blocking_reasons": blocking_reasons,
        "manifest": manifest,
    }
    provisional = OpenAIDevelopmentManifestPreparationV01.model_construct(
        **values, preparation_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestPreparationV01.model_validate(
        {
            **values,
            "preparation_sha256": _canonical_model_hash(
                provisional, "preparation_sha256"
            ),
        }
    )


def _build_final_manifest_v0_2(
    *,
    source_routes: tuple[OpenAIDevelopmentSourceRouteV01, ...],
    partition_policy: OpenAIDevelopmentPartitionPolicyV02,
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV01,
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV02, ...],
    execution_budget: OpenAIDevelopmentExecutionBudgetV01,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01,
) -> OpenAIDevelopmentManifestV02:
    values = {
        "manifest_schema_version": DEVELOPMENT_MANIFEST_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID_V0_2,
        "provider_identifier": "openai",
        "requested_model_alias": "gpt-5.4-mini",
        "returned_preflight_model_identifier": OPENAI_RETURNED_PREFLIGHT_MODEL,
        "model_version_or_snapshot_provenance": "unavailable",
        "provider_sdk_version": "2.46.0",
        "provider_configuration_id": OPENAI_PROVIDER_CONFIGURATION_ID,
        "model_configuration_id": OPENAI_MODEL_CONFIGURATION_ID,
        "strict_schema_sha256": OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV01(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "source_routes": source_routes,
        "partition_policy": partition_policy,
        "repeat_selection_policy": repeat_selection_policy,
        "invocations": invocations,
        "execution_budget": execution_budget,
        "pricing_observation": pricing_observation,
        "pricing_review": pricing_review,
        "data_controls_observation": data_controls_observation,
        "data_controls_review": data_controls_review,
        "context_limit_observation": context_limit_observation,
        "cache_policy": OpenAIDevelopmentCachePolicyV02(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "manifest_review_status": "pending_independent_review",
        "execution_authorization_required": True,
        "execution_authorization_status": "not_provided",
    }
    provisional = OpenAIDevelopmentManifestV02.model_construct(
        **values, manifest_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestV02.model_validate(
        {
            **values,
            "manifest_sha256": _canonical_model_hash(
                provisional, "manifest_sha256"
            ),
        }
    )


def prepare_openai_development_manifest_v0_2(
    *,
    source_routes: Sequence[OpenAIDevelopmentSourceRouteV01],
    parsed_documents: Mapping[str, ParsedDocument],
    partition_policy: OpenAIDevelopmentPartitionPolicyV02,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01 | None = None,
) -> OpenAIDevelopmentManifestPreparationV02:
    """Prepare a no-call v0.2 hash inventory from approved development inputs."""
    routes = tuple(
        OpenAIDevelopmentSourceRouteV01.model_validate(
            route.model_dump(mode="python")
        )
        for route in source_routes
    )
    try:
        validated_partition_policy = OpenAIDevelopmentPartitionPolicyV02.model_validate(
            partition_policy.model_dump(mode="python")
        )
        validated_pricing = OpenAIPricingObservation.model_validate(
            pricing_observation.model_dump(mode="python")
        )
        validated_pricing_review = ReviewedObservationBindingV01.model_validate(
            pricing_review.model_dump(mode="python")
        )
        validated_controls = OpenAIDataControlsObservation.model_validate(
            data_controls_observation.model_dump(mode="python")
        )
        validated_controls_review = ReviewedObservationBindingV01.model_validate(
            data_controls_review.model_dump(mode="python")
        )
        validated_context = (
            None
            if context_limit_observation is None
            else ReviewedContextLimitObservationV01.model_validate(
                context_limit_observation.model_dump(mode="python")
            )
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "reviewed v0.2 manifest inputs do not satisfy immutable contracts",
        ) from error
    if tuple(route.source_id for route in routes) != APPROVED_SOURCE_ORDER:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "source routes must use the exact approved source order",
        )
    if set(parsed_documents) != set(APPROVED_SOURCE_ORDER):
        raise Stage4BError(
            Stage4BErrorCode.PROHIBITED_SOURCE,
            "preparation requires exactly the approved development sources",
        )
    if (
        validated_pricing_review.observation_kind != "pricing"
        or validated_pricing_review.observation_sha256
        != _canonical_observation_hash(validated_pricing)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "pricing review does not bind the supplied observation",
        )
    if (
        validated_controls_review.observation_kind != "data_controls"
        or validated_controls_review.observation_sha256
        != _canonical_observation_hash(validated_controls)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "data-control review does not bind the supplied observation",
        )

    primary_requests: list[tuple[LLMExtractionRequestV02, str]] = []
    for route in routes:
        document = _validate_document_route(
            parsed_documents[route.source_id], route
        )
        primary_requests.extend(
            (
                request,
                route.parsed_document_canonical_sha256,
            )
            for request in _partition_primary_requests_v0_2(
                document=document,
                policy=validated_partition_policy,
            )
        )
    repeated_request, repeated_primary_id = _repeat_request_v0_2(
        [request for request, _ in primary_requests]
    )
    repeated_route_hash = next(
        route_hash
        for request, route_hash in primary_requests
        if request.request_id == repeated_primary_id
    )
    ordered_requests = (*primary_requests, (repeated_request, repeated_route_hash))
    invocations = tuple(
        build_hash_only_invocation_identity_v0_2(
            request=request,
            invocation_order=index,
            parsed_document_canonical_sha256=route_hash,
            pricing_observation=validated_pricing,
            repeated_primary_request_id=(
                repeated_primary_id
                if request.invocation_role is InvocationRole.REPEAT
                else None
            ),
        )
        for index, (request, route_hash) in enumerate(ordered_requests, start=1)
    )
    budget = _cost_budget(
        invocations=invocations,
        pricing=validated_pricing,
    )
    manifest = None
    status = "blocked"
    blocking_reasons = ("reviewed_context_limit_observation_missing",)
    repeat_policy = OpenAIDevelopmentRepeatSelectionPolicyV01()
    if validated_context is not None:
        manifest = _build_final_manifest_v0_2(
            source_routes=routes,
            partition_policy=validated_partition_policy,
            repeat_selection_policy=repeat_policy,
            invocations=invocations,
            execution_budget=budget,
            pricing_observation=validated_pricing,
            pricing_review=validated_pricing_review,
            data_controls_observation=validated_controls,
            data_controls_review=validated_controls_review,
            context_limit_observation=validated_context,
        )
        status = "eligible_for_independent_review"
        blocking_reasons = ()

    values = {
        "preparation_schema_version": DEVELOPMENT_PREPARATION_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID_V0_2,
        "source_routes": routes,
        "partition_policy": validated_partition_policy,
        "repeat_selection_policy": repeat_policy,
        "invocations": invocations,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV01(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "execution_budget": budget,
        "pricing_observation": validated_pricing,
        "pricing_review": validated_pricing_review,
        "data_controls_observation": validated_controls,
        "data_controls_review": validated_controls_review,
        "cache_policy": OpenAIDevelopmentCachePolicyV02(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "context_limit_observation": validated_context,
        "readiness_status": status,
        "blocking_reasons": blocking_reasons,
        "manifest": manifest,
    }
    provisional = OpenAIDevelopmentManifestPreparationV02.model_construct(
        **values, preparation_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestPreparationV02.model_validate(
        {
            **values,
            "preparation_sha256": _canonical_model_hash(
                provisional, "preparation_sha256"
            ),
        }
    )


def _build_final_manifest_v0_3(
    *,
    source_routes: tuple[OpenAIDevelopmentSourceRouteV01, ...],
    partition_policy: OpenAIDevelopmentPartitionPolicyV03,
    repeat_selection_policy: OpenAIDevelopmentRepeatSelectionPolicyV03,
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV03, ...],
    execution_budget: OpenAIDevelopmentExecutionBudgetV01,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01,
) -> OpenAIDevelopmentManifestV03:
    values = {
        "manifest_schema_version": DEVELOPMENT_MANIFEST_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID_V0_3,
        "prompt_version": "0.3",
        "provider_identifier": "openai",
        "requested_model_alias": "gpt-5.4-mini",
        "returned_preflight_model_identifier": OPENAI_RETURNED_PREFLIGHT_MODEL,
        "model_version_or_snapshot_provenance": "unavailable",
        "provider_sdk_version": "2.46.0",
        "provider_configuration_id": OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        "model_configuration_id": OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        "response_schema_name": OPENAI_RESPONSE_SCHEMA_NAME_V0_3,
        "strict_schema_sha256": OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV03(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "source_routes": source_routes,
        "partition_policy": partition_policy,
        "repeat_selection_policy": repeat_selection_policy,
        "invocations": invocations,
        "execution_budget": execution_budget,
        "pricing_observation": pricing_observation,
        "pricing_review": pricing_review,
        "data_controls_observation": data_controls_observation,
        "data_controls_review": data_controls_review,
        "context_limit_observation": context_limit_observation,
        "cache_policy": OpenAIDevelopmentCachePolicyV03(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "manifest_review_status": "pending_independent_review",
        "execution_authorization_required": True,
        "execution_authorization_status": "not_provided",
    }
    provisional = OpenAIDevelopmentManifestV03.model_construct(
        **values, manifest_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestV03.model_validate(
        {
            **values,
            "manifest_sha256": _canonical_model_hash(
                provisional, "manifest_sha256"
            ),
        }
    )


def prepare_openai_development_manifest_v0_3(
    *,
    source_routes: Sequence[OpenAIDevelopmentSourceRouteV01],
    parsed_documents: Mapping[str, ParsedDocument],
    partition_policy: OpenAIDevelopmentPartitionPolicyV03,
    pricing_observation: OpenAIPricingObservation,
    pricing_review: ReviewedObservationBindingV01,
    data_controls_observation: OpenAIDataControlsObservation,
    data_controls_review: ReviewedObservationBindingV01,
    context_limit_observation: ReviewedContextLimitObservationV01 | None = None,
) -> OpenAIDevelopmentManifestPreparationV03:
    """Prepare a no-call v0.3 hash inventory from approved development inputs."""
    routes = tuple(
        OpenAIDevelopmentSourceRouteV01.model_validate(
            route.model_dump(mode="python")
        )
        for route in source_routes
    )
    try:
        validated_partition_policy = OpenAIDevelopmentPartitionPolicyV03.model_validate(
            partition_policy.model_dump(mode="python")
        )
        validated_pricing = OpenAIPricingObservation.model_validate(
            pricing_observation.model_dump(mode="python")
        )
        validated_pricing_review = ReviewedObservationBindingV01.model_validate(
            pricing_review.model_dump(mode="python")
        )
        validated_controls = OpenAIDataControlsObservation.model_validate(
            data_controls_observation.model_dump(mode="python")
        )
        validated_controls_review = ReviewedObservationBindingV01.model_validate(
            data_controls_review.model_dump(mode="python")
        )
        validated_context = (
            None
            if context_limit_observation is None
            else ReviewedContextLimitObservationV01.model_validate(
                context_limit_observation.model_dump(mode="python")
            )
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "reviewed v0.3 manifest inputs do not satisfy immutable contracts",
        ) from error
    if tuple(route.source_id for route in routes) != APPROVED_SOURCE_ORDER:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "source routes must use the exact approved source order",
        )
    if set(parsed_documents) != set(APPROVED_SOURCE_ORDER):
        raise Stage4BError(
            Stage4BErrorCode.PROHIBITED_SOURCE,
            "preparation requires exactly the approved development sources",
        )
    if (
        validated_pricing_review.observation_kind != "pricing"
        or validated_pricing_review.observation_sha256
        != _canonical_observation_hash(validated_pricing)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "pricing review does not bind the supplied observation",
        )
    if (
        validated_controls_review.observation_kind != "data_controls"
        or validated_controls_review.observation_sha256
        != _canonical_observation_hash(validated_controls)
    ):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "data-control review does not bind the supplied observation",
        )

    primary_requests: list[tuple[LLMExtractionRequestV03, str]] = []
    for route in routes:
        document = _validate_document_route(
            parsed_documents[route.source_id], route
        )
        primary_requests.extend(
            (
                request,
                route.parsed_document_canonical_sha256,
            )
            for request in _partition_primary_requests_v0_3(
                document=document,
                policy=validated_partition_policy,
            )
        )
    repeated_request, repeated_primary_id = _repeat_request_v0_3(
        [request for request, _ in primary_requests]
    )
    repeated_route_hash = next(
        route_hash
        for request, route_hash in primary_requests
        if request.request_id == repeated_primary_id
    )
    ordered_requests = (*primary_requests, (repeated_request, repeated_route_hash))
    invocations = tuple(
        build_hash_only_invocation_identity_v0_3(
            request=request,
            invocation_order=index,
            parsed_document_canonical_sha256=route_hash,
            pricing_observation=validated_pricing,
            repeated_primary_request_id=(
                repeated_primary_id
                if request.invocation_role is InvocationRole.REPEAT
                else None
            ),
        )
        for index, (request, route_hash) in enumerate(ordered_requests, start=1)
    )
    budget = _cost_budget(
        invocations=invocations,
        pricing=validated_pricing,
    )
    manifest = None
    status = "blocked"
    blocking_reasons = ("reviewed_context_limit_observation_missing",)
    repeat_policy = OpenAIDevelopmentRepeatSelectionPolicyV03()
    if validated_context is not None:
        manifest = _build_final_manifest_v0_3(
            source_routes=routes,
            partition_policy=validated_partition_policy,
            repeat_selection_policy=repeat_policy,
            invocations=invocations,
            execution_budget=budget,
            pricing_observation=validated_pricing,
            pricing_review=validated_pricing_review,
            data_controls_observation=validated_controls,
            data_controls_review=validated_controls_review,
            context_limit_observation=validated_context,
        )
        status = "eligible_for_independent_review"
        blocking_reasons = ()

    values = {
        "preparation_schema_version": DEVELOPMENT_PREPARATION_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID_V0_3,
        "prompt_version": "0.3",
        "source_routes": routes,
        "partition_policy": validated_partition_policy,
        "repeat_selection_policy": repeat_policy,
        "invocations": invocations,
        "preflight_evidence": OpenAIDevelopmentPreflightBindingV03(),
        "provider_controls": OpenAIDevelopmentProviderControlsV01(),
        "execution_budget": budget,
        "pricing_observation": validated_pricing,
        "pricing_review": validated_pricing_review,
        "data_controls_observation": validated_controls,
        "data_controls_review": validated_controls_review,
        "cache_policy": OpenAIDevelopmentCachePolicyV03(),
        "access_policy": OpenAIDevelopmentAccessPolicyV01(),
        "context_limit_observation": validated_context,
        "readiness_status": status,
        "blocking_reasons": blocking_reasons,
        "manifest": manifest,
    }
    provisional = OpenAIDevelopmentManifestPreparationV03.model_construct(
        **values, preparation_sha256="0" * 64
    )
    return OpenAIDevelopmentManifestPreparationV03.model_validate(
        {
            **values,
            "preparation_sha256": _canonical_model_hash(
                provisional, "preparation_sha256"
            ),
        }
    )


def development_manifest_bytes(manifest: OpenAIDevelopmentManifestV01) -> bytes:
    """Return canonical UTF-8 manifest bytes with exactly one trailing LF."""
    validated = OpenAIDevelopmentManifestV01.model_validate(
        manifest.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json")) + b"\n"


def development_manifest_bytes_v0_2(
    manifest: OpenAIDevelopmentManifestV02,
) -> bytes:
    """Return canonical UTF-8 v0.2 manifest bytes with exactly one LF."""
    validated = OpenAIDevelopmentManifestV02.model_validate(
        manifest.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json")) + b"\n"


def load_development_manifest_v0_2(path: Path) -> OpenAIDevelopmentManifestV02:
    """Load one v0.2 manifest through canonical and self-hash validation."""
    content = _read_validated_regular_file(path)
    try:
        canonical_content = canonical_lf_json_bytes(content)
        manifest = OpenAIDevelopmentManifestV02.model_validate_json(
            canonical_content
        )
    except (ValidationError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.2 development manifest is not valid canonical evidence",
        ) from error
    if development_manifest_bytes_v0_2(manifest) != canonical_content:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.2 development manifest does not round-trip canonically",
        )
    return manifest


def development_manifest_bytes_v0_3(
    manifest: OpenAIDevelopmentManifestV03,
) -> bytes:
    """Return canonical UTF-8 v0.3 manifest bytes with exactly one LF."""
    validated = OpenAIDevelopmentManifestV03.model_validate(
        manifest.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json")) + b"\n"


def load_development_manifest_v0_3(path: Path) -> OpenAIDevelopmentManifestV03:
    """Load one v0.3 manifest through canonical and self-hash validation."""
    content = _read_validated_regular_file(path)
    try:
        canonical_content = canonical_lf_json_bytes(content)
        manifest = OpenAIDevelopmentManifestV03.model_validate_json(
            canonical_content
        )
    except (ValidationError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.3 development manifest is not valid canonical evidence",
        ) from error
    if development_manifest_bytes_v0_3(manifest) != canonical_content:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "v0.3 development manifest does not round-trip canonically",
        )
    return manifest


__all__ = [
    "APPROVED_SOURCE_ORDER",
    "CONSERVATIVE_CONTEXT_SAFETY_RULE",
    "CONSERVATIVE_TOKEN_ADMISSION_METHOD",
    "PARTITION_POLICY_ID",
    "PARTITION_POLICY_ID_V0_2",
    "PARTITION_POLICY_ID_V0_3",
    "REPEAT_SELECTION_POLICY_ID",
    "REPEAT_SELECTION_POLICY_ID_V0_3",
    "PLANNED_AUTHORIZATION_CAP_USD",
    "OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256",
    "OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256_V0_3",
    "OpenAIDevelopmentCachePolicyV01",
    "OpenAIDevelopmentCachePolicyV02",
    "OpenAIDevelopmentCachePolicyV03",
    "OpenAIDevelopmentExecutionBudgetV01",
    "OpenAIDevelopmentInvocationIdentityV01",
    "OpenAIDevelopmentInvocationIdentityV02",
    "OpenAIDevelopmentInvocationIdentityV03",
    "OpenAIDevelopmentManifestPreparationV01",
    "OpenAIDevelopmentManifestPreparationV02",
    "OpenAIDevelopmentManifestPreparationV03",
    "OpenAIDevelopmentManifestV01",
    "OpenAIDevelopmentManifestV02",
    "OpenAIDevelopmentManifestV03",
    "OpenAIDevelopmentPartitionPolicyV01",
    "OpenAIDevelopmentPartitionPolicyV02",
    "OpenAIDevelopmentPartitionPolicyV03",
    "OpenAIDevelopmentPreflightBindingV03",
    "OpenAIDevelopmentRepeatSelectionPolicyV01",
    "OpenAIDevelopmentRepeatSelectionPolicyV03",
    "OpenAIDevelopmentSourceRouteV01",
    "ReviewedContextLimitObservationV01",
    "ReviewedObservationBindingV01",
    "approved_parsed_document_relative_path",
    "build_hash_only_invocation_identity",
    "build_hash_only_invocation_identity_v0_2",
    "build_hash_only_invocation_identity_v0_3",
    "build_reviewed_context_limit_observation",
    "build_reviewed_observation_binding",
    "build_source_route_identity",
    "canonical_lf_json_bytes",
    "canonical_lf_json_sha256",
    "development_manifest_bytes",
    "development_manifest_bytes_v0_2",
    "development_manifest_bytes_v0_3",
    "load_development_manifest_v0_2",
    "load_development_manifest_v0_3",
    "load_approved_parsed_document",
    "prepare_openai_development_manifest",
    "prepare_openai_development_manifest_v0_2",
    "prepare_openai_development_manifest_v0_3",
    "validate_successful_preflight_evidence",
    "validate_successful_preflight_evidence_v0_4",
]
