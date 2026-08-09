"""Canonical Stage 4C request-manifest contracts."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from document_intelligence.ingestion.models import LocationType
from document_intelligence.llm_extraction.contracts import (
    EXPERIMENT_ID,
    OUTPUT_CONTRACT_ID,
    PROMPT_VERSION,
    InvocationRole,
    LLMExtractionRequest,
    SHA256_PATTERN,
    validate_development_source_id,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


MANIFEST_SCHEMA_VERSION: Literal["0.1"] = "0.1"
MAX_PRIMARY_INVOCATIONS = 100
MAX_REPEAT_INVOCATIONS = 10


def _looks_like_absolute_path(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _reject_absolute_paths(value: Any) -> None:
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "manifest values must not contain absolute paths",
            )
        return
    if isinstance(value, dict):
        for item in value.values():
            _reject_absolute_paths(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_absolute_paths(item)


def _raise_typed_validation_error(error: ValidationError) -> None:
    for item in error.errors():
        nested = item.get("ctx", {}).get("error")
        if isinstance(nested, Stage4BError):
            raise nested from error
    raise error


class EvidenceBlockIdentity(BaseModel):
    """Content-bound identity for one ordered request evidence block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    evidence_id: str
    block_id: str
    sequence: int = Field(gt=0)
    text_sha256: str = Field(pattern=SHA256_PATTERN)
    location_type: LocationType
    location_value: str


class RequestManifestInvocation(BaseModel):
    """One ordered primary or repeat invocation and its exact request envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    invocation_role: InvocationRole
    request_id: str
    canonical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    document_sha256: str = Field(pattern=SHA256_PATTERN)
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    ordered_evidence_blocks: tuple[EvidenceBlockIdentity, ...] = Field(min_length=1)
    request: LLMExtractionRequest

    @model_validator(mode="after")
    def validate_invocation(self) -> RequestManifestInvocation:
        validate_development_source_id(self.source_id)
        if (
            self.request.experiment_id != EXPERIMENT_ID
            or self.request.prompt_version != PROMPT_VERSION
        ):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "the v0.1 manifest cannot contain another request version",
            )
        validate_request_identity(self.request)
        expected = {
            "source_id": self.request.source_id,
            "invocation_role": self.request.invocation_role,
            "request_id": self.request.request_id,
            "canonical_request_sha256": self.request.canonical_request_sha256,
            "document_sha256": self.request.document_sha256,
            "prompt_sha256": self.request.prompt_sha256,
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise Stage4BError(
                    Stage4BErrorCode.INVALID_MANIFEST,
                    f"invocation {field_name} does not match its request envelope",
                )
        expected_blocks = tuple(
            EvidenceBlockIdentity(
                source_id=block.source_id,
                evidence_id=block.evidence_id,
                block_id=block.block_id,
                sequence=block.sequence,
                text_sha256=uppercase_sha256_bytes(block.text.encode("utf-8")),
                location_type=block.location.location_type,
                location_value=block.location.location_value,
            )
            for block in self.request.evidence_blocks
        )
        if self.ordered_evidence_blocks != expected_blocks:
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "ordered evidence-block identities do not match the request",
            )
        return self


class RequestManifest(BaseModel):
    """Strict, self-hashed Stage 4C request manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_schema_version: Literal["0.1"] = MANIFEST_SCHEMA_VERSION
    experiment_id: Literal["llm-extraction-baseline-v0.1"] = EXPERIMENT_ID
    prompt_version: Literal["0.1"] = PROMPT_VERSION
    prompt_sha256s: tuple[str, ...]
    output_contract_id: Literal["candidate-extraction-result-0.1"] = (
        OUTPUT_CONTRACT_ID
    )
    provider_configuration_id: str
    model_configuration_id: str
    invocations: tuple[RequestManifestInvocation, ...] = Field(min_length=1)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_manifest(self) -> RequestManifest:
        request_ids = [item.request_id for item in self.invocations]
        if len(request_ids) != len(set(request_ids)):
            raise Stage4BError(
                Stage4BErrorCode.DUPLICATE_INVOCATION,
                "manifest request IDs must be unique",
            )
        invocation_identities = [
            (
                item.invocation_role.value,
                item.source_id,
                item.canonical_request_sha256,
            )
            for item in self.invocations
        ]
        if len(invocation_identities) != len(set(invocation_identities)):
            raise Stage4BError(
                Stage4BErrorCode.DUPLICATE_INVOCATION,
                "manifest invocation identities must be unique",
            )
        primary_count = sum(
            item.invocation_role is InvocationRole.PRIMARY
            for item in self.invocations
        )
        repeat_count = len(self.invocations) - primary_count
        if (
            primary_count > MAX_PRIMARY_INVOCATIONS
            or repeat_count > MAX_REPEAT_INVOCATIONS
        ):
            raise Stage4BError(
                Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED,
                "manifest invocation counts exceed the fixed Stage 4 limits",
            )
        if self.prompt_sha256s != tuple(
            item.prompt_sha256 for item in self.invocations
        ):
            raise Stage4BError(
                Stage4BErrorCode.INVALID_MANIFEST,
                "prompt_sha256s must follow invocation order exactly",
            )
        for item in self.invocations:
            if (
                item.request.experiment_id != self.experiment_id
                or item.request.prompt_version != self.prompt_version
                or item.request.output_contract_id != self.output_contract_id
                or item.request.provider_configuration_id
                != self.provider_configuration_id
                or item.request.model_configuration_id
                != self.model_configuration_id
            ):
                raise Stage4BError(
                    Stage4BErrorCode.INVALID_MANIFEST,
                    "manifest and request configuration identities differ",
                )
        payload = self.model_dump(mode="json", exclude={"manifest_sha256"})
        _reject_absolute_paths(payload)
        expected_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
        if self.manifest_sha256 != expected_hash:
            raise Stage4BError(
                Stage4BErrorCode.MANIFEST_HASH_MISMATCH,
                "manifest_sha256 does not match canonical manifest bytes",
            )
        return self


def build_manifest_invocation(
    request: LLMExtractionRequest,
) -> RequestManifestInvocation:
    """Bind one validated request to its ordered evidence identities."""
    validate_request_identity(request)
    try:
        return RequestManifestInvocation(
            source_id=request.source_id,
            invocation_role=request.invocation_role,
            request_id=request.request_id,
            canonical_request_sha256=request.canonical_request_sha256,
            document_sha256=request.document_sha256,
            prompt_sha256=request.prompt_sha256,
            ordered_evidence_blocks=tuple(
                EvidenceBlockIdentity(
                    source_id=block.source_id,
                    evidence_id=block.evidence_id,
                    block_id=block.block_id,
                    sequence=block.sequence,
                    text_sha256=uppercase_sha256_bytes(block.text.encode("utf-8")),
                    location_type=block.location.location_type,
                    location_value=block.location.location_value,
                )
                for block in request.evidence_blocks
            ),
            request=request,
        )
    except ValidationError as error:
        _raise_typed_validation_error(error)


def build_request_manifest(
    requests: Iterable[LLMExtractionRequest],
) -> RequestManifest:
    """Build a canonical manifest without repository discovery or file access."""
    invocations = tuple(build_manifest_invocation(request) for request in requests)
    if not invocations:
        raise Stage4BError(
            Stage4BErrorCode.INVALID_MANIFEST,
            "a request manifest requires at least one invocation",
        )
    first = invocations[0].request
    payload = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256s": [item.prompt_sha256 for item in invocations],
        "output_contract_id": OUTPUT_CONTRACT_ID,
        "provider_configuration_id": first.provider_configuration_id,
        "model_configuration_id": first.model_configuration_id,
        "invocations": [item.model_dump(mode="json") for item in invocations],
    }
    manifest_hash = uppercase_sha256_bytes(canonical_json_bytes(payload))
    try:
        return RequestManifest.model_validate(
            {**payload, "manifest_sha256": manifest_hash}
        )
    except ValidationError as error:
        _raise_typed_validation_error(error)


def validate_request_manifest(manifest: RequestManifest) -> RequestManifest:
    """Revalidate a possibly copied manifest and preserve typed stop reasons."""
    try:
        return RequestManifest.model_validate(manifest.model_dump(mode="python"))
    except ValidationError as error:
        _raise_typed_validation_error(error)


def request_manifest_bytes(manifest: RequestManifest) -> bytes:
    """Return exact canonical bytes after revalidating the manifest hash."""
    validated = validate_request_manifest(manifest)
    return canonical_json_bytes(validated.model_dump(mode="json"))


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "MAX_PRIMARY_INVOCATIONS",
    "MAX_REPEAT_INVOCATIONS",
    "EvidenceBlockIdentity",
    "RequestManifest",
    "RequestManifestInvocation",
    "build_manifest_invocation",
    "build_request_manifest",
    "request_manifest_bytes",
    "validate_request_manifest",
]
