"""Offline-tested contract for one future synthetic OpenAI preflight."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, Protocol, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
    LLMProviderResponse,
    ProviderTerminalStatus,
    SHA256_PATTERN,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_API_SURFACE,
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OPENAI_REQUIRED_SDK_VERSION,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.validation import validate_provider_output


PREFLIGHT_SCHEMA_VERSION: Literal["0.1"] = "0.1"
PREFLIGHT_ID: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.1"] = (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.1"
)
PREFLIGHT_AUTHORIZATION_SCOPE: Literal[
    "single-synthetic-openai-preflight-v0.1"
] = "single-synthetic-openai-preflight-v0.1"
PREFLIGHT_INPUT_CLASSIFICATION: Literal["synthetic_preflight_text"] = (
    "synthetic_preflight_text"
)
PREFLIGHT_REQUEST_ID = "synthetic-preflight-request-v0.1"
PREFLIGHT_EVIDENCE_ID = "synthetic-preflight-evidence-v0.1"
PREFLIGHT_BLOCK_ID = "synthetic-preflight-block-v0.1"
PREFLIGHT_SYNTHETIC_TEXT = (
    "Synthetic preflight only. No development-document content is present, "
    "and no real-world fact is asserted."
)
_MILLION = Decimal("1000000")
_FORBIDDEN_VERSION_FIELD_NAMES = frozenset(
    {
        "_request_id",
        "created",
        "created_at",
        "created_timestamp",
        "id",
        "model",
        "model_alias",
        "model_id",
        "provider_request_id",
        "provider_response_id",
        "request_id",
        "response_id",
        "returned_model_identifier",
        "sdk.version",
        "sdk_version",
        "provider_sdk_version",
    }
)
_FORBIDDEN_PUBLIC_METADATA_FIELD_SEGMENTS = frozenset(
    {
        "api_key",
        "authorization",
        "authorization_header",
        "credentials",
        "evidence",
        "evidence_text",
        "headers",
        "output",
        "output_text",
        "prompt",
        "prompt_text",
        "raw_response",
    }
)
_UNAVAILABLE_VERSION_FIELD_SEGMENTS = frozenset(
    {
        "model_snapshot",
        "model_version",
        "revision",
        "revision_id",
        "snapshot",
        "snapshot_id",
        "snapshot_name",
        "version",
        "version_id",
    }
)
_REQUIRED_PUBLIC_METADATA_PATHS = (
    "response.id",
    "response.model",
    "response._request_id",
    "sdk.version",
)


def _require_trimmed(value: str, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be trimmed and nonblank")
    return value


def _normalized_field_path(value: str) -> str:
    return ".".join(
        segment.strip().casefold().replace("-", "_")
        for segment in value.split(".")
    )


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value


def _utc_json(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class OpenAIPreflightAuthorization(BaseModel):
    """Explicit project-owner authorization for one synthetic provider call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_id: str
    authorized_by: str
    authorized_at_utc: datetime
    scope: Literal["single-synthetic-openai-preflight-v0.1"]
    maximum_provider_calls: Literal[1]
    real_provider_preflight_authorized: Literal[True]

    @field_validator("authorization_id", "authorized_by")
    @classmethod
    def validate_identifiers(cls, value: str, info: Any) -> str:
        return _require_trimmed(value, info.field_name)

    @field_validator("authorized_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "authorized_at_utc")

    @field_serializer("authorized_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)


class OpenAIPricingObservation(BaseModel):
    """Dated caller-supplied pricing evidence, never a permanent constant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_at_utc: datetime
    source_title: str
    source_url: str
    input_usd_per_million_tokens: Decimal = Field(gt=0)
    output_usd_per_million_tokens: Decimal = Field(gt=0)
    currency: Literal["USD"]

    @field_validator("observed_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "observed_at_utc")

    @field_validator("source_title", "source_url")
    @classmethod
    def validate_source(cls, value: str, info: Any) -> str:
        validated = _require_trimmed(value, info.field_name)
        if info.field_name == "source_url" and not validated.startswith(
            ("https://", "http://")
        ):
            raise ValueError("source_url must be an HTTP(S) reviewed source")
        return validated

    @field_validator(
        "input_usd_per_million_tokens",
        "output_usd_per_million_tokens",
    )
    @classmethod
    def canonicalize_price(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_serializer("observed_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @field_serializer(
        "input_usd_per_million_tokens",
        "output_usd_per_million_tokens",
        when_used="json",
    )
    def serialize_price(self, value: Decimal) -> str:
        return format(value, "f")


class OpenAIDataControlsObservation(BaseModel):
    """Dated reviewed provider data-control terms for the future request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_at_utc: datetime
    source_title: str
    source_url: str
    store_false_required: Literal[True]
    zero_retention_claimed: Literal[False]
    retention_and_abuse_monitoring_summary: str

    @field_validator("observed_at_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "observed_at_utc")

    @field_validator(
        "source_title",
        "source_url",
        "retention_and_abuse_monitoring_summary",
    )
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        validated = _require_trimmed(value, info.field_name)
        if info.field_name == "source_url" and not validated.startswith(
            ("https://", "http://")
        ):
            raise ValueError("source_url must be an HTTP(S) reviewed source")
        return validated

    @field_serializer("observed_at_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)


class ProviderVersionIdentifier(BaseModel):
    """One separately provider-exposed model-version or snapshot field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str
    value: str

    @field_validator("field_name", "value")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _require_trimmed(value, info.field_name)

    @model_validator(mode="after")
    def reject_inferred_identity_fields(self) -> ProviderVersionIdentifier:
        normalized_name = _normalized_field_path(self.field_name)
        final_segment = normalized_name.rsplit(".", maxsplit=1)[-1]
        if (
            normalized_name in _FORBIDDEN_VERSION_FIELD_NAMES
            or final_segment in _FORBIDDEN_VERSION_FIELD_NAMES
        ):
            raise ValueError(
                "model, response, request, and created fields are not separate "
                "version provenance"
            )
        return self


ModelVersionOrSnapshotProvenance: TypeAlias = (
    Literal["unavailable"] | tuple[ProviderVersionIdentifier, ...]
)
ProviderPublicMetadataValue: TypeAlias = (
    StrictStr | StrictInt | StrictBool | None
)
_VERSION_PROVENANCE_ADAPTER = TypeAdapter(ModelVersionOrSnapshotProvenance)


def _validated_version_provenance(
    value: object,
) -> ModelVersionOrSnapshotProvenance:
    try:
        validated = _VERSION_PROVENANCE_ADAPTER.validate_python(value)
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_VERSION_PROVENANCE_INVALID,
            "model version or snapshot provenance is invalid",
        ) from error
    if validated == "unavailable":
        return validated
    if not validated:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_VERSION_PROVENANCE_INVALID,
            "model version or snapshot provenance must not be empty",
        )
    names = [_normalized_field_path(item.field_name) for item in validated]
    if len(names) != len(set(names)):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_VERSION_PROVENANCE_INVALID,
            "model version or snapshot field names must be case-insensitively unique",
        )
    return validated


def _validated_metadata_field_path(value: str) -> str:
    validated = _require_trimmed(value, "provider_public_metadata_field_path")
    segments = tuple(part.strip().casefold() for part in validated.split("."))
    if any(not part for part in segments):
        raise ValueError("provider public metadata field paths must be complete")
    normalized_segments = tuple(part.replace("-", "_") for part in segments)
    if any(
        segment in _FORBIDDEN_PUBLIC_METADATA_FIELD_SEGMENTS
        for segment in normalized_segments
    ):
        raise ValueError(
            "provider public metadata must not include output, prompt, evidence, "
            "authorization, header, API-key, or credential fields"
        )
    return validated


def _validated_metadata_field_paths(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value:
        raise ValueError(
            "provider_public_metadata_field_paths must be a non-empty tuple"
        )
    paths: list[str] = []
    for path in value:
        if not isinstance(path, str):
            raise ValueError("provider public metadata field paths must be strings")
        paths.append(_validated_metadata_field_path(path))
    normalized_paths = [_normalized_field_path(path) for path in paths]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise ValueError(
            "provider public metadata field paths must be case-insensitively unique"
        )
    return tuple(paths)
class ProviderPublicMetadataEntry(BaseModel):
    """One safe scalar from the provider's public response metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    value: ProviderPublicMetadataValue

    @field_validator("field_path")
    @classmethod
    def validate_field_path(cls, value: str) -> str:
        return _validated_metadata_field_path(value)

    @field_validator("value")
    @classmethod
    def validate_value(
        cls, value: ProviderPublicMetadataValue
    ) -> ProviderPublicMetadataValue:
        if isinstance(value, str) and not value.strip():
            raise ValueError("provider public metadata strings must not be blank")
        return value


def _validated_metadata_entries(
    value: object,
) -> tuple[ProviderPublicMetadataEntry, ...]:
    if not isinstance(value, tuple) or not value:
        raise ValueError("provider_public_metadata_entries must be a non-empty tuple")
    entries: list[ProviderPublicMetadataEntry] = []
    for entry in value:
        if not isinstance(entry, ProviderPublicMetadataEntry):
            raise ValueError(
                "provider public metadata entries must use the typed entry contract"
            )
        entries.append(
            ProviderPublicMetadataEntry.model_validate(
                entry.model_dump(mode="python")
            )
        )
    normalized_paths = [
        _normalized_field_path(entry.field_path) for entry in entries
    ]
    if len(normalized_paths) != len(set(normalized_paths)):
        raise ValueError(
            "provider public metadata field paths must be case-insensitively unique"
        )
    return tuple(entries)


def _public_metadata_projection(
    entries: tuple[ProviderPublicMetadataEntry, ...],
) -> dict[str, ProviderPublicMetadataValue]:
    return {entry.field_path: entry.value for entry in entries}


def _validate_provenance_path_inventory(
    provenance: ModelVersionOrSnapshotProvenance,
    field_paths: tuple[str, ...],
) -> None:
    validated_provenance = _validated_version_provenance(provenance)
    validated_paths = _validated_metadata_field_paths(field_paths)
    path_set = set(validated_paths)
    for required_path in _REQUIRED_PUBLIC_METADATA_PATHS:
        if required_path not in path_set:
            raise ValueError(
                f"required provider public metadata path is missing: {required_path}"
            )
    if validated_provenance == "unavailable":
        for field_path in validated_paths:
            normalized_path = _normalized_field_path(field_path)
            final_segment = normalized_path.rsplit(".", maxsplit=1)[-1]
            if (
                normalized_path != "sdk.version"
                and final_segment in _UNAVAILABLE_VERSION_FIELD_SEGMENTS
            ):
                raise ValueError(
                    "unavailable version provenance contradicts provider public "
                    f"metadata: {field_path}"
                )
        return
    for identifier in validated_provenance:
        if identifier.field_name not in path_set:
            raise ValueError(
                "version provenance is absent from provider public metadata paths: "
                f"{identifier.field_name}"
            )


def build_synthetic_openai_preflight_request() -> LLMExtractionRequest:
    """Build one fixed in-memory request with no development-document text."""
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id=PREFLIGHT_EVIDENCE_ID,
        block_id=PREFLIGHT_BLOCK_ID,
        sequence=1,
        text=PREFLIGHT_SYNTHETIC_TEXT,
        location=SourceLocation(
            location_type=LocationType.DOCUMENT_METADATA,
            location_value="synthetic-preflight",
        ),
    )
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id=PREFLIGHT_REQUEST_ID,
        source_id="S001",
        document_sha256=uppercase_sha256_bytes(
            PREFLIGHT_SYNTHETIC_TEXT.encode("utf-8")
        ),
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=(block,),
    )


class OpenAIPreflightRecord(BaseModel):
    """Canonical passed record for one authorized synthetic compatibility call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preflight_schema_version: Literal["0.1"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.1"]
    experiment_id: Literal["llm-extraction-baseline-v0.1"]
    authorization: OpenAIPreflightAuthorization
    execution_timestamp_utc: datetime
    input_classification: Literal["synthetic_preflight_text"]
    provider_call_count: Literal[1]
    preflight_status: Literal["passed"]
    provider_identifier: Literal["openai"]
    api_surface: Literal["responses"]
    requested_model_alias: Literal["gpt-5.4-mini"]
    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.1"
    ]
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.1"
    ]
    request_id: str
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    strict_schema_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    returned_model_identifier: str
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    provider_public_metadata_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_public_metadata_field_paths: tuple[str, ...]
    version_provenance_observed_from_same_provider_call: Literal[True]
    provider_request_id: str
    provider_response_id: str
    provider_sdk_version: str
    strict_schema_compatible: Literal[True]
    local_output_validation_status: Literal["valid"]
    raw_response_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_output_sha256: str = Field(pattern=SHA256_PATTERN)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    retry_count: Literal[0]
    store_requested: Literal[False]
    streaming_enabled: Literal[False]
    background_enabled: Literal[False]
    tools_enabled: Literal[False]
    pricing_observation: OpenAIPricingObservation
    data_controls_observation: OpenAIDataControlsObservation
    estimated_actual_cost_usd: Decimal = Field(ge=0)
    preflight_record_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("execution_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "execution_timestamp_utc")

    @field_serializer("execution_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @field_serializer("estimated_actual_cost_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @field_validator("model_version_or_snapshot_provenance", mode="after")
    @classmethod
    def validate_version_provenance(
        cls, value: ModelVersionOrSnapshotProvenance
    ) -> ModelVersionOrSnapshotProvenance:
        try:
            return _validated_version_provenance(value)
        except Stage4BError as error:
            raise ValueError(error.message) from error

    @field_validator("provider_public_metadata_field_paths", mode="after")
    @classmethod
    def validate_metadata_field_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_metadata_field_paths(value)

    @model_validator(mode="after")
    def validate_record(self) -> OpenAIPreflightRecord:
        for field_name in (
            "request_id",
            "returned_model_identifier",
            "version_provenance_source_response_id",
            "provider_request_id",
            "provider_response_id",
            "provider_sdk_version",
        ):
            _require_trimmed(getattr(self, field_name), field_name)
        if self.version_provenance_source_response_id != self.provider_response_id:
            raise ValueError(
                "version provenance source response ID must equal provider response ID"
            )
        _validate_provenance_path_inventory(
            self.model_version_or_snapshot_provenance,
            self.provider_public_metadata_field_paths,
        )
        if self.provider_sdk_version not in {
            OPENAI_INSTALLED_SDK_VERSION,
            OPENAI_REQUIRED_SDK_VERSION,
        } or OPENAI_INSTALLED_SDK_VERSION != OPENAI_REQUIRED_SDK_VERSION:
            raise ValueError("provider SDK version must equal the pinned adapter version")
        if self.authorization.authorized_at_utc > self.execution_timestamp_utc:
            raise ValueError("authorization must not postdate execution")
        execution_date = self.execution_timestamp_utc.date()
        if self.pricing_observation.observed_at_utc.date() != execution_date:
            raise ValueError("pricing observation must use the execution UTC date")
        if self.data_controls_observation.observed_at_utc.date() != execution_date:
            raise ValueError("data-control observation must use the execution UTC date")
        if isinstance(self.input_tokens, bool) or isinstance(self.output_tokens, bool):
            raise ValueError("token usage must use integers")

        request = build_synthetic_openai_preflight_request()
        expected_request = {
            "request_id": request.request_id,
            "canonical_request_sha256": request.canonical_request_sha256,
            "prompt_sha256": request.prompt_sha256,
            "document_sha256": request.document_sha256,
        }
        for field_name, expected in expected_request.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} differs from the synthetic request")

        schema = build_openai_candidate_schema()
        payload = build_openai_responses_payload(request)
        expected_schema_hash = uppercase_sha256_bytes(canonical_json_bytes(schema))
        expected_payload_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
        if self.strict_schema_sha256 != expected_schema_hash:
            raise ValueError("strict_schema_sha256 differs from the production schema")
        if self.provider_payload_sha256 != expected_payload_hash:
            raise ValueError("provider_payload_sha256 differs from the exact payload")

        expected_cost = _estimated_cost(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            pricing=self.pricing_observation,
        )
        if self.estimated_actual_cost_usd != expected_cost:
            raise ValueError("estimated actual cost does not reconcile")

        expected_hash = uppercase_sha256_bytes(
            canonical_json_bytes(
                _preflight_record_payload(self, include_hash=False)
            )
        )
        if self.preflight_record_sha256 != expected_hash:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_RECORD_HASH_MISMATCH,
                "preflight_record_sha256 does not match canonical record bytes",
            )
        return self


def _estimated_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    pricing: OpenAIPricingObservation,
) -> Decimal:
    cost = (
        Decimal(input_tokens) * pricing.input_usd_per_million_tokens
        + Decimal(output_tokens) * pricing.output_usd_per_million_tokens
    ) / _MILLION
    return Decimal("0") if cost == 0 else cost.normalize()


def _preflight_record_payload(
    record: OpenAIPreflightRecord,
    *,
    include_hash: bool,
) -> dict[str, Any]:
    excluded = set() if include_hash else {"preflight_record_sha256"}
    return record.model_dump(mode="json", exclude=excluded)


def _build_preflight_record(**values: Any) -> OpenAIPreflightRecord:
    provisional = OpenAIPreflightRecord.model_construct(
        **values,
        preflight_record_sha256="0" * 64,
    )
    record_hash = uppercase_sha256_bytes(
        canonical_json_bytes(
            _preflight_record_payload(provisional, include_hash=False)
        )
    )
    return OpenAIPreflightRecord.model_validate(
        {**values, "preflight_record_sha256": record_hash}
    )


def preflight_record_bytes(record: OpenAIPreflightRecord) -> bytes:
    """Return canonical UTF-8 bytes after complete self-hash validation."""
    validated = OpenAIPreflightRecord.model_validate(
        record.model_dump(mode="python")
    )
    return canonical_json_bytes(
        _preflight_record_payload(validated, include_hash=True)
    )


def _validate_authorization(
    authorization: OpenAIPreflightAuthorization,
) -> OpenAIPreflightAuthorization:
    if not isinstance(authorization, OpenAIPreflightAuthorization):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "explicit preflight authorization is required",
        )
    try:
        return OpenAIPreflightAuthorization.model_validate(
            authorization.model_dump(mode="python")
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "preflight authorization is invalid",
        ) from error


def _validate_terms_model(
    value: object,
    model_type: type[OpenAIPricingObservation]
    | type[OpenAIDataControlsObservation],
) -> OpenAIPricingObservation | OpenAIDataControlsObservation:
    if not isinstance(value, model_type):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
            "explicit reviewed pricing and data-control observations are required",
        )
    try:
        return model_type.model_validate(value.model_dump(mode="python"))
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
            "reviewed preflight terms are invalid",
        ) from error


def _validated_execution_timestamp(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
            "preflight clock must return a datetime",
        )
    try:
        return _require_utc(value, "execution_timestamp_utc")
    except ValueError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
            "preflight clock must return timezone-aware UTC",
        ) from error


def _validated_openai_response(
    response: LLMProviderResponse,
) -> LLMProviderResponse:
    if not isinstance(response, LLMProviderResponse):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "provider must return LLMProviderResponse",
        )
    try:
        validated = LLMProviderResponse.model_validate(
            response.model_dump(mode="python")
        )
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "provider response metadata is invalid",
        ) from error
    metadata = (
        validated.provider_request_id,
        validated.provider_response_id,
        validated.provider_sdk_version,
    )
    if (
        validated.terminal_status is not ProviderTerminalStatus.SUCCESS
        or validated.provider_identifier != OPENAI_PROVIDER_IDENTIFIER
        or any(value is None for value in metadata)
        or validated.provider_sdk_version != OPENAI_INSTALLED_SDK_VERSION
        or validated.provider_sdk_version != OPENAI_REQUIRED_SDK_VERSION
        or validated.token_usage is None
        or validated.token_usage.input_tokens is None
        or validated.token_usage.output_tokens is None
        or validated.retry_count != 0
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "successful OpenAI response metadata is incomplete or inconsistent",
        )
    return validated


class OpenAIPreflightProviderObservation(BaseModel):
    """Response and public version metadata observed from one provider call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response: LLMProviderResponse
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    observed_from_same_provider_call: Literal[True]
    provider_public_metadata_entries: tuple[ProviderPublicMetadataEntry, ...]

    @field_validator("model_version_or_snapshot_provenance", mode="after")
    @classmethod
    def validate_version_provenance(
        cls, value: ModelVersionOrSnapshotProvenance
    ) -> ModelVersionOrSnapshotProvenance:
        try:
            return _validated_version_provenance(value)
        except Stage4BError as error:
            raise ValueError(error.message) from error

    @field_validator("provider_public_metadata_entries", mode="after")
    @classmethod
    def validate_metadata_entries(
        cls, value: tuple[ProviderPublicMetadataEntry, ...]
    ) -> tuple[ProviderPublicMetadataEntry, ...]:
        return _validated_metadata_entries(value)

    @property
    def provider_public_metadata_field_paths(self) -> tuple[str, ...]:
        """Return the ordered paths derived from validated metadata entries."""
        return tuple(
            entry.field_path for entry in self.provider_public_metadata_entries
        )

    @property
    def provider_public_metadata_sha256(self) -> str:
        """Hash the canonical safe metadata projection."""
        return uppercase_sha256_bytes(
            canonical_json_bytes(
                _public_metadata_projection(self.provider_public_metadata_entries)
            )
        )

    @model_validator(mode="after")
    def validate_same_call_binding(self) -> OpenAIPreflightProviderObservation:
        validated_response = _validated_openai_response(self.response)
        source_response_id = _require_trimmed(
            self.version_provenance_source_response_id,
            "version_provenance_source_response_id",
        )
        if source_response_id != validated_response.provider_response_id:
            raise ValueError(
                "version provenance source response ID must equal the observed "
                "provider response ID"
            )
        metadata = _public_metadata_projection(self.provider_public_metadata_entries)
        required_metadata = {
            "response.id": validated_response.provider_response_id,
            "response.model": validated_response.model_identifier,
            "response._request_id": validated_response.provider_request_id,
            "sdk.version": validated_response.provider_sdk_version,
        }
        for field_path in _REQUIRED_PUBLIC_METADATA_PATHS:
            if field_path not in metadata:
                raise ValueError(
                    f"required provider public metadata entry is missing: {field_path}"
                )
            if metadata[field_path] != required_metadata[field_path]:
                raise ValueError(
                    f"provider public metadata does not reconcile: {field_path}"
                )
        provenance = self.model_version_or_snapshot_provenance
        _validate_provenance_path_inventory(
            provenance,
            self.provider_public_metadata_field_paths,
        )
        if provenance != "unavailable":
            for identifier in provenance:
                if metadata[identifier.field_name] != identifier.value:
                    raise ValueError(
                        "version provenance differs from provider public metadata: "
                        f"{identifier.field_name}"
                    )
        return self


class OpenAIPreflightProvider(Protocol):
    """One-call bridge that binds response and public metadata observation."""

    def generate_preflight(
        self,
        request: LLMExtractionRequest,
    ) -> OpenAIPreflightProviderObservation:
        """Return one response and its same-call public metadata observation."""
        ...


def _validated_provider_observation(
    observation: object,
) -> OpenAIPreflightProviderObservation:
    if not isinstance(observation, OpenAIPreflightProviderObservation):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "provider must return OpenAIPreflightProviderObservation",
        )
    try:
        _validated_version_provenance(
            observation.model_version_or_snapshot_provenance
        )
        _validated_metadata_entries(
            observation.provider_public_metadata_entries
        )
        return OpenAIPreflightProviderObservation.model_validate(
            observation.model_dump(mode="python")
        )
    except Stage4BError:
        raise
    except (AttributeError, TypeError, ValidationError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "provider preflight observation is invalid or not bound to one response",
        ) from error


def run_openai_synthetic_preflight(
    *,
    provider: OpenAIPreflightProvider,
    authorization: OpenAIPreflightAuthorization,
    pricing_observation: OpenAIPricingObservation,
    data_controls_observation: OpenAIDataControlsObservation,
    clock: Callable[[], datetime],
) -> OpenAIPreflightRecord:
    """Run one authorized call; canonical builders read only prompt assets."""
    validated_authorization = _validate_authorization(authorization)
    execution_timestamp = _validated_execution_timestamp(clock)
    if validated_authorization.authorized_at_utc > execution_timestamp:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "preflight authorization must not postdate execution",
        )
    validated_pricing = _validate_terms_model(
        pricing_observation, OpenAIPricingObservation
    )
    validated_data_controls = _validate_terms_model(
        data_controls_observation, OpenAIDataControlsObservation
    )
    if (
        validated_pricing.observed_at_utc.date() != execution_timestamp.date()
        or validated_data_controls.observed_at_utc.date()
        != execution_timestamp.date()
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_TERMS_INVALID,
            "pricing and data-control observations must use the execution UTC date",
        )
    request = build_synthetic_openai_preflight_request()
    schema = build_openai_candidate_schema()
    payload = build_openai_responses_payload(request)
    strict_schema_sha256 = uppercase_sha256_bytes(canonical_json_bytes(schema))
    provider_payload_sha256 = uppercase_sha256_bytes(canonical_json_bytes(payload))

    observation = _validated_provider_observation(
        provider.generate_preflight(request)
    )
    response = observation.response
    version_provenance = observation.model_version_or_snapshot_provenance
    validated_output = validate_provider_output(request, response)
    result = validated_output.candidate_result
    if (
        result.entities
        or result.evidence_references
        or result.candidate_facts
        or "abstained_no_supported_candidate" not in result.warnings
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_OUTPUT_INVALID,
            "synthetic preflight must return a zero-candidate abstention",
        )

    token_usage = response.token_usage
    if (
        token_usage is None
        or token_usage.input_tokens is None
        or token_usage.output_tokens is None
        or response.provider_request_id is None
        or response.provider_response_id is None
        or response.provider_sdk_version is None
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "validated provider response metadata unexpectedly became incomplete",
        )
    estimated_cost = _estimated_cost(
        input_tokens=token_usage.input_tokens,
        output_tokens=token_usage.output_tokens,
        pricing=validated_pricing,
    )

    return _build_preflight_record(
        preflight_schema_version=PREFLIGHT_SCHEMA_VERSION,
        preflight_id=PREFLIGHT_ID,
        experiment_id=EXPERIMENT_ID,
        authorization=validated_authorization,
        execution_timestamp_utc=execution_timestamp,
        input_classification=PREFLIGHT_INPUT_CLASSIFICATION,
        provider_call_count=1,
        preflight_status="passed",
        provider_identifier=OPENAI_PROVIDER_IDENTIFIER,
        api_surface=OPENAI_API_SURFACE,
        requested_model_alias=OPENAI_REQUESTED_MODEL_ALIAS,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        request_id=request.request_id,
        canonical_request_sha256=request.canonical_request_sha256,
        prompt_sha256=request.prompt_sha256,
        document_sha256=request.document_sha256,
        strict_schema_sha256=strict_schema_sha256,
        provider_payload_sha256=provider_payload_sha256,
        returned_model_identifier=response.model_identifier,
        model_version_or_snapshot_provenance=version_provenance,
        version_provenance_source_response_id=(
            observation.version_provenance_source_response_id
        ),
        provider_public_metadata_sha256=(
            observation.provider_public_metadata_sha256
        ),
        provider_public_metadata_field_paths=(
            observation.provider_public_metadata_field_paths
        ),
        version_provenance_observed_from_same_provider_call=(
            observation.observed_from_same_provider_call
        ),
        provider_request_id=response.provider_request_id,
        provider_response_id=response.provider_response_id,
        provider_sdk_version=response.provider_sdk_version,
        strict_schema_compatible=True,
        local_output_validation_status="valid",
        raw_response_sha256=response.raw_response_sha256,
        parsed_output_sha256=validated_output.canonical_output_sha256,
        input_tokens=token_usage.input_tokens,
        output_tokens=token_usage.output_tokens,
        latency_ms=response.latency_ms,
        retry_count=0,
        store_requested=payload["store"],
        streaming_enabled=payload["stream"],
        background_enabled=payload["background"],
        tools_enabled=bool(payload["tools"]),
        pricing_observation=validated_pricing,
        data_controls_observation=validated_data_controls,
        estimated_actual_cost_usd=estimated_cost,
    )


__all__ = [
    "ModelVersionOrSnapshotProvenance",
    "OpenAIPreflightProvider",
    "OpenAIDataControlsObservation",
    "OpenAIPreflightAuthorization",
    "OpenAIPreflightProviderObservation",
    "OpenAIPreflightRecord",
    "OpenAIPricingObservation",
    "PREFLIGHT_AUTHORIZATION_SCOPE",
    "PREFLIGHT_ID",
    "PREFLIGHT_SCHEMA_VERSION",
    "ProviderPublicMetadataEntry",
    "ProviderVersionIdentifier",
    "build_synthetic_openai_preflight_request",
    "preflight_record_bytes",
    "run_openai_synthetic_preflight",
]
