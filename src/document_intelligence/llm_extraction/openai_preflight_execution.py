"""Default-deny local transaction boundary for one future OpenAI preflight."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from document_intelligence.llm_extraction.contracts import LLMExtractionRequest
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    PREFLIGHT_ID,
    PREFLIGHT_INPUT_CLASSIFICATION,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightRecord,
    OpenAIPricingObservation,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_preflight_bridge import (
    OpenAIResponsesPreflightBridge,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_API_SURFACE,
    OPENAI_PROVIDER_IDENTIFIER,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OpenAIResponsesProvider,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
    validate_request_identity,
)


EXECUTION_CONFIRMATION = "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_1"
EXECUTION_PLAN_SCHEMA_VERSION: Literal["0.1"] = "0.1"
ATTEMPT_MARKER_SCHEMA_VERSION: Literal["0.1"] = "0.1"
MAXIMUM_INPUT_FILE_BYTES = 32 * 1024
OUTPUT_DIRECTORY = PurePosixPath("reports/llm_extraction/openai_preflight")
ATTEMPT_MARKER_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.1.attempt.json"
)
SUCCESSFUL_RECORD_RELATIVE_PATH = OUTPUT_DIRECTORY / (
    "openai-gpt-5.4-mini-synthetic-preflight-v0.1.record.json"
)
PROJECT_DISTRIBUTION_NAME = "llm-document-intelligence-pipeline"
_PROJECT_METADATA_RELATIVE_PATH = PurePosixPath("pyproject.toml")
_PROJECT_SOURCE_RELATIVE_PATH = PurePosixPath(
    "src/document_intelligence/llm_extraction/openai_preflight_execution.py"
)
_PROJECT_PROMPT_RELATIVE_PATHS = (
    PurePosixPath(
        "src/document_intelligence/llm_extraction/prompts/system_v0_1.txt"
    ),
    PurePosixPath(
        "src/document_intelligence/llm_extraction/prompts/extraction_v0_1.txt"
    ),
)
_PROTECTED_REPOSITORY_PREFIXES = (
    ("artifacts", "annotations"),
    ("artifacts", "ingestion"),
    ("artifacts", "llm_extraction"),
    ("artifacts", "stage_3b"),
    ("data", "annotations"),
    ("data", "manifests"),
    ("data", "raw"),
    ("evaluation",),
    ("reports", "llm_extraction"),
)


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value


def _utc_json(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class OpenAIPreflightExecutionPlan(BaseModel):
    """Immutable, non-sensitive identity for the fixed execution boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_plan_schema_version: Literal["0.1"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.1"]
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.1"]
    provider_identifier: Literal["openai"]
    api_surface: Literal["responses"]
    requested_model_alias: Literal["gpt-5.4-mini"]
    maximum_provider_calls: Literal[1]
    input_classification: Literal["synthetic_preflight_text"]
    canonical_request_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    synthetic_document_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    strict_schema_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    attempt_marker_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.1.attempt.json"
    ]
    successful_record_path: Literal[
        "reports/llm_extraction/openai_preflight/"
        "openai-gpt-5.4-mini-synthetic-preflight-v0.1.record.json"
    ]
    execution_plan_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightExecutionPlan:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(
                    mode="json",
                    exclude={"execution_plan_sha256"},
                )
            )
        )
        if self.execution_plan_sha256 != expected:
            raise ValueError("execution_plan_sha256 does not match plan identity")
        return self


@dataclass(frozen=True)
class _ExecutionPlanAnchors:
    canonical_request_sha256: str
    prompt_sha256: str
    synthetic_document_sha256: str
    strict_schema_sha256: str
    provider_payload_sha256: str


def _derive_execution_plan_anchors() -> _ExecutionPlanAnchors:
    """Derive every plan anchor from the current production builders."""
    request = build_synthetic_openai_preflight_request()
    return _derive_execution_plan_anchors_for_request(request)


def _derive_execution_plan_anchors_for_request(
    request: LLMExtractionRequest,
) -> _ExecutionPlanAnchors:
    """Derive all five anchors from one exact validated request."""
    if not isinstance(request, LLMExtractionRequest):
        raise TypeError("preflight request must use LLMExtractionRequest")
    validate_request_identity(request)
    request_bytes = canonical_json_bytes(
        request.model_dump(mode="json", exclude={"canonical_request_sha256"})
    )
    schema = build_openai_candidate_schema()
    payload = build_openai_responses_payload(request)
    return _ExecutionPlanAnchors(
        canonical_request_sha256=uppercase_sha256_bytes(request_bytes),
        prompt_sha256=request.prompt_sha256,
        synthetic_document_sha256=request.document_sha256,
        strict_schema_sha256=uppercase_sha256_bytes(canonical_json_bytes(schema)),
        provider_payload_sha256=uppercase_sha256_bytes(
            canonical_json_bytes(payload)
        ),
    )


def _build_execution_plan(
    anchors: _ExecutionPlanAnchors,
) -> OpenAIPreflightExecutionPlan:
    """Assemble the deterministic plan after anchor derivation is complete."""
    values = {
        "execution_plan_schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_scope": PREFLIGHT_AUTHORIZATION_SCOPE,
        "provider_identifier": OPENAI_PROVIDER_IDENTIFIER,
        "api_surface": OPENAI_API_SURFACE,
        "requested_model_alias": OPENAI_REQUESTED_MODEL_ALIAS,
        "maximum_provider_calls": 1,
        "input_classification": PREFLIGHT_INPUT_CLASSIFICATION,
        "canonical_request_sha256": anchors.canonical_request_sha256,
        "prompt_sha256": anchors.prompt_sha256,
        "synthetic_document_sha256": anchors.synthetic_document_sha256,
        "strict_schema_sha256": anchors.strict_schema_sha256,
        "provider_payload_sha256": anchors.provider_payload_sha256,
        "attempt_marker_path": ATTEMPT_MARKER_RELATIVE_PATH.as_posix(),
        "successful_record_path": SUCCESSFUL_RECORD_RELATIVE_PATH.as_posix(),
    }
    plan_hash = uppercase_sha256_bytes(canonical_json_bytes(values))
    return OpenAIPreflightExecutionPlan.model_validate(
        {**values, "execution_plan_sha256": plan_hash}
    )


def build_openai_preflight_execution_plan() -> OpenAIPreflightExecutionPlan:
    """Derive production anchors once and build their deterministic plan."""
    return _build_execution_plan(_derive_execution_plan_anchors())


def _require_plan_anchor_match(
    plan: OpenAIPreflightExecutionPlan,
    anchors: _ExecutionPlanAnchors,
) -> None:
    for field_name in (
        "canonical_request_sha256",
        "prompt_sha256",
        "synthetic_document_sha256",
        "strict_schema_sha256",
        "provider_payload_sha256",
    ):
        if getattr(plan, field_name) != getattr(anchors, field_name):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                f"provider-entry {field_name} differs from the readiness plan",
            )


@dataclass(frozen=True)
class _PlanBoundPreflightProvider:
    """Bind the exact runner request to the marker's readiness plan."""

    plan: OpenAIPreflightExecutionPlan
    delegate: OpenAIResponsesPreflightBridge

    def generate_preflight(self, request: LLMExtractionRequest) -> object:
        try:
            anchors = _derive_execution_plan_anchors_for_request(request)
        except Exception:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                "provider-entry request could not be bound to the readiness plan",
            ) from None
        _require_plan_anchor_match(self.plan, anchors)
        return self.delegate.generate_preflight(request)


class OpenAIPreflightAttemptMarker(BaseModel):
    """Permanent local evidence that a provider call may have started."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    marker_schema_version: Literal["0.1"]
    preflight_id: Literal["openai-gpt-5.4-mini-synthetic-preflight-v0.1"]
    authorization_id: str
    authorization_scope: Literal["single-synthetic-openai-preflight-v0.1"]
    execution_plan_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    attempt_timestamp_utc: datetime
    maximum_provider_calls: Literal[1]
    state: Literal["provider_call_may_have_started"]
    marker_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")

    @field_validator("authorization_id")
    @classmethod
    def validate_authorization_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("authorization_id must be trimmed and nonblank")
        return value

    @field_validator("attempt_timestamp_utc")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _require_utc(value, "attempt_timestamp_utc")

    @field_serializer("attempt_timestamp_utc", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return _utc_json(value)

    @model_validator(mode="after")
    def validate_self_hash(self) -> OpenAIPreflightAttemptMarker:
        expected = uppercase_sha256_bytes(
            canonical_json_bytes(
                self.model_dump(mode="json", exclude={"marker_sha256"})
            )
        )
        if self.marker_sha256 != expected:
            raise ValueError("marker_sha256 does not match marker identity")
        return self


def _build_attempt_marker(
    *,
    authorization: OpenAIPreflightAuthorization,
    plan: OpenAIPreflightExecutionPlan,
    timestamp: datetime,
) -> OpenAIPreflightAttemptMarker:
    values = {
        "marker_schema_version": ATTEMPT_MARKER_SCHEMA_VERSION,
        "preflight_id": PREFLIGHT_ID,
        "authorization_id": authorization.authorization_id,
        "authorization_scope": authorization.scope,
        "execution_plan_sha256": plan.execution_plan_sha256,
        "attempt_timestamp_utc": _utc_json(timestamp),
        "maximum_provider_calls": 1,
        "state": "provider_call_may_have_started",
    }
    marker_hash = uppercase_sha256_bytes(canonical_json_bytes(values))
    return OpenAIPreflightAttemptMarker.model_validate(
        {**values, "marker_sha256": marker_hash}
    )


def attempt_marker_bytes(marker: OpenAIPreflightAttemptMarker) -> bytes:
    """Return canonical marker bytes after complete self-hash validation."""
    validated = OpenAIPreflightAttemptMarker.model_validate(
        marker.model_dump(mode="python")
    )
    return canonical_json_bytes(validated.model_dump(mode="json"))


@dataclass(frozen=True)
class OpenAIPreflightInputs:
    authorization: OpenAIPreflightAuthorization
    pricing_observation: OpenAIPricingObservation
    data_controls_observation: OpenAIDataControlsObservation


@dataclass(frozen=True)
class OpenAIPreflightReadiness:
    plan: OpenAIPreflightExecutionPlan
    inputs: OpenAIPreflightInputs
    execution_timestamp_utc: datetime
    repository_root: Path
    attempt_marker_path: Path
    successful_record_path: Path


@dataclass(frozen=True)
class OpenAIPreflightExecutionResult:
    plan: OpenAIPreflightExecutionPlan
    marker: OpenAIPreflightAttemptMarker
    record: OpenAIPreflightRecord
    attempt_marker_path: Path
    successful_record_path: Path


def _require_record_matches_plan(
    record: OpenAIPreflightRecord,
    plan: OpenAIPreflightExecutionPlan,
) -> None:
    if not isinstance(record, OpenAIPreflightRecord):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "preflight runner did not return the frozen record contract",
        )
    expected = {
        "canonical_request_sha256": plan.canonical_request_sha256,
        "prompt_sha256": plan.prompt_sha256,
        "document_sha256": plan.synthetic_document_sha256,
        "strict_schema_sha256": plan.strict_schema_sha256,
        "provider_payload_sha256": plan.provider_payload_sha256,
    }
    for field_name, value in expected.items():
        if getattr(record, field_name) != value:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
                f"returned record {field_name} differs from the readiness plan",
            )


def _has_reparse_attribute(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _absolute_lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_remote_or_device_path(path: Path, *, label: str) -> None:
    raw = os.fspath(path)
    if not isinstance(raw, str):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} path must use the local filesystem",
        )
    windows_form = raw.replace("/", "\\")
    if windows_form.startswith("\\\\"):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} path must not use UNC or device namespaces",
        )
    if os.name == "nt":
        drive = Path(raw).drive
        if drive:
            import ctypes

            drive_type = ctypes.windll.kernel32.GetDriveTypeW(f"{drive}\\")
            if drive_type == 4:  # DRIVE_REMOTE
                raise Stage4BError(
                    Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                    f"{label} path must not use a remote drive",
                )


def _validate_path_chain(path: Path, *, label: str) -> Path:
    _reject_remote_or_device_path(path, label=label)
    candidate = _absolute_lexical_path(path)
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as error:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                f"{label} path could not be inspected safely",
            ) from error
        if stat.S_ISLNK(metadata.st_mode) or _has_reparse_attribute(metadata):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                f"{label} path must not contain a symlink or reparse point",
            )
    return candidate


def _metadata_identity(metadata: os.stat_result) -> tuple[int, int] | None:
    inode = getattr(metadata, "st_ino", 0)
    device = getattr(metadata, "st_dev", 0)
    if not inode:
        return None
    return int(device), int(inode)


def _identities_differ(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    first_identity = _metadata_identity(first)
    second_identity = _metadata_identity(second)
    return (
        first_identity is not None
        and second_identity is not None
        and first_identity != second_identity
    )


def _open_read_only_descriptor(path: Path) -> int:
    """Open one local file without following its final link where supported."""
    binary = getattr(os, "O_BINARY", 0)
    if os.name != "nt":
        flags = os.O_RDONLY | binary | getattr(os, "O_NOFOLLOW", 0)
        return os.open(path, flags)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x00200000 | 0x08000000,  # OPEN_REPARSE_POINT | SEQUENTIAL_SCAN
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, os.strerror(error_code), str(path))
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | binary)
    except Exception:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise


def _read_validated_descriptor(path: Path, *, label: str) -> bytes:
    """Read bytes only from the exact regular-file descriptor that was checked."""
    candidate = _validate_path_chain(path, label=label)
    try:
        before = os.lstat(candidate)
    except (FileNotFoundError, OSError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input must exist and be readable",
        ) from error
    if (
        stat.S_ISLNK(before.st_mode)
        or _has_reparse_attribute(before)
        or not stat.S_ISREG(before.st_mode)
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input must be a regular non-link file",
        )
    if before.st_size > MAXIMUM_INPUT_FILE_BYTES:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input exceeds the 32 KiB limit",
        )

    descriptor: int | None = None
    try:
        descriptor = _open_read_only_descriptor(candidate)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _has_reparse_attribute(opened)
            or _identities_differ(before, opened)
        ):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                f"{label} input changed or was not a regular local file",
            )
        _validate_path_chain(candidate, label=label)
        after_open = os.lstat(candidate)
        if (
            stat.S_ISLNK(after_open.st_mode)
            or _has_reparse_attribute(after_open)
            or not stat.S_ISREG(after_open.st_mode)
            or _identities_differ(before, after_open)
            or _identities_differ(opened, after_open)
        ):
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                f"{label} input changed during validation",
            )
        if opened.st_size > MAXIMUM_INPUT_FILE_BYTES:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                f"{label} input exceeds the 32 KiB limit",
            )
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            raw = handle.read(MAXIMUM_INPUT_FILE_BYTES + 1)
            opened_after_read = os.fstat(handle.fileno())
            _validate_path_chain(candidate, label=label)
            after_read = os.lstat(candidate)
            if (
                not stat.S_ISREG(opened_after_read.st_mode)
                or stat.S_ISLNK(after_read.st_mode)
                or _has_reparse_attribute(after_read)
                or not stat.S_ISREG(after_read.st_mode)
                or _identities_differ(opened, opened_after_read)
                or _identities_differ(opened_after_read, after_read)
            ):
                raise Stage4BError(
                    Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
                    f"{label} input changed while it was read",
                )
    except Stage4BError:
        raise
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input could not be read safely",
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > MAXIMUM_INPUT_FILE_BYTES:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input exceeds the 32 KiB limit",
        )
    return raw


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    raw = _read_validated_descriptor(path, label=label)
    try:
        text = raw.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant is forbidden: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input must be one strict UTF-8 JSON object",
        ) from error
    if not isinstance(payload, dict):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input must contain a JSON object",
        )
    return payload


def _validate_input_model(
    *,
    path: Path,
    label: str,
    model_type: type[OpenAIPreflightAuthorization]
    | type[OpenAIPricingObservation]
    | type[OpenAIDataControlsObservation],
) -> OpenAIPreflightAuthorization | OpenAIPricingObservation | OpenAIDataControlsObservation:
    try:
        return model_type.model_validate(_read_json_object(path, label=label))
    except Stage4BError:
        raise
    except ValidationError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            f"{label} input does not satisfy its frozen contract",
        ) from error


def _reject_protected_repository_input(path: Path, repository_root: Path) -> None:
    _reject_remote_or_device_path(path, label="preflight input")
    candidate = _absolute_lexical_path(path)
    root = _absolute_lexical_path(repository_root)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return
    normalized = tuple(part.casefold() for part in relative.parts)
    if any(
        normalized[: len(prefix)] == prefix
        for prefix in _PROTECTED_REPOSITORY_PREFIXES
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID,
            "preflight inputs must not use protected repository assets",
        )


def _installed_repository_root() -> Path:
    return Path(__file__).parents[3]


def _require_regular_identity_path(path: Path, *, label: str) -> None:
    candidate = _validate_path_chain(path, label=label)
    try:
        metadata = os.lstat(candidate)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "installed project repository identity is incomplete",
        ) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or _has_reparse_attribute(metadata)
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "installed project repository identity is invalid",
        )


def _validate_project_repository_identity(repository_root: Path) -> Path:
    try:
        root = _validate_path_chain(repository_root, label="project repository")
        root_status = os.lstat(root)
        git_status = os.lstat(root / ".git")
    except (OSError, Stage4BError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "the installed project repository root could not be verified",
        ) from error
    if not stat.S_ISDIR(root_status.st_mode) or (
        stat.S_ISLNK(git_status.st_mode) or _has_reparse_attribute(git_status)
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "the installed project repository root is not a safe local checkout",
        )
    if not (stat.S_ISDIR(git_status.st_mode) or stat.S_ISREG(git_status.st_mode)):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "the installed project repository has no valid Git identity",
        )
    required_files = (
        _PROJECT_METADATA_RELATIVE_PATH,
        _PROJECT_SOURCE_RELATIVE_PATH,
        *_PROJECT_PROMPT_RELATIVE_PATHS,
    )
    for relative in required_files:
        _require_regular_identity_path(
            root.joinpath(*relative.parts), label="project identity"
        )
    try:
        metadata_bytes = _read_validated_descriptor(
            root.joinpath(*_PROJECT_METADATA_RELATIVE_PATH.parts),
            label="project metadata",
        )
    except Stage4BError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "the installed project metadata could not be verified",
        ) from error
    expected_name = f'name = "{PROJECT_DISTRIBUTION_NAME}"'.encode("utf-8")
    expected_script = (
        b'run-openai-synthetic-preflight = '
        b'"document_intelligence.llm_extraction.openai_preflight_cli:main"'
    )
    lines = metadata_bytes.splitlines()
    if b"[project]" not in lines or expected_name not in lines or expected_script not in lines:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "the installed project metadata does not match this execution gate",
        )
    return root


def resolve_production_repository_root(
    launch_directory: Path | None = None,
) -> Path:
    """Bind production CLI execution to this installed local checkout only."""
    root = _validate_project_repository_identity(_installed_repository_root())
    selected = launch_directory if launch_directory is not None else Path.cwd()
    try:
        launch = _validate_path_chain(selected, label="launch directory")
        launch_status = os.lstat(launch)
        launch.relative_to(root)
    except (OSError, ValueError, Stage4BError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "command must be launched from this verified project repository",
        ) from error
    if not stat.S_ISDIR(launch_status.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "command launch location must be a repository directory",
        )
    return root


def _load_openai_preflight_inputs(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
) -> OpenAIPreflightInputs:
    """Load three files under one private, explicit repository boundary."""
    paths = (authorization_path, pricing_path, data_controls_path)
    protected_roots = {
        _absolute_lexical_path(repository_root),
        _absolute_lexical_path(_installed_repository_root()),
    }
    for path in paths:
        for protected_root in protected_roots:
            _reject_protected_repository_input(path, protected_root)
    authorization = _validate_input_model(
        path=authorization_path,
        label="authorization",
        model_type=OpenAIPreflightAuthorization,
    )
    pricing = _validate_input_model(
        path=pricing_path,
        label="pricing observation",
        model_type=OpenAIPricingObservation,
    )
    data_controls = _validate_input_model(
        path=data_controls_path,
        label="data-controls observation",
        model_type=OpenAIDataControlsObservation,
    )
    assert isinstance(authorization, OpenAIPreflightAuthorization)
    assert isinstance(pricing, OpenAIPricingObservation)
    assert isinstance(data_controls, OpenAIDataControlsObservation)
    return OpenAIPreflightInputs(
        authorization=authorization,
        pricing_observation=pricing,
        data_controls_observation=data_controls,
    )


def load_openai_preflight_inputs(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
) -> OpenAIPreflightInputs:
    """Load three inputs against the installed-checkout protection boundary."""
    root = _installed_repository_root()
    return _load_openai_preflight_inputs(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
    )


def _validated_timestamp(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "execution clock must return a timezone-aware UTC datetime",
        )
    try:
        return _require_utc(value, "execution_timestamp_utc")
    except ValueError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "execution clock must return a timezone-aware UTC datetime",
        ) from error


def _validate_loaded_inputs(
    inputs: OpenAIPreflightInputs,
    execution_timestamp: datetime,
) -> OpenAIPreflightInputs:
    try:
        authorization = OpenAIPreflightAuthorization.model_validate(
            inputs.authorization.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "preflight authorization is invalid",
        ) from error
    try:
        pricing = OpenAIPricingObservation.model_validate(
            inputs.pricing_observation.model_dump(mode="python")
        )
        data_controls = OpenAIDataControlsObservation.model_validate(
            inputs.data_controls_observation.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "pricing or data-control observation is invalid",
        ) from error
    if authorization.authorized_at_utc > execution_timestamp:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "authorization timestamp must not postdate execution",
        )
    if (
        pricing.observed_at_utc.date() != execution_timestamp.date()
        or data_controls.observed_at_utc.date() != execution_timestamp.date()
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "pricing and data-control observations must use the execution UTC date",
        )
    return OpenAIPreflightInputs(authorization, pricing, data_controls)


def _fixed_artifact_paths(repository_root: Path) -> tuple[Path, Path, Path]:
    root = _validate_path_chain(repository_root, label="repository root")
    try:
        metadata = os.lstat(root)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "repository root must be an existing regular directory",
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "repository root must be an existing regular directory",
        )
    output = root.joinpath(*OUTPUT_DIRECTORY.parts)
    marker = root.joinpath(*ATTEMPT_MARKER_RELATIVE_PATH.parts)
    record = root.joinpath(*SUCCESSFUL_RECORD_RELATIVE_PATH.parts)
    return output, marker, record


def _require_artifacts_absent(marker: Path, record: Path) -> None:
    if os.path.lexists(marker):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
            "the fixed preflight attempt marker already exists",
        )
    if os.path.lexists(record):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS,
            "the fixed successful preflight record already exists",
        )


def _validate_openai_preflight_readiness(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    clock: Callable[[], datetime],
) -> OpenAIPreflightReadiness:
    """Validate local inputs and fixed artifact state without secrets or writes."""
    inputs = _load_openai_preflight_inputs(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=repository_root,
    )
    timestamp = _validated_timestamp(clock)
    inputs = _validate_loaded_inputs(inputs, timestamp)
    anchors = _derive_execution_plan_anchors()
    plan = _build_execution_plan(anchors)
    output, marker, record = _fixed_artifact_paths(repository_root)
    _validate_path_chain(output, label="preflight output")
    _validate_path_chain(marker, label="preflight attempt marker")
    _validate_path_chain(record, label="preflight successful record")
    _require_artifacts_absent(marker, record)
    return OpenAIPreflightReadiness(
        plan=plan,
        inputs=inputs,
        execution_timestamp_utc=timestamp,
        repository_root=_absolute_lexical_path(repository_root),
        attempt_marker_path=marker,
        successful_record_path=record,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_openai_preflight_readiness(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
) -> OpenAIPreflightReadiness:
    """Validate readiness only against this installed project checkout."""
    root = resolve_production_repository_root(Path.cwd())
    return _validate_openai_preflight_readiness(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        clock=_utc_now,
    )


def _create_output_directory(repository_root: Path) -> Path:
    output, _, _ = _fixed_artifact_paths(repository_root)
    _validate_path_chain(output, label="preflight output")
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output directory could not be created",
        ) from error
    output = _validate_path_chain(output, label="preflight output")
    try:
        metadata = os.lstat(output)
    except OSError as error:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output directory could not be inspected",
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "preflight output path is not a directory",
        )
    return output


def _write_exclusive(path: Path, payload: bytes, *, marker: bool) -> None:
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(payload + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        code = (
            Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS
            if marker
            else Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED
        )
        raise Stage4BError(
            code,
            "fixed preflight artifact already exists and cannot be overwritten",
        ) from error
    except OSError as error:
        if created and not marker:
            try:
                path.unlink()
            except OSError:
                pass
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "fixed preflight artifact could not be written",
        ) from error


def _production_openai_client_factory(api_key: str) -> object:
    """Construct the pinned SDK client only after every local gate passes."""
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _openai_api_key_from_environment() -> str | None:
    """Read only the one approved credential variable at the gated boundary."""
    return os.environ.get("OPENAI_API_KEY")


def _execute_openai_synthetic_preflight_transaction(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    repository_root: Path,
    execute_real_preflight: bool,
    confirmation: str | None,
    clock: Callable[[], datetime],
    api_key_reader: Callable[[], str | None],
    client_factory: Callable[[str], object],
) -> OpenAIPreflightExecutionResult:
    """Run the fixed one-call transaction only after every default-deny gate."""
    if execute_real_preflight is not True:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "explicit real-preflight execution flag is required",
        )
    if confirmation != EXECUTION_CONFIRMATION:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID,
            "exact real-preflight confirmation phrase is required",
        )
    readiness = _validate_openai_preflight_readiness(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=repository_root,
        clock=clock,
    )
    try:
        api_key = api_key_reader()
    except Exception:
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
            "OPENAI_API_KEY could not be read at the gated boundary",
        ) from None
    if (
        not isinstance(api_key, str)
        or not api_key.strip()
        or api_key != api_key.strip()
    ):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING,
            "OPENAI_API_KEY must be supplied as one nonblank environment value",
        )
    _create_output_directory(readiness.repository_root)
    _require_artifacts_absent(
        readiness.attempt_marker_path,
        readiness.successful_record_path,
    )
    marker = _build_attempt_marker(
        authorization=readiness.inputs.authorization,
        plan=readiness.plan,
        timestamp=readiness.execution_timestamp_utc,
    )
    _write_exclusive(
        readiness.attempt_marker_path,
        attempt_marker_bytes(marker),
        marker=True,
    )
    if os.path.lexists(readiness.successful_record_path):
        raise Stage4BError(
            Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
            "successful preflight record appeared after marker creation",
        )
    try:
        client = client_factory(api_key)
        provider = _PlanBoundPreflightProvider(
            plan=readiness.plan,
            delegate=OpenAIResponsesPreflightBridge(
                provider=OpenAIResponsesProvider(client=client)
            ),
        )
    except Exception:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "OpenAI client or provider-wrapper construction failed",
        ) from None
    try:
        record = run_openai_synthetic_preflight(
            provider=provider,
            authorization=readiness.inputs.authorization,
            pricing_observation=readiness.inputs.pricing_observation,
            data_controls_observation=readiness.inputs.data_controls_observation,
            clock=lambda: readiness.execution_timestamp_utc,
        )
    except Stage4BError:
        raise
    except Exception:
        raise Stage4BError(
            Stage4BErrorCode.EXECUTION_FAILED,
            "OpenAI synthetic preflight execution failed",
        ) from None
    _require_record_matches_plan(record, readiness.plan)
    _write_exclusive(
        readiness.successful_record_path,
        preflight_record_bytes(record),
        marker=False,
    )
    return OpenAIPreflightExecutionResult(
        plan=readiness.plan,
        marker=marker,
        record=record,
        attempt_marker_path=readiness.attempt_marker_path,
        successful_record_path=readiness.successful_record_path,
    )


def execute_openai_synthetic_preflight(
    *,
    authorization_path: Path,
    pricing_path: Path,
    data_controls_path: Path,
    execute_real_preflight: bool,
    confirmation: str | None,
) -> OpenAIPreflightExecutionResult:
    """Execute only against this verified checkout and its fixed artifacts."""
    root = resolve_production_repository_root(Path.cwd())
    return _execute_openai_synthetic_preflight_transaction(
        authorization_path=authorization_path,
        pricing_path=pricing_path,
        data_controls_path=data_controls_path,
        repository_root=root,
        execute_real_preflight=execute_real_preflight,
        confirmation=confirmation,
        clock=_utc_now,
        api_key_reader=_openai_api_key_from_environment,
        client_factory=_production_openai_client_factory,
    )


__all__ = [
    "ATTEMPT_MARKER_RELATIVE_PATH",
    "EXECUTION_CONFIRMATION",
    "OpenAIPreflightAttemptMarker",
    "OpenAIPreflightExecutionPlan",
    "OpenAIPreflightExecutionResult",
    "OpenAIPreflightInputs",
    "OpenAIPreflightReadiness",
    "SUCCESSFUL_RECORD_RELATIVE_PATH",
    "attempt_marker_bytes",
    "build_openai_preflight_execution_plan",
    "execute_openai_synthetic_preflight",
    "load_openai_preflight_inputs",
    "validate_openai_preflight_readiness",
]
