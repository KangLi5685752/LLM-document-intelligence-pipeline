"""Offline tests for the Stage 4D-3A preflight execution transaction."""

from __future__ import annotations

import inspect
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError, RateLimitError
from pydantic import ValidationError

import document_intelligence.llm_extraction.openai_preflight_execution as execution
import document_intelligence.llm_extraction.openai_preflight as preflight_contract
from document_intelligence.llm_extraction.errors import (
    Stage4BError,
    Stage4BErrorCode,
)
from document_intelligence.llm_extraction.openai_preflight import (
    PREFLIGHT_AUTHORIZATION_SCOPE,
    OpenAIDataControlsObservation,
    OpenAIPreflightAuthorization,
    OpenAIPricingObservation,
    build_synthetic_openai_preflight_request,
    preflight_record_bytes,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MAX_TIMEOUT_SECONDS,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    build_request_envelope,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
FICTIONAL_KEY = "fictional-test-key-value"


def _authorization(
    *,
    authorized_at: datetime = NOW - timedelta(minutes=5),
) -> OpenAIPreflightAuthorization:
    return OpenAIPreflightAuthorization(
        authorization_id="fictional-stage-4d-3a-authorization",
        authorized_by="Fictional Project Owner",
        authorized_at_utc=authorized_at,
        scope=PREFLIGHT_AUTHORIZATION_SCOPE,
        maximum_provider_calls=1,
        real_provider_preflight_authorized=True,
    )


def _pricing(*, observed_at: datetime = NOW) -> OpenAIPricingObservation:
    return OpenAIPricingObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed pricing",
        source_url="https://example.invalid/pricing",
        input_usd_per_million_tokens=Decimal("1.25"),
        output_usd_per_million_tokens=Decimal("5.50"),
        currency="USD",
    )


def _data_controls(
    *,
    observed_at: datetime = NOW,
) -> OpenAIDataControlsObservation:
    return OpenAIDataControlsObservation(
        observed_at_utc=observed_at,
        source_title="Fictional reviewed data controls",
        source_url="https://example.invalid/data-controls",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary=(
            "Fictional limitations remain applicable to this test observation."
        ),
    )


def _write_model(path: Path, model: object) -> None:
    payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
    path.write_bytes(canonical_json_bytes(payload))


def _input_paths(
    tmp_path: Path,
    *,
    authorization: OpenAIPreflightAuthorization | None = None,
    pricing: OpenAIPricingObservation | None = None,
    data_controls: OpenAIDataControlsObservation | None = None,
) -> tuple[Path, Path, Path]:
    authorization_path = tmp_path / "authorization.json"
    pricing_path = tmp_path / "pricing.json"
    data_controls_path = tmp_path / "data-controls.json"
    _write_model(authorization_path, authorization or _authorization())
    _write_model(pricing_path, pricing or _pricing())
    _write_model(data_controls_path, data_controls or _data_controls())
    return authorization_path, pricing_path, data_controls_path


def _raw_output(*, valid: bool = True) -> str:
    if not valid:
        return "{not-json"
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-execution-batch-v0.1",
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
    def __init__(self, *, valid_output: bool = True) -> None:
        self.status = "completed"
        self.model = "gpt-5.4-mini-fictional-returned-id"
        self.id = "resp_fictional_execution_001"
        self._request_id = "req_fictional_execution_001"
        self.output = (
            SimpleNamespace(
                type="message",
                content=(
                    SimpleNamespace(
                        type="output_text",
                        text=_raw_output(valid=valid_output),
                    ),
                ),
            ),
        )
        self.usage = SimpleNamespace(input_tokens=100, output_tokens=25)

    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "python"
        return {
            "id": self.id,
            "model": self.model,
            "metadata": {"fictional_label": "transient-public-value"},
        }


class FakeResponses:
    def __init__(self, outcome: object, marker_path: Path) -> None:
        self.outcome = outcome
        self.marker_path = marker_path
        self.calls: list[dict[str, Any]] = []
        self.marker_present_at_call = False

    def create(self, **kwargs: Any) -> object:
        self.marker_present_at_call = self.marker_path.is_file()
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: object, marker_path: Path) -> None:
        self.responses = FakeResponses(outcome, marker_path)
        self.option_calls: list[dict[str, object]] = []

    def with_options(self, *, max_retries: int, timeout: float):
        self.option_calls.append(
            {"max_retries": max_retries, "timeout": timeout}
        )
        return self


def _artifact_paths(root: Path) -> tuple[Path, Path]:
    return (
        root.joinpath(*execution.ATTEMPT_MARKER_RELATIVE_PATH.parts),
        root.joinpath(*execution.SUCCESSFUL_RECORD_RELATIVE_PATH.parts),
    )


def _execute(
    tmp_path: Path,
    *,
    outcome: object | None = None,
    paths: tuple[Path, Path, Path] | None = None,
    api_key_reader: Any = None,
    client_factory: Any = None,
    confirmation: str | None = execution.EXECUTION_CONFIRMATION,
    execute_real_preflight: bool = True,
):
    selected_paths = paths or _input_paths(tmp_path)
    marker_path, _ = _artifact_paths(tmp_path)
    client = FakeClient(outcome or FictionalSDKResponse(), marker_path)
    key_calls: list[str] = []
    factory_calls: list[str] = []

    def read_key() -> str:
        key_calls.append("called")
        return FICTIONAL_KEY

    def build_client(key: str) -> object:
        factory_calls.append(key)
        return client

    result = execution._execute_openai_synthetic_preflight_transaction(
        authorization_path=selected_paths[0],
        pricing_path=selected_paths[1],
        data_controls_path=selected_paths[2],
        repository_root=tmp_path,
        execute_real_preflight=execute_real_preflight,
        confirmation=confirmation,
        clock=lambda: NOW,
        api_key_reader=api_key_reader or read_key,
        client_factory=client_factory or build_client,
    )
    return result, client, key_calls, factory_calls


def test_execution_plan_is_deterministic_and_self_hashed() -> None:
    first = execution.build_openai_preflight_execution_plan()
    second = execution.build_openai_preflight_execution_plan()

    assert first == second
    payload = first.model_dump(mode="json", exclude={"execution_plan_sha256"})
    assert first.execution_plan_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(payload)
    )
    with pytest.raises(ValidationError):
        execution.OpenAIPreflightExecutionPlan.model_validate(
            {**first.model_dump(mode="python"), "execution_plan_sha256": "0" * 64}
        )


def test_execution_plan_hashes_match_existing_production_builders() -> None:
    plan = execution.build_openai_preflight_execution_plan()
    request = build_synthetic_openai_preflight_request()

    assert plan.canonical_request_sha256 == request.canonical_request_sha256
    assert plan.prompt_sha256 == request.prompt_sha256
    assert plan.synthetic_document_sha256 == request.document_sha256
    assert plan.strict_schema_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_candidate_schema())
    )
    assert plan.provider_payload_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(build_openai_responses_payload(request))
    )


def test_execution_module_contains_no_hard_coded_sha256_literals() -> None:
    source = Path(execution.__file__).read_text(encoding="utf-8")

    assert re.findall(r'"[A-F0-9]{64}"', source) == []


def test_changed_production_schema_builder_changes_runtime_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_builder = execution.build_openai_candidate_schema
    original = execution.build_openai_preflight_execution_plan()

    def changed_builder() -> dict[str, Any]:
        schema = original_builder()
        schema["x-fictional-contract-change"] = True
        return schema

    monkeypatch.setattr(execution, "build_openai_candidate_schema", changed_builder)
    changed = execution.build_openai_preflight_execution_plan()

    assert changed.strict_schema_sha256 != original.strict_schema_sha256
    assert changed.execution_plan_sha256 != original.execution_plan_sha256


def test_readiness_plan_uses_one_transaction_derived_anchor_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    original_request_builder = execution.build_synthetic_openai_preflight_request
    original_schema_builder = execution.build_openai_candidate_schema
    original_payload_builder = execution.build_openai_responses_payload
    observed: dict[str, object] = {}

    def request_builder():
        request = original_request_builder()
        observed["request"] = request
        return request

    def schema_builder() -> dict[str, Any]:
        schema = original_schema_builder()
        observed["schema"] = schema
        return schema

    def payload_builder(request: object) -> dict[str, Any]:
        payload = original_payload_builder(request)  # type: ignore[arg-type]
        observed["payload"] = payload
        return payload

    monkeypatch.setattr(
        execution, "build_synthetic_openai_preflight_request", request_builder
    )
    monkeypatch.setattr(execution, "build_openai_candidate_schema", schema_builder)
    monkeypatch.setattr(execution, "build_openai_responses_payload", payload_builder)

    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )
    request = observed["request"]
    assert readiness.plan.canonical_request_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(
            request.model_dump(  # type: ignore[attr-defined]
                mode="json", exclude={"canonical_request_sha256"}
            )
        )
    )
    assert readiness.plan.prompt_sha256 == request.prompt_sha256  # type: ignore[attr-defined]
    assert readiness.plan.synthetic_document_sha256 == request.document_sha256  # type: ignore[attr-defined]
    assert readiness.plan.strict_schema_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(observed["schema"])
    )
    assert readiness.plan.provider_payload_sha256 == uppercase_sha256_bytes(
        canonical_json_bytes(observed["payload"])
    )


def test_execution_plan_contains_only_non_sensitive_identity() -> None:
    raw = canonical_json_bytes(
        execution.build_openai_preflight_execution_plan().model_dump(mode="json")
    )

    for forbidden in (
        b"fictional-test-key",
        b"Synthetic preflight only",
        b"system_prompt",
        b"raw_response",
        b"retention_and_abuse_monitoring_summary",
    ):
        assert forbidden not in raw


def test_execution_plan_fixes_paths_and_one_call_limit() -> None:
    plan = execution.build_openai_preflight_execution_plan()

    assert plan.maximum_provider_calls == 1
    assert plan.attempt_marker_path == execution.ATTEMPT_MARKER_RELATIVE_PATH.as_posix()
    assert plan.successful_record_path == (
        execution.SUCCESSFUL_RECORD_RELATIVE_PATH.as_posix()
    )


def test_anchor_derivation_reads_only_frozen_prompt_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[Path] = []
    original_open = Path.open

    def tracked_open(path: Path, *args: object, **kwargs: object):
        opened.append(path.resolve())
        return original_open(path, *args, **kwargs)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("environment, client and network access is forbidden")

    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(execution, "_openai_api_key_from_environment", forbidden)
    monkeypatch.setattr(execution, "_production_openai_client_factory", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    plan = execution.build_openai_preflight_execution_plan()

    assert plan.maximum_provider_calls == 1
    prompt_root = Path(execution.__file__).parent / "prompts"
    assert set(opened) == {
        (prompt_root / "system_v0_1.txt").resolve(),
        (prompt_root / "extraction_v0_1.txt").resolve(),
    }


def test_valid_explicit_inputs_load_through_existing_models(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)

    inputs = execution.load_openai_preflight_inputs(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
    )

    assert inputs.authorization == _authorization()
    assert inputs.pricing_observation == _pricing()
    assert inputs.data_controls_observation == _data_controls()


@pytest.mark.parametrize(
    "invalid_bytes",
    (
        b"\xff\xfe",
        b'{"duplicate":1,"duplicate":2}',
        b"{} {}",
        b"[]",
        b"NaN",
    ),
)
def test_invalid_input_encoding_or_json_fails_closed(
    tmp_path: Path,
    invalid_bytes: bytes,
) -> None:
    paths = _input_paths(tmp_path)
    paths[0].write_bytes(invalid_bytes)

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


def test_oversized_input_fails_closed(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    paths[1].write_bytes(b" " * (execution.MAXIMUM_INPUT_FILE_BYTES + 1))

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


@pytest.mark.parametrize("invalid_entry", ("missing", "directory"))
def test_missing_or_non_file_input_fails_closed(
    tmp_path: Path,
    invalid_entry: str,
) -> None:
    paths = _input_paths(tmp_path)
    paths[0].unlink()
    if invalid_entry == "directory":
        paths[0].mkdir()

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


def test_symlink_input_fails_closed(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    target = tmp_path / "real-authorization.json"
    target.write_bytes(paths[0].read_bytes())
    paths[0].unlink()
    try:
        paths[0].symlink_to(target)
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


def test_extra_input_field_fails_existing_strict_model(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    payload = json.loads(paths[2].read_text(encoding="utf-8"))
    payload["provider_override"] = "forbidden"
    paths[2].write_bytes(canonical_json_bytes(payload))

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


def test_input_loading_opens_only_three_explicit_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    opened: list[Path] = []
    original_open = execution._open_read_only_descriptor

    def tracked_open(path: Path) -> int:
        opened.append(path.resolve())
        return original_open(path)

    monkeypatch.setattr(execution, "_open_read_only_descriptor", tracked_open)

    execution.load_openai_preflight_inputs(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
    )

    assert opened == [path.resolve() for path in paths]


@pytest.mark.parametrize(
    "protected_relative_path",
    (
        "artifacts/ingestion/stage_2a_development/S001.json",
        "artifacts/stage_3b/development_parsed/S001.json",
        "artifacts/ingestion/stage_2b_held_out/S005.json",
        "data/raw/S007.pdf",
        "data/annotations/public_gold_facts_v0.1.jsonl",
        "evaluation/baselines/deterministic-baseline-v0.4/development/report.json",
        "data/manifests/stage_4d_request_manifest.json",
        "artifacts/llm_extraction/response_cache/entry.json",
        execution.ATTEMPT_MARKER_RELATIVE_PATH.as_posix(),
        execution.SUCCESSFUL_RECORD_RELATIVE_PATH.as_posix(),
    ),
)
def test_protected_repository_inputs_fail_before_any_descriptor_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    protected_relative_path: str,
) -> None:
    paths = list(_input_paths(tmp_path))
    paths[2] = tmp_path.joinpath(*protected_relative_path.split("/"))
    opened: list[Path] = []

    def forbidden_open(path: Path) -> int:
        opened.append(path)
        raise AssertionError("protected input must fail before open")

    monkeypatch.setattr(execution, "_open_read_only_descriptor", forbidden_open)

    with pytest.raises(Stage4BError) as captured:
        execution._load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID
    assert opened == []


def test_private_root_injection_cannot_unprotect_installed_repository_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = list(_input_paths(tmp_path))
    installed_root = Path(execution.__file__).parents[3]
    paths[2] = installed_root / "data" / "annotations" / "public_gold_facts_v0.1.jsonl"
    opened: list[Path] = []

    def forbidden_open(path: Path) -> int:
        opened.append(path)
        raise AssertionError("installed protected input must fail before open")

    monkeypatch.setattr(execution, "_open_read_only_descriptor", forbidden_open)

    with pytest.raises(Stage4BError) as captured:
        execution._load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID
    assert opened == []


def test_parent_symlink_input_fails_before_descriptor_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = list(_input_paths(tmp_path))
    real_parent = tmp_path / "real-input-parent"
    real_parent.mkdir()
    target = real_parent / "authorization.json"
    target.write_bytes(paths[0].read_bytes())
    linked_parent = tmp_path / "linked-input-parent"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symbolic links are unavailable: {error}")
    paths[0] = linked_parent / "authorization.json"
    opened: list[Path] = []
    monkeypatch.setattr(
        execution,
        "_open_read_only_descriptor",
        lambda path: opened.append(path) or -1,
    )

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID
    assert opened == []


@pytest.mark.parametrize(
    "unsafe_path",
    (
        r"\\fictional-server\share\authorization.json",
        r"\\?\C:\fictional\authorization.json",
        r"\\.\C:\fictional\authorization.json",
    ),
)
def test_unc_and_device_paths_fail_before_filesystem_inspection(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_path: str,
) -> None:
    inspected: list[object] = []
    monkeypatch.setattr(
        execution.os,
        "lstat",
        lambda path: inspected.append(path) or (_ for _ in ()).throw(
            AssertionError("unsafe path must fail before lstat")
        ),
    )
    monkeypatch.setattr(
        execution,
        "_open_read_only_descriptor",
        lambda path: (_ for _ in ()).throw(
            AssertionError("unsafe path must fail before open")
        ),
    )

    with pytest.raises(Stage4BError) as captured:
        execution._read_json_object(Path(unsafe_path), label="authorization")

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID
    assert inspected == []


def test_replacement_between_inspection_and_open_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    original_open = execution._open_read_only_descriptor
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(paths[0].read_bytes())
    original = tmp_path / "inspected-original.json"

    def replacing_open(path: Path) -> int:
        path.replace(original)
        replacement.replace(path)
        return original_open(path)

    monkeypatch.setattr(execution, "_open_read_only_descriptor", replacing_open)

    with pytest.raises(Stage4BError) as captured:
        execution.load_openai_preflight_inputs(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_INPUT_FILE_INVALID


def test_parser_uses_the_descriptor_that_was_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    opened_descriptors: list[int] = []
    parsed_descriptors: list[int] = []
    original_descriptor_open = execution._open_read_only_descriptor
    original_fdopen = execution.os.fdopen

    def tracked_descriptor_open(path: Path) -> int:
        descriptor = original_descriptor_open(path)
        opened_descriptors.append(descriptor)
        return descriptor

    def tracked_fdopen(descriptor: int, *args: object, **kwargs: object):
        parsed_descriptors.append(descriptor)
        return original_fdopen(descriptor, *args, **kwargs)

    monkeypatch.setattr(
        execution, "_open_read_only_descriptor", tracked_descriptor_open
    )
    monkeypatch.setattr(execution.os, "fdopen", tracked_fdopen)

    execution.load_openai_preflight_inputs(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
    )

    assert parsed_descriptors == opened_descriptors
    assert len(opened_descriptors) == 3


def test_readiness_never_reads_key_constructs_client_or_writes(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    output = tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts)

    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )

    assert readiness.plan.maximum_provider_calls == 1
    assert not output.exists()


@pytest.mark.parametrize(
    ("execute_flag", "confirmation"),
    (
        (False, execution.EXECUTION_CONFIRMATION),
        (True, None),
        (True, ""),
        (True, execution.EXECUTION_CONFIRMATION.lower()),
        (True, f" {execution.EXECUTION_CONFIRMATION}"),
        (True, f"{execution.EXECUTION_CONFIRMATION} "),
        (True, "EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT"),
    ),
)
def test_missing_or_inexact_execution_gate_fails_before_secret_access(
    tmp_path: Path,
    execute_flag: bool,
    confirmation: str | None,
) -> None:
    paths = _input_paths(tmp_path)
    key_calls: list[str] = []
    factory_calls: list[str] = []

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=execute_flag,
            confirmation=confirmation,
            clock=lambda: NOW,
            api_key_reader=lambda: key_calls.append("called") or FICTIONAL_KEY,
            client_factory=lambda key: factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert key_calls == []
    assert factory_calls == []
    assert not tmp_path.joinpath(*execution.OUTPUT_DIRECTORY.parts).exists()


@pytest.mark.parametrize("invalid_kind", ("authorization", "pricing", "controls"))
def test_invalid_local_input_fails_before_secret_access(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    if invalid_kind == "authorization":
        paths = _input_paths(
            tmp_path,
            authorization=_authorization(authorized_at=NOW + timedelta(minutes=1)),
        )
    elif invalid_kind == "pricing":
        paths = _input_paths(
            tmp_path,
            pricing=_pricing(observed_at=NOW - timedelta(days=1)),
        )
    else:
        paths = _input_paths(
            tmp_path,
            data_controls=_data_controls(observed_at=NOW - timedelta(days=1)),
        )
    key_calls: list[str] = []
    factory_calls: list[str] = []

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: key_calls.append("called") or FICTIONAL_KEY,
            client_factory=lambda key: factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert key_calls == []
    assert factory_calls == []


@pytest.mark.parametrize("artifact", ("marker", "record"))
def test_existing_fixed_artifact_blocks_before_secret_and_client(
    tmp_path: Path,
    artifact: str,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    target = marker if artifact == "marker" else record
    target.parent.mkdir(parents=True)
    target.write_text("fictional-existing-artifact\n", encoding="utf-8")
    key_calls: list[str] = []
    factory_calls: list[str] = []

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: key_calls.append("called") or FICTIONAL_KEY,
            client_factory=lambda key: factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS
    assert key_calls == []
    assert factory_calls == []


@pytest.mark.parametrize("missing_key", (None, "", " ", " padded"))
def test_missing_or_blank_key_fails_before_marker_and_client(
    tmp_path: Path,
    missing_key: str | None,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    factory_calls: list[str] = []

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: missing_key,
            client_factory=lambda key: factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING
    assert factory_calls == []
    assert not marker.exists()
    assert not record.exists()


def test_anchor_derivation_precedes_key_access_and_marker_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    marker, _ = _artifact_paths(tmp_path)
    events: list[str] = []
    original_derivation = execution._derive_execution_plan_anchors

    def derive_anchors():
        assert not marker.exists()
        events.append("anchors")
        return original_derivation()

    def read_key() -> str:
        assert not marker.exists()
        events.append("key")
        return FICTIONAL_KEY

    monkeypatch.setattr(execution, "_derive_execution_plan_anchors", derive_anchors)

    result, client, _, _ = _execute(
        tmp_path,
        paths=paths,
        api_key_reader=read_key,
    )

    assert result.record.preflight_status == "passed"
    assert events == ["anchors", "key"]
    assert len(client.responses.calls) == 1


def test_exact_provider_entry_request_is_bound_to_readiness_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_requests: list[object] = []
    original_derivation = execution._derive_execution_plan_anchors_for_request

    def captured_derivation(request: object):
        captured_requests.append(request)
        return original_derivation(request)  # type: ignore[arg-type]

    monkeypatch.setattr(
        execution,
        "_derive_execution_plan_anchors_for_request",
        captured_derivation,
    )

    result, client, _, _ = _execute(tmp_path)

    assert len(captured_requests) == 2
    assert captured_requests[0] == captured_requests[1]
    provider_entry_anchors = original_derivation(  # type: ignore[arg-type]
        captured_requests[1]
    )
    execution._require_plan_anchor_match(result.plan, provider_entry_anchors)
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(
    "drift_kind",
    ("request", "prompt", "document"),
)
def test_request_prompt_or_document_drift_fails_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_kind: str,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    request = preflight_contract.build_synthetic_openai_preflight_request()
    evidence_blocks = request.evidence_blocks
    request_id = request.request_id
    document_sha256 = request.document_sha256
    if drift_kind == "request":
        request_id = "openai-synthetic-preflight-request-drift"
    elif drift_kind == "prompt":
        evidence_blocks = (
            request.evidence_blocks[0].model_copy(
                update={"text": "Fictional changed synthetic preflight text."}
            ),
        )
    else:
        document_sha256 = "A" * 64
    drifted = build_request_envelope(
        invocation_role=request.invocation_role,
        request_id=request_id,
        source_id=request.source_id,
        document_sha256=document_sha256,
        provider_configuration_id=request.provider_configuration_id,
        model_configuration_id=request.model_configuration_id,
        evidence_blocks=evidence_blocks,
    )
    assert drifted.canonical_request_sha256 != request.canonical_request_sha256
    if drift_kind == "prompt":
        assert drifted.prompt_sha256 != request.prompt_sha256
    if drift_kind == "document":
        assert drifted.document_sha256 != request.document_sha256

    def install_drift_after_readiness() -> str:
        monkeypatch.setattr(
            preflight_contract,
            "build_synthetic_openai_preflight_request",
            lambda: drifted,
        )
        return FICTIONAL_KEY

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=install_drift_after_readiness,
            client_factory=lambda key: client,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert marker.is_file()
    assert not record.exists()
    assert client.responses.calls == []


def test_schema_drift_fails_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    original_builder = execution.build_openai_candidate_schema

    def install_drift_after_readiness() -> str:
        def changed_schema() -> dict[str, Any]:
            schema = original_builder()
            schema["x-fictional-provider-entry-drift"] = True
            return schema

        monkeypatch.setattr(
            execution, "build_openai_candidate_schema", changed_schema
        )
        return FICTIONAL_KEY

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=install_drift_after_readiness,
            client_factory=lambda key: client,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert marker.is_file()
    assert not record.exists()
    assert client.responses.calls == []


def test_payload_drift_fails_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    original_builder = execution.build_openai_responses_payload

    def install_drift_after_readiness() -> str:
        def changed_payload(request: object) -> dict[str, Any]:
            payload = original_builder(request)  # type: ignore[arg-type]
            payload["x-fictional-provider-entry-drift"] = True
            return payload

        monkeypatch.setattr(
            execution, "build_openai_responses_payload", changed_payload
        )
        return FICTIONAL_KEY

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=install_drift_after_readiness,
            client_factory=lambda key: client,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert marker.is_file()
    assert not record.exists()
    assert client.responses.calls == []


@pytest.mark.parametrize(
    "record_field",
    (
        "canonical_request_sha256",
        "prompt_sha256",
        "document_sha256",
        "strict_schema_sha256",
        "provider_payload_sha256",
    ),
)
def test_returned_record_anchor_drift_is_not_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_field: str,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record_path = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    original_runner = execution.run_openai_synthetic_preflight

    def drifted_runner(**kwargs: object):
        record = original_runner(**kwargs)  # type: ignore[arg-type]
        return record.model_copy(update={record_field: "A" * 64})

    monkeypatch.setattr(
        execution, "run_openai_synthetic_preflight", drifted_runner
    )

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda key: client,
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_EXECUTION_GATE_INVALID
    assert marker.is_file()
    assert not record_path.exists()
    assert len(client.responses.calls) == 1


def test_marker_precedes_sanitized_client_factory_failure(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)

    def failed_factory(key: str) -> object:
        raise RuntimeError(f"fictional factory must not leak {key}")

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=failed_factory,
        )

    assert captured.value.code is Stage4BErrorCode.EXECUTION_FAILED
    assert captured.value.__cause__ is None
    assert FICTIONAL_KEY not in str(captured.value)
    assert marker.is_file()
    assert not record.exists()


def test_provider_wrapper_construction_failure_is_sanitized_after_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)

    def failed_wrapper(*args: object, **kwargs: object) -> object:
        assert marker.is_file()
        raise RuntimeError(f"fictional wrapper must not leak {FICTIONAL_KEY}")

    monkeypatch.setattr(execution, "OpenAIResponsesProvider", failed_wrapper)

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: FICTIONAL_KEY,
            client_factory=lambda key: object(),
        )

    assert captured.value.code is Stage4BErrorCode.EXECUTION_FAILED
    assert captured.value.__cause__ is None
    assert FICTIONAL_KEY not in str(captured.value)
    assert marker.is_file()
    assert not record.exists()


def test_key_reader_failure_is_sanitized_before_marker_and_client(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    factory_calls: list[str] = []

    def failed_reader() -> str:
        raise RuntimeError(f"must not leak {FICTIONAL_KEY}")

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=failed_reader,
            client_factory=lambda key: factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_API_KEY_MISSING
    assert captured.value.__cause__ is None
    assert FICTIONAL_KEY not in str(captured.value)
    assert factory_calls == []
    assert not marker.exists()
    assert not record.exists()


def test_marker_exists_before_client_factory_is_entered(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    marker, _ = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    marker_states: list[bool] = []

    def build_client(key: str) -> object:
        marker_states.append(marker.is_file())
        return client

    result = execution._execute_openai_synthetic_preflight_transaction(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        execute_real_preflight=True,
        confirmation=execution.EXECUTION_CONFIRMATION,
        clock=lambda: NOW,
        api_key_reader=lambda: FICTIONAL_KEY,
        client_factory=build_client,
    )

    assert result.record.preflight_status == "passed"
    assert marker_states == [True]


def test_valid_fake_execution_is_one_call_transaction(tmp_path: Path) -> None:
    result, client, key_calls, factory_calls = _execute(tmp_path)
    marker, record = _artifact_paths(tmp_path)

    assert key_calls == ["called"]
    assert factory_calls == [FICTIONAL_KEY]
    assert client.responses.marker_present_at_call is True
    assert len(client.responses.calls) == 1
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert marker.is_file()
    assert record.is_file()
    assert marker.read_bytes() == execution.attempt_marker_bytes(result.marker) + b"\n"
    assert record.read_bytes() == preflight_record_bytes(result.record) + b"\n"
    assert marker.read_bytes().endswith(b"\n")
    assert not marker.read_bytes().endswith(b"\n\n")
    assert not record.read_bytes().endswith(b"\n\n")
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert set(marker_payload) == {
        "authorization_id",
        "authorization_scope",
        "attempt_timestamp_utc",
        "execution_plan_sha256",
        "marker_schema_version",
        "marker_sha256",
        "maximum_provider_calls",
        "preflight_id",
        "state",
    }
    assert marker_payload["state"] == "provider_call_may_have_started"
    without_hash = dict(marker_payload)
    del without_hash["marker_sha256"]
    assert marker_payload["marker_sha256"] == uppercase_sha256_bytes(
        canonical_json_bytes(without_hash)
    )
    assert marker_payload["execution_plan_sha256"] == result.plan.execution_plan_sha256
    assert result.record.canonical_request_sha256 == (
        result.plan.canonical_request_sha256
    )
    assert result.record.prompt_sha256 == result.plan.prompt_sha256
    assert result.record.document_sha256 == result.plan.synthetic_document_sha256
    assert result.record.strict_schema_sha256 == result.plan.strict_schema_sha256
    assert result.record.provider_payload_sha256 == (
        result.plan.provider_payload_sha256
    )


def test_marker_and_record_writes_both_reject_overwrite(tmp_path: Path) -> None:
    marker, record = _artifact_paths(tmp_path)
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"existing-marker\n")
    record.write_bytes(b"existing-record\n")

    with pytest.raises(Stage4BError) as marker_error:
        execution._write_exclusive(marker, b"replacement", marker=True)
    with pytest.raises(Stage4BError) as record_error:
        execution._write_exclusive(record, b"replacement", marker=False)

    assert marker_error.value.code is Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS
    assert record_error.value.code is Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED
    assert marker.read_bytes() == b"existing-marker\n"
    assert record.read_bytes() == b"existing-record\n"


@pytest.mark.parametrize(
    ("outcome", "expected_code"),
    (
        (
            APITimeoutError(
                request=httpx.Request("POST", "https://example.invalid")
            ),
            Stage4BErrorCode.TIMEOUT,
        ),
        (
            RateLimitError(
                "fictional rate limit",
                response=httpx.Response(
                    429,
                    request=httpx.Request("POST", "https://example.invalid"),
                ),
                body=None,
            ),
            Stage4BErrorCode.RATE_LIMIT,
        ),
        (
            APIStatusError(
                "fictional API failure",
                response=httpx.Response(
                    500,
                    request=httpx.Request("POST", "https://example.invalid"),
                ),
                body=None,
            ),
            Stage4BErrorCode.PROVIDER_API_FAILURE,
        ),
    ),
)
def test_provider_failure_leaves_marker_and_no_record(
    tmp_path: Path,
    outcome: BaseException,
    expected_code: Stage4BErrorCode,
) -> None:
    marker, record = _artifact_paths(tmp_path)
    client = FakeClient(outcome, marker)

    with pytest.raises(Stage4BError) as captured:
        _execute(tmp_path, outcome=outcome, client_factory=lambda key: client)

    assert captured.value.code is expected_code
    assert marker.is_file()
    assert not record.exists()
    assert len(client.responses.calls) == 1


def test_invalid_structured_output_leaves_marker_and_no_record(
    tmp_path: Path,
) -> None:
    marker, record = _artifact_paths(tmp_path)
    response = FictionalSDKResponse(valid_output=False)
    client = FakeClient(response, marker)

    with pytest.raises(Stage4BError) as captured:
        _execute(tmp_path, outcome=response, client_factory=lambda key: client)

    assert captured.value.code is Stage4BErrorCode.INVALID_JSON
    assert marker.is_file()
    assert not record.exists()
    assert len(client.responses.calls) == 1


def test_record_write_failure_preserves_marker_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker, record = _artifact_paths(tmp_path)
    client = FakeClient(FictionalSDKResponse(), marker)
    original_write = execution._write_exclusive

    def controlled_write(path: Path, payload: bytes, *, marker: bool) -> None:
        if not marker:
            raise Stage4BError(
                Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED,
                "fictional record installation failure",
            )
        original_write(path, payload, marker=True)

    monkeypatch.setattr(execution, "_write_exclusive", controlled_write)

    with pytest.raises(Stage4BError) as captured:
        _execute(tmp_path, client_factory=lambda key: client)

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ARTIFACT_WRITE_FAILED
    assert marker.is_file()
    assert not record.exists()
    assert len(client.responses.calls) == 1


def test_second_execution_is_blocked_before_second_client_or_call(
    tmp_path: Path,
) -> None:
    paths = _input_paths(tmp_path)
    _, first_client, _, _ = _execute(tmp_path, paths=paths)
    second_factory_calls: list[str] = []

    with pytest.raises(Stage4BError) as captured:
        execution._execute_openai_synthetic_preflight_transaction(
            authorization_path=paths[0],
            pricing_path=paths[1],
            data_controls_path=paths[2],
            repository_root=tmp_path,
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
            clock=lambda: NOW,
            api_key_reader=lambda: (_ for _ in ()).throw(
                AssertionError("secret read must be blocked")
            ),
            client_factory=lambda key: second_factory_calls.append(key),
        )

    assert captured.value.code is Stage4BErrorCode.PREFLIGHT_ATTEMPT_ALREADY_EXISTS
    assert second_factory_calls == []
    assert len(first_client.responses.calls) == 1


def test_secret_and_transient_values_are_absent_from_artifacts_and_result_text(
    tmp_path: Path,
) -> None:
    result, _, _, _ = _execute(tmp_path)
    marker, record = _artifact_paths(tmp_path)
    combined = marker.read_bytes() + record.read_bytes()

    assert FICTIONAL_KEY.encode() not in combined
    assert _raw_output().encode() not in marker.read_bytes()
    assert b"transient-public-value" not in record.read_bytes()
    assert b"public_mapping" not in record.read_bytes()
    assert FICTIONAL_KEY not in str(result)


def test_execution_api_exposes_no_provider_or_output_overrides() -> None:
    parameters = inspect.signature(
        execution.execute_openai_synthetic_preflight
    ).parameters

    for forbidden in (
        "repository_root",
        "clock",
        "api_key_reader",
        "client_factory",
        "model",
        "provider",
        "payload",
        "schema",
        "output_path",
        "attempt_path",
        "provider_call_count",
    ):
        assert forbidden not in parameters

    readiness_parameters = inspect.signature(
        execution.validate_openai_preflight_readiness
    ).parameters
    assert "repository_root" not in readiness_parameters
    assert "clock" not in readiness_parameters
    assert execution._execute_openai_synthetic_preflight_transaction.__name__.startswith(
        "_"
    )
    assert "_execute_openai_synthetic_preflight_transaction" not in execution.__all__


def test_public_execution_rejects_repository_root_keyword() -> None:
    with pytest.raises(TypeError):
        execution.execute_openai_synthetic_preflight(  # type: ignore[call-arg]
            authorization_path=Path("authorization.json"),
            pricing_path=Path("pricing.json"),
            data_controls_path=Path("controls.json"),
            repository_root=Path("second-root"),
            execute_real_preflight=True,
            confirmation=execution.EXECUTION_CONFIRMATION,
        )


def test_fake_execution_performs_no_network_or_document_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)

    result, client, _, _ = _execute(tmp_path)

    assert result.record.preflight_status == "passed"
    assert len(client.responses.calls) == 1


def test_production_factory_is_lazy_and_not_called_by_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _input_paths(tmp_path)

    def forbidden_factory(key: str) -> object:
        raise AssertionError("production client construction is forbidden")

    monkeypatch.setattr(execution, "_production_openai_client_factory", forbidden_factory)

    readiness = execution._validate_openai_preflight_readiness(
        authorization_path=paths[0],
        pricing_path=paths[1],
        data_controls_path=paths[2],
        repository_root=tmp_path,
        clock=lambda: NOW,
    )

    assert readiness.plan.preflight_id == execution.PREFLIGHT_ID


def test_production_credential_reader_uses_only_approved_environment_name() -> None:
    source = inspect.getsource(execution._openai_api_key_from_environment)

    assert "OPENAI_API_KEY" in source
    assert "stdin" not in source
    assert "config" not in source
