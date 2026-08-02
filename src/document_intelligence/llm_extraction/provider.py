"""Narrow provider-neutral transport protocol for Stage 4B."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequest,
    LLMProviderResponse,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Transport-only boundary with no extraction or evaluation behavior."""

    def generate(self, request: LLMExtractionRequest) -> LLMProviderResponse:
        """Return one terminal response for one validated request envelope."""
        ...


__all__ = ["LLMProvider"]
