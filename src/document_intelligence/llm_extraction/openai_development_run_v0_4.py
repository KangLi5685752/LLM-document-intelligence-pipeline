"""Compact default-deny Stage 4D development execution path for v0.4."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.llm_extraction import (
    openai_preflight_execution_v0_2 as credential_safety,
)
from document_intelligence.llm_extraction.cache import (
    V0_4_OPENAI_CACHE_ROOT,
    CacheIdentityV04,
    ResponseCache,
    build_cache_record,
    cache_identity_from_request,
    cache_identity_sha256,
    safe_cache_path,
)
from document_intelligence.llm_extraction.contracts import (
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequestV04,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ValidatedCandidateOutput,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    build_source_route_identity,
    load_approved_parsed_document,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL_CONFIGURATION_ID_V0_4,
    OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
    OpenAIResponsesProvider,
    build_openai_candidate_schema_v0_4,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope_v0_4,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.provenance import AttemptProvenance
from document_intelligence.llm_extraction.validation import (
    validate_provider_output_v0_4,
)


EXECUTION_ID: Literal[
    "openai-gpt-5.4-mini-five-source-development-execution-v0.4"
] = "openai-gpt-5.4-mini-five-source-development-execution-v0.4"
EXECUTION_CONFIRMATION: Literal[
    "EXECUTE_BOUNDED_FIVE_SOURCE_OPENAI_DEVELOPMENT_V0_4"
] = "EXECUTE_BOUNDED_FIVE_SOURCE_OPENAI_DEVELOPMENT_V0_4"
EXECUTION_ARTIFACT_ROOT = (
    "reports/llm_extraction/openai_development_execution/"
    "openai-gpt-5.4-mini-five-source-development-v0.4"
)
MAXIMUM_PROVIDER_CALLS: Literal[7] = 7
MAXIMUM_TOTAL_ATTEMPTS: Literal[7] = 7
MAXIMUM_RETRIES: Literal[0] = 0
COST_CAP_USD = Decimal("1.25")
INPUT_USD_PER_MILLION_TOKENS = Decimal("0.75")
OUTPUT_USD_PER_MILLION_TOKENS = Decimal("4.50")
MAXIMUM_PROVIDER_PAYLOAD_BYTES = 200000
SOURCE_ORDER = ("S001", "S002", "S003", "S004", "S006")
EXPECTED_REQUEST_IDS = (
    "llm-v0.4-S001-primary-001",
    "llm-v0.4-S002-primary-001",
    "llm-v0.4-S003-primary-001",
    "llm-v0.4-S004-primary-001",
    "llm-v0.4-S004-primary-002",
    "llm-v0.4-S004-primary-003",
    "llm-v0.4-S006-primary-001",
)
PARTITION_RANGES = {
    "S001": ((1, 26),),
    "S002": ((1, 22),),
    "S003": ((1, 16),),
    "S004": ((1, 53), (54, 100), (101, 118)),
    "S006": ((1, 61),),
}


@dataclass(frozen=True)
class _SourceRouteMetadata:
    source_id: str
    parsed_document_relative_path: str
    document_sha256: str
    parsed_document_canonical_sha256: str


_PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
_SOURCE_ROUTES = (
    _SourceRouteMetadata(
        "S001",
        "artifacts/stage_3b/v0_2_development_input/parsed/S001.json",
        "DE68EED45514303E2E0E4280B5CDE8B7167AAA17D6F69E1B0716765AE4DE807D",
        "3B9EBE3086106CE5D0CE1C6FD86618326DB1CDFB59F87C1C9E5E6A1A6FA20119",
    ),
    _SourceRouteMetadata(
        "S002",
        "artifacts/stage_3b/v0_2_development_input/parsed/S002.json",
        "BC586580B66B7E29B6AB824408055B168F83909D3CFECFDA085EBF1E418E5358",
        "8CBDF528FC7EC897020C2B920DCFC5EA1F922806518D86877C16F418DA30CC3C",
    ),
    _SourceRouteMetadata(
        "S003",
        "artifacts/stage_3b/v0_2_development_input/parsed/S003.json",
        "ACC700C1D245171B413BE248E2D1B21C07666F6891AA273F271D19E64CE2AE6F",
        "9E06C9089C4BEFDFE53B60A12EED72282D73B7B9960BDF56F410F6FB0AA49F2C",
    ),
    _SourceRouteMetadata(
        "S004",
        "artifacts/stage_3b/v0_2_development_input/parsed/S004.json",
        "3417156B104AA32EF795491739B7790EEFE5E6F83F2F15A95E3872C4693CB5C0",
        "0FD8FFA660019BFE5FDB9114423C10B579D322F700A03211FBE60F0EC3A93F9C",
    ),
    _SourceRouteMetadata(
        "S006",
        "artifacts/stage_3b/v0_2_development_input/parsed/S006.json",
        "DFE9F765EDD68F02698C7EB140F29DD88CA7010C928C3EBAE072DC7EA4D0B213",
        "AB0A4F3BC5E7A0B188550B1E5E3FD8D35517BAFEC14E2787512D3EA51D129344",
    ),
)


def _canonical_hash(model: BaseModel, hash_field: str) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(model.model_dump(mode="json", exclude={hash_field}))
    )


class DevelopmentRunInvocationV04(BaseModel):
    """One fresh primary request identity and its conservative budget."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_order: int = Field(ge=1, le=7)
    request_id: str
    source_id: str
    canonical_request_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_bytes: int = Field(gt=0, le=MAXIMUM_PROVIDER_PAYLOAD_BYTES)
    cache_identity_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    conservative_cost_ceiling_usd: Decimal = Field(ge=0)

    @field_serializer("conservative_cost_ceiling_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")


class DevelopmentRunSpecV04(BaseModel):
    """One compact self-hashed specification for the bounded v0.4 run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_spec_schema_version: Literal["0.1"] = "0.1"
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.4"
    ] = EXECUTION_ID
    repository_head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    invocations: tuple[DevelopmentRunInvocationV04, ...] = Field(
        min_length=7, max_length=7
    )
    strict_schema_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    maximum_provider_calls: Literal[7] = MAXIMUM_PROVIDER_CALLS
    maximum_total_attempts: Literal[7] = MAXIMUM_TOTAL_ATTEMPTS
    maximum_retries: Literal[0] = MAXIMUM_RETRIES
    maximum_output_tokens_per_call: Literal[4096] = OPENAI_MAX_OUTPUT_TOKENS
    cost_cap_usd: Decimal
    aggregate_conservative_cost_ceiling_usd: Decimal = Field(ge=0)
    cache_root: Literal[
        ".cache/llm_extraction/llm-extraction-baseline-v0.4/openai/"
    ] = V0_4_OPENAI_CACHE_ROOT
    execution_artifact_root: Literal[
        "reports/llm_extraction/openai_development_execution/"
        "openai-gpt-5.4-mini-five-source-development-v0.4"
    ] = EXECUTION_ARTIFACT_ROOT
    run_spec_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_serializer(
        "cost_cap_usd",
        "aggregate_conservative_cost_ceiling_usd",
        when_used="json",
    )
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_spec(self) -> DevelopmentRunSpecV04:
        if self.cost_cap_usd != COST_CAP_USD:
            raise ValueError("v0.4 run cost cap must be exactly USD 1.25")
        if self.aggregate_conservative_cost_ceiling_usd > self.cost_cap_usd:
            raise ValueError("aggregate conservative cost exceeds the run cap")
        if tuple(item.request_id for item in self.invocations) != EXPECTED_REQUEST_IDS:
            raise ValueError("run spec must contain the exact seven primary requests")
        if tuple(item.invocation_order for item in self.invocations) != tuple(
            range(1, 8)
        ):
            raise ValueError("run spec invocation order must be exactly 1..7")
        expected_sources = ("S001", "S002", "S003", "S004", "S004", "S004", "S006")
        if tuple(item.source_id for item in self.invocations) != expected_sources:
            raise ValueError("run spec source order differs from the approved routes")
        if self.run_spec_sha256 != _canonical_hash(self, "run_spec_sha256"):
            raise ValueError("run_spec_sha256 does not match canonical content")
        return self


class DevelopmentRunAuthorizationV04(BaseModel):
    """Small owner authorization bound to one exact run-spec identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_schema_version: Literal["0.1"] = "0.1"
    authorization_id: str
    execution_id: Literal[
        "openai-gpt-5.4-mini-five-source-development-execution-v0.4"
    ] = EXECUTION_ID
    run_spec_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    maximum_provider_calls: Literal[7] = MAXIMUM_PROVIDER_CALLS
    maximum_total_attempts: Literal[7] = MAXIMUM_TOTAL_ATTEMPTS
    maximum_retries: Literal[0] = MAXIMUM_RETRIES
    cost_cap_usd: Decimal
    explicitly_authorized_by_project_owner: Literal[True] = True
    project_owner_identity: str
    authorization_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_serializer("cost_cap_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @field_validator("authorization_id", "project_owner_identity")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("authorization identity fields must be trimmed and nonblank")
        return value

    @model_validator(mode="after")
    def validate_authorization(self) -> DevelopmentRunAuthorizationV04:
        if self.cost_cap_usd != COST_CAP_USD:
            raise ValueError("v0.4 authorization cost cap must be exactly USD 1.25")
        if self.authorization_sha256 != _canonical_hash(
            self, "authorization_sha256"
        ):
            raise ValueError("authorization_sha256 does not match canonical content")
        return self


@dataclass(frozen=True)
class DevelopmentRunReadinessV04:
    """In-memory exact run spec plus reconstructed requests."""

    repository_root: Path
    spec: DevelopmentRunSpecV04
    requests: tuple[LLMExtractionRequestV04, ...]


@dataclass(frozen=True)
class DevelopmentRunResultV04:
    """Completed local result boundary for immediate evaluation."""

    readiness: DevelopmentRunReadinessV04
    provider_call_count: int
    cache_hit_count: int
    output_paths: tuple[Path, ...]
    execution_record_path: Path


def _cost(*, input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * INPUT_USD_PER_MILLION_TOKENS
        + Decimal(output_tokens) * OUTPUT_USD_PER_MILLION_TOKENS
    ) / Decimal(1000000)


def _repository_head(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "current repository HEAD could not be resolved",
        ) from error
    return completed.stdout.strip()


def _load_development_documents(repository_root: Path) -> dict[str, ParsedDocument]:
    documents: dict[str, ParsedDocument] = {}
    for metadata in _SOURCE_ROUTES:
        route = build_source_route_identity(
            source_id=metadata.source_id,
            parsed_document_relative_path=metadata.parsed_document_relative_path,
            document_sha256=metadata.document_sha256,
            parsed_document_canonical_sha256=(
                metadata.parsed_document_canonical_sha256
            ),
            parser_commit=_PARSER_COMMIT,
        )
        documents[metadata.source_id] = load_approved_parsed_document(
            repository_root=repository_root,
            requested_source_id=metadata.source_id,
            route=route,
        )
    return documents


def _partition_blocks(
    document: ParsedDocument,
    start: int,
    end: int,
) -> tuple[ApprovedEvidenceBlock, ...]:
    by_sequence = {block.sequence: block for block in document.blocks}
    expected = tuple(range(start, end + 1))
    if any(sequence not in by_sequence for sequence in expected):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved development route block inventory is incomplete",
        )
    blocks = tuple(
        ApprovedEvidenceBlock(
            source_id=document.source_id or "",
            evidence_id=(
                f"llm-evidence-v0.4-{document.source_id}-{by_sequence[sequence].block_id}"
            ),
            block_id=by_sequence[sequence].block_id,
            sequence=by_sequence[sequence].sequence,
            text=by_sequence[sequence].text,
            location=by_sequence[sequence].location,
        )
        for sequence in expected
    )
    if any(not block.text.strip() for block in blocks):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "approved development route contains a blank selected block",
        )
    return blocks


def build_development_requests_v0_4(
    documents: Mapping[str, ParsedDocument],
) -> tuple[LLMExtractionRequestV04, ...]:
    """Build exactly seven fresh primary requests from approved block routes."""
    if tuple(sorted(documents)) != tuple(sorted(SOURCE_ORDER)):
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "development documents must contain exactly S001/S002/S003/S004/S006",
        )
    requests: list[LLMExtractionRequestV04] = []
    for source_id in SOURCE_ORDER:
        document = ParsedDocument.model_validate(
            documents[source_id].model_dump(mode="python")
        )
        if document.source_id != source_id:
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "development document source differs from its approved route",
            )
        for ordinal, (start, end) in enumerate(PARTITION_RANGES[source_id], start=1):
            request = build_request_envelope_v0_4(
                invocation_role=InvocationRole.PRIMARY,
                request_id=f"llm-v0.4-{source_id}-primary-{ordinal:03d}",
                source_id=source_id,
                document_sha256=document.checksum_sha256,
                provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID_V0_4,
                model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID_V0_4,
                evidence_blocks=_partition_blocks(document, start, end),
            )
            payload_bytes = canonical_json_bytes(
                build_openai_responses_payload(
                    request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4
                )
            )
            if len(payload_bytes) > MAXIMUM_PROVIDER_PAYLOAD_BYTES:
                raise Stage4BError(
                    Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                    "v0.4 provider payload exceeds the reviewed 200000-byte ceiling",
                )
            requests.append(request)
    if tuple(request.request_id for request in requests) != EXPECTED_REQUEST_IDS:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "constructed v0.4 request inventory differs from the seven approved routes",
        )
    return tuple(requests)


def build_run_spec_v0_4(
    requests: Sequence[LLMExtractionRequestV04],
    *,
    repository_head_sha: str,
) -> DevelopmentRunSpecV04:
    """Build the canonical compact readiness specification without I/O."""
    strict_schema_sha256 = uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_candidate_schema_v0_4())
    )
    invocations: list[DevelopmentRunInvocationV04] = []
    for order, request in enumerate(requests, start=1):
        payload_bytes = canonical_json_bytes(
            build_openai_responses_payload(
                request, DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4
            )
        )
        identity = cache_identity_from_request(request)
        if not isinstance(identity, CacheIdentityV04):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_RECORD_INVALID,
                "v0.4 request did not produce a v0.4 cache identity",
            )
        invocations.append(
            DevelopmentRunInvocationV04(
                invocation_order=order,
                request_id=request.request_id,
                source_id=request.source_id,
                canonical_request_sha256=request.canonical_request_sha256,
                prompt_sha256=request.prompt_sha256,
                provider_payload_sha256=uppercase_sha256_bytes(payload_bytes),
                provider_payload_bytes=len(payload_bytes),
                cache_identity_sha256=cache_identity_sha256(identity),
                conservative_cost_ceiling_usd=_cost(
                    input_tokens=len(payload_bytes),
                    output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                ),
            )
        )
    aggregate = sum(
        (item.conservative_cost_ceiling_usd for item in invocations), Decimal("0")
    )
    values = {
        "run_spec_schema_version": "0.1",
        "execution_id": EXECUTION_ID,
        "repository_head_sha": repository_head_sha,
        "invocations": tuple(invocations),
        "strict_schema_sha256": strict_schema_sha256,
        "maximum_provider_calls": MAXIMUM_PROVIDER_CALLS,
        "maximum_total_attempts": MAXIMUM_TOTAL_ATTEMPTS,
        "maximum_retries": MAXIMUM_RETRIES,
        "maximum_output_tokens_per_call": OPENAI_MAX_OUTPUT_TOKENS,
        "cost_cap_usd": COST_CAP_USD,
        "aggregate_conservative_cost_ceiling_usd": aggregate,
        "cache_root": V0_4_OPENAI_CACHE_ROOT,
        "execution_artifact_root": EXECUTION_ARTIFACT_ROOT,
    }
    provisional = DevelopmentRunSpecV04.model_construct(
        **values, run_spec_sha256="0" * 64
    )
    return DevelopmentRunSpecV04.model_validate(
        {**values, "run_spec_sha256": _canonical_hash(provisional, "run_spec_sha256")}
    )


def prepare_development_run_v0_4(
    *,
    repository_root: Path,
    repository_head_sha: str | None = None,
    documents: Mapping[str, ParsedDocument] | None = None,
) -> DevelopmentRunReadinessV04:
    """Prepare exact offline readiness without credential or client activity."""
    root = repository_root.resolve()
    selected_documents = (
        dict(documents) if documents is not None else _load_development_documents(root)
    )
    requests = build_development_requests_v0_4(selected_documents)
    spec = build_run_spec_v0_4(
        requests,
        repository_head_sha=repository_head_sha or _repository_head(root),
    )
    return DevelopmentRunReadinessV04(root, spec, requests)


def build_development_authorization_v0_4(
    *,
    spec: DevelopmentRunSpecV04,
    authorization_id: str,
    project_owner_identity: str,
) -> DevelopmentRunAuthorizationV04:
    """Build a compact self-hashed owner authorization for one exact spec."""
    values = {
        "authorization_schema_version": "0.1",
        "authorization_id": authorization_id,
        "execution_id": spec.execution_id,
        "run_spec_sha256": spec.run_spec_sha256,
        "maximum_provider_calls": spec.maximum_provider_calls,
        "maximum_total_attempts": spec.maximum_total_attempts,
        "maximum_retries": spec.maximum_retries,
        "cost_cap_usd": spec.cost_cap_usd,
        "explicitly_authorized_by_project_owner": True,
        "project_owner_identity": project_owner_identity,
    }
    provisional = DevelopmentRunAuthorizationV04.model_construct(
        **values, authorization_sha256="0" * 64
    )
    return DevelopmentRunAuthorizationV04.model_validate(
        {
            **values,
            "authorization_sha256": _canonical_hash(
                provisional, "authorization_sha256"
            ),
        }
    )


def authorization_bytes_v0_4(authorization: DevelopmentRunAuthorizationV04) -> bytes:
    validated = DevelopmentRunAuthorizationV04.model_validate(
        authorization.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


def _load_authorization(path: Path) -> DevelopmentRunAuthorizationV04:
    try:
        return DevelopmentRunAuthorizationV04.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
            "v0.4 development authorization is unavailable or invalid",
        ) from error


def _artifact_target(
    repository_root: Path,
    category: str | None,
    filename: str,
) -> Path:
    root = repository_root / EXECUTION_ARTIFACT_ROOT
    if category is not None:
        root /= category
    safe_root = ResponseCache(root).root
    return safe_cache_path(safe_root, filename)


def _write_exclusive_or_identical(target: Path, content: bytes) -> None:
    if os.path.lexists(target):
        if target.is_file() and not target.is_symlink() and target.read_bytes() == content:
            return
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
            "immutable v0.4 development artifact already exists with different bytes",
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if not target.is_file() or target.is_symlink() or target.read_bytes() != content:
                raise Stage4BError(
                    Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
                    "concurrent immutable v0.4 artifact differs",
                )
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.DEVELOPMENT_ARTIFACT_WRITE_FAILED,
                "v0.4 development artifact installation failed",
            ) from error
    finally:
        temporary.unlink(missing_ok=True)


def _self_hashed_payload(payload: dict[str, object], hash_field: str) -> dict[str, object]:
    return {
        **payload,
        hash_field: uppercase_sha256_bytes(canonical_json_bytes(payload)),
    }


def _load_marker(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
            "existing v0.4 attempt marker is invalid",
        ) from error
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
            "existing v0.4 attempt marker is not canonical",
        )
    claimed = payload.get("marker_sha256")
    unhashed = {key: value for key, value in payload.items() if key != "marker_sha256"}
    if claimed != uppercase_sha256_bytes(canonical_json_bytes(unhashed)):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
            "existing v0.4 attempt marker hash is invalid",
        )
    return payload


def _actual_response_cost(response: LLMProviderResponse) -> Decimal:
    usage = response.token_usage
    if (
        usage is None
        or usage.input_tokens is None
        or usage.output_tokens is None
        or usage.output_tokens > OPENAI_MAX_OUTPUT_TOKENS
    ):
        raise Stage4BError(
            Stage4BErrorCode.COST_BUDGET_EXCEEDED,
            "provider token usage is absent or exceeds the v0.4 output cap",
        )
    return _cost(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


def _openai_api_key_from_environment() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def _production_openai_client_factory(api_key: str) -> object:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _production_provider_call(
    client: object,
    request: LLMExtractionRequestV04,
) -> LLMProviderResponse:
    return OpenAIResponsesProvider(
        client=client,  # type: ignore[arg-type]
        configuration=DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_4,
    ).generate(request)


def execute_development_run_v0_4(
    *,
    repository_root: Path,
    authorization_path: Path | None,
    execute_real_development: bool,
    confirmation: str | None,
    repository_head_sha: str | None = None,
    documents: Mapping[str, ParsedDocument] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    api_key_reader: Callable[[], str | None] = _openai_api_key_from_environment,
    client_factory: Callable[[str], object] = _production_openai_client_factory,
    provider_call: Callable[
        [object, LLMExtractionRequestV04], LLMProviderResponse
    ] = _production_provider_call,
    local_validator: Callable[
        [LLMExtractionRequestV04, LLMProviderResponse], ValidatedCandidateOutput
    ] = validate_provider_output_v0_4,
) -> DevelopmentRunResultV04:
    """Execute at most seven calls only after the explicit bound real-mode gate."""
    if execute_real_development is not True or confirmation != EXECUTION_CONFIRMATION:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_EXECUTION_GATE_INVALID,
            "explicit real-development flag and exact confirmation are required",
        )
    if authorization_path is None:
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
            "an exact v0.4 project-owner authorization is required",
        )
    readiness = prepare_development_run_v0_4(
        repository_root=repository_root,
        repository_head_sha=repository_head_sha,
        documents=documents,
    )
    authorization = _load_authorization(authorization_path)
    if (
        authorization.execution_id != readiness.spec.execution_id
        or authorization.run_spec_sha256 != readiness.spec.run_spec_sha256
        or authorization.cost_cap_usd != readiness.spec.cost_cap_usd
    ):
        raise Stage4BError(
            Stage4BErrorCode.DEVELOPMENT_AUTHORIZATION_INVALID,
            "project-owner authorization does not bind the exact v0.4 run spec",
        )

    root = readiness.repository_root
    cache = ResponseCache(root / V0_4_OPENAI_CACHE_ROOT)
    provider_calls = 0
    attempts = 0
    cache_hits = 0
    newly_incurred_cost = Decimal("0")
    output_paths: list[Path] = []
    outcomes: list[dict[str, object]] = []

    for request, invocation in zip(
        readiness.requests, readiness.spec.invocations, strict=True
    ):
        identity = cache_identity_from_request(request)
        assert isinstance(identity, CacheIdentityV04)
        marker_path = _artifact_target(
            root, "attempts", f"{invocation.cache_identity_sha256}.attempt.json"
        )
        failure_path = _artifact_target(
            root, "failures", f"{invocation.cache_identity_sha256}.failure.json"
        )
        output_path = _artifact_target(
            root, "outputs", f"{request.request_id}.json"
        )
        marker: dict[str, object] | None = None
        stage = "cache_read"
        try:
            if os.path.lexists(failure_path):
                raise Stage4BError(
                    Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                    "a prior v0.4 failure permanently blocks this invocation",
                )
            try:
                cached = cache.read(identity)
            except Stage4BError as error:
                if error.code is not Stage4BErrorCode.CACHE_MISS:
                    raise
                cached = None

            if cached is None:
                stage = "attempt_gate"
                if os.path.lexists(marker_path):
                    raise Stage4BError(
                        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                        "a consumed v0.4 attempt without cache cannot be retried",
                    )
                if (
                    provider_calls + 1 > MAXIMUM_PROVIDER_CALLS
                    or attempts + 1 > MAXIMUM_TOTAL_ATTEMPTS
                    or newly_incurred_cost
                    + invocation.conservative_cost_ceiling_usd
                    > authorization.cost_cap_usd
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.ATTEMPT_BUDGET_EXCEEDED,
                        "the next invocation would exceed the authorized budget",
                    )
                marker = _self_hashed_payload(
                    {
                        "marker_schema_version": "0.1",
                        "execution_id": EXECUTION_ID,
                        "run_spec_sha256": readiness.spec.run_spec_sha256,
                        "authorization_sha256": authorization.authorization_sha256,
                        "request_id": request.request_id,
                        "cache_identity_sha256": invocation.cache_identity_sha256,
                    },
                    "marker_sha256",
                )
                _write_exclusive_or_identical(
                    marker_path, canonical_json_bytes(marker)
                )
                attempts += 1

                stage = "credential_access"
                try:
                    credential = credential_safety.validate_openai_api_key_shape(
                        api_key_reader()
                    )
                except Exception:
                    raise Stage4BError(
                        Stage4BErrorCode.PREFLIGHT_API_KEY_INVALID,
                        "OPENAI_API_KEY is unavailable or invalid at the gated boundary",
                    ) from None
                stage = "client_construction"
                client = client_factory(credential)
                stage = "provider_call"
                provider_calls += 1
                response = provider_call(client, request)
                if (
                    response.request_id != request.request_id
                    or response.terminal_status is not ProviderTerminalStatus.SUCCESS
                    or response.retry_count != 0
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.PROVIDER_NOT_SUCCESSFUL,
                        "provider response does not satisfy the retry-zero request boundary",
                    )
                actual_cost = _actual_response_cost(response)
                if (
                    actual_cost > invocation.conservative_cost_ceiling_usd
                    or newly_incurred_cost + actual_cost > authorization.cost_cap_usd
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.COST_BUDGET_EXCEEDED,
                        "provider usage exceeds the authorized v0.4 budget",
                    )
                attempt = AttemptProvenance(
                    attempt_number=1,
                    terminal_status=ProviderTerminalStatus.SUCCESS,
                    provider_call_performed=True,
                    response_sha256=response.raw_response_sha256,
                    latency_ms=response.latency_ms,
                )
                stage = "cache_install"
                cached = cache.append(
                    build_cache_record(
                        identity=identity,
                        response=response,
                        original_provider_call_timestamp=clock(),
                        original_attempts=(attempt,),
                        estimated_cost_usd=actual_cost,
                    )
                )
                cached = cache.read(identity)
                newly_incurred_cost += actual_cost
                cache_status = "miss"
            else:
                cache_hits += 1
                cache_status = "hit"
                if not os.path.lexists(marker_path):
                    raise Stage4BError(
                        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                        "v0.4 cache record lacks its bound attempt marker",
                    )
                marker = _load_marker(marker_path)
                if (
                    marker.get("run_spec_sha256") != readiness.spec.run_spec_sha256
                    or marker.get("authorization_sha256")
                    != authorization.authorization_sha256
                    or marker.get("request_id") != request.request_id
                    or marker.get("cache_identity_sha256")
                    != invocation.cache_identity_sha256
                ):
                    raise Stage4BError(
                        Stage4BErrorCode.DEVELOPMENT_ATTEMPT_ALREADY_EXISTS,
                        "v0.4 cache marker does not bind this run authorization",
                    )
                cached_cost = _actual_response_cost(cached.response)
                if cached_cost > invocation.conservative_cost_ceiling_usd:
                    raise Stage4BError(
                        Stage4BErrorCode.COST_BUDGET_EXCEEDED,
                        "cached provider usage exceeds the invocation ceiling",
                    )

            stage = "local_validation"
            validated = local_validator(request, cached.response)
            candidate_result = validated.candidate_result
            output_bytes = canonical_json_bytes(
                candidate_result.model_dump(mode="json")
            )
            _write_exclusive_or_identical(output_path, output_bytes)
            output_paths.append(output_path)
            outcomes.append(
                {
                    "invocation_order": invocation.invocation_order,
                    "request_id": request.request_id,
                    "source_id": request.source_id,
                    "cache_status": cache_status,
                    "candidate_output_sha256": uppercase_sha256_bytes(output_bytes),
                }
            )
        except Exception as error:
            code = (
                error.code
                if isinstance(error, Stage4BError)
                else Stage4BErrorCode.EXECUTION_FAILED
            )
            if marker is not None or stage != "cache_read":
                failure = _self_hashed_payload(
                    {
                        "failure_schema_version": "0.1",
                        "execution_id": EXECUTION_ID,
                        "run_spec_sha256": readiness.spec.run_spec_sha256,
                        "authorization_sha256": authorization.authorization_sha256,
                        "request_id": request.request_id,
                        "cache_identity_sha256": invocation.cache_identity_sha256,
                        "failure_stage": stage,
                        "error_code": code.value,
                    },
                    "failure_sha256",
                )
                _write_exclusive_or_identical(
                    failure_path, canonical_json_bytes(failure)
                )
            raise Stage4BError(
                code, "bounded v0.4 development invocation failed closed"
            ) from None

    if len(outcomes) != MAXIMUM_PROVIDER_CALLS:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "all seven v0.4 primary invocations must validate",
        )
    execution_record = _self_hashed_payload(
        {
            "execution_record_schema_version": "0.1",
            "execution_id": EXECUTION_ID,
            "run_spec_sha256": readiness.spec.run_spec_sha256,
            "authorization_sha256": authorization.authorization_sha256,
            "provider_call_count": provider_calls,
            "cache_hit_count": cache_hits,
            "retry_count": 0,
            "newly_incurred_cost_usd": format(newly_incurred_cost, "f"),
            "outcomes": outcomes,
        },
        "execution_record_sha256",
    )
    execution_record_path = _artifact_target(
        root, None, "execution-record.json"
    )
    _write_exclusive_or_identical(
        execution_record_path, canonical_json_bytes(execution_record)
    )
    return DevelopmentRunResultV04(
        readiness=readiness,
        provider_call_count=provider_calls,
        cache_hit_count=cache_hits,
        output_paths=tuple(output_paths),
        execution_record_path=execution_record_path,
    )


__all__ = [
    "COST_CAP_USD",
    "EXECUTION_ARTIFACT_ROOT",
    "EXECUTION_CONFIRMATION",
    "EXECUTION_ID",
    "EXPECTED_REQUEST_IDS",
    "MAXIMUM_PROVIDER_CALLS",
    "MAXIMUM_RETRIES",
    "MAXIMUM_TOTAL_ATTEMPTS",
    "DevelopmentRunAuthorizationV04",
    "DevelopmentRunInvocationV04",
    "DevelopmentRunReadinessV04",
    "DevelopmentRunResultV04",
    "DevelopmentRunSpecV04",
    "authorization_bytes_v0_4",
    "build_development_authorization_v0_4",
    "build_development_requests_v0_4",
    "build_run_spec_v0_4",
    "execute_development_run_v0_4",
    "prepare_development_run_v0_4",
]
