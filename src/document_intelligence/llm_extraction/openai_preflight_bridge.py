"""Same-call OpenAI SDK metadata bridge for the synthetic preflight."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from document_intelligence.llm_extraction.contracts import (
    LLMExtractionRequest,
    LLMProviderResponse,
)
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIPreflightProviderObservation,
    ProviderPublicMetadataEntry,
    ProviderVersionIdentifier,
)
from document_intelligence.llm_extraction.openai_provider import (
    OpenAIResponsesProvider,
)


_VERSION_FIELD_SEGMENTS = frozenset(
    {
        "model_snapshot",
        "model_version",
        "revision",
        "revision_id",
        "snapshot",
        "snapshot_id",
        "snapshot_name",
        "version",
        "version_id",
    }
)
_SDK_VERSION_FIELD_SEGMENTS = frozenset(
    {"provider_sdk_version", "sdk_version"}
)
_SENSITIVE_SUBTREE_SEGMENTS = frozenset(
    {
        "api_key",
        "authorization",
        "authorization_header",
        "credentials",
        "error",
        "errors",
        "evidence",
        "evidence_text",
        "headers",
        "instructions",
        "output",
        "output_text",
        "prompt",
        "prompt_text",
        "raw_response",
        "reasoning",
        "tool",
        "tools",
    }
)


def _metadata_error(message: str) -> Stage4BError:
    return Stage4BError(
        Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID,
        message,
    )


def _normalized_segment(value: str) -> str:
    return value.casefold().replace("-", "_")


def _public_response_mapping(sdk_response: object) -> Mapping[str, Any]:
    model_dump = getattr(sdk_response, "model_dump", None)
    if not callable(model_dump):
        raise _metadata_error(
            "OpenAI SDK response must expose callable model_dump(mode='python')"
        )
    try:
        payload = model_dump(mode="python")
    except Exception as error:
        raise _metadata_error(
            "OpenAI SDK public response serialization failed"
        ) from error
    if not isinstance(payload, Mapping):
        raise _metadata_error(
            "OpenAI SDK model_dump(mode='python') must return a mapping"
        )
    return payload


def _is_sdk_version_path(normalized_parts: tuple[str, ...]) -> bool:
    if normalized_parts[-1] in _SDK_VERSION_FIELD_SEGMENTS:
        return True
    return any(
        segment == "sdk" or segment.endswith("_sdk")
        for segment in normalized_parts[1:-1]
        if not segment.isdecimal()
    )


def _reconciled_public_identity(
    public_mapping: Mapping[str, Any],
    response: LLMProviderResponse,
) -> tuple[str, str]:
    values: list[str] = []
    for field_name, expected in (
        ("id", response.provider_response_id),
        ("model", response.model_identifier),
    ):
        value = public_mapping.get(field_name)
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
        ):
            raise _metadata_error(
                "OpenAI SDK public response identity must include a trimmed "
                f"nonblank top-level {field_name}"
            )
        if value != expected:
            raise _metadata_error(
                "OpenAI SDK public response identity does not reconcile with "
                f"the mapped response: {field_name}"
            )
        values.append(value)
    return values[0], values[1]


def _version_metadata(
    public_mapping: Mapping[str, Any],
) -> tuple[
    tuple[ProviderPublicMetadataEntry, ...],
    tuple[ProviderVersionIdentifier, ...],
]:
    entries: list[ProviderPublicMetadataEntry] = []
    identifiers: list[ProviderVersionIdentifier] = []
    seen_normalized_paths: set[str] = set()

    def walk(
        container: Mapping[str, Any] | list[Any] | tuple[Any, ...],
        original_parts: tuple[str, ...],
        normalized_parts: tuple[str, ...],
    ) -> None:
        if isinstance(container, (list, tuple)):
            for index, value in enumerate(container):
                index_segment = str(index)
                child_original = (*original_parts, index_segment)
                child_normalized = (*normalized_parts, index_segment)
                if isinstance(value, (Mapping, list, tuple)):
                    walk(value, child_original, child_normalized)
                elif isinstance(value, Iterable) and not isinstance(
                    value, (str, bytes, bytearray)
                ):
                    raise _metadata_error(
                        "OpenAI SDK public response contains an unsupported "
                        f"container: {'.'.join(child_original)}"
                    )
            return

        keys: list[tuple[str, str]] = []
        for key in container:
            if not isinstance(key, str) or not key.strip() or key != key.strip():
                raise _metadata_error(
                    "OpenAI SDK public response mapping keys must be trimmed strings"
                )
            keys.append((_normalized_segment(key), key))

        for normalized_key, key in sorted(keys):
            value = container[key]
            child_original = (*original_parts, key)
            child_normalized = (*normalized_parts, normalized_key)
            if normalized_key in _SENSITIVE_SUBTREE_SEGMENTS:
                continue
            if normalized_key in _VERSION_FIELD_SEGMENTS:
                if _is_sdk_version_path(child_normalized):
                    continue
                normalized_path = ".".join(child_normalized)
                if normalized_path in seen_normalized_paths:
                    raise _metadata_error(
                        "OpenAI SDK public response exposes duplicate normalized "
                        f"version metadata path: {normalized_path}"
                    )
                seen_normalized_paths.add(normalized_path)
                if value is None:
                    continue
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or value != value.strip()
                ):
                    raise _metadata_error(
                        "OpenAI SDK version metadata must be a trimmed nonblank "
                        f"string: {'.'.join(child_original)}"
                    )
                field_path = ".".join(child_original)
                entries.append(
                    ProviderPublicMetadataEntry(
                        field_path=field_path,
                        value=value,
                    )
                )
                identifiers.append(
                    ProviderVersionIdentifier(
                        field_name=field_path,
                        value=value,
                    )
                )
            elif isinstance(value, (Mapping, list, tuple)):
                walk(value, child_original, child_normalized)
            elif isinstance(value, Iterable) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                raise _metadata_error(
                    "OpenAI SDK public response contains an unsupported "
                    f"container: {'.'.join(child_original)}"
                )

    walk(public_mapping, ("response",), ("response",))
    return tuple(entries), tuple(identifiers)


class OpenAIResponsesPreflightBridge:
    """Adapt one injected provider call into a validated preflight observation."""

    def __init__(self, *, provider: OpenAIResponsesProvider) -> None:
        if not isinstance(provider, OpenAIResponsesProvider):
            raise TypeError("provider must be an OpenAIResponsesProvider")
        self._provider = provider

    def generate_preflight(
        self,
        request: LLMExtractionRequest,
    ) -> OpenAIPreflightProviderObservation:
        """Return response and safe public metadata from the exact same SDK call."""
        call_result = self._provider._execute(request)
        response = call_result.response
        public_mapping = _public_response_mapping(call_result.sdk_response)
        public_response_id, public_model = _reconciled_public_identity(
            public_mapping,
            response,
        )
        version_entries, version_identifiers = _version_metadata(public_mapping)
        standard_entries = (
            ProviderPublicMetadataEntry(
                field_path="response.id",
                value=public_response_id,
            ),
            ProviderPublicMetadataEntry(
                field_path="response.model",
                value=public_model,
            ),
            ProviderPublicMetadataEntry(
                field_path="response._request_id",
                value=response.provider_request_id,
            ),
            ProviderPublicMetadataEntry(
                field_path="sdk.version",
                value=response.provider_sdk_version,
            ),
        )
        provenance = version_identifiers or "unavailable"
        return OpenAIPreflightProviderObservation(
            response=response,
            model_version_or_snapshot_provenance=provenance,
            version_provenance_source_response_id=response.provider_response_id,
            observed_from_same_provider_call=True,
            provider_public_metadata_entries=standard_entries + version_entries,
        )


__all__ = ["OpenAIResponsesPreflightBridge"]
