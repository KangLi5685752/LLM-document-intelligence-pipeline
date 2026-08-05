"""Offline Stage 4D development-manifest tests using fictional documents."""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.llm_extraction.cache import (
    CacheIdentity,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
from document_intelligence.llm_extraction.manifest import RequestManifest
import document_intelligence.llm_extraction.openai_development_manifest as manifest_module
from document_intelligence.llm_extraction.openai_development_manifest import (
    APPROVED_SOURCE_ORDER,
    CONSERVATIVE_CONTEXT_SAFETY_RULE,
    PARTITION_POLICY_ID,
    PLANNED_AUTHORIZATION_CAP_USD,
    REPEAT_SELECTION_POLICY_ID,
    OpenAIDevelopmentCachePolicyV01,
    OpenAIDevelopmentInvocationIdentityV01,
    OpenAIDevelopmentManifestPreparationV01,
    OpenAIDevelopmentManifestV01,
    OpenAIDevelopmentPartitionPolicyV01,
    OpenAIDevelopmentRepeatSelectionPolicyV01,
    OpenAIDevelopmentSourceRouteV01,
    ReviewedContextLimitObservationV01,
    approved_parsed_document_relative_path,
    build_reviewed_context_limit_observation,
    build_reviewed_observation_binding,
    build_source_route_identity,
    canonical_lf_json_bytes,
    canonical_lf_json_sha256,
    development_manifest_bytes,
    load_approved_parsed_document,
    prepare_openai_development_manifest,
    validate_successful_preflight_evidence,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_ROOT = REPOSITORY_ROOT / "reports/llm_extraction/openai_preflight"
FICTIONAL_REVIEW_TIME = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def _fictional_document(
    source_id: str,
    *,
    texts: tuple[str, ...] | None = None,
    large: bool = False,
) -> ParsedDocument:
    selected_texts = texts
    if selected_texts is None:
        selected_texts = (
            (
                "Fictional public administrative text A. " * 1500,
                "Fictional public administrative text B. " * 1500,
                "Fictional public administrative text C. " * 1500,
            )
            if large
            else (f"Fictional neutral content for {source_id}.",)
        )
    return ParsedDocument.model_validate(
        {
            "schema_version": "0.1",
            "document_id": f"FICTIONAL-DOC-{source_id}",
            "source_id": source_id,
            "source_format": "PDF",
            "filename": f"fictional-{source_id}.pdf",
            "checksum_sha256": uppercase_sha256_bytes(
                f"fictional-document-{source_id}".encode("utf-8")
            ),
            "blocks": [
                {
                    "block_id": f"FICTIONAL-{source_id}-B{index:04d}",
                    "sequence": index,
                    "block_type": "page_text",
                    "text": text,
                    "location": {
                        "location_type": "page",
                        "location_value": str(index),
                        "page_number": index,
                    },
                }
                for index, text in enumerate(selected_texts, start=1)
            ],
            "parse_status": "success",
        }
    )


def _document_hash(document: ParsedDocument) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(document.model_dump(mode="json"))
    )


def _fictional_inputs():
    documents = {
        source_id: _fictional_document(source_id, large=source_id == "S004")
        for source_id in APPROVED_SOURCE_ORDER
    }
    routes = tuple(
        build_source_route_identity(
            source_id=source_id,
            parsed_document_relative_path=f"fictional/parsed/{source_id}.json",
            document_sha256=documents[source_id].checksum_sha256,
            parsed_document_canonical_sha256=_document_hash(documents[source_id]),
            parser_commit="a" * 40,
        )
        for source_id in APPROVED_SOURCE_ORDER
    )
    pricing = OpenAIPricingObservation(
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        source_title="Fictional pricing review",
        source_url="https://example.invalid/fictional-pricing",
        input_usd_per_million_tokens=Decimal("0.75"),
        output_usd_per_million_tokens=Decimal("4.50"),
        currency="USD",
    )
    controls = OpenAIDataControlsObservation(
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        source_title="Fictional data-controls review",
        source_url="https://example.invalid/fictional-data-controls",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary=(
            "Fictional terms retain the non-zero-retention warning."
        ),
    )
    pricing_review = build_reviewed_observation_binding(
        observation_kind="pricing",
        evidence_id="FICTIONAL-PRICING-REVIEW-001",
        reviewed_by="Fictional Reviewer",
        reviewed_at_utc=FICTIONAL_REVIEW_TIME,
        observation=pricing,
    )
    controls_review = build_reviewed_observation_binding(
        observation_kind="data_controls",
        evidence_id="FICTIONAL-DATA-CONTROLS-REVIEW-001",
        reviewed_by="Fictional Reviewer",
        reviewed_at_utc=FICTIONAL_REVIEW_TIME,
        observation=controls,
    )
    policy = OpenAIDevelopmentPartitionPolicyV01()
    return (
        documents,
        routes,
        pricing,
        pricing_review,
        controls,
        controls_review,
        policy,
    )


def _fictional_context(
    token_boundary: int = 1_000_000,
    *,
    shared: bool = True,
) -> ReviewedContextLimitObservationV01:
    return build_reviewed_context_limit_observation(
        source_title="Fictional context-limit review",
        source_url="https://example.invalid/fictional-context",
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        reviewer="Fictional Reviewer",
        exact_context_window_tokens=token_boundary,
        input_output_reasoning_share_context_window=shared,
    )


def _prepare(*, context: ReviewedContextLimitObservationV01 | None = None):
    (
        documents,
        routes,
        pricing,
        pricing_review,
        controls,
        controls_review,
        policy,
    ) = _fictional_inputs()
    return prepare_openai_development_manifest(
        source_routes=routes,
        parsed_documents=documents,
        partition_policy=policy,
        pricing_observation=pricing,
        pricing_review=pricing_review,
        data_controls_observation=controls,
        data_controls_review=controls_review,
        context_limit_observation=context,
    )


def _recomputed_manifest_payload(
    manifest: OpenAIDevelopmentManifestV01,
    **updates: object,
) -> dict[str, object]:
    provisional = manifest.model_copy(
        update={**updates, "manifest_sha256": "0" * 64}
    )
    payload = provisional.model_dump(mode="python")
    payload["manifest_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(
            provisional.model_dump(mode="json", exclude={"manifest_sha256"})
        )
        + b"\n"
    )
    return payload


def _recomputed_preparation_payload(
    preparation: OpenAIDevelopmentManifestPreparationV01,
    **updates: object,
) -> dict[str, object]:
    provisional = preparation.model_copy(
        update={**updates, "preparation_sha256": "0" * 64}
    )
    payload = provisional.model_dump(mode="python")
    payload["preparation_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(
            provisional.model_dump(mode="json", exclude={"preparation_sha256"})
        )
        + b"\n"
    )
    return payload


def _recomputed_route(
    route: OpenAIDevelopmentSourceRouteV01,
    **updates: object,
) -> OpenAIDevelopmentSourceRouteV01:
    provisional = route.model_copy(update={**updates, "route_sha256": "0" * 64})
    payload = provisional.model_dump(mode="python")
    payload["route_sha256"] = uppercase_sha256_bytes(
        canonical_json_bytes(
            provisional.model_dump(mode="json", exclude={"route_sha256"})
        )
        + b"\n"
    )
    return OpenAIDevelopmentSourceRouteV01.model_validate(payload)


def _with_recomputed_cache_identity(
    invocation: OpenAIDevelopmentInvocationIdentityV01,
    **updates: object,
) -> OpenAIDevelopmentInvocationIdentityV01:
    changed = invocation.model_copy(update=updates)
    identity = CacheIdentity(
        experiment_id=manifest_module.EXPERIMENT_ID,
        invocation_role=changed.invocation_role,
        request_id=changed.request_id,
        canonical_request_sha256=changed.canonical_request_sha256,
        provider_configuration_id=(
            manifest_module.OPENAI_PROVIDER_CONFIGURATION_ID
        ),
        model_configuration_id=manifest_module.OPENAI_MODEL_CONFIGURATION_ID,
        prompt_sha256=changed.prompt_sha256,
        document_sha256=changed.document_sha256,
    )
    return OpenAIDevelopmentInvocationIdentityV01.model_validate(
        changed.model_copy(
            update={"cache_identity_sha256": cache_identity_sha256(identity)}
        ).model_dump(mode="python")
    )


def _with_overlapping_primary_evidence(
    invocations: tuple[OpenAIDevelopmentInvocationIdentityV01, ...],
) -> tuple[OpenAIDevelopmentInvocationIdentityV01, ...]:
    source_primaries = [
        item
        for item in invocations
        if item.source_id == "S004" and item.invocation_role.value == "primary"
    ]
    assert len(source_primaries) > 1
    first, second = source_primaries[:2]
    changed_blocks = (
        first.ordered_evidence_blocks[-1],
        *second.ordered_evidence_blocks[1:],
    )
    changed_second = OpenAIDevelopmentInvocationIdentityV01.model_validate(
        second.model_copy(
            update={"ordered_evidence_blocks": changed_blocks}
        ).model_dump(mode="python")
    )
    return tuple(
        changed_second if item.request_id == second.request_id else item
        for item in invocations
    )


def _single_block_document_with_payload_size(target_size: int) -> ParsedDocument:
    seed = _fictional_document("S001", texts=("A",))
    block = manifest_module._approved_blocks(seed)[0]
    request = manifest_module._request(
        source_id="S001",
        document_sha256=seed.checksum_sha256,
        role=manifest_module.InvocationRole.PRIMARY,
        ordinal=1,
        blocks=(block,),
    )
    seed_size = len(manifest_module._request_measurements(request)[2])
    text_length = target_size - (seed_size - 1)
    assert text_length > 0
    document = _fictional_document("S001", texts=("A" * text_length,))
    rebuilt_block = manifest_module._approved_blocks(document)[0]
    rebuilt_request = manifest_module._request(
        source_id="S001",
        document_sha256=document.checksum_sha256,
        role=manifest_module.InvocationRole.PRIMARY,
        ordinal=1,
        blocks=(rebuilt_block,),
    )
    assert len(manifest_module._request_measurements(rebuilt_request)[2]) == target_size
    return document


def test_canonical_lf_content_hash_is_independent_of_checkout_line_endings() -> None:
    lf = b'{"alpha":1,"nested":{"beta":2}}\n'
    crlf = b'{"alpha":1,"nested":{"beta":2}}\r\n\r\n'

    assert canonical_lf_json_bytes(lf).endswith(b"\n")
    assert not canonical_lf_json_bytes(lf).endswith(b"\n\n")
    assert canonical_lf_json_bytes(lf) == canonical_lf_json_bytes(crlf)
    assert canonical_lf_json_sha256(lf) == canonical_lf_json_sha256(crlf)


def test_canonical_lf_content_rejects_bom_duplicate_keys_and_nonfinite() -> None:
    with pytest.raises(ValueError, match="BOM"):
        canonical_lf_json_bytes(b'\xef\xbb\xbf{"value":1}\n')
    with pytest.raises(ValueError, match="duplicate"):
        canonical_lf_json_bytes(b'{"value":1,"value":2}\n')
    with pytest.raises(ValueError, match="non-finite"):
        canonical_lf_json_bytes(b'{"value":NaN}\n')


def test_committed_v0_3_preflight_binding_uses_canonical_lf_content() -> None:
    attempt = PREFLIGHT_ROOT / (
        "openai-gpt-5.4-mini-synthetic-preflight-v0.3.attempt.json"
    )
    success = PREFLIGHT_ROOT / (
        "openai-gpt-5.4-mini-synthetic-preflight-v0.3.record.json"
    )

    validate_successful_preflight_evidence(
        attempt_content=attempt.read_bytes(),
        success_record_content=success.read_bytes(),
    )
    assert canonical_lf_json_sha256(attempt.read_bytes()) == (
        "94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119"
    )
    assert canonical_lf_json_sha256(success.read_bytes()) == (
        "C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2"
    )


def test_existing_stage_4c_request_manifest_contract_is_unchanged() -> None:
    assert tuple(RequestManifest.model_fields) == (
        "manifest_schema_version",
        "experiment_id",
        "prompt_version",
        "prompt_sha256s",
        "output_contract_id",
        "provider_configuration_id",
        "model_configuration_id",
        "invocations",
        "manifest_sha256",
    )


def test_reviewed_context_observation_is_strict_self_hashed_and_fictional() -> None:
    observation = _fictional_context()

    assert observation.requested_model_alias == "gpt-5.4-mini"
    assert observation.returned_model_identifier == "gpt-5.4-mini-2026-03-17"
    assert observation.exact_safety_rule == CONSERVATIVE_CONTEXT_SAFETY_RULE
    assert re.fullmatch(r"[0-9A-F]{64}", observation.observation_sha256)
    with pytest.raises(ValidationError, match="frozen_instance"):
        observation.reviewer = "Another Reviewer"  # type: ignore[misc]

    payload = observation.model_dump(mode="python")
    payload["observation_sha256"] = "F" * 64
    with pytest.raises(ValidationError, match="observation_sha256"):
        ReviewedContextLimitObservationV01.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("max_output_tokens_4096_supported", False),
        ("reasoning_effort_none_supported", False),
        ("token_admission_method", "fictional_other_method"),
        ("exact_safety_rule", "fictional weaker rule"),
    ),
)
def test_context_observation_rejects_weakened_admission_fields(
    field_name: str,
    value: object,
) -> None:
    payload = _fictional_context().model_dump(mode="python")
    payload[field_name] = value
    with pytest.raises(ValidationError):
        ReviewedContextLimitObservationV01.model_validate(payload)


@pytest.mark.parametrize("value", (True, 1.5, "1000000"))
def test_context_boundary_requires_an_exact_integer(value: object) -> None:
    with pytest.raises(ValidationError, match="must use an integer"):
        ReviewedContextLimitObservationV01.model_validate(
            {
                "source_title": "Fictional context review",
                "source_url": "https://example.invalid/context",
                "observed_at_utc": FICTIONAL_REVIEW_TIME,
                "reviewer": "Fictional Reviewer",
                "exact_context_window_tokens": value,
                "input_output_reasoning_share_context_window": True,
                "max_output_tokens_4096_supported": True,
                "reasoning_effort_none_supported": True,
                "observation_sha256": "0" * 64,
            }
        )


def test_preparation_without_context_is_valid_but_not_review_eligible() -> None:
    preparation = _prepare()

    assert preparation.readiness_status == "blocked"
    assert preparation.blocking_reasons == (
        "reviewed_context_limit_observation_missing",
    )
    assert preparation.context_limit_observation is None
    assert preparation.manifest is None
    assert re.fullmatch(r"[0-9A-F]{64}", preparation.preparation_sha256)


def test_fictional_context_produces_deterministic_hash_only_manifest() -> None:
    first = _prepare(context=_fictional_context())
    second = _prepare(context=_fictional_context())
    assert first.manifest is not None
    assert second.manifest is not None
    assert first.manifest == second.manifest
    assert first.manifest.manifest_review_status == "pending_independent_review"
    assert first.manifest.execution_authorization_required is True
    assert first.manifest.execution_authorization_status == "not_provided"
    assert "execution_authorization_id" not in type(first.manifest).model_fields
    assert "real_provider_execution_authorized" not in type(first.manifest).model_fields

    serialized = development_manifest_bytes(first.manifest)
    assert serialized.endswith(b"\n")
    assert not serialized.endswith(b"\n\n")
    assert not serialized.startswith(b"\xef\xbb\xbf")
    assert b"Fictional public administrative text" not in serialized
    assert b"raw_prompt" not in serialized
    assert b"provider_request_body" not in serialized
    assert b"api_key" not in serialized
    assert (
        first.manifest.access_policy.owner_outcomes_as_prompt_input_authorized
        is False
    )
    assert (
        b'"owner_outcomes_as_prompt_input_authorized":false'
        in serialized
    )


def test_context_preparation_revalidates_with_its_exact_nested_manifest() -> None:
    preparation = _prepare(context=_fictional_context())
    payload = _recomputed_preparation_payload(preparation)

    assert OpenAIDevelopmentManifestPreparationV01.model_validate(payload) == (
        preparation
    )


def test_context_preparation_rejects_separately_valid_nested_manifest() -> None:
    preparation = _prepare(context=_fictional_context(1_000_000))
    different = _prepare(context=_fictional_context(1_000_001))
    assert preparation.manifest is not None
    assert different.manifest is not None
    assert preparation.manifest != different.manifest

    different_manifest = OpenAIDevelopmentManifestV01.model_validate(
        _recomputed_manifest_payload(different.manifest)
    )
    payload = _recomputed_preparation_payload(
        preparation,
        manifest=different_manifest,
    )

    with pytest.raises(
        ValidationError,
        match="nested manifest context_limit_observation.*preparation",
    ):
        OpenAIDevelopmentManifestPreparationV01.model_validate(payload)


def test_models_are_frozen_and_reject_extra_fields() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    with pytest.raises(ValidationError, match="frozen_instance"):
        preparation.manifest.manifest_review_status = "changed"  # type: ignore[misc]
    payload = preparation.manifest.model_dump(mode="python")
    payload["extra_field"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("reasoning_effort", "low"),
        ("max_output_tokens", 4095),
        ("strict_json_schema", False),
        ("store", True),
        ("stream", True),
        ("background", True),
        ("tools", ("fictional-tool",)),
        ("tool_choice", "auto"),
        ("provider_side_retries", 1),
        ("response_timeout_seconds", 121),
    ),
)
def test_provider_controls_reject_every_changed_value(
    field_name: str,
    value: object,
) -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    controls_type = type(preparation.manifest.provider_controls)
    payload = preparation.manifest.provider_controls.model_dump(mode="python")
    payload[field_name] = value
    with pytest.raises(ValidationError):
        controls_type.model_validate(payload)


def test_partition_and_repeat_policy_ids_are_exact() -> None:
    assert OpenAIDevelopmentPartitionPolicyV01().policy_id == PARTITION_POLICY_ID
    assert (
        OpenAIDevelopmentRepeatSelectionPolicyV01().policy_id
        == REPEAT_SELECTION_POLICY_ID
    )


@pytest.mark.parametrize("value", (199999, 200001, True, "200000"))
def test_partition_payload_ceiling_is_exact_and_not_caller_overridable(
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        OpenAIDevelopmentPartitionPolicyV01.model_validate(
            {"maximum_provider_payload_bytes": value}
        )


def test_exact_200000_byte_single_block_is_accepted() -> None:
    document = _single_block_document_with_payload_size(200000)
    requests = manifest_module._partition_primary_requests(
        document=document,
        policy=OpenAIDevelopmentPartitionPolicyV01(),
    )
    assert len(requests) == 1
    assert len(manifest_module._request_measurements(requests[0])[2]) == 200000


def test_200001_byte_single_block_fails_closed() -> None:
    document = _single_block_document_with_payload_size(200001)
    with pytest.raises(Stage4BError) as captured:
        manifest_module._partition_primary_requests(
            document=document,
            policy=OpenAIDevelopmentPartitionPolicyV01(),
        )
    assert captured.value.code is Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED


def test_partitioning_is_deterministic_complete_and_does_not_truncate_blocks() -> None:
    first = _prepare(context=_fictional_context())
    second = _prepare(context=_fictional_context())
    assert first.manifest is not None
    assert second.manifest is not None
    assert first.manifest.invocations == second.manifest.invocations

    primary = [
        item
        for item in first.manifest.invocations
        if item.invocation_role.value == "primary"
    ]
    s004 = [item for item in primary if item.source_id == "S004"]
    assert len(s004) > 1
    flattened = [
        identity.block_id
        for invocation in s004
        for identity in invocation.ordered_evidence_blocks
    ]
    assert flattened == [
        "FICTIONAL-S004-B0001",
        "FICTIONAL-S004-B0002",
        "FICTIONAL-S004-B0003",
    ]
    assert all(
        item.provider_payload_bytes <= 200000
        for item in first.manifest.invocations
    )


def test_partitioning_calls_production_request_and_payload_builders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_calls = 0
    payload_calls = 0
    original_request = manifest_module.build_request_envelope
    original_payload = manifest_module.build_openai_responses_payload

    def counted_request(*args: Any, **kwargs: Any):
        nonlocal request_calls
        request_calls += 1
        return original_request(*args, **kwargs)

    def counted_payload(*args: Any, **kwargs: Any):
        nonlocal payload_calls
        payload_calls += 1
        return original_payload(*args, **kwargs)

    monkeypatch.setattr(manifest_module, "build_request_envelope", counted_request)
    monkeypatch.setattr(manifest_module, "build_openai_responses_payload", counted_payload)
    _prepare()
    assert request_calls > 0
    assert payload_calls > 0


def test_repeat_is_last_predeclared_and_has_distinct_request_and_cache_identity() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    primary = {
        item.request_id: item
        for item in manifest.invocations
        if item.invocation_role.value == "primary"
    }
    repeat = manifest.invocations[-1]
    expected = min(
        primary.values(),
        key=lambda item: (-item.provider_payload_bytes, item.request_id),
    )

    assert repeat.invocation_role.value == "repeat"
    assert repeat.repeated_primary_request_id == expected.request_id
    assert repeat.request_id != expected.request_id
    assert repeat.canonical_request_sha256 != expected.canonical_request_sha256
    assert repeat.cache_identity_sha256 != expected.cache_identity_sha256
    assert repeat.prompt_sha256 == expected.prompt_sha256
    assert repeat.provider_payload_sha256 == expected.provider_payload_sha256
    assert repeat.parsed_document_canonical_sha256 == (
        expected.parsed_document_canonical_sha256
    )


def test_repeat_tie_break_uses_lexicographically_smallest_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_doc = _fictional_document("S001")
    second_doc = _fictional_document("S002")
    first = manifest_module._partition_primary_requests(
        document=first_doc,
        policy=OpenAIDevelopmentPartitionPolicyV01(),
    )[0]
    second = manifest_module._partition_primary_requests(
        document=second_doc,
        policy=OpenAIDevelopmentPartitionPolicyV01(),
    )[0]
    original = manifest_module._request_measurements

    def equal_payload(request):
        prompt, request_bytes, _ = original(request)
        return prompt, request_bytes, b"x" * 100

    monkeypatch.setattr(manifest_module, "_request_measurements", equal_payload)
    _, selected = manifest_module._repeat_request((second, first))
    assert selected == min(first.request_id, second.request_id)


def test_context_admission_always_reserves_4096_tokens_even_when_not_shared() -> None:
    blocked = _prepare()
    maximum_payload = max(item.provider_payload_bytes for item in blocked.invocations)
    context = _fictional_context(maximum_payload + 4095, shared=False)
    with pytest.raises(ValidationError, match="reviewed context boundary"):
        _prepare(context=context)


def test_context_admission_accepts_exact_payload_plus_4096_boundary() -> None:
    blocked = _prepare()
    maximum_payload = max(item.provider_payload_bytes for item in blocked.invocations)
    preparation = _prepare(context=_fictional_context(maximum_payload + 4096))
    assert preparation.manifest is not None


def test_cost_plan_uses_planning_and_conservative_methods_and_fixed_cap() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    budget = preparation.manifest.execution_budget
    assert budget.planned_authorization_cap_usd == PLANNED_AUTHORIZATION_CAP_USD
    assert budget.broad_project_cost_ceiling_usd == Decimal("25")
    assert budget.maximum_retries_per_invocation == 0
    assert budget.provider_side_retries == 0
    assert budget.maximum_provider_calls == len(preparation.manifest.invocations)
    assert budget.maximum_total_attempts == budget.maximum_provider_calls
    assert budget.repeat_request_count == 1
    assert budget.aggregate_planning_cost_usd <= (
        budget.aggregate_conservative_cost_ceiling_usd
    )
    assert budget.aggregate_conservative_cost_ceiling_usd <= Decimal("1.25")
    for item in preparation.manifest.invocations:
        assert item.planning_input_token_estimate == (
            item.provider_payload_bytes + 3
        ) // 4
        assert item.conservative_input_token_proxy == item.provider_payload_bytes
        assert item.maximum_output_tokens == 4096
        assert item.planning_cost_ceiling_usd <= item.conservative_call_ceiling_usd


def test_cost_plan_fails_when_fictional_rates_exceed_fixed_cap() -> None:
    (
        documents,
        routes,
        _,
        _,
        controls,
        controls_review,
        policy,
    ) = _fictional_inputs()
    expensive = OpenAIPricingObservation(
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        source_title="Fictional expensive pricing",
        source_url="https://example.invalid/expensive",
        input_usd_per_million_tokens=Decimal("1000"),
        output_usd_per_million_tokens=Decimal("1000"),
        currency="USD",
    )
    expensive_review = build_reviewed_observation_binding(
        observation_kind="pricing",
        evidence_id="FICTIONAL-EXPENSIVE-PRICING",
        reviewed_by="Fictional Reviewer",
        reviewed_at_utc=FICTIONAL_REVIEW_TIME,
        observation=expensive,
    )
    with pytest.raises(Stage4BError) as captured:
        prepare_openai_development_manifest(
            source_routes=routes,
            parsed_documents=documents,
            partition_policy=policy,
            pricing_observation=expensive,
            pricing_review=expensive_review,
            data_controls_observation=controls,
            data_controls_review=controls_review,
        )
    assert captured.value.code is Stage4BErrorCode.COST_BUDGET_EXCEEDED


def test_review_bindings_must_match_their_observations() -> None:
    (
        documents,
        routes,
        pricing,
        pricing_review,
        controls,
        controls_review,
        policy,
    ) = _fictional_inputs()
    wrong_review = pricing_review.model_copy(
        update={"observation_sha256": "F" * 64}
    )
    with pytest.raises(Stage4BError) as captured:
        prepare_openai_development_manifest(
            source_routes=routes,
            parsed_documents=documents,
            partition_policy=policy,
            pricing_observation=pricing,
            pricing_review=wrong_review,
            data_controls_observation=controls,
            data_controls_review=controls_review,
        )
    assert captured.value.code is Stage4BErrorCode.INVALID_MANIFEST


def test_manifest_rejects_recomputed_budget_drift() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    changed_budget = preparation.manifest.execution_budget.model_copy(
        update={
            "maximum_total_attempts": (
                preparation.manifest.execution_budget.maximum_total_attempts + 1
            )
        }
    )
    payload = _recomputed_manifest_payload(
        preparation.manifest,
        execution_budget=changed_budget,
    )
    with pytest.raises(ValidationError, match="execution budget"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_manifest_rejects_recomputed_cache_identity_hash_drift() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    changed_first = manifest.invocations[0].model_copy(
        update={"cache_identity_sha256": "0" * 64}
    )
    payload = _recomputed_manifest_payload(
        manifest,
        invocations=(changed_first, *manifest.invocations[1:]),
    )
    with pytest.raises(ValidationError, match="serialized invocation"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_manifest_rejects_route_and_invocation_document_hash_drift() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    changed_route = _recomputed_route(
        manifest.source_routes[0],
        document_sha256="F" * 64,
    )
    payload = _recomputed_manifest_payload(
        manifest,
        source_routes=(changed_route, *manifest.source_routes[1:]),
    )
    with pytest.raises(ValidationError, match="document_sha256.*route"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_manifest_rejects_route_and_invocation_parsed_hash_drift() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    changed_route = _recomputed_route(
        manifest.source_routes[0],
        parsed_document_canonical_sha256="E" * 64,
    )
    payload = _recomputed_manifest_payload(
        manifest,
        source_routes=(changed_route, *manifest.source_routes[1:]),
    )
    with pytest.raises(
        ValidationError,
        match="parsed_document_canonical_sha256.*route",
    ):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_manifest_rejects_skipped_primary_partition_ordinal() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    first = manifest.invocations[0]
    changed_first = _with_recomputed_cache_identity(
        first,
        request_id=f"llm-v0.1-{first.source_id}-primary-002",
    )
    payload = _recomputed_manifest_payload(
        manifest,
        invocations=(changed_first, *manifest.invocations[1:]),
    )
    with pytest.raises(ValidationError, match="exactly 001..N"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_manifest_rejects_overlapping_primary_evidence_inventory() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    payload = _recomputed_manifest_payload(
        manifest,
        invocations=_with_overlapping_primary_evidence(manifest.invocations),
    )
    with pytest.raises(ValidationError, match="block IDs.*unique"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


def test_blocked_preparation_rejects_overlapping_primary_evidence_inventory() -> None:
    preparation = _prepare()
    assert preparation.context_limit_observation is None
    assert preparation.manifest is None
    payload = _recomputed_preparation_payload(
        preparation,
        invocations=_with_overlapping_primary_evidence(preparation.invocations),
    )
    with pytest.raises(ValidationError, match="block IDs.*unique"):
        OpenAIDevelopmentManifestPreparationV01.model_validate(payload)


def test_manifest_rejects_nonmaximal_repeat_selection() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    manifest = preparation.manifest
    primary = [
        item
        for item in manifest.invocations
        if item.invocation_role.value == "primary"
    ]
    repeat = manifest.invocations[-1]
    alternative = min(
        primary,
        key=lambda item: (item.provider_payload_bytes, item.request_id),
    )
    changed_repeat = _with_recomputed_cache_identity(
        repeat,
        source_id=alternative.source_id,
        request_id=f"llm-v0.1-{alternative.source_id}-repeat-001",
        repeated_primary_request_id=alternative.request_id,
        block_count=alternative.block_count,
        ordered_evidence_blocks=alternative.ordered_evidence_blocks,
        total_supplied_text_bytes=alternative.total_supplied_text_bytes,
        canonical_prompt_bytes=alternative.canonical_prompt_bytes,
        canonical_request_bytes=alternative.canonical_request_bytes,
        provider_payload_bytes=alternative.provider_payload_bytes,
        document_sha256=alternative.document_sha256,
        parsed_document_canonical_sha256=(
            alternative.parsed_document_canonical_sha256
        ),
        prompt_sha256=alternative.prompt_sha256,
        canonical_request_sha256="F" * 64,
        provider_payload_sha256=alternative.provider_payload_sha256,
        planning_input_token_estimate=alternative.planning_input_token_estimate,
        conservative_input_token_proxy=alternative.conservative_input_token_proxy,
        maximum_output_cost_usd=alternative.maximum_output_cost_usd,
        planning_cost_ceiling_usd=alternative.planning_cost_ceiling_usd,
        conservative_call_ceiling_usd=(alternative.conservative_call_ceiling_usd),
    )
    changed_invocations = (*manifest.invocations[:-1], changed_repeat)
    payload = _recomputed_manifest_payload(
        manifest,
        invocations=changed_invocations,
    )
    with pytest.raises(ValidationError, match="largest deterministic primary"):
        OpenAIDevelopmentManifestV01.model_validate(payload)


@pytest.mark.parametrize("source_id", ("S005", "S007", "S999"))
def test_prohibited_source_is_rejected_before_path_validation(
    source_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_path(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        raise AssertionError("path validation must not occur")

    monkeypatch.setattr(
        manifest_module,
        "_validate_repository_relative_path",
        forbidden_path,
    )
    with pytest.raises(Stage4BError) as captured:
        approved_parsed_document_relative_path(
            source_id,
            "fictional/parsed/source.json",
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert calls == 0


@pytest.mark.parametrize("source_id", ("S005", "S007", "S999"))
def test_loader_denies_source_before_route_or_filesystem_activity(
    source_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_filesystem(*args: Any, **kwargs: Any):
        nonlocal calls
        calls += 1
        raise AssertionError("filesystem access must not occur")

    monkeypatch.setattr(manifest_module, "_safe_existing_file", forbidden_filesystem)
    with pytest.raises(Stage4BError) as captured:
        load_approved_parsed_document(
            repository_root=tmp_path,
            requested_source_id=source_id,
            route=object(),  # type: ignore[arg-type]
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert calls == 0


@pytest.mark.parametrize(
    "value",
    (
        "/absolute/cache/",
        "C:/absolute/cache/",
        "//server/share/cache/",
        "\\\\?\\C:\\device\\cache\\",
        "../escaping/cache/",
        ".cache/no-trailing-slash",
    ),
)
def test_cache_policy_rejects_absolute_unc_device_and_escaping_paths(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        OpenAIDevelopmentCachePolicyV01.model_validate(
            {"relative_cache_root": value}
        )


def test_fictional_approved_route_loads_after_source_hash_and_schema_checks(
    tmp_path: Path,
) -> None:
    document = _fictional_document("S001")
    relative_value = approved_parsed_document_relative_path(
        "S001",
        "fictional/parsed/S001.json",
    )
    target = tmp_path.joinpath(*Path(relative_value).parts)
    target.parent.mkdir(parents=True)
    target.write_bytes(canonical_json_bytes(document.model_dump(mode="json")) + b"\n")
    route = build_source_route_identity(
        source_id="S001",
        parsed_document_relative_path=relative_value,
        document_sha256=document.checksum_sha256,
        parsed_document_canonical_sha256=_document_hash(document),
        parser_commit="b" * 40,
    )
    loaded = load_approved_parsed_document(
        repository_root=tmp_path,
        requested_source_id="S001",
        route=route,
    )
    assert loaded == document


def test_fictional_route_rejects_unsafe_ancestor_without_partial_output(
    tmp_path: Path,
) -> None:
    document = _fictional_document("S001")
    outside = tmp_path / "outside"
    outside.mkdir()
    fictional = tmp_path / "fictional"
    try:
        fictional.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this platform cannot create the required directory link")
    route = build_source_route_identity(
        source_id="S001",
        parsed_document_relative_path="fictional/parsed/S001.json",
        document_sha256=document.checksum_sha256,
        parsed_document_canonical_sha256=_document_hash(document),
        parser_commit="b" * 40,
    )
    with pytest.raises(Stage4BError) as captured:
        load_approved_parsed_document(
            repository_root=tmp_path,
            requested_source_id="S001",
            route=route,
        )
    assert captured.value.code is Stage4BErrorCode.INVALID_MANIFEST
    assert list(outside.iterdir()) == []


def test_invocations_bind_route_hashes_request_formats_and_evidence_formats() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    route_hashes = {
        route.source_id: route.parsed_document_canonical_sha256
        for route in preparation.manifest.source_routes
    }
    for item in preparation.manifest.invocations:
        assert item.parsed_document_canonical_sha256 == route_hashes[item.source_id]
        if item.invocation_role.value == "primary":
            assert re.fullmatch(
                rf"llm-v0\.1-{item.source_id}-primary-[0-9]{{3}}",
                item.request_id,
            )
        else:
            assert item.request_id == f"llm-v0.1-{item.source_id}-repeat-001"
        for evidence in item.ordered_evidence_blocks:
            assert evidence.evidence_id == (
                f"llm-evidence-v0.1-{item.source_id}-{evidence.block_id}"
            )


def test_primary_invocation_order_is_source_then_partition_ordinal() -> None:
    preparation = _prepare(context=_fictional_context())
    assert preparation.manifest is not None
    primary = [
        item
        for item in preparation.manifest.invocations
        if item.invocation_role.value == "primary"
    ]
    source_rank = {
        source_id: index for index, source_id in enumerate(APPROVED_SOURCE_ORDER)
    }
    assert primary == sorted(
        primary,
        key=lambda item: (
            source_rank[item.source_id],
            int(item.request_id.rsplit("-", 1)[-1]),
        ),
    )


def test_preparation_rejects_extra_source() -> None:
    (
        documents,
        routes,
        pricing,
        pricing_review,
        controls,
        controls_review,
        policy,
    ) = _fictional_inputs()
    documents["S007"] = _fictional_document("S007")
    with pytest.raises(Stage4BError) as captured:
        prepare_openai_development_manifest(
            source_routes=routes,
            parsed_documents=documents,
            partition_policy=policy,
            pricing_observation=pricing,
            pricing_review=pricing_review,
            data_controls_observation=controls,
            data_controls_review=controls_review,
        )
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE


def test_module_has_no_gold_matcher_evaluation_client_or_network_imports() -> None:
    source = Path(manifest_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden_segments = (
        "baseline_gold",
        "matching",
        "evaluation",
        "openai.OpenAI",
        "requests",
        "httpx",
    )
    assert not [
        name
        for name in imported
        if any(segment in name for segment in forbidden_segments)
    ]
    assert "artifacts/annotations/public_gold_parsed" not in source
    assert "400000" not in source
