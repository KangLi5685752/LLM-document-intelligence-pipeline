"""Mock-only Stage 4C manifest runner with bounded retries and provenance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from document_intelligence.extraction.models import CandidateReviewStatus
from document_intelligence.llm_extraction.cache import (
    CacheIdentity,
    ResponseCache,
    build_cache_record,
)
from document_intelligence.llm_extraction.contracts import (
    InvocationRole,
    LLMProviderResponse,
    ProviderTerminalStatus,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.manifest import (
    RequestManifest,
    validate_request_manifest,
)
from document_intelligence.llm_extraction.provenance import (
    AttemptProvenance,
    CacheStatus,
    InvocationProvenance,
    MockRunReport,
    ValidationStatus,
    build_mock_run_report,
)
from document_intelligence.llm_extraction.provider import LLMProvider
from document_intelligence.llm_extraction.validation import validate_provider_output


MAX_PRIMARY_INVOCATIONS = 100
MAX_REPEAT_INVOCATIONS = 10
MAX_RETRIES_PER_INVOCATION = 1
MAX_TOTAL_ATTEMPTS = 220
MAX_RESPONSE_TIMEOUT_SECONDS = 120
MAX_TOTAL_ESTIMATED_COST_USD = Decimal("25")


class ExecutionBudget(BaseModel):
    """Explicit limits that may narrow but never widen the Stage 4 contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_primary_invocations: int = Field(
        default=MAX_PRIMARY_INVOCATIONS, ge=0, le=MAX_PRIMARY_INVOCATIONS
    )
    max_repeat_invocations: int = Field(
        default=MAX_REPEAT_INVOCATIONS, ge=0, le=MAX_REPEAT_INVOCATIONS
    )
    max_retries_per_invocation: int = Field(
        default=MAX_RETRIES_PER_INVOCATION,
        ge=0,
        le=MAX_RETRIES_PER_INVOCATION,
    )
    max_total_attempts: int = Field(
        default=MAX_TOTAL_ATTEMPTS, ge=0, le=MAX_TOTAL_ATTEMPTS
    )
    response_timeout_seconds: int = Field(
        default=MAX_RESPONSE_TIMEOUT_SECONDS,
        gt=0,
        le=MAX_RESPONSE_TIMEOUT_SECONDS,
    )
    max_total_estimated_cost_usd: Decimal = Field(
        default=MAX_TOTAL_ESTIMATED_COST_USD,
        ge=0,
        le=MAX_TOTAL_ESTIMATED_COST_USD,
    )
    estimated_cost_per_attempt_usd: Decimal = Field(default=Decimal("0"), ge=0)
    retryable_failure_codes: tuple[str, ...] = (
        "transport_error",
        "rate_limit",
        "timeout",
    )

    @field_serializer(
        "max_total_estimated_cost_usd",
        "estimated_cost_per_attempt_usd",
        when_used="json",
    )
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_codes(self) -> ExecutionBudget:
        if any(
            not code.strip() or code != code.strip()
            for code in self.retryable_failure_codes
        ):
            raise ValueError("retryable failure codes must be trimmed and non-blank")
        if len(self.retryable_failure_codes) != len(
            set(self.retryable_failure_codes)
        ):
            raise ValueError("retryable failure codes must be unique")
        return self


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "the injected execution clock must return timezone-aware UTC",
        )
    if value.utcoffset() != timedelta(0):
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "the injected execution clock must return UTC",
        )
    return value


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _check_manifest_budget(
    manifest: RequestManifest, budget: ExecutionBudget
) -> None:
    primary_count = sum(
        item.invocation_role is InvocationRole.PRIMARY
        for item in manifest.invocations
    )
    repeat_count = len(manifest.invocations) - primary_count
    if (
        primary_count > budget.max_primary_invocations
        or repeat_count > budget.max_repeat_invocations
    ):
        raise Stage4BError(
            Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
            "manifest invocation counts exceed the configured execution budget",
        )


def _check_attempt_budget(
    *,
    attempts_so_far: int,
    estimated_cost_so_far: Decimal,
    budget: ExecutionBudget,
) -> None:
    if attempts_so_far + 1 > budget.max_total_attempts:
        raise Stage4BError(
            Stage4BErrorCode.ATTEMPT_BUDGET_EXCEEDED,
            "the next provider attempt would exceed the configured attempt budget",
        )
    if (
        estimated_cost_so_far + budget.estimated_cost_per_attempt_usd
        > budget.max_total_estimated_cost_usd
    ):
        raise Stage4BError(
            Stage4BErrorCode.COST_BUDGET_EXCEEDED,
            "the next provider attempt would exceed the configured cost budget",
        )


def _attempt_from_response(
    *,
    attempt_number: int,
    response: LLMProviderResponse,
    retry_reason: str | None,
) -> AttemptProvenance:
    failure_code = (
        response.failure_codes[0]
        if response.terminal_status is not ProviderTerminalStatus.SUCCESS
        else None
    )
    return AttemptProvenance(
        attempt_number=attempt_number,
        terminal_status=response.terminal_status,
        provider_call_performed=True,
        response_sha256=response.raw_response_sha256,
        latency_ms=response.latency_ms,
        retry_reason=retry_reason,
        failure_code=failure_code,
    )


def run_mock_development(
    *,
    manifest: RequestManifest,
    provider: LLMProvider,
    cache: ResponseCache,
    clock: Callable[[], datetime],
    budget: ExecutionBudget | None = None,
) -> MockRunReport:
    """Run one validated manifest without discovery, gold, matching, or network I/O."""
    selected_budget = budget or ExecutionBudget()
    validated_manifest = validate_request_manifest(manifest)
    _check_manifest_budget(validated_manifest, selected_budget)

    invocation_provenance: list[InvocationProvenance] = []
    attempts_so_far = 0
    estimated_cost_so_far = Decimal("0")

    for invocation in validated_manifest.invocations:
        request = invocation.request
        validate_development_source_id(request.source_id)
        identity = CacheIdentity.from_request(request)
        current_attempts: tuple[AttemptProvenance, ...] = ()
        original_attempts: tuple[AttemptProvenance, ...]
        original_timestamp: datetime | None
        invocation_cost = Decimal("0")
        response: LLMProviderResponse | None = None
        cache_status = CacheStatus.HIT

        try:
            cached = cache.read(identity)
        except Stage4BError as error:
            if error.code is not Stage4BErrorCode.CACHE_MISS:
                raise
            cache_status = CacheStatus.MISS
            attempts: list[AttemptProvenance] = []
            retry_reason: str | None = None
            provider_error_code: str | None = None
            original_timestamp = None

            for attempt_number in range(
                1, selected_budget.max_retries_per_invocation + 2
            ):
                _check_attempt_budget(
                    attempts_so_far=attempts_so_far,
                    estimated_cost_so_far=estimated_cost_so_far,
                    budget=selected_budget,
                )
                call_timestamp = _utc_now(clock)
                attempts_so_far += 1
                invocation_cost += selected_budget.estimated_cost_per_attempt_usd
                estimated_cost_so_far += selected_budget.estimated_cost_per_attempt_usd
                original_timestamp = call_timestamp
                try:
                    response = provider.generate(request)
                except Stage4BError as provider_error:
                    response = None
                    provider_error_code = provider_error.code.value
                    attempts.append(
                        AttemptProvenance(
                            attempt_number=attempt_number,
                            terminal_status=(
                                ProviderTerminalStatus.TIMEOUT
                                if provider_error.code is Stage4BErrorCode.TIMEOUT
                                else ProviderTerminalStatus.FAILURE
                            ),
                            provider_call_performed=True,
                            response_sha256=None,
                            latency_ms=None,
                            retry_reason=retry_reason,
                            failure_code=provider_error_code,
                        )
                    )
                    if (
                        provider_error_code
                        in selected_budget.retryable_failure_codes
                        and attempt_number
                        <= selected_budget.max_retries_per_invocation
                    ):
                        retry_reason = provider_error_code
                        continue
                    break

                if response.retry_count != 0:
                    raise Stage4BError(
                        Stage4BErrorCode.RETRY_NOT_PERMITTED,
                        "provider-side retries are not permitted by the Stage 4C runner",
                    )
                attempt = _attempt_from_response(
                    attempt_number=attempt_number,
                    response=response,
                    retry_reason=retry_reason,
                )
                attempts.append(attempt)
                if response.terminal_status is ProviderTerminalStatus.SUCCESS:
                    break
                provider_error_code = attempt.failure_code
                if (
                    provider_error_code in selected_budget.retryable_failure_codes
                    and attempt_number <= selected_budget.max_retries_per_invocation
                ):
                    retry_reason = provider_error_code
                    continue
                break

            current_attempts = tuple(attempts)
            original_attempts = current_attempts
            if response is not None and (
                response.terminal_status is ProviderTerminalStatus.SUCCESS
            ):
                if original_timestamp is None:
                    raise Stage4BError(
                        Stage4BErrorCode.EXECUTION_FAILED,
                        "successful provider response is missing its call timestamp",
                    )
                record = build_cache_record(
                    identity=identity,
                    response=response,
                    original_provider_call_timestamp=original_timestamp,
                    original_attempts=original_attempts,
                    estimated_cost_usd=invocation_cost,
                )
                cache.append(record)
        else:
            response = cached.response
            original_timestamp = cached.original_provider_call_timestamp
            original_attempts = cached.original_attempts
            invocation_cost = cached.estimated_cost_usd

        parse_timestamp = _utc_now(clock)
        parsed_output_hash: str | None = None
        validation_status = ValidationStatus.NOT_ATTEMPTED
        warning_codes: tuple[str, ...] = ()
        failure_codes: tuple[str, ...] = ()
        candidate_count = 0
        review_required_count = 0
        abstained = False

        if response is None:
            terminal_status = (
                current_attempts[-1].terminal_status
                if current_attempts
                else ProviderTerminalStatus.FAILURE
            )
            if current_attempts:
                last_code = current_attempts[-1].failure_code
                failure_codes = (last_code,) if last_code is not None else ()
            token_usage = None
            latency_ms = None
            raw_response_hash = None
        else:
            terminal_status = response.terminal_status
            warning_codes = response.warning_codes
            failure_codes = response.failure_codes
            token_usage = response.token_usage
            latency_ms = response.latency_ms
            raw_response_hash = response.raw_response_sha256
            if terminal_status is ProviderTerminalStatus.SUCCESS:
                try:
                    validated_output = validate_provider_output(request, response)
                except Stage4BError as validation_error:
                    validation_status = ValidationStatus.INVALID
                    failure_codes = _ordered_unique(
                        (*failure_codes, validation_error.code.value)
                    )
                else:
                    validation_status = ValidationStatus.VALID
                    parsed_output_hash = validated_output.canonical_output_sha256
                    candidate_count = len(
                        validated_output.candidate_result.candidate_facts
                    )
                    review_required_count = sum(
                        fact.review_status is CandidateReviewStatus.REQUIRED
                        for fact in validated_output.candidate_result.candidate_facts
                    )
                    abstained = candidate_count == 0

        invocation_provenance.append(
            InvocationProvenance(
                manifest_sha256=validated_manifest.manifest_sha256,
                request_id=request.request_id,
                invocation_role=request.invocation_role,
                source_id=request.source_id,
                provider_identifier=(
                    response.provider_identifier if response is not None else None
                ),
                model_identifier=(
                    response.model_identifier if response is not None else None
                ),
                provider_request_id=(
                    response.provider_request_id if response is not None else None
                ),
                provider_response_id=(
                    response.provider_response_id if response is not None else None
                ),
                provider_sdk_version=(
                    response.provider_sdk_version if response is not None else None
                ),
                canonical_request_sha256=request.canonical_request_sha256,
                provider_configuration_id=request.provider_configuration_id,
                model_configuration_id=request.model_configuration_id,
                prompt_sha256=request.prompt_sha256,
                document_sha256=request.document_sha256,
                cache_status=cache_status,
                provider_call_performed=bool(current_attempts),
                attempts=current_attempts,
                original_attempts=original_attempts,
                terminal_status=terminal_status,
                raw_response_sha256=raw_response_hash,
                parsed_output_sha256=parsed_output_hash,
                validation_status=validation_status,
                warning_codes=warning_codes,
                failure_codes=failure_codes,
                token_usage=token_usage,
                estimated_cost_usd=invocation_cost,
                latency_ms=latency_ms,
                original_provider_call_timestamp=original_timestamp,
                local_parse_event_timestamp=parse_timestamp,
                candidate_count=candidate_count,
                review_required_candidate_count=review_required_count,
                abstained=abstained,
            )
        )

    return build_mock_run_report(
        manifest_sha256=validated_manifest.manifest_sha256,
        invocations=tuple(invocation_provenance),
    )


__all__ = [
    "MAX_PRIMARY_INVOCATIONS",
    "MAX_REPEAT_INVOCATIONS",
    "MAX_RETRIES_PER_INVOCATION",
    "MAX_RESPONSE_TIMEOUT_SECONDS",
    "MAX_TOTAL_ATTEMPTS",
    "MAX_TOTAL_ESTIMATED_COST_USD",
    "ExecutionBudget",
    "run_mock_development",
]
