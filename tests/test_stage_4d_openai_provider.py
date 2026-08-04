"""Offline contract tests for the narrow Stage 4D-1 OpenAI adapter."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)
from pydantic import ValidationError

from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.extraction.predicates import PREDICATE_REGISTRY
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    DeterministicMockProvider,
    InvocationRole,
    LLMProvider,
    MockResponseFixture,
    ProviderTerminalStatus,
    Stage4BError,
    Stage4BErrorCode,
    build_request_envelope,
    validate_provider_output,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION,
    OPENAI_INSTALLED_SDK_VERSION,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_TIMEOUT_SECONDS,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OPENAI_REQUESTED_MODEL_ALIAS,
    OPENAI_REQUIRED_SDK_VERSION,
    OPENAI_REASONING_EFFORT,
    OpenAIProviderFailure,
    OpenAIResponsesConfiguration,
    OpenAIResponsesProvider,
    audit_openai_strict_schema,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    PromptAssets,
    canonical_json_bytes,
    canonical_prompt_bytes,
    canonical_request_sha256,
    load_prompt_assets,
    prompt_sha256,
)


SYSTEM_PROMPT_SHA256 = (
    "7200C323E396C12C20B604B4AEB1730D3C12FF7FFC27B995E3B68D5531C48B6E"
)
EXTRACTION_PROMPT_SHA256 = (
    "1CE32F2BC3404498849CED6364821DF29C2B70CF97F311F6A57CF849EAC56C13"
)


class FakeResponses:
    """Record one public Responses create call without network access."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeOpenAIClient:
    """Record documented client options and expose a fake Responses resource."""

    def __init__(self, outcome: Any) -> None:
        self.responses = FakeResponses(outcome)
        self.option_calls: list[dict[str, Any]] = []

    def with_options(self, *, max_retries: int, timeout: float):
        self.option_calls.append(
            {"max_retries": max_retries, "timeout": timeout}
        )
        return self


def _request(
    *,
    provider_configuration_id: str = OPENAI_PROVIDER_CONFIGURATION_ID,
    model_configuration_id: str = OPENAI_MODEL_CONFIGURATION_ID,
):
    block = ApprovedEvidenceBlock(
        source_id="S001",
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text="A fictional delivery initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="fictional-openai-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=provider_configuration_id,
        model_configuration_id=model_configuration_id,
        evidence_blocks=(block,),
    )


def _raw_output() -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-openai-batch-001",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [],
            "candidate_facts": [],
            "warnings": ["abstained_no_supported_candidate"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _representative_raw_output() -> str:
    evidence = {
        "evidence_id": "fictional-evidence-001",
        "source_id": "S001",
        "block_id": "fictional-block-001",
        "location_type": "page",
        "location_value": "1",
        "text_excerpt": "A fictional delivery initiative is active.",
        "evidence_status": "supported",
    }

    def fact(
        candidate_id: str,
        *,
        subject_text: str,
        subject_type: str,
        predicate: str,
        raw_value: str,
        normalized_value: object,
        value_type: str,
        qualifiers: dict[str, object],
    ) -> dict[str, object]:
        return {
            "candidate_id": candidate_id,
            "source_id": "S001",
            "document_family": "fictional_delivery_note",
            "subject_text": subject_text,
            "subject_type": subject_type,
            "predicate": predicate,
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "value_type": value_type,
            "qualifiers": qualifiers,
            "evidence_ids": ["fictional-evidence-001"],
            "confidence": 0.75,
            "review_status": "not_required",
            "extraction_method": "llm",
            "warnings": [],
        }

    return json.dumps(
        {
            "schema_version": "0.1",
            "batch_id": "fictional-openai-batch-predicates",
            "source_ids": ["S001"],
            "entities": [],
            "evidence_references": [evidence],
            "candidate_facts": [
                fact(
                    "fictional-status-001",
                    subject_text="fictional delivery initiative",
                    subject_type="initiative",
                    predicate="status",
                    raw_value="active",
                    normalized_value="active",
                    value_type="status",
                    qualifiers={},
                ),
                fact(
                    "fictional-risk-001",
                    subject_text="fictional dependency risk",
                    subject_type="risk",
                    predicate="risk",
                    raw_value="A fictional dependency may be delayed.",
                    normalized_value="fictional dependency delay",
                    value_type="string",
                    qualifiers={
                        "risk_id": "R-FICTIONAL-1",
                        "owner": None,
                        "rating": None,
                    },
                ),
                fact(
                    "fictional-metric-001",
                    subject_text="fictional adoption rate",
                    subject_type="metric",
                    predicate="metric",
                    raw_value="7 percentage points",
                    normalized_value=7,
                    value_type="percentage",
                    qualifiers={
                        "metric_name": "fictional adoption rate",
                        "unit": "percentage points",
                        "population": None,
                        "period": None,
                    },
                ),
            ],
            "warnings": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _response(
    *,
    status: str = "completed",
    output_text: str | None = None,
    content_type: str = "output_text",
    model: str | None = "gpt-5.4-mini-fictional-snapshot",
    response_id: str | None = "resp_fictional_001",
    request_id: str | None = "req_fictional_001",
) -> SimpleNamespace:
    content = []
    if output_text is not None:
        content.append(SimpleNamespace(type=content_type, text=output_text))
    return SimpleNamespace(
        status=status,
        model=model,
        id=response_id,
        _request_id=request_id,
        output=[SimpleNamespace(type="message", content=content)],
        usage=SimpleNamespace(input_tokens=23, output_tokens=11),
    )


def _assert_no_client_access(client: FakeOpenAIClient) -> None:
    assert client.option_calls == []
    assert client.responses.calls == []


def test_provider_protocol_and_constructor_are_injected_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("adapter construction attempted environment or network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    client = FakeOpenAIClient(_response(output_text=_raw_output()))

    provider = OpenAIResponsesProvider(client=client)

    assert isinstance(provider, LLMProvider)
    _assert_no_client_access(client)
    assert OPENAI_INSTALLED_SDK_VERSION == OPENAI_REQUIRED_SDK_VERSION == "2.46.0"


def test_payload_is_deterministic_text_only_and_strict() -> None:
    request = _request()

    first = build_openai_responses_payload(request)
    second = build_openai_responses_payload(request)

    assert first == second
    assert first["model"] == OPENAI_REQUESTED_MODEL_ALIAS == "gpt-5.4-mini"
    assert first["max_output_tokens"] == OPENAI_MAX_OUTPUT_TOKENS == 4096
    assert first["reasoning"] == {
        "effort": OPENAI_REASONING_EFFORT,
    } == {"effort": "none"}
    assert first["store"] is False
    assert first["stream"] is False
    assert first["background"] is False
    assert first["tools"] == []
    assert first["tool_choice"] == "none"
    assert {item["role"] for item in first["input"]} == {"system", "user"}
    assert all(
        content["type"] == "input_text"
        for item in first["input"]
        for content in item["content"]
    )
    assert all(
        isinstance(content["text"], str)
        for item in first["input"]
        for content in item["content"]
    )
    response_format = first["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["name"] == "candidate_extraction_result_0_1"
    provider_schema = response_format["schema"]
    assert provider_schema == build_openai_candidate_schema()
    assert provider_schema != CandidateExtractionResult.model_json_schema(
        mode="serialization"
    )
    assert provider_schema["properties"]["schema_version"]["const"] == "0.1"
    for forbidden in (
        "conversation",
        "files",
        "file_search",
        "functions",
        "previous_response_id",
        "retrieval",
        "web_search",
    ):
        assert forbidden not in first


def test_configuration_requires_immutable_exact_cost_controls() -> None:
    configuration = DEFAULT_OPENAI_RESPONSES_CONFIGURATION

    assert configuration.max_output_tokens == 4096
    assert configuration.reasoning_effort == "none"
    with pytest.raises(ValidationError, match="Instance is frozen"):
        configuration.max_output_tokens = 1  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Instance is frozen"):
        configuration.reasoning_effort = "low"  # type: ignore[misc]


@pytest.mark.parametrize("missing_field", ("max_output_tokens", "reasoning_effort"))
def test_configuration_reconstruction_rejects_missing_cost_control(
    missing_field: str,
) -> None:
    payload = DEFAULT_OPENAI_RESPONSES_CONFIGURATION.model_dump(mode="python")
    del payload[missing_field]

    with pytest.raises(ValidationError):
        OpenAIResponsesConfiguration.model_validate(payload)


@pytest.mark.parametrize(
    "invalid_value",
    (True, False, 0, -1, 4095, 4097, 4096.0, "4096", None),
)
def test_configuration_rejects_non_exact_max_output_tokens(
    invalid_value: object,
) -> None:
    payload = DEFAULT_OPENAI_RESPONSES_CONFIGURATION.model_dump(mode="python")
    payload["max_output_tokens"] = invalid_value

    with pytest.raises(ValidationError):
        OpenAIResponsesConfiguration.model_validate(payload)


@pytest.mark.parametrize(
    "invalid_value",
    ("low", "minimal", "NONE", "none ", 0, None),
)
def test_configuration_rejects_non_exact_reasoning_effort(
    invalid_value: object,
) -> None:
    payload = DEFAULT_OPENAI_RESPONSES_CONFIGURATION.model_dump(mode="python")
    payload["reasoning_effort"] = invalid_value

    with pytest.raises(ValidationError):
        OpenAIResponsesConfiguration.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    (
        ("max_output_tokens", None),
        ("max_output_tokens", 4095),
        ("reasoning", None),
        ("reasoning", {"effort": "low"}),
    ),
)
def test_cost_control_omission_or_change_alters_canonical_payload_hash(
    field_name: str,
    changed_value: object,
) -> None:
    payload = build_openai_responses_payload(_request())
    changed = json.loads(json.dumps(payload))
    if changed_value is None:
        del changed[field_name]
    else:
        changed[field_name] = changed_value

    original_hash = hashlib.sha256(canonical_json_bytes(payload)).digest()
    changed_hash = hashlib.sha256(canonical_json_bytes(changed)).digest()
    assert changed_hash != original_hash


def _assert_every_declared_object_is_closed_and_required(node: object) -> None:
    if isinstance(node, dict):
        assert "default" not in node
        if node.get("type") == "object":
            properties = node.get("properties")
            assert isinstance(properties, dict)
            assert node.get("additionalProperties") is False
            assert node.get("required") == list(properties)
        for value in node.values():
            _assert_every_declared_object_is_closed_and_required(value)
    elif isinstance(node, list):
        for value in node:
            _assert_every_declared_object_is_closed_and_required(value)


def _predicate_variant(schema: dict[str, Any], predicate: str) -> dict[str, Any]:
    variants = schema["$defs"]["CandidateFact"]["anyOf"]
    return next(
        variant
        for variant in variants
        if variant["properties"]["predicate"]["const"] == predicate
    )


def test_provider_schema_is_recursively_closed_required_and_default_free() -> None:
    schema = build_openai_candidate_schema()

    audit_openai_strict_schema(schema)
    _assert_every_declared_object_is_closed_and_required(schema)
    assert schema["type"] == "object"
    assert "anyOf" not in schema
    assert len(schema["$defs"]["CandidateFact"]["anyOf"]) == len(
        PREDICATE_REGISTRY
    )


def test_predicate_variants_close_none_optional_and_required_qualifiers() -> None:
    schema = build_openai_candidate_schema()
    status = _predicate_variant(schema, "status")
    risk = _predicate_variant(schema, "risk")
    metric = _predicate_variant(schema, "metric")

    assert status["properties"]["qualifiers"] == {
        "additionalProperties": False,
        "properties": {},
        "required": [],
        "type": "object",
    }
    risk_qualifiers = risk["properties"]["qualifiers"]
    assert risk_qualifiers["required"] == ["risk_id", "owner", "rating"]
    assert all(
        {branch.get("type") for branch in definition["anyOf"]} >= {"null"}
        for definition in risk_qualifiers["properties"].values()
    )
    metric_qualifiers = metric["properties"]["qualifiers"]
    assert metric_qualifiers["required"] == [
        "metric_name",
        "unit",
        "population",
        "period",
    ]
    assert "null" not in {
        branch.get("type")
        for branch in metric_qualifiers["properties"]["metric_name"]["anyOf"]
    }
    assert all(
        "null"
        in {branch.get("type") for branch in metric_qualifiers["properties"][name]["anyOf"]}
        for name in ("unit", "population", "period")
    )
    for predicate, variant in (("status", status), ("risk", risk), ("metric", metric)):
        assert variant["properties"]["predicate"] == {
            "const": predicate,
            "type": "string",
        }
        assert variant["properties"]["extraction_method"] == {
            "const": "llm",
            "type": "string",
        }


def test_representative_strict_provider_shape_passes_existing_validator() -> None:
    raw_output = _representative_raw_output()
    payload = json.loads(raw_output)
    schema = build_openai_candidate_schema()

    assert set(payload) == set(schema["properties"])
    for fact in payload["candidate_facts"]:
        variant = _predicate_variant(schema, fact["predicate"])
        assert set(fact) == set(variant["properties"])
        assert set(fact["qualifiers"]) == set(
            variant["properties"]["qualifiers"]["properties"]
        )

    response = OpenAIResponsesProvider(
        client=FakeOpenAIClient(_response(output_text=raw_output))
    ).generate(_request())
    validated = validate_provider_output(_request(), response)

    assert [
        fact.predicate for fact in validated.candidate_result.candidate_facts
    ] == ["status", "risk", "metric"]


def test_request_identity_is_checked_before_client_access() -> None:
    request = _request().model_copy(update={"prompt_sha256": "F" * 64})
    client = FakeOpenAIClient(_response(output_text=_raw_output()))

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(request)

    assert captured.value.code is Stage4BErrorCode.PROMPT_HASH_MISMATCH
    _assert_no_client_access(client)


@pytest.mark.parametrize(
    ("field_name", "value", "expected_code"),
    (
        (
            "provider_configuration_id",
            "fictional-wrong-provider-configuration",
            Stage4BErrorCode.PROVIDER_CONFIGURATION_MISMATCH,
        ),
        (
            "model_configuration_id",
            "fictional-wrong-model-configuration",
            Stage4BErrorCode.MODEL_CONFIGURATION_MISMATCH,
        ),
    ),
)
def test_configuration_mismatch_is_rejected_before_client_access(
    field_name: str,
    value: str,
    expected_code: Stage4BErrorCode,
) -> None:
    request = _request(**{field_name: value})
    client = FakeOpenAIClient(_response(output_text=_raw_output()))

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(request)

    assert captured.value.code is expected_code
    _assert_no_client_access(client)


@pytest.mark.parametrize("source_id", ("S005", "S007", "fictional"))
def test_prohibited_source_is_rejected_before_client_access(source_id: str) -> None:
    request = _request()
    block = request.evidence_blocks[0].model_copy(update={"source_id": source_id})
    request = request.model_copy(
        update={"source_id": source_id, "evidence_blocks": (block,)}
    )
    request = request.model_copy(
        update={
            "prompt_sha256": prompt_sha256(
                evidence_blocks=request.evidence_blocks,
                model_configuration_id=request.model_configuration_id,
            )
        }
    )
    request = request.model_copy(
        update={"canonical_request_sha256": canonical_request_sha256(request)}
    )
    client = FakeOpenAIClient(_response(output_text=_raw_output()))

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(request)

    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    _assert_no_client_access(client)


def test_malformed_cross_source_request_is_rejected_before_client_access() -> None:
    request = _request()
    block = request.evidence_blocks[0].model_copy(update={"source_id": "S002"})
    request = request.model_copy(update={"evidence_blocks": (block,)})
    request = request.model_copy(
        update={
            "prompt_sha256": prompt_sha256(
                evidence_blocks=request.evidence_blocks,
                model_configuration_id=request.model_configuration_id,
            )
        }
    )
    request = request.model_copy(
        update={"canonical_request_sha256": canonical_request_sha256(request)}
    )
    client = FakeOpenAIClient(_response(output_text=_raw_output()))

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(request)

    assert captured.value.code is Stage4BErrorCode.INVALID_PROVIDER_REQUEST
    _assert_no_client_access(client)


def test_completed_response_maps_exact_output_identity_usage_and_options() -> None:
    raw_output = _raw_output()
    client = FakeOpenAIClient(_response(output_text=raw_output))
    clock_values = iter((10.0, 10.125))
    provider = OpenAIResponsesProvider(client=client, clock=lambda: next(clock_values))

    result = provider.generate(_request())

    assert result.request_id == "fictional-openai-request-001"
    assert result.provider_identifier == "openai"
    assert result.model_identifier == "gpt-5.4-mini-fictional-snapshot"
    assert result.provider_request_id == "req_fictional_001"
    assert result.provider_response_id == "resp_fictional_001"
    assert result.provider_sdk_version == "2.46.0"
    assert result.raw_response == raw_output
    assert result.raw_response_sha256 == hashlib.sha256(
        raw_output.encode("utf-8")
    ).hexdigest().upper()
    assert result.token_usage is not None
    assert result.token_usage.input_tokens == 23
    assert result.token_usage.output_tokens == 11
    assert result.latency_ms == 125
    assert result.retry_count == 0
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert client.responses.calls == [build_openai_responses_payload(_request())]
    assert client.responses.calls[0]["max_output_tokens"] == 4096
    assert client.responses.calls[0]["reasoning"] == {"effort": "none"}


def test_additive_response_metadata_is_immutable_complete_and_nonblank() -> None:
    response = OpenAIResponsesProvider(
        client=FakeOpenAIClient(_response(output_text=_raw_output()))
    ).generate(_request())

    with pytest.raises(ValidationError, match="Instance is frozen"):
        response.provider_request_id = "req_changed"  # type: ignore[misc]

    for field_name, value in (
        ("provider_request_id", None),
        ("provider_response_id", " "),
        ("provider_sdk_version", "2.46.0 "),
    ):
        payload = response.model_dump(mode="python")
        payload[field_name] = value
        with pytest.raises(ValidationError):
            type(response).model_validate(payload)


def _sdk_exception(kind: str) -> BaseException:
    request = httpx.Request("POST", "https://api.openai.invalid/v1/responses")
    if kind == "timeout":
        return APITimeoutError(request=request)
    if kind == "rate_limit":
        response = httpx.Response(429, request=request)
        return RateLimitError("fictional rate limit", response=response, body=None)
    if kind == "transport_error":
        return APIConnectionError(
            message="fictional connection failure", request=request
        )
    response = httpx.Response(400, request=request)
    return APIStatusError("fictional API failure", response=response, body=None)


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    (
        ("timeout", Stage4BErrorCode.TIMEOUT),
        ("rate_limit", Stage4BErrorCode.RATE_LIMIT),
        ("transport_error", Stage4BErrorCode.TRANSPORT_ERROR),
        ("api_failure", Stage4BErrorCode.PROVIDER_API_FAILURE),
    ),
)
def test_sdk_failures_are_typed_and_never_retried(
    kind: str, expected_code: Stage4BErrorCode
) -> None:
    client = FakeOpenAIClient(_sdk_exception(kind))

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(_request())

    assert captured.value.code is expected_code
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert len(client.responses.calls) == 1


def test_api_status_failure_retains_only_sanitized_safe_diagnostics() -> None:
    fictional_secret = "sk-fictional-provider-secret-must-not-be-retained"
    request = httpx.Request("POST", "https://api.openai.invalid/v1/responses")
    response = httpx.Response(
        401,
        request=request,
        headers={
            "x-request-id": "req_fictional_safe_001",
            "authorization": f"Bearer {fictional_secret}",
            "x-fictional-sensitive-header": fictional_secret,
        },
        content=f'{{"unsafe":"{fictional_secret}"}}'.encode("utf-8"),
    )
    error = APIStatusError(
        f"unsafe raw message {fictional_secret}",
        response=response,
        body={
            "type": "invalid_request_error",
            "code": "invalid_api_key",
            "message": fictional_secret,
            "prompt": "fictional prompt must not be retained",
        },
    )
    client = FakeOpenAIClient(error)

    with pytest.raises(OpenAIProviderFailure) as captured:
        OpenAIResponsesProvider(client=client).generate(_request())

    failure = captured.value
    assert failure.code is Stage4BErrorCode.PROVIDER_API_FAILURE
    assert failure.diagnostics.model_dump(mode="python") == {
        "http_status_code": 401,
        "provider_error_type": "invalid_request_error",
        "provider_error_code": "invalid_api_key",
        "provider_request_id": "req_fictional_safe_001",
    }
    serialized = json.dumps(failure.diagnostics.model_dump(mode="json"))
    for forbidden in (
        fictional_secret,
        "unsafe raw message",
        "fictional prompt",
        "authorization",
        "x-fictional-sensitive-header",
    ):
        assert forbidden not in serialized
        assert forbidden not in str(failure)
        assert forbidden not in repr(failure)
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert client.option_calls == [
        {"max_retries": 0, "timeout": OPENAI_MAX_TIMEOUT_SECONDS}
    ]
    assert len(client.responses.calls) == 1


def test_unsafe_provider_diagnostic_values_are_omitted() -> None:
    request = httpx.Request("POST", "https://api.openai.invalid/v1/responses")
    response = httpx.Response(
        400,
        request=request,
        headers={"x-request-id": "unsafe request id with spaces"},
    )
    client = FakeOpenAIClient(
        APIStatusError(
            "fictional unsafe diagnostics",
            response=response,
            body={
                "type": "unsafe type with spaces",
                "code": "unsafe\ncode",
            },
        )
    )

    with pytest.raises(OpenAIProviderFailure) as captured:
        OpenAIResponsesProvider(client=client).generate(_request())

    assert captured.value.diagnostics.model_dump(mode="python") == {
        "http_status_code": 400,
        "provider_error_type": None,
        "provider_error_code": None,
        "provider_request_id": None,
    }


@pytest.mark.parametrize(
    ("response", "expected_code"),
    (
        (_response(status="incomplete"), Stage4BErrorCode.INCOMPLETE_RESPONSE),
        (_response(status="failed"), Stage4BErrorCode.FAILED_RESPONSE),
        (_response(status="queued"), Stage4BErrorCode.RESPONSE_NOT_COMPLETED),
        (_response(), Stage4BErrorCode.MISSING_OUTPUT_TEXT),
        (
            _response(output_text="fictional refusal", content_type="refusal"),
            Stage4BErrorCode.PROVIDER_REFUSAL,
        ),
        (
            _response(output_text=_raw_output(), model=None),
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
        ),
        (
            _response(output_text=_raw_output(), response_id=None),
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
        ),
        (
            _response(output_text=_raw_output(), request_id=None),
            Stage4BErrorCode.MISSING_PROVIDER_METADATA,
        ),
    ),
)
def test_noncompleted_refusal_missing_text_and_identity_fail_closed(
    response: SimpleNamespace, expected_code: Stage4BErrorCode
) -> None:
    client = FakeOpenAIClient(response)

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(_request())

    assert captured.value.code is expected_code
    assert len(client.responses.calls) == 1


def test_malformed_output_is_preserved_without_repair_or_fabrication() -> None:
    client = FakeOpenAIClient(_response(output_text="{not-json"))
    response = OpenAIResponsesProvider(client=client).generate(_request())

    assert response.raw_response == "{not-json"
    with pytest.raises(Stage4BError) as captured:
        validate_provider_output(_request(), response)
    assert captured.value.code is Stage4BErrorCode.INVALID_JSON


def test_canonical_prompt_hashes_are_platform_independent() -> None:
    assets = load_prompt_assets()
    system_lf = assets.system_prompt_bytes.replace(b"\r\n", b"\n")
    extraction_lf = assets.extraction_prompt_bytes.replace(b"\r\n", b"\n")
    variants = (
        PromptAssets(system_lf, extraction_lf),
        PromptAssets(
            system_lf.replace(b"\n", b"\r\n"),
            extraction_lf.replace(b"\n", b"\r\n"),
        ),
    )

    prompt_payloads = [
        json.loads(
            canonical_prompt_bytes(
                evidence_blocks=_request().evidence_blocks,
                model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
                assets=variant,
            )
        )
        for variant in variants
    ]

    assert prompt_payloads[0] == prompt_payloads[1]
    assert prompt_payloads[0]["system_prompt_sha256"] == SYSTEM_PROMPT_SHA256
    assert (
        prompt_payloads[0]["extraction_prompt_sha256"]
        == EXTRACTION_PROMPT_SHA256
    )


def test_existing_deterministic_mock_response_remains_compatible() -> None:
    request = _request(
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
    )
    provider = DeterministicMockProvider(
        {
            request.canonical_request_sha256: MockResponseFixture(
                terminal_status=ProviderTerminalStatus.SUCCESS,
                raw_response=_raw_output(),
            )
        }
    )

    response = provider.generate(request)

    assert response.provider_request_id is None
    assert response.provider_response_id is None
    assert response.provider_sdk_version is None
    assert response.raw_response == _raw_output()
