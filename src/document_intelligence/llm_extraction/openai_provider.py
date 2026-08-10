"""Narrow OpenAI Responses API adapter for Stage 4D-1."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from importlib.metadata import version as package_version
from typing import Any, Final, Literal, Protocol, TypeAlias

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.extraction.predicates import PREDICATE_DEFINITIONS
from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequest,
    LLMExtractionRequestAny,
    LLMExtractionRequestV02,
    LLMExtractionRequestV03,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    canonical_prompt_bytes,
    validate_request_identity,
)


OPENAI_PROVIDER_IDENTIFIER: Literal["openai"] = "openai"
OPENAI_API_SURFACE: Literal["responses"] = "responses"
OPENAI_REQUESTED_MODEL_ALIAS: Literal["gpt-5.4-mini"] = "gpt-5.4-mini"
OPENAI_PROVIDER_CONFIGURATION_ID: Literal[
    "openai-responses-text-strict-json-v0.1"
] = "openai-responses-text-strict-json-v0.1"
OPENAI_MODEL_CONFIGURATION_ID: Literal[
    "openai-gpt-5.4-mini-text-strict-json-v0.1"
] = "openai-gpt-5.4-mini-text-strict-json-v0.1"
OPENAI_RESPONSE_SCHEMA_NAME: Literal[
    "candidate_extraction_result_0_1"
] = "candidate_extraction_result_0_1"
OPENAI_PROVIDER_CONFIGURATION_ID_V0_3: Literal[
    "openai-responses-text-strict-json-v0.2"
] = "openai-responses-text-strict-json-v0.2"
OPENAI_MODEL_CONFIGURATION_ID_V0_3: Literal[
    "openai-gpt-5.4-mini-text-strict-json-v0.2"
] = "openai-gpt-5.4-mini-text-strict-json-v0.2"
OPENAI_RESPONSE_SCHEMA_NAME_V0_3: Literal[
    "candidate_extraction_result_0_1_aliases_empty_v0_3"
] = "candidate_extraction_result_0_1_aliases_empty_v0_3"
OPENAI_REQUIRED_SDK_VERSION: Literal["2.46.0"] = "2.46.0"
OPENAI_INSTALLED_SDK_VERSION = package_version("openai")
OPENAI_MAX_TIMEOUT_SECONDS = 120.0
OPENAI_MAX_OUTPUT_TOKENS: Final[Literal[4096]] = 4096
OPENAI_REASONING_EFFORT: Final[Literal["none"]] = "none"
_SAFE_PROVIDER_DIAGNOSTIC_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")


class OpenAIProviderFailureDiagnostics(BaseModel):
    """Immutable allowlisted fields extracted from one SDK status failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    http_status_code: int | None = Field(default=None, ge=100, le=599)
    provider_error_type: str | None = None
    provider_error_code: str | None = None
    provider_request_id: str | None = None

    @field_validator("http_status_code", mode="before")
    @classmethod
    def validate_status_code(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("http_status_code must use an integer")
        return value

    @field_validator(
        "provider_error_type",
        "provider_error_code",
        "provider_request_id",
        mode="before",
    )
    @classmethod
    def validate_safe_text(cls, value: object) -> object:
        if value is None:
            return None
        if type(value) is not str or _SAFE_PROVIDER_DIAGNOSTIC_PATTERN.fullmatch(
            value
        ) is None:
            raise ValueError("provider diagnostic text is not safely representable")
        return value


class OpenAIProviderFailure(Stage4BError):
    """Stable provider failure carrying only sanitized immutable diagnostics."""

    def __init__(
        self,
        code: Stage4BErrorCode,
        diagnostics: OpenAIProviderFailureDiagnostics,
    ) -> None:
        if code not in {
            Stage4BErrorCode.RATE_LIMIT,
            Stage4BErrorCode.PROVIDER_API_FAILURE,
        }:
            raise ValueError("provider status failure code is not supported")
        self.diagnostics = OpenAIProviderFailureDiagnostics.model_validate(
            diagnostics.model_dump(mode="python")
        )
        message = (
            "OpenAI Responses request was rate limited"
            if code is Stage4BErrorCode.RATE_LIMIT
            else "OpenAI Responses API returned a non-retryable failure"
        )
        super().__init__(code, message)


def _safe_provider_diagnostic(value: object) -> str | None:
    if type(value) is not str:
        return None
    if _SAFE_PROVIDER_DIAGNOSTIC_PATTERN.fullmatch(value) is None:
        return None
    return value


def _status_failure(
    error: APIStatusError,
    code: Stage4BErrorCode,
) -> OpenAIProviderFailure:
    status = getattr(error, "status_code", None)
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    diagnostics = OpenAIProviderFailureDiagnostics(
        http_status_code=status,
        provider_error_type=_safe_provider_diagnostic(getattr(error, "type", None)),
        provider_error_code=_safe_provider_diagnostic(getattr(error, "code", None)),
        provider_request_id=_safe_provider_diagnostic(
            getattr(error, "request_id", None)
        ),
    )
    return OpenAIProviderFailure(code, diagnostics)


class OpenAIResponsesConfiguration(BaseModel):
    """Immutable exact configuration for the first OpenAI comparator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_identifier: Literal["openai"] = OPENAI_PROVIDER_IDENTIFIER
    api_surface: Literal["responses"] = OPENAI_API_SURFACE
    requested_model_alias: Literal["gpt-5.4-mini"] = (
        OPENAI_REQUESTED_MODEL_ALIAS
    )
    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.1"
    ] = OPENAI_PROVIDER_CONFIGURATION_ID
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.1"
    ] = OPENAI_MODEL_CONFIGURATION_ID
    response_schema_name: Literal[
        "candidate_extraction_result_0_1"
    ] = OPENAI_RESPONSE_SCHEMA_NAME
    max_output_tokens: Literal[4096]
    reasoning_effort: Literal["none"]
    timeout_seconds: float = Field(
        default=OPENAI_MAX_TIMEOUT_SECONDS,
        gt=0,
        le=OPENAI_MAX_TIMEOUT_SECONDS,
    )

    @field_validator("max_output_tokens", mode="before")
    @classmethod
    def _require_exact_max_output_tokens(cls, value: object) -> object:
        if type(value) is not int or value != OPENAI_MAX_OUTPUT_TOKENS:
            raise ValueError("max_output_tokens must be exactly 4096")
        return value

    @field_validator("reasoning_effort", mode="before")
    @classmethod
    def _require_exact_reasoning_effort(cls, value: object) -> object:
        if type(value) is not str or value != OPENAI_REASONING_EFFORT:
            raise ValueError("reasoning_effort must be exactly none")
        return value


DEFAULT_OPENAI_RESPONSES_CONFIGURATION = OpenAIResponsesConfiguration(
    max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
    reasoning_effort=OPENAI_REASONING_EFFORT,
)


class OpenAIResponsesConfigurationV03(OpenAIResponsesConfiguration):
    """Immutable additive configuration for the alias-safe v0.3 boundary."""

    provider_configuration_id: Literal[
        "openai-responses-text-strict-json-v0.2"
    ] = OPENAI_PROVIDER_CONFIGURATION_ID_V0_3
    model_configuration_id: Literal[
        "openai-gpt-5.4-mini-text-strict-json-v0.2"
    ] = OPENAI_MODEL_CONFIGURATION_ID_V0_3
    response_schema_name: Literal[
        "candidate_extraction_result_0_1_aliases_empty_v0_3"
    ] = OPENAI_RESPONSE_SCHEMA_NAME_V0_3


DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3 = OpenAIResponsesConfigurationV03(
    max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
    reasoning_effort=OPENAI_REASONING_EFFORT,
)
OpenAIResponsesConfigurationAny: TypeAlias = (
    OpenAIResponsesConfiguration | OpenAIResponsesConfigurationV03
)


class ResponsesResource(Protocol):
    """Public-shape subset used from an injected Responses resource."""

    def create(self, **kwargs: Any) -> Any:
        """Create one response using explicit request keyword arguments."""
        ...


class ConfiguredOpenAIClient(Protocol):
    """Public-shape subset returned by the SDK's with_options method."""

    responses: ResponsesResource


class OpenAIClient(Protocol):
    """Dependency-injected public client surface used by the adapter."""

    def with_options(
        self,
        *,
        max_retries: int,
        timeout: float,
    ) -> ConfiguredOpenAIClient:
        """Return a client with bounded timeout and retries disabled."""
        ...


@dataclass(frozen=True)
class _OpenAIResponsesCallResult:
    """Transient mapped response plus the exact SDK response from one call."""

    response: LLMProviderResponse
    sdk_response: object


def _validated_request(request: LLMExtractionRequestAny) -> LLMExtractionRequestAny:
    validate_request_identity(request)
    validate_development_source_id(request.source_id)
    try:
        request_type = (
            LLMExtractionRequestV03
            if isinstance(request, LLMExtractionRequestV03)
            else (
                LLMExtractionRequestV02
                if isinstance(request, LLMExtractionRequestV02)
                else LLMExtractionRequest
            )
        )
        return request_type.model_validate(request.model_dump(mode="python"))
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_PROVIDER_REQUEST,
            "request does not satisfy the existing provider-neutral contract",
        ) from error


def _strictify_declared_objects(schema: Any) -> None:
    """Close declared objects, require their properties, and remove defaults."""
    if isinstance(schema, dict):
        schema.pop("default", None)
        if schema.get("type") == "object":
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                raise ValueError("strict object schemas must declare properties")
            schema["additionalProperties"] = False
            schema["required"] = list(properties)
        for value in schema.values():
            _strictify_declared_objects(value)
    elif isinstance(schema, list):
        for value in schema:
            _strictify_declared_objects(value)


def _qualifier_property_schema(
    qualifier_value_schema: dict[str, Any],
    *,
    nullable: bool,
) -> dict[str, Any]:
    branches = deepcopy(qualifier_value_schema.get("anyOf"))
    if not isinstance(branches, list):
        raise ValueError("QualifierValue must remain represented by anyOf")
    if not nullable:
        branches = [branch for branch in branches if branch.get("type") != "null"]
    return {"anyOf": branches}


def audit_openai_strict_schema(schema: dict[str, Any]) -> None:
    """Raise when a generated schema violates the required strict object rules."""
    if schema.get("type") != "object":
        raise ValueError("the strict provider schema root must be an object")

    def audit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "default" in node:
                raise ValueError(f"default is forbidden at {path}")
            if node.get("type") == "object":
                properties = node.get("properties")
                if not isinstance(properties, dict):
                    raise ValueError(f"object properties are missing at {path}")
                if node.get("additionalProperties") is not False:
                    raise ValueError(f"object is not closed at {path}")
                required = node.get("required")
                if required != list(properties):
                    raise ValueError(
                        f"required must exactly cover declared properties at {path}"
                    )
            for key, value in node.items():
                audit(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                audit(value, f"{path}/{index}")

    audit(schema, "#")


def build_openai_candidate_schema() -> dict[str, Any]:
    """Derive a closed strict schema from CandidateExtractionResult 0.1."""
    schema = deepcopy(
        CandidateExtractionResult.model_json_schema(mode="serialization")
    )
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        raise ValueError("CandidateExtractionResult schema must define $defs")
    candidate_fact = definitions.get("CandidateFact")
    if not isinstance(candidate_fact, dict):
        raise ValueError("CandidateExtractionResult schema must define CandidateFact")
    candidate_properties = candidate_fact.get("properties")
    if not isinstance(candidate_properties, dict):
        raise ValueError("CandidateFact schema must declare properties")
    qualifiers = candidate_properties.get("qualifiers")
    if not isinstance(qualifiers, dict):
        raise ValueError("CandidateFact schema must define qualifiers")
    qualifier_value_schema = qualifiers.get("additionalProperties")
    if not isinstance(qualifier_value_schema, dict):
        raise ValueError("qualifiers must remain derived from QualifierValue")

    candidate_properties["qualifiers"] = {
        "additionalProperties": False,
        "properties": {},
        "required": [],
        "title": qualifiers.get("title", "Qualifiers"),
        "type": "object",
    }
    _strictify_declared_objects(schema)
    strict_candidate_fact = deepcopy(candidate_fact)
    variants: list[dict[str, Any]] = []
    for definition in PREDICATE_DEFINITIONS:
        variant = deepcopy(strict_candidate_fact)
        properties = variant["properties"]
        properties["predicate"] = {
            "const": definition.name,
            "type": "string",
        }
        properties["extraction_method"] = {
            "const": "llm",
            "type": "string",
        }
        properties["subject_type"] = {
            "enum": [item.value for item in definition.allowed_subject_types],
            "type": "string",
        }
        properties["value_type"] = {
            "enum": [item.value for item in definition.allowed_value_types],
            "type": "string",
        }
        qualifier_properties = {
            name: _qualifier_property_schema(
                qualifier_value_schema,
                nullable=False,
            )
            for name in definition.required_qualifiers
        }
        qualifier_properties.update(
            {
                name: _qualifier_property_schema(
                    qualifier_value_schema,
                    nullable=True,
                )
                for name in definition.optional_qualifiers
            }
        )
        properties["qualifiers"] = {
            "additionalProperties": False,
            "properties": qualifier_properties,
            "required": list(qualifier_properties),
            "type": "object",
        }
        variant["required"] = list(properties)
        variants.append(variant)

    definitions["CandidateFact"] = {"anyOf": variants}
    audit_openai_strict_schema(schema)
    return schema


def build_openai_candidate_schema_v0_3() -> dict[str, Any]:
    """Derive the additive v0.3 schema with provider aliases fixed empty."""
    schema = deepcopy(build_openai_candidate_schema())
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        raise ValueError("CandidateExtractionResult schema must define $defs")
    candidate_entity = definitions.get("CandidateEntity")
    if not isinstance(candidate_entity, dict):
        raise ValueError("CandidateExtractionResult schema must define CandidateEntity")
    properties = candidate_entity.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("CandidateEntity schema must declare properties")
    aliases = properties.get("aliases")
    if not isinstance(aliases, dict) or aliases.get("type") != "array":
        raise ValueError("CandidateEntity aliases must remain an array")
    aliases["maxItems"] = 0
    audit_openai_strict_schema(schema)
    return schema


def build_openai_responses_payload(
    request: LLMExtractionRequestAny,
    configuration: OpenAIResponsesConfigurationAny = (
        DEFAULT_OPENAI_RESPONSES_CONFIGURATION
    ),
) -> dict[str, Any]:
    """Build a deterministic text-only Responses payload without client access."""
    validated = _validated_request(request)
    request_is_v0_3 = isinstance(validated, LLMExtractionRequestV03)
    configuration_is_v0_3 = isinstance(
        configuration, OpenAIResponsesConfigurationV03
    )
    if request_is_v0_3 != configuration_is_v0_3:
        raise Stage4BError(
            Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH,
            "request version does not match the OpenAI adapter configuration",
        )
    if (
        validated.provider_configuration_id
        != configuration.provider_configuration_id
    ):
        raise Stage4BError(
            Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH,
            "request provider_configuration_id does not match the OpenAI adapter",
        )
    if validated.model_configuration_id != configuration.model_configuration_id:
        raise Stage4BError(
            Stage4BErrorCode.MODEL_CONFIGURATION_MISMATCH,
            "request model_configuration_id does not match the OpenAI adapter",
        )

    prompt_payload = json.loads(
        canonical_prompt_bytes(
            evidence_blocks=validated.evidence_blocks,
            model_configuration_id=validated.model_configuration_id,
            prompt_version=validated.prompt_version,
            output_contract_id=validated.output_contract_id,
        )
    )
    ordered_blocks = canonical_json_bytes(
        prompt_payload["ordered_evidence_blocks"]
    ).decode("utf-8")
    user_text = (
        f"{prompt_payload['extraction_prompt']}\n\n"
        f"Ordered evidence blocks (canonical JSON):\n{ordered_blocks}"
    )
    output_schema = (
        build_openai_candidate_schema_v0_3()
        if request_is_v0_3
        else build_openai_candidate_schema()
    )

    return {
        "model": configuration.requested_model_alias,
        "max_output_tokens": configuration.max_output_tokens,
        "reasoning": {"effort": configuration.reasoning_effort},
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt_payload["system_prompt"],
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": configuration.response_schema_name,
                "strict": True,
                "schema": output_schema,
            }
        },
        "store": False,
        "stream": False,
        "background": False,
        "tools": [],
        "tool_choice": "none",
    }


def _required_provider_text(response: Any, attribute: str) -> str:
    value = getattr(response, attribute, None)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise Stage4BError(
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
            f"completed response is missing valid {attribute}",
        )
    return value


def _exact_output_text(response: Any) -> str:
    text_parts: list[str] = []
    for output_item in getattr(response, "output", ()) or ():
        if getattr(output_item, "type", None) != "message":
            continue
        for content_item in getattr(output_item, "content", ()) or ():
            content_type = getattr(content_item, "type", None)
            if content_type == "refusal":
                raise Stage4BError(
                    Stage4BErrorCode.PROVIDER_REFUSAL,
                    "completed response contains a provider refusal",
                )
            if content_type == "output_text":
                text = getattr(content_item, "text", None)
                if isinstance(text, str):
                    text_parts.append(text)
    if len(text_parts) != 1 or not text_parts[0].strip():
        raise Stage4BError(
            Stage4BErrorCode.MISSING_OUTPUT_TEXT,
            "completed response must contain exactly one usable output text item",
        )
    return text_parts[0]


def _token_usage(response: Any) -> ProviderTokenUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    values: dict[str, int | None] = {}
    for target_name, provider_name in (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
    ):
        value = getattr(usage, provider_name, None)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise Stage4BError(
                Stage4BErrorCode.MISSING_PROVIDER_METADATA,
                f"provider usage {provider_name} must be a non-negative integer",
            )
        values[target_name] = value
    return ProviderTokenUsage(**values)


class OpenAIResponsesProvider:
    """Synchronous injected-client adapter with no credential discovery."""

    def __init__(
        self,
        *,
        client: OpenAIClient,
        configuration: OpenAIResponsesConfigurationAny = (
            DEFAULT_OPENAI_RESPONSES_CONFIGURATION
        ),
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if client is None:
            raise TypeError("client must be an already constructed client object")
        if OPENAI_INSTALLED_SDK_VERSION != OPENAI_REQUIRED_SDK_VERSION:
            raise RuntimeError(
                "installed OpenAI SDK version does not match the pinned adapter version"
            )
        self._client = client
        self._configuration = configuration
        self._clock = clock

    @property
    def configuration(self) -> OpenAIResponsesConfigurationAny:
        """Return the immutable adapter configuration."""
        return self._configuration

    def generate(self, request: LLMExtractionRequestAny) -> LLMProviderResponse:
        """Perform one non-retrying call after complete local request validation."""
        return self._execute(request).response

    def _execute(
        self, request: LLMExtractionRequestAny
    ) -> _OpenAIResponsesCallResult:
        """Perform and map one call while transiently retaining its SDK response."""
        payload = build_openai_responses_payload(request, self._configuration)
        started = self._clock()
        failure: Stage4BError | None = None
        response: Any | None = None
        try:
            configured_client = self._client.with_options(
                max_retries=0,
                timeout=self._configuration.timeout_seconds,
            )
            response = configured_client.responses.create(**payload)
        except APITimeoutError:
            failure = Stage4BError(
                Stage4BErrorCode.TIMEOUT,
                "OpenAI Responses request timed out",
            )
        except RateLimitError as error:
            failure = _status_failure(error, Stage4BErrorCode.RATE_LIMIT)
        except APIConnectionError:
            failure = Stage4BError(
                Stage4BErrorCode.TRANSPORT_ERROR,
                "OpenAI Responses transport failed",
            )
        except APIStatusError as error:
            failure = _status_failure(
                error,
                Stage4BErrorCode.PROVIDER_API_FAILURE,
            )
        except APIError:
            failure = Stage4BError(
                Stage4BErrorCode.PROVIDER_API_FAILURE,
                "OpenAI SDK reported a non-retryable provider failure",
            )
        if failure is not None:
            raise failure
        if response is None:
            raise Stage4BError(
                Stage4BErrorCode.PROVIDER_API_FAILURE,
                "OpenAI SDK returned no response",
            )
        elapsed_seconds = self._clock() - started
        latency_ms = max(0, round(elapsed_seconds * 1000))

        status = getattr(response, "status", None)
        if status == "incomplete":
            raise Stage4BError(
                Stage4BErrorCode.INCOMPLETE_RESPONSE,
                "OpenAI response is incomplete",
            )
        if status == "failed":
            raise Stage4BError(
                Stage4BErrorCode.FAILED_RESPONSE,
                "OpenAI response has failed status",
            )
        if status != "completed":
            raise Stage4BError(
                Stage4BErrorCode.RESPONSE_NOT_COMPLETED,
                "OpenAI response is not terminal and completed",
            )

        model_identifier = _required_provider_text(response, "model")
        provider_response_id = _required_provider_text(response, "id")
        provider_request_id = _required_provider_text(response, "_request_id")
        raw_response = _exact_output_text(response)
        return _OpenAIResponsesCallResult(
            response=LLMProviderResponse(
                request_id=request.request_id,
                provider_identifier=self._configuration.provider_identifier,
                model_identifier=model_identifier,
                provider_request_id=provider_request_id,
                provider_response_id=provider_response_id,
                provider_sdk_version=OPENAI_INSTALLED_SDK_VERSION,
                terminal_status=ProviderTerminalStatus.SUCCESS,
                raw_response=raw_response,
                raw_response_sha256=uppercase_sha256(raw_response),
                token_usage=_token_usage(response),
                latency_ms=latency_ms,
                retry_count=0,
            ),
            sdk_response=response,
        )


__all__ = [
    "DEFAULT_OPENAI_RESPONSES_CONFIGURATION",
    "DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3",
    "OPENAI_API_SURFACE",
    "OPENAI_INSTALLED_SDK_VERSION",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "OPENAI_MAX_TIMEOUT_SECONDS",
    "OPENAI_MODEL_CONFIGURATION_ID",
    "OPENAI_MODEL_CONFIGURATION_ID_V0_3",
    "OPENAI_PROVIDER_CONFIGURATION_ID",
    "OPENAI_PROVIDER_CONFIGURATION_ID_V0_3",
    "OPENAI_PROVIDER_IDENTIFIER",
    "OPENAI_REQUESTED_MODEL_ALIAS",
    "OPENAI_REQUIRED_SDK_VERSION",
    "OPENAI_REASONING_EFFORT",
    "OPENAI_RESPONSE_SCHEMA_NAME",
    "OPENAI_RESPONSE_SCHEMA_NAME_V0_3",
    "OpenAIProviderFailure",
    "OpenAIProviderFailureDiagnostics",
    "OpenAIResponsesConfiguration",
    "OpenAIResponsesConfigurationAny",
    "OpenAIResponsesConfigurationV03",
    "OpenAIResponsesProvider",
    "audit_openai_strict_schema",
    "build_openai_candidate_schema",
    "build_openai_candidate_schema_v0_3",
    "build_openai_responses_payload",
]
