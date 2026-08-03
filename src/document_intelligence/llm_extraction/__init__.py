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
from document_intelligence.llm_extraction.cache import (
    CacheIdentity,
    CacheRecord,
    ResponseCache,
    build_cache_record,
    cache_identity_sha256,
    cache_record_bytes,
)
from document_intelligence.llm_extraction.manifest import (
    EvidenceBlockIdentity,
    RequestManifest,
    RequestManifestInvocation,
    build_manifest_invocation,
    build_request_manifest,
    request_manifest_bytes,
    validate_request_manifest,
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
from document_intelligence.llm_extraction.provenance import (
    AttemptProvenance,
    CacheStatus,
    InvocationProvenance,
    MockRunReport,
    ValidationStatus,
    build_mock_run_report,
    mock_run_report_bytes,
)
from document_intelligence.llm_extraction.runner import (
    ExecutionBudget,
    run_mock_development,
)
from document_intelligence.llm_extraction.validation import validate_provider_output


__all__ = [
    "APPROVED_DEVELOPMENT_SOURCE_IDS",
    "EXPERIMENT_ID",
    "OUTPUT_CONTRACT_ID",
    "PROMPT_VERSION",
    "ApprovedEvidenceBlock",
    "AttemptProvenance",
    "CacheIdentity",
    "CacheRecord",
    "CacheStatus",
    "DeterministicMockProvider",
    "EvidenceBlockIdentity",
    "ExecutionBudget",
    "InvocationRole",
    "LLMExtractionRequest",
    "LLMProvider",
    "LLMProviderResponse",
    "MockResponseFixture",
    "MockRunReport",
    "ProviderTerminalStatus",
    "ProviderTokenUsage",
    "RequestManifest",
    "RequestManifestInvocation",
    "ResponseCache",
    "Stage4BError",
    "Stage4BErrorCode",
    "ValidatedCandidateOutput",
    "ValidationStatus",
    "build_cache_record",
    "build_manifest_invocation",
    "build_request_envelope",
    "build_request_manifest",
    "build_mock_run_report",
    "cache_identity_sha256",
    "cache_record_bytes",
    "canonical_prompt_bytes",
    "canonical_request_bytes",
    "load_prompt_assets",
    "prompt_sha256",
    "mock_run_report_bytes",
    "request_manifest_bytes",
    "run_mock_development",
    "validate_development_source_id",
    "validate_provider_output",
    "validate_request_manifest",
    "validate_request_identity",
]
