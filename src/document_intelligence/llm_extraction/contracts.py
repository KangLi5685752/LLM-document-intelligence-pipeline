"""Provider-neutral Stage 4B request, response, and validation contracts."""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.ingestion.models import SourceLocation
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)


EXPERIMENT_ID_V0_1: Literal["llm-extraction-baseline-v0.1"] = (
    "llm-extraction-baseline-v0.1"
)
EXPERIMENT_ID_V0_2: Literal["llm-extraction-baseline-v0.2"] = (
    "llm-extraction-baseline-v0.2"
)
EXPERIMENT_ID_V0_3: Literal["llm-extraction-baseline-v0.3"] = (
    "llm-extraction-baseline-v0.3"
)
PROMPT_VERSION_V0_1: Literal["0.1"] = "0.1"
PROMPT_VERSION_V0_2: Literal["0.2"] = "0.2"
PROMPT_VERSION_V0_3: Literal["0.3"] = "0.3"
EXPERIMENT_ID: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID_V0_1
PROMPT_VERSION: Literal["0.1"] = PROMPT_VERSION_V0_1
OUTPUT_CONTRACT_ID: Literal["candidate-extraction-result-0.1"] = (
    "candidate-extraction-result-0.1"
)
APPROVED_DEVELOPMENT_SOURCE_IDS = frozenset(
    {"S001", "S002", "S003", "S004", "S006"}
)
SHA256_PATTERN = r"^[0-9A-F]{64}$"
ADDITIVE_PROVIDER_METADATA_FIELDS = frozenset(
    {
        "provider_request_id",
        "provider_response_id",
        "provider_sdk_version",
    }
)


def _require_trimmed(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    return value


def validate_development_source_id(source_id: str) -> str:
    """Validate the pure Stage 4 development allowlist without file access."""
    if source_id not in APPROVED_DEVELOPMENT_SOURCE_IDS:
        raise Stage4BError(
            Stage4BErrorCode.PROHIBITED_SOURCE,
            f"source_id {source_id!r} is not approved for Stage 4 development",
        )
    return source_id


def uppercase_sha256(value: str) -> str:
    """Return the uppercase SHA-256 of the exact UTF-8 representation."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


class InvocationRole(str, Enum):
    """Predeclared logical invocation roles."""

    PRIMARY = "primary"
    REPEAT = "repeat"


class ProviderTerminalStatus(str, Enum):
    """Terminal provider outcomes represented without retry orchestration."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


class ApprovedEvidenceBlock(BaseModel):
    """One ordered, approved Common Document Object block envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    evidence_id: str
    block_id: str
    sequence: int = Field(gt=0)
    text: str
    location: SourceLocation

    @model_validator(mode="after")
    def validate_block(self) -> ApprovedEvidenceBlock:
        """Require approved source identity and explicit existing location data."""
        validate_development_source_id(self.source_id)
        for field_name in ("evidence_id", "block_id"):
            _require_trimmed(getattr(self, field_name), field_name)
        if not self.text.strip():
            raise ValueError("text must not be blank")
        return self


class LLMExtractionRequest(BaseModel):
    """Small canonical request envelope accepted by a provider transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    invocation_role: InvocationRole
    request_id: str
    source_id: str
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_version: Literal["0.1"] = PROMPT_VERSION
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_configuration_id: str
    model_configuration_id: str
    output_contract_id: Literal["candidate-extraction-result-0.1"] = (
        OUTPUT_CONTRACT_ID
    )
    evidence_blocks: tuple[ApprovedEvidenceBlock, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_request(self) -> LLMExtractionRequest:
        """Enforce one approved source and a stable ordered block allowlist."""
        validate_development_source_id(self.source_id)
        for field_name in (
            "request_id",
            "provider_configuration_id",
            "model_configuration_id",
        ):
            _require_trimmed(getattr(self, field_name), field_name)

        if any(block.source_id != self.source_id for block in self.evidence_blocks):
            raise ValueError("every evidence block source_id must equal request source_id")
        evidence_ids = [block.evidence_id for block in self.evidence_blocks]
        block_ids = [block.block_id for block in self.evidence_blocks]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence block evidence_ids must be unique")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("evidence block block_ids must be unique")
        sequences = [block.sequence for block in self.evidence_blocks]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("evidence blocks must have unique increasing sequences")
        return self


class LLMExtractionRequestV02(LLMExtractionRequest):
    """Additive prompt-v0.2 request without widening the v0.1 model."""

    experiment_id: Literal["llm-extraction-baseline-v0.2"] = EXPERIMENT_ID_V0_2
    prompt_version: Literal["0.2"] = PROMPT_VERSION_V0_2

    @model_validator(mode="after")
    def validate_v0_2_identity(self) -> LLMExtractionRequestV02:
        """Require exact v0.2 request and evidence identity templates."""
        match = re.fullmatch(
            rf"llm-v0\.2-{re.escape(self.source_id)}-"
            rf"{self.invocation_role.value}-(\d{{3}})",
            self.request_id,
        )
        if match is None or int(match.group(1)) < 1:
            raise ValueError("request_id must use the exact v0.2 identity template")
        for block in self.evidence_blocks:
            expected = f"llm-evidence-v0.2-{self.source_id}-{block.block_id}"
            if block.evidence_id != expected:
                raise ValueError(
                    "evidence_id must use the exact v0.2 evidence identity template"
                )
        return self


class LLMExtractionRequestV03(LLMExtractionRequest):
    """Additive alias-safe provider request without widening older models."""

    experiment_id: Literal["llm-extraction-baseline-v0.3"] = EXPERIMENT_ID_V0_3
    prompt_version: Literal["0.3"] = PROMPT_VERSION_V0_3

    @model_validator(mode="after")
    def validate_v0_3_identity(self) -> LLMExtractionRequestV03:
        """Require exact v0.3 request and evidence identity templates."""
        match = re.fullmatch(
            rf"llm-v0\.3-{re.escape(self.source_id)}-"
            rf"{self.invocation_role.value}-(\d{{3}})",
            self.request_id,
        )
        if match is None or int(match.group(1)) < 1:
            raise ValueError("request_id must use the exact v0.3 identity template")
        for block in self.evidence_blocks:
            expected = f"llm-evidence-v0.3-{self.source_id}-{block.block_id}"
            if block.evidence_id != expected:
                raise ValueError(
                    "evidence_id must use the exact v0.3 evidence identity template"
                )
        return self


LLMExtractionRequestAny: TypeAlias = (
    LLMExtractionRequest | LLMExtractionRequestV02 | LLMExtractionRequestV03
)


class ProviderTokenUsage(BaseModel):
    """Optional exact token usage reported by a provider transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class LLMProviderResponse(BaseModel):
    """Exact terminal response returned by the provider-neutral boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    provider_identifier: str
    model_identifier: str
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    provider_sdk_version: str | None = None
    terminal_status: ProviderTerminalStatus
    raw_response: str
    raw_response_sha256: str = Field(pattern=SHA256_PATTERN)
    token_usage: ProviderTokenUsage | None = None
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    failure_codes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_response(self) -> LLMProviderResponse:
        """Verify exact raw identity and coherent terminal metadata."""
        for field_name in ("request_id", "provider_identifier", "model_identifier"):
            _require_trimmed(getattr(self, field_name), field_name)
        provider_metadata = (
            self.provider_request_id,
            self.provider_response_id,
            self.provider_sdk_version,
        )
        for field_name in (
            "provider_request_id",
            "provider_response_id",
            "provider_sdk_version",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_trimmed(value, field_name)
        if any(value is not None for value in provider_metadata) and not all(
            value is not None for value in provider_metadata
        ):
            raise ValueError(
                "provider request ID, response ID, and SDK version must be "
                "supplied together"
            )
        if self.raw_response_sha256 != uppercase_sha256(self.raw_response):
            raise ValueError("raw_response_sha256 must match exact raw_response UTF-8 bytes")
        for label, codes in (
            ("warning_codes", self.warning_codes),
            ("failure_codes", self.failure_codes),
        ):
            if any(not code.strip() or code != code.strip() for code in codes):
                raise ValueError(f"{label} must contain trimmed non-blank strings")
            if len(codes) != len(set(codes)):
                raise ValueError(f"{label} must be unique")
        if self.terminal_status is ProviderTerminalStatus.SUCCESS:
            if self.failure_codes:
                raise ValueError("successful responses must not contain failure_codes")
        elif not self.failure_codes:
            raise ValueError("unsuccessful responses require at least one failure code")
        return self


class ValidatedCandidateOutput(BaseModel):
    """Typed, canonically identified Stage 4B validation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    source_id: str
    candidate_result: CandidateExtractionResult
    canonical_output_sha256: str = Field(pattern=SHA256_PATTERN)


def absent_additive_provider_metadata(value: object) -> set[str]:
    """Return only additive metadata fields that are absent on a model."""
    return {
        field_name
        for field_name in ADDITIVE_PROVIDER_METADATA_FIELDS
        if getattr(value, field_name, None) is None
    }


__all__ = [
    "APPROVED_DEVELOPMENT_SOURCE_IDS",
    "ADDITIVE_PROVIDER_METADATA_FIELDS",
    "EXPERIMENT_ID",
    "EXPERIMENT_ID_V0_1",
    "EXPERIMENT_ID_V0_2",
    "EXPERIMENT_ID_V0_3",
    "OUTPUT_CONTRACT_ID",
    "PROMPT_VERSION",
    "PROMPT_VERSION_V0_1",
    "PROMPT_VERSION_V0_2",
    "PROMPT_VERSION_V0_3",
    "ApprovedEvidenceBlock",
    "InvocationRole",
    "LLMExtractionRequest",
    "LLMExtractionRequestAny",
    "LLMExtractionRequestV02",
    "LLMExtractionRequestV03",
    "LLMProviderResponse",
    "ProviderTerminalStatus",
    "ProviderTokenUsage",
    "ValidatedCandidateOutput",
    "absent_additive_provider_metadata",
    "uppercase_sha256",
    "validate_development_source_id",
]
