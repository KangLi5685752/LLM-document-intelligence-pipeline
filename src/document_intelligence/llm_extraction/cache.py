"""Append-only local response cache for Stage 4C mock execution."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    EXPERIMENT_ID_V0_2,
    InvocationRole,
    LLMExtractionRequest,
    LLMExtractionRequestAny,
    LLMExtractionRequestV02,
    LLMProviderResponse,
    ProviderTerminalStatus,
    SHA256_PATTERN,
    absent_additive_provider_metadata,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    ModelVersionOrSnapshotProvenance,
    _validate_provenance_path_inventory,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)
from document_intelligence.llm_extraction.provenance import AttemptProvenance


CACHE_SCHEMA_VERSION: Literal["0.1"] = "0.1"
V0_2_OPENAI_CACHE_ROOT = (
    ".cache/llm_extraction/llm-extraction-baseline-v0.2/openai/"
)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cache timestamps must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("cache timestamps must use UTC")
    return value


class CacheIdentity(BaseModel):
    """Complete logical identity for one append-only response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    invocation_role: InvocationRole
    request_id: str
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_configuration_id: str
    model_configuration_id: str
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    document_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def from_request(cls, request: LLMExtractionRequest) -> CacheIdentity:
        return cls(
            experiment_id=request.experiment_id,
            invocation_role=request.invocation_role,
            request_id=request.request_id,
            canonical_request_sha256=request.canonical_request_sha256,
            provider_configuration_id=request.provider_configuration_id,
            model_configuration_id=request.model_configuration_id,
            prompt_sha256=request.prompt_sha256,
            document_sha256=request.document_sha256,
        )


class CacheIdentityV02(CacheIdentity):
    """Additive cache identity for prompt-v0.2 requests."""

    experiment_id: Literal["llm-extraction-baseline-v0.2"] = EXPERIMENT_ID_V0_2

    @classmethod
    def from_request(cls, request: LLMExtractionRequestV02) -> CacheIdentityV02:
        return cls(
            experiment_id=request.experiment_id,
            invocation_role=request.invocation_role,
            request_id=request.request_id,
            canonical_request_sha256=request.canonical_request_sha256,
            provider_configuration_id=request.provider_configuration_id,
            model_configuration_id=request.model_configuration_id,
            prompt_sha256=request.prompt_sha256,
            document_sha256=request.document_sha256,
        )


CacheIdentityAny: TypeAlias = CacheIdentity | CacheIdentityV02


def cache_identity_from_request(request: LLMExtractionRequestAny) -> CacheIdentityAny:
    """Select the cache identity model from the explicit request version."""
    if isinstance(request, LLMExtractionRequestV02):
        return CacheIdentityV02.from_request(request)
    return CacheIdentity.from_request(request)


class OpenAIOriginalCallProvenanceV01(BaseModel):
    """Safe same-call metadata retained before local output validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_schema_version: Literal["0.1"] = "0.1"
    model_version_or_snapshot_provenance: ModelVersionOrSnapshotProvenance
    version_provenance_source_response_id: str
    provider_public_metadata_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_public_metadata_field_paths: tuple[str, ...]
    observed_from_same_provider_call: Literal[True] = True

    @field_validator("version_provenance_source_response_id")
    @classmethod
    def validate_source_response_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError(
                "version_provenance_source_response_id must be trimmed and nonblank"
            )
        return value

    @model_validator(mode="after")
    def validate_provenance(self) -> OpenAIOriginalCallProvenanceV01:
        try:
            _validate_provenance_path_inventory(
                self.model_version_or_snapshot_provenance,
                self.provider_public_metadata_field_paths,
            )
        except Stage4BError as error:
            raise ValueError(error.message) from error
        return self


def _openai_provenance_projection(
    provenance: OpenAIOriginalCallProvenanceV01,
    response: LLMProviderResponse,
) -> dict[str, object]:
    if (
        response.provider_response_id is None
        or response.provider_request_id is None
        or response.provider_sdk_version is None
    ):
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "OpenAI original-call provenance requires complete response identity",
        )
    projection: dict[str, object] = {
        "response.id": response.provider_response_id,
        "response.model": response.model_identifier,
        "response._request_id": response.provider_request_id,
        "sdk.version": response.provider_sdk_version,
    }
    version_provenance = provenance.model_version_or_snapshot_provenance
    if version_provenance != "unavailable":
        projection.update(
            (identifier.field_name, identifier.value)
            for identifier in version_provenance
        )
    return projection


class CacheRecord(BaseModel):
    """Canonical cached response with immutable original-call provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cache_schema_version: Literal["0.1"] = CACHE_SCHEMA_VERSION
    identity: CacheIdentity | CacheIdentityV02
    response: LLMProviderResponse
    original_provider_call_timestamp: datetime
    original_attempts: tuple[AttemptProvenance, ...] = Field(min_length=1)
    estimated_cost_usd: Decimal = Field(ge=0)
    openai_original_call_provenance: OpenAIOriginalCallProvenanceV01 | None = None
    cache_record_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("original_provider_call_timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @field_serializer("estimated_cost_usd", when_used="json")
    def serialize_cost(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_record(self) -> CacheRecord:
        if self.response.request_id != self.identity.request_id:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_RECORD_INVALID,
                "cached response request identity differs",
            )
        if self.response.terminal_status is not ProviderTerminalStatus.SUCCESS:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_RECORD_INVALID,
                "only successful terminal responses may be cached",
            )
        final_attempt = self.original_attempts[-1]
        if (
            final_attempt.terminal_status is not ProviderTerminalStatus.SUCCESS
            or final_attempt.response_sha256 != self.response.raw_response_sha256
        ):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_RECORD_INVALID,
                "cached original attempts do not reconcile with the response",
            )
        provenance = self.openai_original_call_provenance
        if provenance is not None:
            if self.response.provider_identifier != "openai":
                raise Stage4BError(
                    Stage4BErrorCode.CACHE_RECORD_INVALID,
                    "OpenAI original-call provenance requires an OpenAI response",
                )
            projection = _openai_provenance_projection(provenance, self.response)
            if (
                provenance.version_provenance_source_response_id
                != self.response.provider_response_id
                or provenance.provider_public_metadata_field_paths
                != tuple(projection)
                or provenance.provider_public_metadata_sha256
                != uppercase_sha256_bytes(canonical_json_bytes(projection))
            ):
                raise Stage4BError(
                    Stage4BErrorCode.CACHE_RECORD_INVALID,
                    "OpenAI original-call provenance does not reconcile with response",
                )
        payload = _cache_record_payload(self, include_hash=False)
        expected_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
        if self.cache_record_sha256 != expected_hash:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_HASH_MISMATCH,
                "cache_record_sha256 does not match canonical cache bytes",
            )
        return self


def cache_identity_sha256(identity: CacheIdentityAny) -> str:
    """Return the opaque filename identity without interpolating user strings."""
    return uppercase_sha256_bytes(
        canonical_json_bytes(identity.model_dump(mode="json"))
    )


def _provider_response_payload(response: LLMProviderResponse) -> dict[str, Any]:
    return response.model_dump(
        mode="json",
        exclude=absent_additive_provider_metadata(response),
    )


def _cache_record_payload(
    record: CacheRecord,
    *,
    include_hash: bool,
) -> dict[str, Any]:
    payload = {
        "cache_schema_version": record.cache_schema_version,
        "identity": record.identity.model_dump(mode="json"),
        "response": _provider_response_payload(record.response),
        "original_provider_call_timestamp": _require_utc(
            record.original_provider_call_timestamp
        ).isoformat().replace("+00:00", "Z"),
        "original_attempts": [
            item.model_dump(mode="json") for item in record.original_attempts
        ],
        "estimated_cost_usd": format(record.estimated_cost_usd, "f"),
    }
    if record.openai_original_call_provenance is not None:
        payload["openai_original_call_provenance"] = (
            record.openai_original_call_provenance.model_dump(mode="json")
        )
    if include_hash:
        payload["cache_record_sha256"] = record.cache_record_sha256
    return payload


def build_cache_record(
    *,
    identity: CacheIdentityAny,
    response: LLMProviderResponse,
    original_provider_call_timestamp: datetime,
    original_attempts: tuple[AttemptProvenance, ...],
    estimated_cost_usd: Decimal,
    openai_original_call_provenance: OpenAIOriginalCallProvenanceV01 | None = None,
) -> CacheRecord:
    """Create a self-hashed immutable response record."""
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "identity": identity.model_dump(mode="json"),
        "response": _provider_response_payload(response),
        "original_provider_call_timestamp": _require_utc(
            original_provider_call_timestamp
        ).isoformat().replace("+00:00", "Z"),
        "original_attempts": [
            item.model_dump(mode="json") for item in original_attempts
        ],
        "estimated_cost_usd": format(estimated_cost_usd, "f"),
    }
    if openai_original_call_provenance is not None:
        payload["openai_original_call_provenance"] = (
            openai_original_call_provenance.model_dump(mode="json")
        )
    record_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
    return CacheRecord.model_validate(
        {**payload, "cache_record_sha256": record_hash}
    )


def cache_record_bytes(record: CacheRecord) -> bytes:
    """Return exact canonical bytes after complete hash validation."""
    validated = CacheRecord.model_validate(record.model_dump(mode="python"))
    return canonical_json_bytes(_cache_record_payload(validated, include_hash=True))


def _has_reparse_attribute(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _absolute_lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _validate_safe_path_chain(
    path: Path,
    *,
    containment_root: Path | None = None,
) -> Path:
    """Validate every existing lexical component without following reparses."""
    candidate = _absolute_lexical_path(path)
    root = (
        _absolute_lexical_path(containment_root)
        if containment_root is not None
        else None
    )
    if root is not None:
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache path escapes its configured root",
            ) from error

    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache path component could not be inspected safely",
            ) from error
        if stat.S_ISLNK(metadata.st_mode) or _has_reparse_attribute(metadata):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache path must not contain a symbolic link or reparse point",
            )

    if root is not None:
        try:
            candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        except (OSError, RuntimeError, ValueError) as error:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "resolved cache path escapes its configured root",
            ) from error
    return candidate


def safe_cache_path(root: Path, relative_path: str) -> Path:
    """Resolve one logical cache path without permitting traversal or reparses."""
    normalized = relative_path.replace("\\", "/")
    logical = PurePosixPath(normalized)
    if (
        not relative_path
        or logical.is_absolute()
        or PureWindowsPath(relative_path).is_absolute()
        or ".." in logical.parts
        or logical.parts != (logical.name,)
    ):
        raise Stage4BError(
            Stage4BErrorCode.CACHE_PATH_ESCAPE,
            "cache entry path must be one relative filename",
        )
    root_absolute = _validate_safe_path_chain(root)
    candidate = root_absolute / logical.name
    return _validate_safe_path_chain(candidate, containment_root=root_absolute)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object keys are forbidden")
        result[key] = value
    return result


def _parse_cache_record(raw: bytes) -> CacheRecord:
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant is forbidden: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cache record is not strict UTF-8 JSON",
        ) from error
    if not isinstance(payload, dict):
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cache record must be a JSON object",
        )
    response = payload.get("response")
    if isinstance(response, dict):
        raw_response = response.get("raw_response")
        response_hash = response.get("raw_response_sha256")
        if isinstance(raw_response, str) and isinstance(response_hash, str):
            if uppercase_sha256_bytes(raw_response.encode("utf-8")) != response_hash:
                raise Stage4BError(
                    Stage4BErrorCode.CACHE_HASH_MISMATCH,
                    "cached raw response hash does not match its exact bytes",
                )
    record_hash = payload.get("cache_record_sha256")
    if isinstance(record_hash, str):
        hash_payload = dict(payload)
        del hash_payload["cache_record_sha256"]
        if uppercase_sha256_bytes(canonical_json_bytes(hash_payload)) != record_hash:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_HASH_MISMATCH,
                "cached record hash does not match its canonical bytes",
            )
    try:
        record = CacheRecord.model_validate(payload)
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cache record does not satisfy the Stage 4C contract",
        ) from error
    if cache_record_bytes(record) != raw:
        raise Stage4BError(
            Stage4BErrorCode.CACHE_RECORD_INVALID,
            "cache record bytes are not canonical",
        )
    return record


def _install_atomic(temporary: Path, target: Path) -> None:
    """Install by exclusive hard link so an existing entry is never replaced."""
    os.link(temporary, target)


class ResponseCache:
    """Filesystem-backed append-only response cache with verified reads."""

    def __init__(self, root: Path) -> None:
        self.root = _validate_safe_path_chain(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = _validate_safe_path_chain(self.root)
        try:
            root_metadata = os.lstat(self.root)
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache root could not be inspected safely",
            ) from error
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache root must be a regular directory",
            )

    def path_for(self, identity: CacheIdentityAny) -> Path:
        """Return the opaque, root-contained entry path for an identity."""
        filename = f"{cache_identity_sha256(identity)}.json"
        return safe_cache_path(self.root, filename)

    def read(self, identity: CacheIdentityAny) -> CacheRecord:
        """Return a fully verified record or raise an explicit cache miss."""
        target = self.path_for(identity)
        if not os.path.lexists(target):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_MISS,
                "no cache record exists for the canonical request identity",
            )
        target = _validate_safe_path_chain(target, containment_root=self.root)
        try:
            target_metadata = os.lstat(target)
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache entry could not be inspected safely",
            ) from error
        if not stat.S_ISREG(target_metadata.st_mode):
            raise Stage4BError(
                Stage4BErrorCode.CACHE_PATH_ESCAPE,
                "cache entry must be a regular non-reparse file",
            )
        _validate_safe_path_chain(target, containment_root=self.root)
        record = _parse_cache_record(target.read_bytes())
        if record.identity != identity:
            raise Stage4BError(
                Stage4BErrorCode.CACHE_RECORD_INVALID,
                "cache record identity differs from its lookup identity",
            )
        return record

    def append(self, record: CacheRecord) -> CacheRecord:
        """Install a new canonical record, read identical content, or fail closed."""
        canonical = cache_record_bytes(record)
        target = self.path_for(record.identity)
        if os.path.lexists(target):
            existing = self.read(record.identity)
            if cache_record_bytes(existing) == canonical:
                return existing
            raise Stage4BError(
                Stage4BErrorCode.CACHE_CONFLICT,
                "an immutable cache entry already exists with different content",
            )

        _validate_safe_path_chain(self.root)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.stem}.", suffix=".tmp", dir=self.root
        )
        temporary = Path(temporary_name)
        descriptor_open = True
        try:
            _validate_safe_path_chain(temporary, containment_root=self.root)
            handle = os.fdopen(descriptor, "wb")
            descriptor_open = False
            with handle:
                handle.write(canonical)
                handle.flush()
                os.fsync(handle.fileno())
            _validate_safe_path_chain(temporary, containment_root=self.root)
            _validate_safe_path_chain(target, containment_root=self.root)
            try:
                _install_atomic(temporary, target)
            except FileExistsError:
                existing = self.read(record.identity)
                if cache_record_bytes(existing) == canonical:
                    return existing
                raise Stage4BError(
                    Stage4BErrorCode.CACHE_CONFLICT,
                    "a concurrent immutable cache entry conflicts",
                )
            except OSError as error:
                raise Stage4BError(
                    Stage4BErrorCode.CACHE_WRITE_FAILED,
                    "atomic cache installation failed",
                ) from error
        finally:
            if descriptor_open:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
        return self.read(record.identity)


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "CacheIdentity",
    "CacheIdentityAny",
    "CacheIdentityV02",
    "CacheRecord",
    "OpenAIOriginalCallProvenanceV01",
    "ResponseCache",
    "build_cache_record",
    "cache_identity_from_request",
    "cache_identity_sha256",
    "cache_record_bytes",
    "safe_cache_path",
    "V0_2_OPENAI_CACHE_ROOT",
]
