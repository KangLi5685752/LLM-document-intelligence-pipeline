"""Additive v0.4 contract separating compatibility from semantic diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import openai_preflight as v0_1
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID_V0_3,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequestV03,
)
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
from document_intelligence.llm_extraction.openai_preflight import (
    ModelVersionOrSnapshotProvenance,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightProvider,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3,
    OPENAI_API_SURFACE,
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MODEL_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OPENAI_REQUIRED_SDK_VERSION,
    build_openai_candidate_schema_v0_3,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope_v0_3,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.validation import validate_provider_output


PREFLIGHT_SCHEMA_VERSION: Literal["0.4"] = "0.4"
PREFLIGHT_ID: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.4"] = (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.4"
)
PREFLIGHT_AUTHORIZATION_SCOPE: Literal[
    "single-synthetic-openai-preflight-v0.4"
] = "single-synthetic-openai-preflight-v0.4"
PREFLIGHT_INPUT_CLASSIFICATION = v0_1.PREFLIGHT_INPUT_CLASSIFICATION
PREFLIGHT_REQUEST_ID = "llm-v0.3-S001-primary-999"
PREFLIGHT_EVIDENCE_ID = "llm-evidence-v0.3-S001-synthetic-preflight-block-v0.4"
PREFLIGHT_BLOCK_ID = "synthetic-preflight-block-v0.4"
PREFLIGHT_SYNTHETIC_TEXT = v0_1.PREFLIGHT_SYNTHETIC_TEXT
EXPECTED_ABSTENTION_WARNING = "abstained_no_supported_candidate"


class OpenAIPreflightAuthorizationV04(OpenAIPreflightAuthorization):
    """Explicit authorization scoped only to the separate v0.4 call."""

    scope: Literal["single-synthetic-openai-preflight-v0.4"]


def build_synthetic_openai_preflight_request_v0_4() -> LLMExtractionRequestV03:
    """Build the reserved v0.4 request in the development-v0.3 family."""
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id=PREFLIGHT_EVIDENCE_ID,
        block_id=PREFLIGHT_BLOCK_ID,
        sequence=1,
        text=PREFLIGHT_SYNTHETIC_TEXT,
        location=SourceLocation(
            location_type=LocationType.DOCUMENT_METADATA,
            location_value="synthetic-preflight-v0.4",
        ),
    )
    return build_request_envelope_v0_3(
        invocation_role=InvocationRole.PRIMARY,
        request_id=PREFLIGHT_REQUEST_ID,
        source_id="S001",
        document_sha256=uppercase_sha256_bytes(
            PREFLIGHT_SYNTHETIC_TEXT.encode("utf-8")
        ),
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        evidence_blocks=(block,),
    )


class OpenAIPreflightSemanticDiagnosticV04(BaseModel):
    """Frozen counts and warning inventory with no raw provider output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_diagnostic_status: Literal[
        "expected_abstention", "valid_semantic_variance"
    ]
    entity_count: int = Field(ge=0)
    evidence_reference_count: int = Field(ge=0)
    candidate_fact_count: int = Field(ge=0)
    warnings: tuple[str, ...]

    @field_validator(
        "entity_count",
        "evidence_reference_count",
        "candidate_fact_count",
        mode="before",
    )
    @classmethod
    def reject_boolean_counts(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("semantic diagnostic counts must use integers")
        return value

    @field_validator("warnings", mode="after")
    @classmethod
    def validate_warning_inventory(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or item != item.strip() for item in value):
            raise ValueError("semantic warnings must be trimmed and nonblank")
        if value != tuple(sorted(value)):
            raise ValueError("semantic warnings must use canonical sorted order")
        return value

    @model_validator(mode="after")
    def validate_classification(self) -> OpenAIPreflightSemanticDiagnosticV04:
        expected = (
            self.entity_count == 0
            and self.evidence_reference_count == 0
            and self.candidate_fact_count == 0
            and self.warnings == (EXPECTED_ABSTENTION_WARNING,)
        )
        required = "expected_abstention" if expected else "valid_semantic_variance"
        if self.semantic_diagnostic_status != required:
            raise ValueError("semantic diagnostic classification is inconsistent")
        return self


def _build_semantic_diagnostic(
    result: CandidateExtractionResult,
) -> OpenAIPreflightSemanticDiagnosticV04:
    warnings = tuple(sorted(result.warnings))
    expected = (
        not result.entities
        and not result.evidence_references
        and not result.candidate_facts
        and warnings == (EXPECTED_ABSTENTION_WARNING,)
    )
    return OpenAIPreflightSemanticDiagnosticV04(
        semantic_diagnostic_status=(
            "expected_abstention" if expected else "valid_semantic_variance"
        ),
        entity_count=len(result.entities),
        evidence_reference_count=len(result.evidence_references),
        candidate_fact_count=len(result.candidate_facts),
        warnings=warnings,
    )


class OpenAIPreflightPostResponseMetadataV04(BaseModel):
    """Safe metadata retained for contractually valid returned responses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    returned_model_identifier: str
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    provider_public_metadata_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_public_metadata_field_paths: tuple[str, ...]
    version_provenance_observed_from_same_provider_call: Literal[True]
    provider_request_id: str
    provider_response_id: str
    provider_sdk_version: str
    raw_response_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    retry_count: Literal[0]

    @model_validator(mode="after")
    def validate_metadata(self) -> OpenAIPreflightPostResponseMetadataV04:
        for field_name in (
            "returned_model_identifier",
            "version_provenance_source_response_id",
            "provider_request_id",
            "provider_response_id",
            "provider_sdk_version",
        ):
            v0_1._require_trimmed(getattr(self, field_name), field_name)
        if self.version_provenance_source_response_id != self.provider_response_id:
            raise ValueError("version provenance must use the same response ID")
        v0_1._validate_provenance_path_inventory(
            self.model_version_or_snapshot_provenance,
            self.provider_public_metadata_field_paths,
        )
        if self.provider_sdk_version != OPENAI_REQUIRED_SDK_VERSION:
            raise ValueError("provider SDK version must equal the pinned version")
        if any(
            isinstance(value, bool)
            for value in (
                self.input_tokens,
                self.output_tokens,
                self.latency_ms,
            )
        ):
            raise ValueError("post-response numeric metadata must use integers")
        return self


class OpenAIPreflightPostResponseFailureV04(Stage4BError):
    """Technical output failure carrying only safe returned-response metadata."""

    def __init__(
        self,
        code: Stage4BErrorCode,
        metadata: OpenAIPreflightPostResponseMetadataV04,
    ) -> None:
        self.safe_metadata = OpenAIPreflightPostResponseMetadataV04.model_validate(
            metadata.model_dump(mode="python")
        )
        super().__init__(code, "OpenAI v0.4 response failed technical validation")


def _post_response_metadata(
    observation: OpenAIPreflightProviderObservation,
) -> OpenAIPreflightPostResponseMetadataV04:
    response = observation.response
    token_usage = response.token_usage
    if (
        token_usage is None
        or token_usage.input_tokens is None
        or token_usage.output_tokens is None
        or response.provider_request_id is None
        or response.provider_response_id is None
        or response.provider_sdk_version is None
        or response.retry_count != 0
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
            "returned response metadata is incomplete or reports a retry",
        )
    return OpenAIPreflightPostResponseMetadataV04(
        returned_model_identifier=response.model_identifier,
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
        version_provenance_observed_from_same_provider_call=(
            observation.observed_from_same_provider_call
        ),
        provider_request_id=response.provider_request_id,
        provider_response_id=response.provider_response_id,
        provider_sdk_version=response.provider_sdk_version,
        raw_response_sha256=response.raw_response_sha256,
        input_tokens=token_usage.input_tokens,
        output_tokens=token_usage.output_tokens,
        latency_ms=response.latency_ms,
        retry_count=0,
    )


class OpenAIPreflightRecordV04(BaseModel):
    """Canonical successful compatibility record for the v0.4 call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preflight_schema_version: Literal["0.4"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.4"]
    experiment_id: Literal["llm-extraction-baseline-v0.3"]
    authorization: OpenAIPreflightAuthorizationV04
    execution_timestamp_utc: datetime
    input_classification: Literal["synthetic_preflight_text"]
    provider_call_count: Literal[1]
    preflight_status: Literal["passed"]
    compatibility_status: Literal["passed"]
    semantic_diagnostic: OpenAIPreflightSemanticDiagnosticV04
    provider_identifier: Literal["openai"]
    api_surface: Literal["responses"]
    requested_model_alias: Literal["gpt-5.4-mini"]
    provider_configuration_id: Literal["openai-responses-text-strict-json-v0.2"]
    model_configuration_id: Literal["openai-gpt-5.4-mini-text-strict-json-v0.2"]
    request_id: str
    canonical_request_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    document_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    strict_schema_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    returned_model_identifier: str
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    provider_public_metadata_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_public_metadata_field_paths: tuple[str, ...]
    version_provenance_observed_from_same_provider_call: Literal[True]
    provider_request_id: str
    provider_response_id: str
    provider_sdk_version: str
    strict_schema_compatible: Literal[True]
    local_output_validation_status: Literal["valid"]
    raw_response_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    parsed_output_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
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
    preflight_record_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_validator("execution_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return v0_1._require_utc(value, "execution_timestamp_utc")

    @field_serializer("execution_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return v0_1._utc_json(value)

    @field_serializer("estimated_actual_cost_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @field_validator("model_version_or_snapshot_provenance", mode="after")
    @classmethod
    def validate_version_provenance(
        cls, value: ModelVersionOrSnapshotProvenance
    ) -> ModelVersionOrSnapshotProvenance:
        try:
            return v0_1._validated_version_provenance(value)
        except Stage4BError as error:
            raise ValueError(error.message) from error

    @field_validator("provider_public_metadata_field_paths", mode="after")
    @classmethod
    def validate_metadata_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return v0_1._validated_metadata_field_paths(value)

    @model_validator(mode="after")
    def validate_record(self) -> OpenAIPreflightRecordV04:
        for field_name in (
            "request_id",
            "returned_model_identifier",
            "version_provenance_source_response_id",
            "provider_request_id",
            "provider_response_id",
            "provider_sdk_version",
        ):
            v0_1._require_trimmed(getattr(self, field_name), field_name)
        if self.version_provenance_source_response_id != self.provider_response_id:
            raise ValueError(
                "version provenance source response ID must equal provider response ID"
            )
        v0_1._validate_provenance_path_inventory(
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

        request = build_synthetic_openai_preflight_request_v0_4()
        for field_name, expected in {
            "request_id": request.request_id,
            "canonical_request_sha256": request.canonical_request_sha256,
            "prompt_sha256": request.prompt_sha256,
            "document_sha256": request.document_sha256,
        }.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} differs from the synthetic request")

        schema = build_openai_candidate_schema_v0_3()
        payload = build_openai_responses_payload(
            request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3
        )
        if self.strict_schema_sha256 != uppercase_sha256_bytes(
            canonical_json_bytes(schema)
        ):
            raise ValueError("strict_schema_sha256 differs from the production schema")
        if self.provider_payload_sha256 != uppercase_sha256_bytes(
            canonical_json_bytes(payload)
        ):
            raise ValueError("provider_payload_sha256 differs from the exact payload")
        expected_cost = v0_1._estimated_cost(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            pricing=self.pricing_observation,
        )
        if self.estimated_actual_cost_usd != expected_cost:
            raise ValueError("estimated actual cost does not reconcile")
        expected_hash = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"preflight_record_sha256"})
            )
        )
        if self.preflight_record_sha256 != expected_hash:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_RECORD_HASH_MISMATCH,
                "preflight_record_sha256 does not match canonical record bytes",
            )
        return self


def _build_preflight_record(**values: Any) -> OpenAIPreflightRecordV04:
    provisional = OpenAIPreflightRecordV04.model_construct(
        **values,
        preflight_record_sha256="0" * 64,
    )
    record_hash = uppercase_sha256_bytes(
        canonical_json_bytes(
            provisional.model_dump(
                mode="json",
                exclude={"preflight_record_sha256"},
            )
        )
    )
    return OpenAIPreflightRecordV04.model_validate(
        {**values, "preflight_record_sha256": record_hash}
    )


def preflight_record_bytes(record: OpenAIPreflightRecordV04) -> bytes:
    """Return canonical v0.4 success bytes after full validation."""
    validated = OpenAIPreflightRecordV04.model_validate(
        record.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


def _validate_authorization(
    authorization: OpenAIPreflightAuthorizationV04,
) -> OpenAIPreflightAuthorizationV04:
    try:
        return OpenAIPreflightAuthorizationV04.model_validate(
            authorization.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "v0.4 preflight authorization is invalid",
        ) from error


def run_openai_synthetic_preflight(
    *,
    provider: OpenAIPreflightProvider,
    authorization: OpenAIPreflightAuthorizationV04,
    pricing_observation: OpenAIPricingObservation,
    data_controls_observation: OpenAIDataControlsObservation,
    clock: Callable[[], datetime],
) -> OpenAIPreflightRecordV04:
    """Run one v0.4 call; semantic variance cannot negate compatibility."""
    validated_authorization = _validate_authorization(authorization)
    execution_timestamp = v0_1._validated_execution_timestamp(clock)
    if validated_authorization.authorized_at_utc > execution_timestamp:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "preflight authorization must not postdate execution",
        )
    validated_pricing = v0_1._validate_terms_model(
        pricing_observation,
        OpenAIPricingObservation,
    )
    validated_data_controls = v0_1._validate_terms_model(
        data_controls_observation,
        OpenAIDataControlsObservation,
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

    request = build_synthetic_openai_preflight_request_v0_4()
    schema = build_openai_candidate_schema_v0_3()
    payload = build_openai_responses_payload(
        request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3
    )
    strict_schema_sha256 = uppercase_sha256_bytes(canonical_json_bytes(schema))
    provider_payload_sha256 = uppercase_sha256_bytes(canonical_json_bytes(payload))
    observation = v0_1._validated_provider_observation(
        provider.generate_preflight(request)
    )
    safe_metadata = _post_response_metadata(observation)

    output_failure_code: Stage4BErrorCode | None = None
    validated_output = None
    try:
        validated_output = validate_provider_output(request, observation.response)
    except Stage4BError as error:
        output_failure_code = error.code
    if output_failure_code is not None:
        raise OpenAIPreflightPostResponseFailureV04(
            output_failure_code,
            safe_metadata,
        )
    if validated_output is None:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "v0.4 output validation returned no result",
        )

    semantic_diagnostic = _build_semantic_diagnostic(
        validated_output.candidate_result
    )
    estimated_cost = v0_1._estimated_cost(
        input_tokens=safe_metadata.input_tokens,
        output_tokens=safe_metadata.output_tokens,
        pricing=validated_pricing,
    )
    return _build_preflight_record(
        preflight_schema_version=PREFLIGHT_SCHEMA_VERSION,
        preflight_id=PREFLIGHT_ID,
        experiment_id=EXPERIMENT_ID_V0_3,
        authorization=validated_authorization,
        execution_timestamp_utc=execution_timestamp,
        input_classification=PREFLIGHT_INPUT_CLASSIFICATION,
        provider_call_count=1,
        preflight_status="passed",
        compatibility_status="passed",
        semantic_diagnostic=semantic_diagnostic,
        provider_identifier=OPENAI_PROVIDER_IDENTIFIER,
        api_surface=OPENAI_API_SURFACE,
        requested_model_alias=OPENAI_REQUESTED_MODEL_ALIAS,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_3,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_3,
        request_id=request.request_id,
        canonical_request_sha256=request.canonical_request_sha256,
        prompt_sha256=request.prompt_sha256,
        document_sha256=request.document_sha256,
        strict_schema_sha256=strict_schema_sha256,
        provider_payload_sha256=provider_payload_sha256,
        returned_model_identifier=safe_metadata.returned_model_identifier,
        model_version_or_snapshot_provenance=(
            safe_metadata.model_version_or_snapshot_provenance
        ),
        version_provenance_source_response_id=(
            safe_metadata.version_provenance_source_response_id
        ),
        provider_public_metadata_sha256=(
            safe_metadata.provider_public_metadata_sha256
        ),
        provider_public_metadata_field_paths=(
            safe_metadata.provider_public_metadata_field_paths
        ),
        version_provenance_observed_from_same_provider_call=(
            safe_metadata.version_provenance_observed_from_same_provider_call
        ),
        provider_request_id=safe_metadata.provider_request_id,
        provider_response_id=safe_metadata.provider_response_id,
        provider_sdk_version=safe_metadata.provider_sdk_version,
        strict_schema_compatible=True,
        local_output_validation_status="valid",
        raw_response_sha256=safe_metadata.raw_response_sha256,
        parsed_output_sha256=validated_output.canonical_output_sha256,
        input_tokens=safe_metadata.input_tokens,
        output_tokens=safe_metadata.output_tokens,
        latency_ms=safe_metadata.latency_ms,
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
    "EXPECTED_ABSTENTION_WARNING",
    "PREFLIGHT_AUTHORIZATION_SCOPE",
    "PREFLIGHT_ID",
    "PREFLIGHT_INPUT_CLASSIFICATION",
    "OpenAIPreflightAuthorizationV04",
    "OpenAIPreflightPostResponseMetadataV04",
    "OpenAIPreflightRecordV04",
    "OpenAIPreflightSemanticDiagnosticV04",
    "build_synthetic_openai_preflight_request_v0_4",
    "preflight_record_bytes",
    "run_openai_synthetic_preflight",
]
