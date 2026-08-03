"""Strict Stage 4C invocation provenance and deterministic mock-run reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    InvocationRole,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    SHA256_PATTERN,
    absent_additive_provider_metadata,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


PROVENANCE_SCHEMA_VERSION: Literal["0.1"] = "0.1"
REPORT_SCHEMA_VERSION: Literal["0.1"] = "0.1"


class CacheStatus(str, Enum):
    """Whether this execution obtained a response from cache or provider."""

    HIT = "hit"
    MISS = "miss"


class ValidationStatus(str, Enum):
    """Deterministic local validation outcome for one response."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_ATTEMPTED = "not_attempted"


def _require_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must use UTC")
    return value


class AttemptProvenance(BaseModel):
    """One bounded provider attempt, separate from cache parsing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_number: int = Field(gt=0)
    terminal_status: ProviderTerminalStatus
    provider_call_performed: bool
    response_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    latency_ms: int | None = Field(default=None, ge=0)
    retry_reason: str | None = None
    failure_code: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> AttemptProvenance:
        if not self.provider_call_performed:
            raise ValueError("attempt provenance requires a provider call")
        if self.attempt_number == 1 and self.retry_reason is not None:
            raise ValueError("the first attempt must not contain a retry reason")
        if self.attempt_number > 1 and not self.retry_reason:
            raise ValueError("retry attempts require a retry reason")
        if self.terminal_status is ProviderTerminalStatus.SUCCESS:
            if self.failure_code is not None:
                raise ValueError("successful attempts must not contain a failure code")
        elif not self.failure_code:
            raise ValueError("unsuccessful attempts require a failure code")
        return self


class InvocationProvenance(BaseModel):
    """Complete local and original-call provenance for one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_schema_version: Literal["0.1"] = PROVENANCE_SCHEMA_VERSION
    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    request_id: str
    invocation_role: InvocationRole
    source_id: str
    provider_identifier: str | None = None
    model_identifier: str | None = None
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    provider_sdk_version: str | None = None
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_configuration_id: str
    model_configuration_id: str
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    cache_status: CacheStatus
    provider_call_performed: bool
    attempts: tuple[AttemptProvenance, ...] = Field(default_factory=tuple)
    original_attempts: tuple[AttemptProvenance, ...] = Field(default_factory=tuple)
    terminal_status: ProviderTerminalStatus
    raw_response_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    parsed_output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    validation_status: ValidationStatus
    warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    failure_codes: tuple[str, ...] = Field(default_factory=tuple)
    token_usage: ProviderTokenUsage | None = None
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    original_provider_call_timestamp: datetime | None = None
    local_parse_event_timestamp: datetime
    candidate_count: int = Field(default=0, ge=0)
    review_required_candidate_count: int = Field(default=0, ge=0)
    abstained: bool = False

    @field_validator(
        "original_provider_call_timestamp",
        "local_parse_event_timestamp",
    )
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value)

    @field_serializer("estimated_cost_usd", when_used="json")
    def serialize_cost(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")

    @model_validator(mode="after")
    def validate_provenance(self) -> InvocationProvenance:
        if self.provider_call_performed != bool(self.attempts):
            raise ValueError("provider_call_performed must reconcile with attempts")
        if (self.provider_identifier is None) != (self.model_identifier is None):
            raise ValueError("provider and model identifiers must be supplied together")
        if self.raw_response_sha256 is not None and self.provider_identifier is None:
            raise ValueError("response provenance requires provider and model identifiers")
        for value in (self.provider_identifier, self.model_identifier):
            if value is not None and (not value.strip() or value != value.strip()):
                raise ValueError("provider and model identifiers must be trimmed")
        provider_metadata = (
            self.provider_request_id,
            self.provider_response_id,
            self.provider_sdk_version,
        )
        for value in provider_metadata:
            if value is not None and (not value.strip() or value != value.strip()):
                raise ValueError("provider metadata values must be trimmed and non-blank")
        if any(value is not None for value in provider_metadata) and not all(
            value is not None for value in provider_metadata
        ):
            raise ValueError(
                "provider request ID, response ID, and SDK version must be "
                "supplied together"
            )
        if any(value is not None for value in provider_metadata) and (
            self.provider_identifier is None or self.model_identifier is None
        ):
            raise ValueError("provider metadata requires provider and model identifiers")
        if self.cache_status is CacheStatus.HIT and self.provider_call_performed:
            raise ValueError("cache hits must not be reported as provider calls")
        if self.cache_status is CacheStatus.HIT and not self.original_attempts:
            raise ValueError("cache hits must retain original attempt provenance")
        if self.cache_status is CacheStatus.MISS and (
            self.original_attempts != self.attempts
        ):
            raise ValueError("fresh responses must identify their current attempts")
        if self.validation_status is ValidationStatus.VALID:
            if self.parsed_output_sha256 is None:
                raise ValueError("valid output requires parsed_output_sha256")
        elif self.parsed_output_sha256 is not None:
            raise ValueError("non-valid output must not claim a parsed output hash")
        if self.terminal_status is not ProviderTerminalStatus.SUCCESS and (
            self.validation_status is not ValidationStatus.NOT_ATTEMPTED
        ):
            raise ValueError("unsuccessful responses must not claim local validation")
        if self.review_required_candidate_count > self.candidate_count:
            raise ValueError("review-required count exceeds candidate count")
        if self.abstained != (
            self.validation_status is ValidationStatus.VALID
            and self.candidate_count == 0
        ):
            raise ValueError("abstention must mean a valid zero-candidate output")
        for codes in (self.warning_codes, self.failure_codes):
            if any(not item.strip() or item != item.strip() for item in codes):
                raise ValueError("warning and failure codes must be trimmed")
            if len(codes) != len(set(codes)):
                raise ValueError("warning and failure codes must be unique")
        return self


class MockRunReport(BaseModel):
    """Deterministic aggregate for one mock-only Stage 4C execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_schema_version: Literal["0.1"] = REPORT_SCHEMA_VERSION
    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    invocation_total: int = Field(ge=0)
    primary_invocation_count: int = Field(ge=0)
    repeat_invocation_count: int = Field(ge=0)
    cache_hit_count: int = Field(ge=0)
    cache_miss_count: int = Field(ge=0)
    provider_call_count: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    successful_terminal_response_count: int = Field(ge=0)
    provider_failure_count: int = Field(ge=0)
    timeout_outcome_count: int = Field(ge=0)
    validation_success_count: int = Field(ge=0)
    validation_failure_count: int = Field(ge=0)
    abstention_count: int = Field(ge=0)
    review_required_output_count: int = Field(ge=0)
    total_reported_input_tokens: int = Field(ge=0)
    total_reported_output_tokens: int = Field(ge=0)
    total_estimated_cost_usd: Decimal = Field(ge=0)
    ordered_invocation_provenance: tuple[InvocationProvenance, ...]
    report_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_serializer("total_estimated_cost_usd", when_used="json")
    def serialize_total_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_report(self) -> MockRunReport:
        invocations = self.ordered_invocation_provenance
        expected = _report_counts(invocations)
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"{field_name} does not reconcile with provenance")
        payload = _mock_run_report_payload(self, include_hash=False)
        expected_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
        if self.report_sha256 != expected_hash:
            raise ValueError("report_sha256 does not match canonical report bytes")
        return self


def invocation_provenance_payload(
    provenance: InvocationProvenance,
) -> dict[str, object]:
    """Serialize provenance while preserving the pre-metadata null contract."""
    return provenance.model_dump(
        mode="json",
        exclude=absent_additive_provider_metadata(provenance),
    )


def _mock_run_report_payload(
    report: MockRunReport,
    *,
    include_hash: bool,
) -> dict[str, object]:
    payload = report.model_dump(
        mode="json",
        exclude={"ordered_invocation_provenance", "report_sha256"},
    )
    payload["ordered_invocation_provenance"] = [
        invocation_provenance_payload(item)
        for item in report.ordered_invocation_provenance
    ]
    if include_hash:
        payload["report_sha256"] = report.report_sha256
    return payload


def _report_counts(
    invocations: tuple[InvocationProvenance, ...],
) -> dict[str, int | Decimal]:
    input_tokens = sum(
        item.token_usage.input_tokens or 0
        for item in invocations
        if item.token_usage is not None
    )
    output_tokens = sum(
        item.token_usage.output_tokens or 0
        for item in invocations
        if item.token_usage is not None
    )
    return {
        "invocation_total": len(invocations),
        "primary_invocation_count": sum(
            item.invocation_role is InvocationRole.PRIMARY for item in invocations
        ),
        "repeat_invocation_count": sum(
            item.invocation_role is InvocationRole.REPEAT for item in invocations
        ),
        "cache_hit_count": sum(
            item.cache_status is CacheStatus.HIT for item in invocations
        ),
        "cache_miss_count": sum(
            item.cache_status is CacheStatus.MISS for item in invocations
        ),
        "provider_call_count": sum(len(item.attempts) for item in invocations),
        "attempt_count": sum(len(item.attempts) for item in invocations),
        "successful_terminal_response_count": sum(
            item.terminal_status is ProviderTerminalStatus.SUCCESS
            for item in invocations
        ),
        "provider_failure_count": sum(
            item.terminal_status is ProviderTerminalStatus.FAILURE
            for item in invocations
        ),
        "timeout_outcome_count": sum(
            item.terminal_status is ProviderTerminalStatus.TIMEOUT
            for item in invocations
        ),
        "validation_success_count": sum(
            item.validation_status is ValidationStatus.VALID for item in invocations
        ),
        "validation_failure_count": sum(
            item.validation_status is ValidationStatus.INVALID for item in invocations
        ),
        "abstention_count": sum(item.abstained for item in invocations),
        "review_required_output_count": sum(
            item.review_required_candidate_count > 0 for item in invocations
        ),
        "total_reported_input_tokens": input_tokens,
        "total_reported_output_tokens": output_tokens,
        "total_estimated_cost_usd": sum(
            (
                item.estimated_cost_usd or Decimal("0")
                if item.cache_status is CacheStatus.MISS
                else Decimal("0")
            )
            for item in invocations
        ),
    }


def build_mock_run_report(
    *,
    manifest_sha256: str,
    invocations: tuple[InvocationProvenance, ...],
) -> MockRunReport:
    """Build a reconciled self-hashed report in manifest invocation order."""
    counts = _report_counts(invocations)
    total_cost = counts["total_estimated_cost_usd"]
    if not isinstance(total_cost, Decimal):
        raise TypeError("total_estimated_cost_usd must be Decimal")
    payload = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "manifest_sha256": manifest_sha256,
        **counts,
        "total_estimated_cost_usd": format(total_cost, "f"),
        "ordered_invocation_provenance": [
            invocation_provenance_payload(item) for item in invocations
        ],
    }
    report_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
    return MockRunReport.model_validate({**payload, "report_sha256": report_hash})


def mock_run_report_bytes(report: MockRunReport) -> bytes:
    """Return canonical report bytes after complete reconciliation."""
    validated = MockRunReport.model_validate(report.model_dump(mode="python"))
    return canonical_json_bytes(
        _mock_run_report_payload(validated, include_hash=True)
    )


__all__ = [
    "PROVENANCE_SCHEMA_VERSION",
    "REPORT_SCHEMA_VERSION",
    "AttemptProvenance",
    "CacheStatus",
    "InvocationProvenance",
    "MockRunReport",
    "ValidationStatus",
    "build_mock_run_report",
    "invocation_provenance_payload",
    "mock_run_report_bytes",
]
