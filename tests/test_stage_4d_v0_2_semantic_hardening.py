"""Offline regressions for additive Stage 4D semantic hardening v0.2."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    AttemptProvenance,
    InvocationRole,
    LLMProviderResponse,
    ProviderTerminalStatus,
    ResponseCache,
    Stage4BError,
    Stage4BErrorCode,
    V0_2_OPENAI_CACHE_ROOT,
    build_cache_record,
    build_manifest_invocation,
    build_request_envelope,
    build_request_envelope_v0_2,
    cache_identity_from_request,
    cache_identity_sha256,
    canonical_prompt_bytes,
    canonical_request_bytes,
    load_prompt_assets,
    validate_provider_output,
)
from document_intelligence.llm_extraction.openai_development_execution import (
    load_development_attempt_marker,
    load_development_failure_record,
)
from document_intelligence.llm_extraction.openai_development_execution_plan import (
    OpenAIDevelopmentExecutionPlanV01,
    development_execution_plan_bytes,
)
from document_intelligence.llm_extraction.openai_development_manifest import (
    OpenAIDevelopmentManifestV01,
    development_manifest_bytes,
)
from document_intelligence.llm_extraction.openai_provider import (
    DEFAULT_OPENAI_RESPONSES_CONFIGURATION,
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID,
    OpenAIResponsesProvider,
    build_openai_candidate_schema,
    build_openai_responses_payload,
)
from document_intelligence.llm_extraction.prompting import (
    PromptAssets,
    canonical_json_bytes,
    canonical_request_sha256,
    prompt_sha256,
    uppercase_sha256_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
V0_1_SYSTEM_PROMPT_SHA256 = (
    "7200C323E396C12C20B604B4AEB1730D3C12FF7FFC27B995E3B68D5531C48B6E"
)
V0_1_EXTRACTION_PROMPT_SHA256 = (
    "1CE32F2BC3404498849CED6364821DF29C2B70CF97F311F6A57CF849EAC56C13"
)
V0_1_REQUEST_SHA256 = (
    "4620CCB826940721AE7CAF88B9047CD090F2C03286E2FA598F48ED78C03982AA"
)
V0_1_PROVIDER_PAYLOAD_SHA256 = (
    "F65A4F5592879E92B075B2ADEAB85598FB46A6E05146FD35038F984461A4FC53"
)
V0_1_CACHE_IDENTITY_SHA256 = (
    "BAA5E03ED8D1D39DC95B392801045184A1169F4E24DF401ABFD77BFCD7913798"
)
STRICT_SCHEMA_SHA256 = (
    "45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74"
)
NOW = datetime(2026, 8, 10, 1, 2, 3, tzinfo=timezone.utc)


def _block(version: str = "0.2", *, source_id: str = "S001") -> ApprovedEvidenceBlock:
    block_id = "fictional-block-001"
    return ApprovedEvidenceBlock(
        source_id=source_id,
        evidence_id=f"llm-evidence-v{version}-{source_id}-{block_id}",
        block_id=block_id,
        sequence=1,
        text="A fictional initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )


def _request_v0_1():
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="fictional-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=(_block("0.1"),),
    )


def _request_v0_2():
    return build_request_envelope_v0_2(
        invocation_role=InvocationRole.PRIMARY,
        request_id="llm-v0.2-S001-primary-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id=OPENAI_PROVIDER_CONFIGURATION_ID,
        model_configuration_id=OPENAI_MODEL_CONFIGURATION_ID,
        evidence_blocks=(_block(),),
    )


def _payload(evidence_id: str = "llm-evidence-v0.2-S001-fictional-block-001"):
    return {
        "schema_version": "0.1",
        "batch_id": "fictional-batch-001",
        "source_ids": ["S001"],
        "entities": [
            {
                "entity_id": "fictional-entity-001",
                "canonical_name": "Fictional Initiative",
                "entity_type": "initiative",
                "aliases": ["Fictional Delivery Programme"],
                "source_ids": ["S001"],
            }
        ],
        "evidence_references": [
            {
                "evidence_id": evidence_id,
                "source_id": "S001",
                "block_id": "fictional-block-001",
                "location_type": "page",
                "location_value": "1",
                "text_excerpt": "A fictional initiative is active.",
                "evidence_status": "supported",
            }
        ],
        "candidate_facts": [
            {
                "candidate_id": "fictional-candidate-001",
                "source_id": "S001",
                "document_family": "fictional_delivery_note",
                "subject_text": "Fictional Initiative",
                "subject_type": "initiative",
                "predicate": "status",
                "raw_value": "active",
                "normalized_value": "active",
                "value_type": "status",
                "qualifiers": {},
                "evidence_ids": [evidence_id],
                "confidence": 0.8,
                "review_status": "not_required",
                "extraction_method": "llm",
                "warnings": [],
            }
        ],
        "warnings": [],
    }


def _response(request, payload: dict[str, object]) -> LLMProviderResponse:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return LLMProviderResponse(
        request_id=request.request_id,
        provider_identifier="fictional-offline-provider",
        model_identifier="fictional-offline-model",
        terminal_status=ProviderTerminalStatus.SUCCESS,
        raw_response=raw,
        raw_response_sha256=uppercase_sha256_bytes(raw.encode("utf-8")),
        latency_ms=0,
        retry_count=0,
    )


class _FakeResponses:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **payload: Any) -> SimpleNamespace:
        self.calls.append(payload)
        return self.response


class _FakeOpenAIClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.responses = _FakeResponses(response)
        self.option_calls: list[dict[str, Any]] = []

    def with_options(self, *, max_retries: int, timeout: float):
        self.option_calls.append(
            {"max_retries": max_retries, "timeout": timeout}
        )
        return self


def _fake_sdk_response(raw_output: str) -> SimpleNamespace:
    return SimpleNamespace(
        status="completed",
        model="gpt-5.4-mini-fictional-v0.2-snapshot",
        id="resp_fictional_v0_2_001",
        _request_id="req_fictional_v0_2_001",
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=raw_output)],
            )
        ],
        usage=SimpleNamespace(input_tokens=101, output_tokens=37),
    )


def _assert_rejected(
    payload: dict[str, object],
    expected_code: Stage4BErrorCode = Stage4BErrorCode.SCHEMA_INVALID,
) -> None:
    request = _request_v0_2()
    response = _response(request, payload)
    original = response.raw_response
    with pytest.raises(Stage4BError) as captured:
        validate_provider_output(request, response)
    assert captured.value.code is expected_code
    assert response.raw_response == original


def test_live_failure_shape_remains_rejected_without_repair() -> None:
    payload = _payload()
    payload["entities"][0]["canonical_name"] = "X"  # type: ignore[index]
    payload["entities"][0]["aliases"] = ["x"]  # type: ignore[index]

    _assert_rejected(payload)


@pytest.mark.parametrize(
    "aliases",
    (["Alternative", "ALTERNATIVE"], [""], [" "], [" Padded "]),
)
def test_casefold_duplicate_blank_and_padded_aliases_are_rejected(
    aliases: list[str],
) -> None:
    payload = _payload()
    payload["entities"][0]["aliases"] = aliases  # type: ignore[index]

    _assert_rejected(payload)


@pytest.mark.parametrize("metric_name", ("", " ", ["Metric", " "]))
def test_blank_required_qualifier_values_are_rejected(metric_name: object) -> None:
    payload = _payload()
    fact = payload["candidate_facts"][0]  # type: ignore[index]
    fact.update(
        {
            "subject_type": "metric",
            "predicate": "metric",
            "raw_value": "7",
            "normalized_value": 7,
            "value_type": "number",
            "qualifiers": {"metric_name": metric_name},
        }
    )

    _assert_rejected(payload, Stage4BErrorCode.INVALID_QUALIFIER)


def test_empty_duplicate_and_dangling_fact_evidence_ids_are_rejected() -> None:
    payload = _payload()
    payload["candidate_facts"][0]["evidence_ids"] = []  # type: ignore[index]
    _assert_rejected(payload, Stage4BErrorCode.MISSING_EVIDENCE_REFERENCE)

    payload = _payload()
    evidence_id = payload["evidence_references"][0]["evidence_id"]  # type: ignore[index]
    payload["candidate_facts"][0]["evidence_ids"] = [  # type: ignore[index]
        evidence_id,
        evidence_id,
    ]
    _assert_rejected(payload)

    payload = _payload()
    payload["candidate_facts"][0]["evidence_ids"] = [  # type: ignore[index]
        "llm-evidence-v0.2-S001-fictional-block-999"
    ]
    _assert_rejected(payload)


@pytest.mark.parametrize("collection", ("entities", "evidence_references", "candidate_facts"))
def test_duplicate_result_object_ids_are_rejected(collection: str) -> None:
    payload = _payload()
    payload[collection].append(copy.deepcopy(payload[collection][0]))  # type: ignore[union-attr,index]

    _assert_rejected(payload)


@pytest.mark.parametrize("layer", ("result", "entity", "fact", "evidence"))
def test_source_disagreement_is_rejected(layer: str) -> None:
    payload = _payload()
    if layer == "result":
        payload["source_ids"] = ["S002"]
        expected = Stage4BErrorCode.SOURCE_MISMATCH
    elif layer == "entity":
        payload["entities"][0]["source_ids"] = ["S002"]  # type: ignore[index]
        expected = Stage4BErrorCode.SCHEMA_INVALID
    elif layer == "fact":
        payload["candidate_facts"][0]["source_id"] = "S002"  # type: ignore[index]
        expected = Stage4BErrorCode.SCHEMA_INVALID
    else:
        payload["evidence_references"][0]["source_id"] = "S002"  # type: ignore[index]
        expected = Stage4BErrorCode.CROSS_SOURCE_EVIDENCE_REFERENCE

    _assert_rejected(payload, expected)


def test_blank_supported_excerpt_and_raw_value_are_rejected() -> None:
    payload = _payload()
    payload["evidence_references"][0]["text_excerpt"] = " "  # type: ignore[index]
    _assert_rejected(payload)

    payload = _payload()
    payload["candidate_facts"][0]["raw_value"] = " "  # type: ignore[index]
    _assert_rejected(payload)


@pytest.mark.parametrize(
    ("location_type", "location_value"),
    (("page", "0"), ("page", "-1"), ("page", "one"), ("slide", "0")),
)
def test_invalid_page_and_slide_locations_are_rejected(
    location_type: str,
    location_value: str,
) -> None:
    payload = _payload()
    evidence = payload["evidence_references"][0]  # type: ignore[index]
    evidence["location_type"] = location_type
    evidence["location_value"] = location_value

    _assert_rejected(payload)


def test_request_location_disagreement_is_rejected() -> None:
    payload = _payload()
    payload["evidence_references"][0]["location_value"] = "2"  # type: ignore[index]

    _assert_rejected(payload, Stage4BErrorCode.UNKNOWN_EVIDENCE_REFERENCE)


def test_negative_normalized_money_is_rejected() -> None:
    payload = _payload()
    fact = payload["candidate_facts"][0]  # type: ignore[index]
    fact.update(
        {
            "predicate": "approved_budget",
            "raw_value": "GBP -1",
            "normalized_value": {"amount": "-1", "currency": "GBP"},
            "value_type": "money",
        }
    )

    _assert_rejected(payload)


@pytest.mark.parametrize("layer", ("candidate", "result"))
def test_blank_warnings_are_rejected(layer: str) -> None:
    payload = _payload()
    if layer == "candidate":
        payload["candidate_facts"][0]["warnings"] = [" "]  # type: ignore[index]
    else:
        payload["warnings"] = [""]

    _assert_rejected(payload)


def test_valid_fictional_semantic_output_is_accepted_unchanged() -> None:
    request = _request_v0_2()
    payload = _payload()
    response = _response(request, payload)

    validated = validate_provider_output(request, response)

    assert validated.candidate_result.model_dump(mode="json") == payload
    assert response.raw_response == json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    )


def test_prompt_v0_2_is_generic_complete_and_deterministic() -> None:
    first = load_prompt_assets("0.2")
    second = load_prompt_assets("0.2")
    text = (first.system_prompt_bytes + first.extraction_prompt_bytes).decode(
        "utf-8"
    )

    assert first == second
    for phrase in (
        "preferred entity name",
        "genuine alternative names",
        "Unicode casefold equivalent",
        "unique after casefolding",
        "trimmed and nonblank",
        "only the supplied source ID",
        "supplied evidence IDs",
        "meaningful nonblank excerpt",
        "meaningful nonblank raw_value",
        "required qualifier values",
        "must each be unique",
        "must resolve both",
        "Preserve the supplied source identifier",
        "Warnings, when present",
        "review routing",
        "semantic self-check",
        "Abstention is preferable to fabrication",
    ):
        assert phrase.casefold() in text.casefold()
    assert not re.search(r"\bS00[1-7]\b", text)
    assert not re.search(r"\bPG(?:C)?-V\d+", text)
    for source_specific_result in (
        "0.028089887640449437",
        "0.04926108374384237",
        "TP 5",
        "FP 173",
        "FN 20",
    ):
        assert source_specific_result not in text


def test_v0_2_prompt_identity_is_invariant_to_lf_and_crlf_assets() -> None:
    installed = load_prompt_assets("0.2")

    def lf(value: bytes) -> bytes:
        return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    lf_assets = PromptAssets(
        system_prompt_bytes=lf(installed.system_prompt_bytes),
        extraction_prompt_bytes=lf(installed.extraction_prompt_bytes),
    )
    crlf_assets = PromptAssets(
        system_prompt_bytes=lf_assets.system_prompt_bytes.replace(b"\n", b"\r\n"),
        extraction_prompt_bytes=lf_assets.extraction_prompt_bytes.replace(
            b"\n", b"\r\n"
        ),
    )
    prompt_arguments = {
        "evidence_blocks": _request_v0_2().evidence_blocks,
        "model_configuration_id": OPENAI_MODEL_CONFIGURATION_ID,
        "prompt_version": "0.2",
    }

    lf_bytes = canonical_prompt_bytes(**prompt_arguments, assets=lf_assets)
    crlf_bytes = canonical_prompt_bytes(**prompt_arguments, assets=crlf_assets)

    assert lf_bytes == crlf_bytes
    assert prompt_sha256(**prompt_arguments, assets=lf_assets) == prompt_sha256(
        **prompt_arguments, assets=crlf_assets
    )


def test_v0_1_prompt_request_payload_and_cache_identities_remain_stable() -> None:
    request = _request_v0_1()
    prompt_payload = json.loads(
        canonical_prompt_bytes(
            evidence_blocks=request.evidence_blocks,
            model_configuration_id=request.model_configuration_id,
        )
    )
    expected_request_bytes = (
        b'{"document_sha256":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",'
        b'"evidence_blocks":[{"block_id":"fictional-block-001","evidence_id":'
        b'"llm-evidence-v0.1-S001-fictional-block-001","location":{"element_index":null,'
        b'"location_type":"page","location_value":"1","message_id":null,"page_number":1,'
        b'"slide_number":null},"sequence":1,"source_id":"S001","text":'
        b'"A fictional initiative is active."}],"experiment_id":'
        b'"llm-extraction-baseline-v0.1","invocation_role":"primary",'
        b'"model_configuration_id":"openai-gpt-5.4-mini-text-strict-json-v0.1",'
        b'"output_contract_id":"candidate-extraction-result-0.1","prompt_sha256":'
        b'"CDD4948845CDA338ED72B596FB636F523F5C699F18D9ED008E50B2A96C94EC18",'
        b'"prompt_version":"0.1","provider_configuration_id":'
        b'"openai-responses-text-strict-json-v0.1","request_id":'
        b'"fictional-request-001","source_id":"S001"}'
    )

    assert prompt_payload["system_prompt_sha256"] == V0_1_SYSTEM_PROMPT_SHA256
    assert (
        prompt_payload["extraction_prompt_sha256"]
        == V0_1_EXTRACTION_PROMPT_SHA256
    )
    assert canonical_request_bytes(request) == expected_request_bytes
    assert request.canonical_request_sha256 == V0_1_REQUEST_SHA256
    assert (
        uppercase_sha256_bytes(
            canonical_json_bytes(build_openai_responses_payload(request))
        )
        == V0_1_PROVIDER_PAYLOAD_SHA256
    )
    assert (
        cache_identity_sha256(cache_identity_from_request(request))
        == V0_1_CACHE_IDENTITY_SHA256
    )


def test_v0_1_and_v0_2_request_payload_schema_and_cache_separation() -> None:
    request_v0_1 = _request_v0_1()
    request_v0_2 = _request_v0_2()
    payload_v0_1 = build_openai_responses_payload(request_v0_1)
    payload_v0_2 = build_openai_responses_payload(request_v0_2)
    identity_v0_1 = cache_identity_from_request(request_v0_1)
    identity_v0_2 = cache_identity_from_request(request_v0_2)

    assert request_v0_2.experiment_id == "llm-extraction-baseline-v0.2"
    assert request_v0_2.prompt_version == "0.2"
    assert request_v0_2.request_id == "llm-v0.2-S001-primary-001"
    assert request_v0_2.evidence_blocks[0].evidence_id == (
        "llm-evidence-v0.2-S001-fictional-block-001"
    )
    assert V0_2_OPENAI_CACHE_ROOT == (
        ".cache/llm_extraction/llm-extraction-baseline-v0.2/openai/"
    )
    assert request_v0_1.prompt_sha256 != request_v0_2.prompt_sha256
    assert (
        request_v0_1.canonical_request_sha256
        != request_v0_2.canonical_request_sha256
    )
    assert canonical_json_bytes(payload_v0_1) != canonical_json_bytes(payload_v0_2)
    assert cache_identity_sha256(identity_v0_1) != cache_identity_sha256(identity_v0_2)
    assert payload_v0_1["text"]["format"]["schema"] == payload_v0_2["text"]["format"]["schema"]  # type: ignore[index]
    assert (
        uppercase_sha256_bytes(canonical_json_bytes(build_openai_candidate_schema()))
        == STRICT_SCHEMA_SHA256
    )
    for request in (request_v0_1, request_v0_2):
        assert request.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID
        assert request.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID
        assert request.output_contract_id == "candidate-extraction-result-0.1"


def _cache_record_for(request, payload: dict[str, object]):
    response = _response(request, payload)
    attempt = AttemptProvenance(
        attempt_number=1,
        terminal_status=ProviderTerminalStatus.SUCCESS,
        provider_call_performed=True,
        response_sha256=response.raw_response_sha256,
        latency_ms=0,
    )
    return build_cache_record(
        identity=cache_identity_from_request(request),
        response=response,
        original_provider_call_timestamp=NOW,
        original_attempts=(attempt,),
        estimated_cost_usd=Decimal("0"),
    )


def test_v0_1_cache_cannot_satisfy_v0_2_and_both_versions_coexist(
    tmp_path: Path,
) -> None:
    request_v0_1 = _request_v0_1()
    request_v0_2 = _request_v0_2()
    identity_v0_1 = cache_identity_from_request(request_v0_1)
    identity_v0_2 = cache_identity_from_request(request_v0_2)
    cache = ResponseCache(tmp_path / "fictional-cache")
    record_v0_1 = _cache_record_for(
        request_v0_1,
        _payload("llm-evidence-v0.1-S001-fictional-block-001"),
    )
    record_v0_2 = _cache_record_for(request_v0_2, _payload())

    cache.append(record_v0_1)
    assert cache.read(identity_v0_1) == record_v0_1
    with pytest.raises(Stage4BError) as captured:
        cache.read(identity_v0_2)
    assert captured.value.code is Stage4BErrorCode.CACHE_MISS
    assert cache.path_for(identity_v0_1) != cache.path_for(identity_v0_2)

    cache.append(record_v0_2)
    assert cache.read(identity_v0_1) == record_v0_1
    assert cache.read(identity_v0_2) == record_v0_2


def test_v0_2_identity_templates_fail_closed() -> None:
    base = _request_v0_2().model_dump(mode="python")
    for invalid_request_id in (
        "llm-v0.1-S001-primary-001",
        "llm-v0.2-S001-primary-000",
        "llm-v0.2-S001-primary-1",
    ):
        payload = {**base, "request_id": invalid_request_id}
        with pytest.raises(ValidationError, match="v0.2 identity template"):
            type(_request_v0_2()).model_validate(payload)

    invalid_block = _block().model_copy(
        update={"evidence_id": "llm-evidence-v0.1-S001-fictional-block-001"}
    )
    payload = {**base, "evidence_blocks": (invalid_block,)}
    with pytest.raises(ValidationError, match="v0.2 evidence identity template"):
        type(_request_v0_2()).model_validate(payload)


def test_v0_2_request_cannot_enter_v0_1_manifest_identity() -> None:
    with pytest.raises(Stage4BError) as captured:
        build_manifest_invocation(_request_v0_2())

    assert captured.value.code is Stage4BErrorCode.INVALID_MANIFEST


def test_valid_v0_2_request_crosses_injected_openai_provider_boundary_once() -> None:
    request = _request_v0_2()
    raw_output = json.dumps(_payload(), sort_keys=True, separators=(",", ":"))
    client = _FakeOpenAIClient(_fake_sdk_response(raw_output))
    expected_payload = build_openai_responses_payload(request)

    response = OpenAIResponsesProvider(client=client).generate(request)
    validated = validate_provider_output(request, response)

    assert client.option_calls == [
        {
            "max_retries": 0,
            "timeout": DEFAULT_OPENAI_RESPONSES_CONFIGURATION.timeout_seconds,
        }
    ]
    assert client.responses.calls == [expected_payload]
    assert expected_payload["model"] == "gpt-5.4-mini"
    assert expected_payload["max_output_tokens"] == 4096
    assert expected_payload["reasoning"] == {"effort": "none"}
    assert expected_payload["text"]["format"]["name"] == (  # type: ignore[index]
        DEFAULT_OPENAI_RESPONSES_CONFIGURATION.response_schema_name
    )
    assert expected_payload["text"]["format"]["strict"] is True  # type: ignore[index]
    assert expected_payload["text"]["format"]["schema"] == (  # type: ignore[index]
        build_openai_candidate_schema()
    )
    assert expected_payload["store"] is False
    assert expected_payload["stream"] is False
    assert expected_payload["background"] is False
    assert expected_payload["tools"] == []
    assert expected_payload["tool_choice"] == "none"
    assert request.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID
    assert request.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID
    assert response.provider_identifier == "openai"
    assert response.retry_count == 0
    assert validated.candidate_result.model_dump(mode="json") == _payload()


class _ForbiddenClient:
    def __init__(self) -> None:
        self.access_count = 0

    def with_options(self, **_: object):
        self.access_count += 1
        raise AssertionError("client construction must not be reached")


@pytest.mark.parametrize("source_id", ("S005", "S007", "fictional"))
def test_v0_2_prohibited_sources_fail_before_provider_access(source_id: str) -> None:
    request = _request_v0_2()
    block = request.evidence_blocks[0].model_copy(
        update={
            "source_id": source_id,
            "evidence_id": f"llm-evidence-v0.2-{source_id}-fictional-block-001",
        }
    )
    request = request.model_copy(
        update={"source_id": source_id, "evidence_blocks": (block,)}
    )
    request = request.model_copy(
        update={
            "prompt_sha256": prompt_sha256(
                evidence_blocks=request.evidence_blocks,
                model_configuration_id=request.model_configuration_id,
                prompt_version="0.2",
            )
        }
    )
    request = request.model_copy(
        update={"canonical_request_sha256": canonical_request_sha256(request)}
    )
    client = _ForbiddenClient()

    with pytest.raises(Stage4BError) as captured:
        OpenAIResponsesProvider(client=client).generate(request)

    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert client.access_count == 0


def test_committed_v0_1_manifest_plan_attempt_and_failure_still_validate() -> None:
    manifest_path = REPOSITORY_ROOT / (
        "reports/llm_extraction/openai_development_manifest/"
        "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
    )
    plan_path = REPOSITORY_ROOT / (
        "reports/llm_extraction/openai_development_execution_plan/"
        "openai-gpt-5.4-mini-five-source-development-execution-plan-v0.1.json"
    )
    manifest_raw = manifest_path.read_bytes()
    plan_raw = plan_path.read_bytes()
    manifest = OpenAIDevelopmentManifestV01.model_validate_json(manifest_raw)
    plan = OpenAIDevelopmentExecutionPlanV01.model_validate_json(plan_raw)
    first = plan.invocations[0]
    marker = load_development_attempt_marker(
        REPOSITORY_ROOT / first.attempt_marker_relative_path
    )
    failure = load_development_failure_record(
        REPOSITORY_ROOT / first.failure_record_relative_path
    )

    assert development_manifest_bytes(manifest) == manifest_raw
    assert development_execution_plan_bytes(plan) == plan_raw
    assert marker.execution_id == plan.execution_id
    assert marker.request_id == first.request_id
    assert failure.execution_id == plan.execution_id
    assert failure.request_id == first.request_id
    assert failure.failure_stage == "local_parse"
