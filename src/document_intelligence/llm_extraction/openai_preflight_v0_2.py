"""Additive v0.2 contract for one future synthetic OpenAI preflight."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError, model_validator

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import openai_preflight as v0_1
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    ModelVersionOrSnapshotProvenance,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightProvider,
    OpenAIPreflightProviderObservation,
    OpenAIPreflightRecord,
    OpenAIPricingObservation,
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


PREFLIGHT_SCHEMA_VERSION: Literal["0.2"] = "0.2"
PREFLIGHT_ID: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.2"] = (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.2"
)
PREFLIGHT_AUTHORIZATION_SCOPE: Literal[
    "single-synthetic-openai-preflight-v0.2"
] = "single-synthetic-openai-preflight-v0.2"
PREFLIGHT_INPUT_CLASSIFICATION = v0_1.PREFLIGHT_INPUT_CLASSIFICATION
PREFLIGHT_REQUEST_ID = "synthetic-preflight-request-v0.2"
PREFLIGHT_EVIDENCE_ID = "synthetic-preflight-evidence-v0.2"
PREFLIGHT_BLOCK_ID = "synthetic-preflight-block-v0.2"
PREFLIGHT_SYNTHETIC_TEXT = v0_1.PREFLIGHT_SYNTHETIC_TEXT


class OpenAIPreflightAuthorizationV02(OpenAIPreflightAuthorization):
    """Explicit authorization scoped only to the separate v0.2 call."""

    scope: Literal["single-synthetic-openai-preflight-v0.2"]


def build_synthetic_openai_preflight_request() -> LLMExtractionRequest:
    """Build the distinct v0.2 request with unchanged synthetic semantics."""
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id=PREFLIGHT_EVIDENCE_ID,
        block_id=PREFLIGHT_BLOCK_ID,
        sequence=1,
        text=PREFLIGHT_SYNTHETIC_TEXT,
        location=SourceLocation(
            location_type=LocationType.DOCUMENT_METADATA,
            location_value="synthetic-preflight-v0.2",
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


class OpenAIPreflightRecordV02(OpenAIPreflightRecord):
    """Canonical successful record for the separately authorized v0.2 call."""

    preflight_schema_version: Literal["0.2"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.2"]
    authorization: OpenAIPreflightAuthorizationV02

    @model_validator(mode="after")
    def validate_record(self) -> OpenAIPreflightRecordV02:
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

        expected_cost = v0_1._estimated_cost(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            pricing=self.pricing_observation,
        )
        if self.estimated_actual_cost_usd != expected_cost:
            raise ValueError("estimated actual cost does not reconcile")

        expected_hash = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(
                    mode="json",
                    exclude={"preflight_record_sha256"},
                )
            )
        )
        if self.preflight_record_sha256 != expected_hash:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_RECORD_HASH_MISMATCH,
                "preflight_record_sha256 does not match canonical record bytes",
            )
        return self


def _build_preflight_record(**values: Any) -> OpenAIPreflightRecordV02:
    provisional = OpenAIPreflightRecordV02.model_construct(
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
    return OpenAIPreflightRecordV02.model_validate(
        {**values, "preflight_record_sha256": record_hash}
    )


def preflight_record_bytes(record: OpenAIPreflightRecordV02) -> bytes:
    """Return canonical v0.2 success bytes after full validation."""
    validated = OpenAIPreflightRecordV02.model_validate(
        record.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


def _validate_authorization(
    authorization: OpenAIPreflightAuthorizationV02,
) -> OpenAIPreflightAuthorizationV02:
    try:
        return OpenAIPreflightAuthorizationV02.model_validate(
            authorization.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_AUTHORIZATION_INVALID,
            "v0.2 preflight authorization is invalid",
        ) from error


def run_openai_synthetic_preflight(
    *,
    provider: OpenAIPreflightProvider,
    authorization: OpenAIPreflightAuthorizationV02,
    pricing_observation: OpenAIPricingObservation,
    data_controls_observation: OpenAIDataControlsObservation,
    clock: Callable[[], datetime],
) -> OpenAIPreflightRecordV02:
    """Run one authorized v0.2 call through unchanged output validation."""
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

    request = build_synthetic_openai_preflight_request()
    schema = build_openai_candidate_schema()
    payload = build_openai_responses_payload(request)
    strict_schema_sha256 = uppercase_sha256_bytes(canonical_json_bytes(schema))
    provider_payload_sha256 = uppercase_sha256_bytes(canonical_json_bytes(payload))
    observation: OpenAIPreflightProviderObservation = (
        v0_1._validated_provider_observation(provider.generate_preflight(request))
    )
    response = observation.response
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
    estimated_cost = v0_1._estimated_cost(
        input_tokens=token_usage.input_tokens,
        output_tokens=token_usage.output_tokens,
        pricing=validated_pricing,
    )
    version_provenance: ModelVersionOrSnapshotProvenance = (
        observation.model_version_or_snapshot_provenance
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
    "PREFLIGHT_AUTHORIZATION_SCOPE",
    "PREFLIGHT_ID",
    "PREFLIGHT_INPUT_CLASSIFICATION",
    "OpenAIPreflightAuthorizationV02",
    "OpenAIPreflightRecordV02",
    "build_synthetic_openai_preflight_request",
    "preflight_record_bytes",
    "run_openai_synthetic_preflight",
]
