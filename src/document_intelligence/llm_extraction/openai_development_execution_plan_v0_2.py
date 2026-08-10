"""Immutable no-call plan for bounded Stage 4D v0.2 development execution."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    model_validator,
)

from document_intelligence.llm_extraction import (
    openai_preflight_execution as preflight_execution,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentAccessPolicyV01,
    OpenAIDevelopmentManifestV02,
    canonical_lf_json_bytes,
    load_development_manifest_v0_2,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


EXECUTION_PLAN_SCHEMA_VERSION: Literal["0.2"] = "0.2"
EXECUTION_ID: Literal[
    "openai-gpt-5.4-mini-five-source-development-execution-v0.2"
] = "openai-gpt-5.4-mini-five-source-development-execution-v0.2"
AUTHORIZATION_SCOPE: Literal[
    "bounded-five-source-openai-development-execution-v0.2"
] = "bounded-five-source-openai-development-execution-v0.2"

MANIFEST_RELATIVE_PATH: Literal[
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
] = (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
)
MANIFEST_SELF_SHA256: Literal[
    "16D9524377677F271CE7C33880B3E69E11A0157491FC8218A7666F8C5577D35C"
] = "16D9524377677F271CE7C33880B3E69E11A0157491FC8218A7666F8C5577D35C"
MANIFEST_CANONICAL_LF_SHA256: Literal[
    "04FF2499BF346D8CB73B2DC03196E7FEE74B5DFF601F79CAC86F4C7B84D3BA3B"
] = "04FF2499BF346D8CB73B2DC03196E7FEE74B5DFF601F79CAC86F4C7B84D3BA3B"
MANIFEST_ARTIFACT_BYTES: Literal[90575] = 90575

EXECUTION_ROOT = (
    "reports/llm_extraction/openai_development_execution/"
    "openai-gpt-5.4-mini-five-source-development-v0.2"
)
ATTEMPT_MARKER_ROOT = f"{EXECUTION_ROOT}/attempts"
FAILURE_RECORD_ROOT = f"{EXECUTION_ROOT}/failures"
EXECUTION_RECORD_PATH = f"{EXECUTION_ROOT}/execution-record.json"

EXPECTED_EXECUTION_PLAN_SHA256: Literal[
    "25588680A1362AC0192A378CD54288AA2DF5584F4C6108E3467BA06DA68AACE9"
] = "25588680A1362AC0192A378CD54288AA2DF5584F4C6108E3467BA06DA68AACE9"


def _canonical_model_hash(model: BaseModel, hash_field: str) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(
            model.model_dump(mode="json", exclude={hash_field})
        )
    )


class DevelopmentExecutionManifestBindingV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: Literal[
        "reports/llm_extraction/openai_development_manifest/"
        "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
    ] = MANIFEST_RELATIVE_PATH
    manifest_sha256: Literal[
        "16D9524377677F271CE7C33880B3E69E11A0157491FC8218A7666F8C5577D35C"
    ] = MANIFEST_SELF_SHA256
    canonical_lf_content_sha256: Literal[
        "04FF2499BF346D8CB73B2DC03196E7FEE74B5DFF601F79CAC86F4C7B84D3BA3B"
    ] = MANIFEST_CANONICAL_LF_SHA256
    artifact_bytes: Literal[90575] = MANIFEST_ARTIFACT_BYTES


class DevelopmentExecutionProviderBindingV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_identifier: Literal["openai"]
    requested_model_alias: Literal["gpt-5.4-mini"]
    returned_preflight_model_identifier: Literal[
        "gpt-5.4-mini-2026-03-17"
    ]
    model_version_or_snapshot_provenance: Literal["unavailable"]
    provider_sdk_version: Literal["2.46.0"]
    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.1"
    ]
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.1"
    ]
    output_contract_id: Literal["candidate-extraction-result-0.1"]
    response_schema_name: Literal["candidate_extraction_result_0_1"]
    strict_schema_sha256: Literal[
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    ]


class DevelopmentExecutionControlsV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    maximum_provider_calls: Literal[8]
    maximum_total_attempts: Literal[8]
    maximum_retries_per_invocation: Literal[0]
    maximum_transaction_retries: Literal[0]
    provider_side_retries: Literal[0]
    response_timeout_seconds: Literal[120]
    maximum_output_tokens_per_invocation: Literal[4096]
    planned_authorization_cap_usd: Decimal
    aggregate_conservative_cost_ceiling_usd: Decimal
    maximum_output_token_budget: Literal[32768]
    same_day_pricing_review_required: Literal[True]
    same_day_data_controls_review_required: Literal[True]

    @field_serializer(
        "planned_authorization_cap_usd",
        "aggregate_conservative_cost_ceiling_usd",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_costs(self) -> DevelopmentExecutionControlsV02:
        if self.planned_authorization_cap_usd != Decimal("1.25"):
            raise ValueError("planned authorization cap must be exactly USD 1.25")
        if (
            self.aggregate_conservative_cost_ceiling_usd
            != Decimal("1.000869")
        ):
            raise ValueError(
                "aggregate conservative cost must match the frozen manifest"
            )
        if (
            self.aggregate_conservative_cost_ceiling_usd
            >= self.planned_authorization_cap_usd
        ):
            raise ValueError("conservative cost must remain below authorization cap")
        return self


class DevelopmentExecutionCachePolicyV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_cache_root: Literal[
        ".cache/llm_extraction/llm-extraction-baseline-v0.2/openai/"
    ]
    read_before_attempt_marker: Literal[True]
    append_only: Literal[True]
    cache_replacement_allowed: Literal[False]
    cache_bypass_allowed: Literal[False]
    successful_responses_only: Literal[True]


class DevelopmentExecutionArtifactPolicyV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_marker_root: Literal[
        "reports/llm_extraction/openai_development_execution/"
        "openai-gpt-5.4-mini-five-source-development-v0.2/attempts"
    ]
    failure_record_root: Literal[
        "reports/llm_extraction/openai_development_execution/"
        "openai-gpt-5.4-mini-five-source-development-v0.2/failures"
    ]
    execution_record_path: Literal[
        "reports/llm_extraction/openai_development_execution/"
        "openai-gpt-5.4-mini-five-source-development-v0.2/"
        "execution-record.json"
    ]
    attempt_marker_installed_before_client_construction: Literal[True]
    attempt_marker_installed_before_credential_access: Literal[True]
    provider_response_cache_installed_before_local_validation: Literal[True]
    failure_record_sanitized_and_self_hashed: Literal[True]
    execution_record_installed_only_after_all_invocations_valid: Literal[True]
    execution_record_installed_exclusively_and_last: Literal[True]


class DevelopmentExecutionPartialFailurePolicyV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stop_after_first_provider_or_local_failure: Literal[True]
    completed_cache_records_are_preserved: Literal[True]
    attempt_without_cache_is_not_retryable_in_v0_2: Literal[True]
    cache_after_local_parse_failure_is_reusable: Literal[True]
    automatic_retry_or_overwrite_is_forbidden: Literal[True]


class DevelopmentExecutionAuthorizationBindingV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    explicit_project_owner_authorization_required: Literal[True]
    authorization_must_bind_execution_plan_sha256: Literal[True]
    authorization_must_bind_manifest_sha256: Literal[True]
    authorization_must_bind_maximum_provider_calls: Literal[8]
    authorization_must_bind_maximum_total_attempts: Literal[8]
    authorization_must_bind_cost_cap_usd: Decimal
    authorization_not_created_by_readiness: Literal[True]

    @field_serializer(
        "authorization_must_bind_cost_cap_usd",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_cost_cap(
        self,
    ) -> DevelopmentExecutionAuthorizationBindingV02:
        if self.authorization_must_bind_cost_cap_usd != Decimal("1.25"):
            raise ValueError("authorization must bind the exact USD 1.25 cap")
        return self


class DevelopmentExecutionInvocationPlanV02(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_order: int = Field(gt=0)
    source_id: Literal["S001", "S002", "S003", "S004", "S006"]
    invocation_role: Literal["primary", "repeat"]
    request_id: str
    repeated_primary_request_id: str | None
    canonical_request_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    strict_schema_sha256: Literal[
        "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
    ]
    provider_payload_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    cache_identity_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_bytes: int = Field(gt=0, le=200000)
    maximum_output_tokens: Literal[4096]
    conservative_call_ceiling_usd: Decimal
    attempt_marker_relative_path: str
    failure_record_relative_path: str

    @field_serializer("conservative_call_ceiling_usd", when_used="json")
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_paths_and_role(
        self,
    ) -> DevelopmentExecutionInvocationPlanV02:
        expected_attempt = (
            f"{ATTEMPT_MARKER_ROOT}/"
            f"{self.cache_identity_sha256}.attempt.json"
        )
        expected_failure = (
            f"{FAILURE_RECORD_ROOT}/"
            f"{self.cache_identity_sha256}.failure.json"
        )
        if self.attempt_marker_relative_path != expected_attempt:
            raise ValueError("attempt marker path does not match cache identity")
        if self.failure_record_relative_path != expected_failure:
            raise ValueError("failure record path does not match cache identity")
        if self.invocation_role == "primary":
            if self.repeated_primary_request_id is not None:
                raise ValueError("primary invocation cannot repeat another request")
            if "-primary-" not in self.request_id:
                raise ValueError("primary request ID does not match its role")
        else:
            if self.request_id != "llm-v0.2-S004-repeat-001":
                raise ValueError("repeat request ID differs from the frozen plan")
            if (
                self.repeated_primary_request_id
                != "llm-v0.2-S004-primary-001"
            ):
                raise ValueError("repeat-primary binding differs from the manifest")
        return self


class OpenAIDevelopmentExecutionPlanV02(BaseModel):
    """Self-hashed no-call plan; this model does not authorize execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_plan_schema_version: Literal["0.2"]
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.2"
    ]
    authorization_scope: Literal[
        "bounded-five-source-openai-development-execution-v0.2"
    ]
    manifest_binding: DevelopmentExecutionManifestBindingV02
    provider_binding: DevelopmentExecutionProviderBindingV02
    execution_controls: DevelopmentExecutionControlsV02
    cache_policy: DevelopmentExecutionCachePolicyV02
    artifact_policy: DevelopmentExecutionArtifactPolicyV02
    partial_failure_policy: DevelopmentExecutionPartialFailurePolicyV02
    authorization_binding: DevelopmentExecutionAuthorizationBindingV02
    access_policy: OpenAIDevelopmentAccessPolicyV01
    invocations: tuple[DevelopmentExecutionInvocationPlanV02, ...] = Field(
        min_length=8,
        max_length=8,
    )
    execution_plan_sha256: Literal[
        "25588680A1362AC0192A378CD54288AA2DF5584F4C6108E3467BA06DA68AACE9"
    ]

    @model_validator(mode="after")
    def validate_plan(self) -> OpenAIDevelopmentExecutionPlanV02:
        orders = [item.invocation_order for item in self.invocations]
        if orders != list(range(1, 9)):
            raise ValueError("invocation order must be exactly 1..8")
        request_ids = [item.request_id for item in self.invocations]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("request IDs must be globally unique")
        cache_ids = [item.cache_identity_sha256 for item in self.invocations]
        if len(cache_ids) != len(set(cache_ids)):
            raise ValueError("cache identities must be globally unique")
        primary = [
            item for item in self.invocations
            if item.invocation_role == "primary"
        ]
        repeat = [
            item for item in self.invocations
            if item.invocation_role == "repeat"
        ]
        if len(primary) != 7 or len(repeat) != 1:
            raise ValueError("plan must contain seven primaries and one repeat")
        if self.invocations[-1] != repeat[0]:
            raise ValueError("repeat invocation must appear last")
        source_counts = {
            source_id: sum(item.source_id == source_id for item in primary)
            for source_id in ("S001", "S002", "S003", "S004", "S006")
        }
        if source_counts != {
            "S001": 1,
            "S002": 1,
            "S003": 1,
            "S004": 3,
            "S006": 1,
        }:
            raise ValueError("primary source distribution differs from manifest")
        if (
            sum(
                item.conservative_call_ceiling_usd
                for item in self.invocations
            )
            != self.execution_controls
            .aggregate_conservative_cost_ceiling_usd
        ):
            raise ValueError("invocation conservative costs do not reconcile")
        if self.execution_plan_sha256 != _canonical_model_hash(
            self,
            "execution_plan_sha256",
        ):
            raise ValueError(
                "execution_plan_sha256 does not match canonical plan content"
            )
        return self


def build_openai_development_execution_plan_v0_2(
    manifest: OpenAIDevelopmentManifestV02,
) -> OpenAIDevelopmentExecutionPlanV02:
    """Build the exact reviewed no-call plan from one frozen manifest."""

    try:
        validated_manifest = OpenAIDevelopmentManifestV02.model_validate(
            manifest.model_dump(mode="python")
        )
    except ValidationError as error:
        raise ValueError("development manifest is invalid") from error

    if validated_manifest.manifest_sha256 != MANIFEST_SELF_SHA256:
        raise ValueError("development manifest identity differs from the frozen input")

    invocation_values = tuple(
        {
            "invocation_order": item.invocation_order,
            "source_id": item.source_id,
            "invocation_role": item.invocation_role.value,
            "request_id": item.request_id,
            "repeated_primary_request_id": item.repeated_primary_request_id,
            "canonical_request_sha256": item.canonical_request_sha256,
            "prompt_sha256": item.prompt_sha256,
            "strict_schema_sha256": item.strict_schema_sha256,
            "provider_payload_sha256": item.provider_payload_sha256,
            "cache_identity_sha256": item.cache_identity_sha256,
            "provider_payload_bytes": item.provider_payload_bytes,
            "maximum_output_tokens": item.maximum_output_tokens,
            "conservative_call_ceiling_usd": format(
                item.conservative_call_ceiling_usd,
                "f",
            ),
            "attempt_marker_relative_path": (
                f"{ATTEMPT_MARKER_ROOT}/"
                f"{item.cache_identity_sha256}.attempt.json"
            ),
            "failure_record_relative_path": (
                f"{FAILURE_RECORD_ROOT}/"
                f"{item.cache_identity_sha256}.failure.json"
            ),
        }
        for item in validated_manifest.invocations
    )

    values: dict[str, Any] = {
        "execution_plan_schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "execution_id": EXECUTION_ID,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "manifest_binding": {
            "relative_path": MANIFEST_RELATIVE_PATH,
            "manifest_sha256": MANIFEST_SELF_SHA256,
            "canonical_lf_content_sha256": MANIFEST_CANONICAL_LF_SHA256,
            "artifact_bytes": MANIFEST_ARTIFACT_BYTES,
        },
        "provider_binding": {
            "provider_identifier": validated_manifest.provider_identifier,
            "requested_model_alias": validated_manifest.requested_model_alias,
            "returned_preflight_model_identifier": (
                validated_manifest.returned_preflight_model_identifier
            ),
            "model_version_or_snapshot_provenance": (
                validated_manifest.model_version_or_snapshot_provenance
            ),
            "provider_sdk_version": validated_manifest.provider_sdk_version,
            "provider_configuration_id": (
                validated_manifest.provider_configuration_id
            ),
            "model_configuration_id": (
                validated_manifest.model_configuration_id
            ),
            "output_contract_id": "candidate-extraction-result-0.1",
            "response_schema_name": "candidate_extraction_result_0_1",
            "strict_schema_sha256": validated_manifest.strict_schema_sha256,
        },
        "execution_controls": {
            "maximum_provider_calls": (
                validated_manifest.execution_budget.maximum_provider_calls
            ),
            "maximum_total_attempts": (
                validated_manifest.execution_budget.maximum_total_attempts
            ),
            "maximum_retries_per_invocation": (
                validated_manifest.execution_budget
                .maximum_retries_per_invocation
            ),
            "maximum_transaction_retries": 0,
            "provider_side_retries": (
                validated_manifest.execution_budget.provider_side_retries
            ),
            "response_timeout_seconds": (
                validated_manifest.execution_budget.response_timeout_seconds
            ),
            "maximum_output_tokens_per_invocation": 4096,
            "planned_authorization_cap_usd": format(
                validated_manifest.execution_budget
                .planned_authorization_cap_usd,
                "f",
            ),
            "aggregate_conservative_cost_ceiling_usd": format(
                validated_manifest.execution_budget
                .aggregate_conservative_cost_ceiling_usd,
                "f",
            ),
            "maximum_output_token_budget": (
                validated_manifest.execution_budget
                .maximum_output_token_budget
            ),
            "same_day_pricing_review_required": True,
            "same_day_data_controls_review_required": True,
        },
        "cache_policy": {
            "relative_cache_root": (
                validated_manifest.cache_policy.relative_cache_root
            ),
            "read_before_attempt_marker": True,
            "append_only": True,
            "cache_replacement_allowed": False,
            "cache_bypass_allowed": False,
            "successful_responses_only": True,
        },
        "artifact_policy": {
            "attempt_marker_root": ATTEMPT_MARKER_ROOT,
            "failure_record_root": FAILURE_RECORD_ROOT,
            "execution_record_path": EXECUTION_RECORD_PATH,
            "attempt_marker_installed_before_client_construction": True,
            "attempt_marker_installed_before_credential_access": True,
            "provider_response_cache_installed_before_local_validation": True,
            "failure_record_sanitized_and_self_hashed": True,
            "execution_record_installed_only_after_all_invocations_valid": True,
            "execution_record_installed_exclusively_and_last": True,
        },
        "partial_failure_policy": {
            "stop_after_first_provider_or_local_failure": True,
            "completed_cache_records_are_preserved": True,
            "attempt_without_cache_is_not_retryable_in_v0_2": True,
            "cache_after_local_parse_failure_is_reusable": True,
            "automatic_retry_or_overwrite_is_forbidden": True,
        },
        "authorization_binding": {
            "explicit_project_owner_authorization_required": True,
            "authorization_must_bind_execution_plan_sha256": True,
            "authorization_must_bind_manifest_sha256": True,
            "authorization_must_bind_maximum_provider_calls": 8,
            "authorization_must_bind_maximum_total_attempts": 8,
            "authorization_must_bind_cost_cap_usd": "1.25",
            "authorization_not_created_by_readiness": True,
        },
        "access_policy": validated_manifest.access_policy.model_dump(
            mode="json"
        ),
        "invocations": invocation_values,
    }

    plan_hash = uppercase_sha256_bytes(canonical_json_bytes(values))
    if plan_hash != EXPECTED_EXECUTION_PLAN_SHA256:
        raise ValueError("derived execution plan identity differs from readiness")

    return OpenAIDevelopmentExecutionPlanV02.model_validate(
        {
            **values,
            "execution_plan_sha256": plan_hash,
        }
    )


def development_execution_plan_bytes_v0_2(
    plan: OpenAIDevelopmentExecutionPlanV02,
) -> bytes:
    """Return canonical UTF-8 plan bytes followed by exactly one LF."""

    validated = OpenAIDevelopmentExecutionPlanV02.model_validate(
        plan.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json")) + b"\n"


def load_development_execution_plan_v0_2(
    path: Path,
) -> OpenAIDevelopmentExecutionPlanV02:
    """Load a canonical LF or CRLF v0.2 plan and validate its self-hash."""

    try:
        raw = preflight_execution._read_validated_descriptor(
            path, label="v0.2 execution plan"
        )
    except Exception as error:
        raise ValueError("v0.2 execution plan must be a safe regular file") from error
    canonical = canonical_lf_json_bytes(raw)
    try:
        plan = OpenAIDevelopmentExecutionPlanV02.model_validate_json(canonical)
    except ValidationError as error:
        raise ValueError("v0.2 execution plan contract is invalid") from error
    if development_execution_plan_bytes_v0_2(plan) != canonical:
        raise ValueError("v0.2 execution plan bytes are not canonical")
    return plan


def write_development_execution_plan_v0_2(
    path: Path,
    plan: OpenAIDevelopmentExecutionPlanV02,
) -> None:
    """Install one canonical v0.2 plan without overwriting an existing path."""

    payload = development_execution_plan_bytes_v0_2(plan)
    try:
        safe_path = preflight_execution._validate_path_chain(
            path, label="v0.2 execution plan"
        )
        safe_parent = preflight_execution._validate_path_chain(
            safe_path.parent, label="v0.2 execution-plan parent"
        )
        if safe_path != path.absolute() or not safe_parent.is_dir():
            raise ValueError
    except Exception as error:
        raise ValueError(
            "v0.2 execution-plan path must use a safe existing parent"
        ) from error
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            safe_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        created = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created and os.path.lexists(safe_path):
            safe_path.unlink()
        raise
    if preflight_execution._read_validated_descriptor(
        safe_path, label="installed v0.2 execution plan"
    ) != payload:
        raise ValueError("installed v0.2 execution plan failed byte verification")


def build_plan_from_frozen_manifest_v0_2(
    manifest_path: Path,
) -> OpenAIDevelopmentExecutionPlanV02:
    """Load the frozen manifest and derive its exact no-call execution plan."""

    return build_openai_development_execution_plan_v0_2(
        load_development_manifest_v0_2(manifest_path)
    )


__all__ = [
    "ATTEMPT_MARKER_ROOT",
    "AUTHORIZATION_SCOPE",
    "DevelopmentExecutionArtifactPolicyV02",
    "DevelopmentExecutionAuthorizationBindingV02",
    "DevelopmentExecutionCachePolicyV02",
    "DevelopmentExecutionControlsV02",
    "DevelopmentExecutionInvocationPlanV02",
    "DevelopmentExecutionManifestBindingV02",
    "DevelopmentExecutionPartialFailurePolicyV02",
    "DevelopmentExecutionProviderBindingV02",
    "EXECUTION_ID",
    "EXECUTION_PLAN_SCHEMA_VERSION",
    "EXECUTION_RECORD_PATH",
    "EXPECTED_EXECUTION_PLAN_SHA256",
    "FAILURE_RECORD_ROOT",
    "MANIFEST_ARTIFACT_BYTES",
    "MANIFEST_CANONICAL_LF_SHA256",
    "MANIFEST_RELATIVE_PATH",
    "MANIFEST_SELF_SHA256",
    "OpenAIDevelopmentExecutionPlanV02",
    "build_openai_development_execution_plan_v0_2",
    "build_plan_from_frozen_manifest_v0_2",
    "development_execution_plan_bytes_v0_2",
    "load_development_execution_plan_v0_2",
    "write_development_execution_plan_v0_2",
]
