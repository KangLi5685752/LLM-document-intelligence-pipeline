"""Provider-neutral contracts for development-only LLM candidate extraction."""

from document_intelligence.llm_extraction.contracts import (
    APPROVED_DEVELOPMENT_SOURCE_IDS,
    EXPERIMENT_ID,
    OUTPUT_CONTRACT_ID,
    PROMPT_VERSION,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ProviderTokenUsage,
    ValidatedCandidateOutput,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.mock_provider import (
    DeterministicMockProvider,
    MockResponseFixture,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope,
    canonical_prompt_bytes,
    canonical_request_bytes,
    load_prompt_assets,
    prompt_sha256,
    validate_request_identity,
)
from document_intelligence.llm_extraction.provider import LLMProvider
from document_intelligence.llm_extraction.validation import validate_provider_output


__all__ = [
    "APPROVED_DEVELOPMENT_SOURCE_IDS",
    "EXPERIMENT_ID",
    "OUTPUT_CONTRACT_ID",
    "PROMPT_VERSION",
    "ApprovedEvidenceBlock",
    "DeterministicMockProvider",
    "InvocationRole",
    "LLMExtractionRequest",
    "LLMProvider",
    "LLMProviderResponse",
    "MockResponseFixture",
    "ProviderTerminalStatus",
    "ProviderTokenUsage",
    "Stage4BError",
    "Stage4BErrorCode",
    "ValidatedCandidateOutput",
    "build_request_envelope",
    "canonical_prompt_bytes",
    "canonical_request_bytes",
    "load_prompt_assets",
    "prompt_sha256",
    "validate_development_source_id",
    "validate_provider_output",
    "validate_request_identity",
]
