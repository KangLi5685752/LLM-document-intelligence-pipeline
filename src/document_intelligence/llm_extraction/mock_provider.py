"""Deterministic, offline provider fixture for Stage 4B tests."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequest,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    uppercase_sha256,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.prompting import validate_request_identity


MOCK_PROVIDER_IDENTIFIER = "stage4b-deterministic-mock-provider"
MOCK_MODEL_IDENTIFIER = "stage4b-deterministic-mock-model"


class MockResponseFixture(BaseModel):
    """One immutable terminal fixture selected by canonical request identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    terminal_status: ProviderTerminalStatus
    raw_response: str
    token_usage: ProviderTokenUsage | None = None
    latency_ms: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    failure_codes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_fixture(self) -> MockResponseFixture:
        """Keep explicit success and failure fixtures coherent."""
        if self.terminal_status is ProviderTerminalStatus.SUCCESS:
            if self.failure_codes:
                raise ValueError("successful mock fixtures must not contain failure_codes")
        elif not self.failure_codes:
            raise ValueError("failed mock fixtures require a failure code")
        return self


class DeterministicMockProvider:
    """Offline fixture lookup with no retries, clocks, randomness, or network."""

    def __init__(self, fixtures: Mapping[str, MockResponseFixture]) -> None:
        self._fixtures = dict(fixtures)

    def generate(self, request: LLMExtractionRequest) -> LLMProviderResponse:
        """Return the exact configured response or fail closed."""
        validate_request_identity(request)
        try:
            fixture = self._fixtures[request.canonical_request_sha256]
        except KeyError as error:
            raise Stage4BError(
                Stage4BErrorCode.MOCK_RESPONSE_NOT_FOUND,
                "no deterministic mock response exists for canonical request identity",
            ) from error
        return LLMProviderResponse(
            request_id=request.request_id,
            provider_identifier=MOCK_PROVIDER_IDENTIFIER,
            model_identifier=MOCK_MODEL_IDENTIFIER,
            terminal_status=fixture.terminal_status,
            raw_response=fixture.raw_response,
            raw_response_sha256=uppercase_sha256(fixture.raw_response),
            token_usage=fixture.token_usage,
            latency_ms=fixture.latency_ms,
            retry_count=fixture.retry_count,
            warning_codes=fixture.warning_codes,
            failure_codes=fixture.failure_codes,
        )


__all__ = [
    "MOCK_MODEL_IDENTIFIER",
    "MOCK_PROVIDER_IDENTIFIER",
    "DeterministicMockProvider",
    "MockResponseFixture",
]
