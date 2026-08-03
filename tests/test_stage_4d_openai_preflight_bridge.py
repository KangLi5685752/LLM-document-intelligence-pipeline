"""Offline tests for the Stage 4D-2B OpenAI same-call metadata bridge."""

from __future__ import annotations

import inspect
import json
import socket
import subprocess
import sys
from collections import deque
from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APITimeoutError

from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPreflightProviderObservation,
    OpenAIPricingObservation,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
    run_openai_synthetic_preflight,
)
from document_intelligence.llm_extraction.openai_preflight_bridge import (
    OpenAIResponsesPreflightBridge,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MAX_TIMEOUT_SECONDS,
    OpenAIResponsesProvider,
    build_openai_responses_payload,
)


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
_DEFAULT_PUBLIC_MAPPING = object()
FICTIONAL_RETURNED_MODEL = "gpt-5.4-mini-fictional-returned-id"


def _raw_output() -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-preflight-batch-v0.1",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class FictionalSDKResponse:
    """Small public SDK-response double with explicit serialization."""

    def __init__(
        self,
        *,
        public_mapping: object = _DEFAULT_PUBLIC_MAPPING,
        include_public_identity: bool = True,
        model: str = FICTIONAL_RETURNED_MODEL,
        response_id: str = "resp_fictional_bridge_001",
        request_id: str = "req_fictional_bridge_001",
    ) -> None:
        self.status = "completed"
        self.model = model
        self.id = response_id
        self._request_id = request_id
        self.output = (
            SimpleNamespace(
                type="message",
                content=(
                    SimpleNamespace(type="output_text", text=_raw_output()),
                ),
            ),
        )
        self.usage = SimpleNamespace(input_tokens=100, output_tokens=25)
        selected_mapping = (
            {} if public_mapping is _DEFAULT_PUBLIC_MAPPING else public_mapping
        )
        if include_public_identity and isinstance(selected_mapping, dict):
            self.public_mapping = {
                "id": response_id,
                "model": model,
                **selected_mapping,
            }
        else:
            self.public_mapping = selected_mapping
        self.model_dump_calls: list[str] = []

    def model_dump(self, *, mode: str) -> object:
        self.model_dump_calls.append(mode)
        return self.public_mapping


class FictionalNonCollectionIterable:
    """Unsupported iterable whose values must never be consumed."""

    def __init__(self, values: tuple[object, ...]) -> None:
        self.values = values
        self.iteration_count = 0

    def __iter__(self):
        self.iteration_count += 1
        return iter(self.values)


class FakeResponses:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeOpenAIClient:
    def __init__(self, outcome: Any) -> None:
        self.responses = FakeResponses(outcome)
        self.option_calls: list[dict[str, Any]] = []

    def with_options(self, *, max_retries: int, timeout: float):
        self.option_calls.append(
            {"max_retries": max_retries, "timeout": timeout}
        )
        return self


def _provider(
    sdk_response: object,
) -> tuple[OpenAIResponsesProvider, FakeOpenAIClient]:
    client = FakeOpenAIClient(sdk_response)
    times = iter((10.0, 10.037))
    return (
        OpenAIResponsesProvider(client=client, clock=lambda: next(times)),
        client,
    )


def _bridge(
    sdk_response: object,
) -> tuple[OpenAIResponsesPreflightBridge, FakeOpenAIClient]:
    provider, client = _provider(sdk_response)
    return OpenAIResponsesPreflightBridge(provider=provider), client


def _observe(
    public_mapping: object = _DEFAULT_PUBLIC_MAPPING,
) -> tuple[OpenAIPreflightProviderObservation, FictionalSDKResponse, FakeOpenAIClient]:
    sdk_response = FictionalSDKResponse(public_mapping=public_mapping)
    bridge, client = _bridge(sdk_response)
    observation = bridge.generate_preflight(
        build_synthetic_openai_preflight_request()
    )
    return observation, sdk_response, client


def _metadata(observation: OpenAIPreflightProviderObservation) -> dict[str, object]:
    return {
        entry.field_path: entry.value
        for entry in observation.provider_public_metadata_entries
    }


def test_bridge_has_exact_preflight_provider_shape() -> None:
    signature = inspect.signature(OpenAIResponsesPreflightBridge.generate_preflight)

    assert tuple(signature.parameters) == ("self", "request")
    assert signature.return_annotation == "OpenAIPreflightProviderObservation"


def test_bridge_uses_one_call_with_existing_options_and_payload() -> None:
    request = build_synthetic_openai_preflight_request()
    bridge, client = _bridge(FictionalSDKResponse())

    bridge.generate_preflight(request)

    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert client.responses.calls == [build_openai_responses_payload(request)]


def test_existing_generate_remains_one_call_with_unchanged_output() -> None:
    request = build_synthetic_openai_preflight_request()
    provider, client = _provider(FictionalSDKResponse())

    response = provider.generate(request)

    assert len(client.responses.calls) == 1
    assert response.provider_response_id == "resp_fictional_bridge_001"
    assert response.provider_request_id == "req_fictional_bridge_001"
    assert response.model_identifier == "gpt-5.4-mini-fictional-returned-id"
    assert response.raw_response == _raw_output()
    assert response.latency_ms == 37


def test_shared_primitive_retains_the_exact_sdk_response_object() -> None:
    request = build_synthetic_openai_preflight_request()
    sdk_response = FictionalSDKResponse()
    provider, _ = _provider(sdk_response)

    result = provider._execute(request)

    assert result.sdk_response is sdk_response
    assert result.response.provider_response_id == sdk_response.id


def test_bridge_maps_required_metadata_from_same_response() -> None:
    observation, sdk_response, client = _observe()

    assert observation.response.provider_response_id == sdk_response.id
    assert observation.response.provider_request_id == sdk_response._request_id
    assert observation.response.model_identifier == sdk_response.model
    assert _metadata(observation) == {
        "response.id": sdk_response.id,
        "response.model": sdk_response.model,
        "response._request_id": sdk_response._request_id,
        "sdk.version": OPENAI_INSTALLED_SDK_VERSION,
    }
    assert observation.version_provenance_source_response_id == sdk_response.id
    assert observation.observed_from_same_provider_call is True
    assert sdk_response.model_dump_calls == ["python"]
    assert len(client.responses.calls) == 1


def test_no_separate_version_field_records_literal_unavailable() -> None:
    observation, _, _ = _observe(
        {"model": FICTIONAL_RETURNED_MODEL, "created_at": 123}
    )

    assert observation.model_version_or_snapshot_provenance == "unavailable"


@pytest.mark.parametrize(
    ("public_mapping", "expected_path", "expected_value"),
    (
        (
            {"snapshot_name": "fictional-snapshot-2026-08-04"},
            "response.snapshot_name",
            "fictional-snapshot-2026-08-04",
        ),
        (
            {"model_version": "fictional-version-7"},
            "response.model_version",
            "fictional-version-7",
        ),
        (
            {"metadata": {"revision_id": "fictional-revision-3"}},
            "response.metadata.revision_id",
            "fictional-revision-3",
        ),
        (
            {"Metadata": {"SNAPSHOT-NAME": "fictional-case-variant"}},
            "response.Metadata.SNAPSHOT-NAME",
            "fictional-case-variant",
        ),
    ),
)
def test_version_fields_produce_exact_matching_provenance(
    public_mapping: object,
    expected_path: str,
    expected_value: str,
) -> None:
    observation, _, _ = _observe(public_mapping)

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple((item.field_name, item.value) for item in provenance) == (
        (expected_path, expected_value),
    )
    assert _metadata(observation)[expected_path] == expected_value


def test_multiple_identifiers_are_all_recorded_in_deterministic_order() -> None:
    observation, _, _ = _observe(
        {
            "zeta": {"snapshot_name": "fictional-snapshot"},
            "alpha": {"revision_id": "fictional-revision"},
            "model_version": "fictional-version",
        }
    )

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple(item.field_name for item in provenance) == (
        "response.alpha.revision_id",
        "response.model_version",
        "response.zeta.snapshot_name",
    )


def test_null_version_field_is_ignored() -> None:
    observation, _, _ = _observe({"snapshot_name": None})

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert "response.snapshot_name" not in _metadata(observation)


@pytest.mark.parametrize(
    "invalid_value",
    ("", " ", True, 1, 1.25, [], (), {}, object()),
)
def test_invalid_version_field_value_fails_closed(invalid_value: object) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(public_mapping={"snapshot_name": invalid_value})
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    "public_mapping",
    (
        {"model": FICTIONAL_RETURNED_MODEL},
        {"model_id": "gpt-5.4-mini-fictional-snapshot"},
        {"created_at": "2026-08-04T12:00:00Z"},
        {"sdk": {"version": "fictional-sdk-version"}},
        {"provider_sdk": {"version": "fictional-sdk-version"}},
        {"openai_sdk": {"version": "fictional-sdk-version"}},
        {"client_sdk": {"version": "fictional-sdk-version"}},
        {"metadata": {"provider_sdk": {"version": "fictional-sdk-version"}}},
        {"metadata": [{"provider_sdk": {"version": "fictional-sdk-version"}}]},
        {"Metadata": {"Provider-SDK": {"VERSION": "fictional-sdk-version"}}},
        {"sdk_version": "fictional-sdk-version"},
        {"provider_sdk_version": "fictional-sdk-version"},
    ),
)
def test_identity_and_sdk_fields_are_not_model_version_provenance(
    public_mapping: object,
) -> None:
    observation, _, _ = _observe(public_mapping)

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert len(observation.provider_public_metadata_entries) == 4


@pytest.mark.parametrize(
    "public_mapping",
    (
        {"sdk": {"metadata": {"version": "fictional-sdk-version"}}},
        {"provider_sdk": {"details": {"version": "fictional-sdk-version"}}},
        {
            "openai_sdk": {
                "metadata": [{"version": "fictional-sdk-version"}],
            }
        },
        {
            "metadata": {
                "client_sdk": {"info": {"version": "fictional-sdk-version"}},
            }
        },
        {
            "Metadata": {
                "Provider-SDK": {
                    "Details": {"VERSION": "fictional-sdk-version"},
                }
            }
        },
        {
            "provider_sdk": [
                {"metadata": {"version": "fictional-sdk-version"}},
            ]
        },
    ),
)
def test_all_sdk_namespace_descendants_are_excluded(
    public_mapping: object,
) -> None:
    observation, _, _ = _observe(public_mapping)

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert len(observation.provider_public_metadata_entries) == 4


@pytest.mark.parametrize(
    ("public_mapping", "expected_path"),
    (
        ({"model_version": "fictional-model-version"}, "response.model_version"),
        ({"model_snapshot": "fictional-model-snapshot"}, "response.model_snapshot"),
        (
            {"metadata": {"snapshot_id": "fictional-snapshot"}},
            "response.metadata.snapshot_id",
        ),
        (
            {"metadata": {"revision_id": "fictional-revision"}},
            "response.metadata.revision_id",
        ),
        (
            {"model_details": [{"version": "fictional-model-detail-version"}]},
            "response.model_details.0.version",
        ),
    ),
)
def test_genuine_model_version_fields_remain_detected(
    public_mapping: object,
    expected_path: str,
) -> None:
    observation, _, _ = _observe(public_mapping)

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple(item.field_name for item in provenance) == (expected_path,)


def test_snapshot_inside_list_of_mappings_is_detected() -> None:
    observation, _, _ = _observe(
        {"model_details": [{"snapshot_id": "fictional-indexed-snapshot"}]}
    )

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple((item.field_name, item.value) for item in provenance) == (
        (
            "response.model_details.0.snapshot_id",
            "fictional-indexed-snapshot",
        ),
    )


def test_nested_revision_inside_tuple_and_list_is_detected() -> None:
    observation, _, _ = _observe(
        {
            "model_details": (
                [{"metadata": {"revision_id": "fictional-nested-revision"}}],
            )
        }
    )

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple((item.field_name, item.value) for item in provenance) == (
        (
            "response.model_details.0.0.metadata.revision_id",
            "fictional-nested-revision",
        ),
    )


def test_multiple_indexed_identifiers_are_deterministic() -> None:
    observation, _, _ = _observe(
        {
            "model_details": [
                {"snapshot_id": "fictional-snapshot-zero"},
                {"revision_id": "fictional-revision-one"},
                {"versions": ({"model_version": "fictional-version-two"},)},
            ]
        }
    )

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple(item.field_name for item in provenance) == (
        "response.model_details.0.snapshot_id",
        "response.model_details.1.revision_id",
        "response.model_details.2.versions.0.model_version",
    )


@pytest.mark.parametrize("invalid_value", ("", " ", False, 17, []))
def test_invalid_version_field_inside_sequence_fails_closed(
    invalid_value: object,
) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(
            public_mapping={
                "model_details": [{"snapshot_id": invalid_value}],
            }
        )
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize("sensitive_path", ("output", "reasoning", "tools"))
def test_version_inside_sensitive_sequence_is_excluded(
    sensitive_path: str,
) -> None:
    observation, _, _ = _observe(
        {
            sensitive_path: [
                {"snapshot_id": "must-not-be-retained"},
            ]
        }
    )

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert len(observation.provider_public_metadata_entries) == 4


def test_non_sensitive_sequence_identifier_cannot_silently_be_unavailable() -> None:
    observation, _, _ = _observe(
        {"metadata": [None, {"revision_id": "fictional-visible-revision"}]}
    )

    provenance = observation.model_version_or_snapshot_provenance
    assert provenance != "unavailable"
    assert tuple(item.field_name for item in provenance) == (
        "response.metadata.1.revision_id",
    )


def test_unsupported_container_that_could_hide_structure_fails_closed() -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(
            public_mapping={
                "metadata": deque([{"snapshot_id": "fictional-hidden"}]),
            }
        )
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    "unsupported_iterable",
    (
        (item for item in ({"snapshot_id": "fictional-generator-snapshot"},)),
        iter(({"revision_id": "fictional-iterator-revision"},)),
        FictionalNonCollectionIterable(
            ({"model_version": "fictional-custom-version"},)
        ),
    ),
)
def test_unsupported_iterables_fail_closed_without_consumption(
    unsupported_iterable: object,
) -> None:
    if isinstance(unsupported_iterable, FictionalNonCollectionIterable):
        assert not isinstance(unsupported_iterable, Collection)
    bridge, client = _bridge(
        FictionalSDKResponse(
            public_mapping={"metadata": unsupported_iterable},
        )
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1
    if isinstance(unsupported_iterable, FictionalNonCollectionIterable):
        assert unsupported_iterable.iteration_count == 0


@pytest.mark.parametrize("sensitive_path", ("output", "reasoning", "tools"))
def test_unsupported_iterable_under_sensitive_subtree_is_skipped(
    sensitive_path: str,
) -> None:
    unsupported_iterable = FictionalNonCollectionIterable(
        ({"model_version": "must-not-be-inspected"},)
    )

    observation, _, _ = _observe({sensitive_path: unsupported_iterable})

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert len(observation.provider_public_metadata_entries) == 4
    assert unsupported_iterable.iteration_count == 0


@pytest.mark.parametrize(
    "sensitive_path",
    (
        "output",
        "instructions",
        "prompt",
        "tools",
        "reasoning",
        "errors",
        "headers",
        "raw-response",
        "api-key",
        "credentials",
    ),
)
def test_sensitive_subtrees_are_not_inspected_or_retained(
    sensitive_path: str,
) -> None:
    observation, _, _ = _observe(
        {sensitive_path: {"snapshot_name": "must-not-be-retained"}}
    )

    assert observation.model_version_or_snapshot_provenance == "unavailable"
    assert len(observation.provider_public_metadata_entries) == 4


@pytest.mark.parametrize("public_mapping", ([], (), "not-a-mapping", 7, None))
def test_model_dump_must_return_mapping(public_mapping: object) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(public_mapping=public_mapping)
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    "public_mapping",
    (
        {"model": FICTIONAL_RETURNED_MODEL},
        {"id": "resp_fictional_bridge_001"},
    ),
)
def test_dumped_identity_fields_are_required(public_mapping: object) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(
            public_mapping=public_mapping,
            include_public_identity=False,
        )
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("id", None),
        ("id", ""),
        ("id", " "),
        ("id", 7),
        ("model", None),
        ("model", ""),
        ("model", " "),
        ("model", 7),
    ),
)
def test_dumped_identity_must_be_trimmed_nonblank_string(
    field_name: str,
    invalid_value: object,
) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(public_mapping={field_name: invalid_value})
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    ("field_name", "mismatched_value"),
    (
        ("id", "resp_fictional_mismatch"),
        ("model", "gpt-5.4-mini-fictional-mismatch"),
    ),
)
def test_dumped_identity_must_match_mapped_response(
    field_name: str,
    mismatched_value: str,
) -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(public_mapping={field_name: mismatched_value})
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


def test_ordinary_model_dump_exception_is_wrapped_consistently() -> None:
    sdk_response = FictionalSDKResponse()

    def fail_model_dump(*, mode: str) -> object:
        raise RuntimeError(f"fictional serialization failure in {mode}")

    sdk_response.model_dump = fail_model_dump  # type: ignore[method-assign]
    bridge, client = _bridge(sdk_response)

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt(), SystemExit()))
def test_model_dump_base_exceptions_are_not_wrapped(interrupt: BaseException) -> None:
    sdk_response = FictionalSDKResponse()

    def interrupt_model_dump(*, mode: str) -> object:
        raise interrupt

    sdk_response.model_dump = interrupt_model_dump  # type: ignore[method-assign]
    bridge, client = _bridge(sdk_response)

    with pytest.raises(type(interrupt)):
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert len(client.responses.calls) == 1


def test_missing_model_dump_fails_closed() -> None:
    sdk_response = FictionalSDKResponse()
    sdk_response.model_dump = None  # type: ignore[method-assign]
    bridge, client = _bridge(sdk_response)

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


def test_duplicate_normalized_version_paths_fail_closed() -> None:
    bridge, client = _bridge(
        FictionalSDKResponse(
            public_mapping={
                "metadata": {
                    "snapshot-name": "fictional-a",
                    "snapshot_name": "fictional-b",
                }
            }
        )
    )

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_PROVIDER_METADATA_INVALID
    assert len(client.responses.calls) == 1


def test_callers_cannot_inject_provenance_metadata_or_response_identity() -> None:
    bridge, client = _bridge(FictionalSDKResponse())
    request = build_synthetic_openai_preflight_request()

    with pytest.raises(TypeError):
        bridge.generate_preflight(  # type: ignore[call-arg]
            request,
            model_version_or_snapshot_provenance="fictional-override",
        )

    assert client.responses.calls == []


def test_provider_timeout_mapping_and_no_retry_remain_unchanged() -> None:
    timeout = APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
    bridge, client = _bridge(timeout)

    with pytest.raises(Stage4BError) as captured:
        bridge.generate_preflight(build_synthetic_openai_preflight_request())

    assert captured.value.code is Stage4BErrorCode.TIMEOUT
    assert len(client.responses.calls) == 1
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]


def test_bridge_constructs_no_default_client_and_reads_no_environment() -> None:
    source = inspect.getsource(sys.modules[OpenAIResponsesPreflightBridge.__module__])

    assert "OpenAI(" not in source
    assert "OPENAI_API_KEY" not in source
    assert "getenv" not in source
    assert "environ" not in source


def test_bridge_performs_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)

    observation, _, _ = _observe()

    assert observation.response.provider_response_id == "resp_fictional_bridge_001"


def test_bridge_accesses_no_development_or_held_out_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[Path] = []
    original_open = Path.open

    def guarded_open(path: Path, *args: object, **kwargs: object):
        resolved = path.resolve()
        lowered = str(resolved).casefold().replace("\\", "/")
        if "/data/" in lowered or "/evaluation/" in lowered:
            raise AssertionError(f"forbidden repository data access: {resolved}")
        opened.append(resolved)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    observation, _, _ = _observe()

    assert observation.response.provider_response_id == "resp_fictional_bridge_001"
    assert all("/data/" not in str(path).casefold() for path in opened)


def test_final_record_excludes_raw_sdk_object_and_transient_metadata_values() -> None:
    sdk_response = FictionalSDKResponse(
        public_mapping={
            "metadata": {"fictional_label": "transient-metadata-secret"}
        }
    )
    bridge, _ = _bridge(sdk_response)
    record = run_openai_synthetic_preflight(
        provider=bridge,
        authorization=OpenAIPreflightAuthorization(
            authorization_id="fictional-authorization",
            authorized_by="Fictional Project Owner",
            authorized_at_utc=NOW - timedelta(minutes=5),
            scope=PREFLIGHT_AUTHORIZATION_SCOPE,
            maximum_provider_calls=1,
            real_provider_preflight_authorized=True,
        ),
        pricing_observation=OpenAIPricingObservation(
            observed_at_utc=NOW,
            source_title="Fictional pricing",
            source_url="https://example.invalid/pricing",
            input_usd_per_million_tokens=Decimal("1.25"),
            output_usd_per_million_tokens=Decimal("5.50"),
            currency="USD",
        ),
        data_controls_observation=OpenAIDataControlsObservation(
            observed_at_utc=NOW,
            source_title="Fictional data controls",
            source_url="https://example.invalid/data-controls",
            store_false_required=True,
            zero_retention_claimed=False,
            retention_and_abuse_monitoring_summary=(
                "Fictional terms retain explicit limitations."
            ),
        ),
        clock=lambda: NOW,
    )

    serialized = preflight_record_bytes(record)
    assert b"transient-metadata-secret" not in serialized
    assert b"public_mapping" not in serialized
    assert b"model_dump_calls" not in serialized


@pytest.mark.parametrize(
    "imports",
    (
        (
            "document_intelligence.llm_extraction.openai_provider,"
            "document_intelligence.llm_extraction.openai_preflight,"
            "document_intelligence.llm_extraction.openai_preflight_bridge"
        ),
        (
            "document_intelligence.llm_extraction.openai_preflight_bridge,"
            "document_intelligence.llm_extraction.openai_preflight,"
            "document_intelligence.llm_extraction.openai_provider"
        ),
    ),
)
def test_import_orders_have_no_circular_import_failure(imports: str) -> None:
    code = ";".join(f"import {name}" for name in imports.split(","))

    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
