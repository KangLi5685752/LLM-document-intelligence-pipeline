"""Offline regressions for the additive Stage 4D development manifest v0.2."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.llm_extraction.cache import (
    CacheIdentityV02,
    cache_identity_sha256,
)
from document_intelligence.llm_extraction.contracts import InvocationRole
from document_intelligence.llm_extraction.errors import Stage4BError, Stage4BErrorCode
import document_intelligence.llm_extraction.openai_development_manifest as manifest_module
from document_intelligence.llm_extraction.openai_development_manifest import (
    APPROVED_SOURCE_ORDER,
    OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256,
    PARTITION_POLICY_ID_V0_2,
    PLANNED_CACHE_ROOT_V0_2,
    REPEAT_SELECTION_POLICY_ID,
    OpenAIDevelopmentManifestV01,
    OpenAIDevelopmentManifestV02,
    OpenAIDevelopmentPartitionPolicyV01,
    OpenAIDevelopmentPartitionPolicyV02,
    ReviewedContextLimitObservationV01,
    build_reviewed_context_limit_observation,
    build_reviewed_observation_binding,
    build_source_route_identity,
    canonical_lf_json_bytes,
    canonical_lf_json_sha256,
    development_manifest_bytes,
    development_manifest_bytes_v0_2,
    load_development_manifest_v0_2,
    prepare_openai_development_manifest,
    prepare_openai_development_manifest_v0_2,
)
from document_intelligence.llm_extraction.openai_preflight import (
    OpenAIDataControlsObservation,
    OpenAIPricingObservation,
)
from document_intelligence.llm_extraction.openai_provider import (
    OPENAI_MODEL_CONFIGURATION_ID,
    OPENAI_PROVIDER_CONFIGURATION_ID,
)
import document_intelligence.llm_extraction.prompting as prompting_module
from document_intelligence.llm_extraction.prompting import (
    PromptAssets,
    canonical_json_bytes,
    uppercase_sha256_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
V0_1_MANIFEST_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json"
)
V0_2_MANIFEST_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json"
)
FICTIONAL_REVIEW_TIME = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _fictional_document(
    source_id: str,
    *,
    large: bool = False,
    shared_text: bool = False,
) -> ParsedDocument:
    if large:
        texts = tuple(
            f"Fictional public administrative text {label}. " * 1500
            for label in ("A", "B", "C")
        )
    else:
        text = (
            "Fictional neutral content."
            if shared_text
            else f"Fictional neutral content for {source_id}."
        )
        texts = (text,)
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
                    "block_id": f"FICTIONAL-B{index:04d}",
                    "sequence": index,
                    "block_type": "page_text",
                    "text": text,
                    "location": {
                        "location_type": "page",
                        "location_value": str(index),
                        "page_number": index,
                    },
                }
                for index, text in enumerate(texts, start=1)
            ],
            "parse_status": "success",
        }
    )


def _document_hash(document: ParsedDocument) -> str:
    return uppercase_sha256_bytes(
        canonical_json_bytes(document.model_dump(mode="json"))
    )


def _fictional_inputs(*, equal_payloads: bool = False):
    documents = {
        source_id: _fictional_document(
            source_id,
            large=not equal_payloads and source_id == "S004",
            shared_text=equal_payloads,
        )
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
        source_title="Fictional planning pricing review",
        source_url="https://example.invalid/fictional-pricing",
        input_usd_per_million_tokens=Decimal("0.75"),
        output_usd_per_million_tokens=Decimal("4.50"),
        currency="USD",
    )
    data_controls = OpenAIDataControlsObservation(
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        source_title="Fictional data-controls review",
        source_url="https://example.invalid/fictional-data-controls",
        store_false_required=True,
        zero_retention_claimed=False,
        retention_and_abuse_monitoring_summary=(
            "Fictional controls retain the non-zero-retention warning."
        ),
    )
    pricing_review = build_reviewed_observation_binding(
        observation_kind="pricing",
        evidence_id="FICTIONAL-V02-PRICING-REVIEW",
        reviewed_by="Fictional Reviewer",
        reviewed_at_utc=FICTIONAL_REVIEW_TIME,
        observation=pricing,
    )
    data_controls_review = build_reviewed_observation_binding(
        observation_kind="data_controls",
        evidence_id="FICTIONAL-V02-DATA-CONTROLS-REVIEW",
        reviewed_by="Fictional Reviewer",
        reviewed_at_utc=FICTIONAL_REVIEW_TIME,
        observation=data_controls,
    )
    return (
        documents,
        routes,
        pricing,
        pricing_review,
        data_controls,
        data_controls_review,
    )


def _context() -> ReviewedContextLimitObservationV01:
    return build_reviewed_context_limit_observation(
        source_title="Fictional context-limit review",
        source_url="https://example.invalid/fictional-context",
        observed_at_utc=FICTIONAL_REVIEW_TIME,
        reviewer="Fictional Reviewer",
        exact_context_window_tokens=400000,
        input_output_reasoning_share_context_window=True,
    )


def _prepare(*, equal_payloads: bool = False):
    (
        documents,
        routes,
        pricing,
        pricing_review,
        data_controls,
        data_controls_review,
    ) = _fictional_inputs(equal_payloads=equal_payloads)
    return prepare_openai_development_manifest_v0_2(
        source_routes=routes,
        parsed_documents=documents,
        partition_policy=OpenAIDevelopmentPartitionPolicyV02(),
        pricing_observation=pricing,
        pricing_review=pricing_review,
        data_controls_observation=data_controls,
        data_controls_review=data_controls_review,
        context_limit_observation=_context(),
    )


def test_v0_2_manifest_inventory_identities_and_context_are_exact() -> None:
    preparation = _prepare()
    assert preparation.manifest is not None
    manifest = preparation.manifest
    primary = [
        item
        for item in manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]

    assert tuple(route.source_id for route in manifest.source_routes) == (
        "S001",
        "S002",
        "S003",
        "S004",
        "S006",
    )
    assert {item.source_id for item in primary} == set(APPROVED_SOURCE_ORDER)
    assert manifest.experiment_id == "llm-extraction-baseline-v0.2"
    assert manifest.partition_policy.policy_id == PARTITION_POLICY_ID_V0_2
    assert manifest.repeat_selection_policy.policy_id == REPEAT_SELECTION_POLICY_ID
    assert manifest.cache_policy.relative_cache_root == PLANNED_CACHE_ROOT_V0_2
    assert manifest.provider_configuration_id == OPENAI_PROVIDER_CONFIGURATION_ID
    assert manifest.model_configuration_id == OPENAI_MODEL_CONFIGURATION_ID
    assert manifest.strict_schema_sha256 == OPENAI_DEVELOPMENT_STRICT_SCHEMA_SHA256
    assert all(
        re.fullmatch(r"llm-v0\.2-S00[12346]-(?:primary|repeat)-\d{3}", item.request_id)
        for item in manifest.invocations
    )
    assert all(
        evidence.evidence_id
        == f"llm-evidence-v0.2-{item.source_id}-{evidence.block_id}"
        for item in manifest.invocations
        for evidence in item.ordered_evidence_blocks
    )
    assert all(
        item.provider_payload_bytes
        <= manifest.partition_policy.maximum_provider_payload_bytes
        for item in manifest.invocations
    )
    assert all(
        item.provider_payload_bytes + 4096
        <= manifest.context_limit_observation.exact_context_window_tokens
        for item in manifest.invocations
    )
    for item in manifest.invocations:
        identity = CacheIdentityV02(
            experiment_id="llm-extraction-baseline-v0.2",
            invocation_role=item.invocation_role,
            request_id=item.request_id,
            canonical_request_sha256=item.canonical_request_sha256,
            provider_configuration_id=manifest.provider_configuration_id,
            model_configuration_id=manifest.model_configuration_id,
            prompt_sha256=item.prompt_sha256,
            document_sha256=item.document_sha256,
        )
        assert cache_identity_sha256(identity) == item.cache_identity_sha256
    assert OpenAIDevelopmentManifestV02.model_validate_json(
        development_manifest_bytes_v0_2(manifest)
    ) == manifest


def test_v0_2_partitioning_is_deterministic_complete_and_whole_block() -> None:
    first = _prepare()
    second = _prepare()
    assert first == second
    assert first.manifest is not None
    documents = _fictional_inputs()[0]
    primary = [
        item
        for item in first.manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    for source_id in APPROVED_SOURCE_ORDER:
        observed = [
            evidence.block_id
            for item in primary
            if item.source_id == source_id
            for evidence in item.ordered_evidence_blocks
        ]
        expected = [
            block.block_id
            for block in documents[source_id].blocks
            if block.text.strip()
        ]
        assert observed == expected


def test_v0_2_builder_loads_prompt_v0_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prompting_module.load_prompt_assets
    versions: list[str] = []

    def tracked(version: str = "0.1") -> PromptAssets:
        versions.append(version)
        return original(version)

    monkeypatch.setattr(prompting_module, "load_prompt_assets", tracked)
    _prepare()
    assert versions
    assert set(versions) == {"0.2"}


def test_changed_prompt_bytes_change_request_payload_and_cache_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _prepare()
    assert original.manifest is not None
    original_loader = prompting_module.load_prompt_assets
    installed = original_loader("0.2")
    changed_assets = PromptAssets(
        system_prompt_bytes=(
            installed.system_prompt_bytes
            + b"\nFictional generic prompt identity change.\n"
        ),
        extraction_prompt_bytes=installed.extraction_prompt_bytes,
    )

    def changed(version: str = "0.1") -> PromptAssets:
        return changed_assets if version == "0.2" else original_loader(version)

    monkeypatch.setattr(prompting_module, "load_prompt_assets", changed)
    updated = _prepare()
    assert updated.manifest is not None
    before = original.manifest.invocations[0]
    after = updated.manifest.invocations[0]
    assert before.prompt_sha256 != after.prompt_sha256
    assert before.canonical_request_sha256 != after.canonical_request_sha256
    assert before.provider_payload_sha256 != after.provider_payload_sha256
    assert before.cache_identity_sha256 != after.cache_identity_sha256


def test_repeat_selection_is_recomputed_from_v0_2_payload_inventory() -> None:
    preparation = _prepare()
    assert preparation.manifest is not None
    primary = [
        item
        for item in preparation.manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    repeat = preparation.manifest.invocations[-1]
    expected = min(
        primary,
        key=lambda item: (-item.provider_payload_bytes, item.request_id),
    )
    assert repeat.invocation_role is InvocationRole.REPEAT
    assert repeat.repeated_primary_request_id == expected.request_id
    assert repeat.provider_payload_bytes == expected.provider_payload_bytes
    assert repeat.canonical_request_sha256 != expected.canonical_request_sha256
    assert repeat.cache_identity_sha256 != expected.cache_identity_sha256


def test_repeat_selection_tie_break_is_lexicographic() -> None:
    preparation = _prepare(equal_payloads=True)
    assert preparation.manifest is not None
    primary = [
        item
        for item in preparation.manifest.invocations
        if item.invocation_role is InvocationRole.PRIMARY
    ]
    assert len({item.provider_payload_bytes for item in primary}) == 1
    assert preparation.manifest.invocations[-1].repeated_primary_request_id == (
        "llm-v0.2-S001-primary-001"
    )


class _ForbiddenDocumentMapping(Mapping[str, ParsedDocument]):
    def __init__(self, prohibited_source: str) -> None:
        self._keys = ("S001", "S002", "S003", "S004", prohibited_source)
        self.value_accesses = 0

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __getitem__(self, key: str) -> ParsedDocument:
        self.value_accesses += 1
        raise AssertionError(f"document access must not occur for {key}")


@pytest.mark.parametrize("source_id", ("S005", "S007"))
def test_prohibited_source_fails_before_document_payload_or_cache_access(
    source_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, routes, pricing, pricing_review, controls, controls_review = (
        _fictional_inputs()
    )
    documents = _ForbiddenDocumentMapping(source_id)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("payload, route value, and cache access must not occur")

    monkeypatch.setattr(manifest_module, "_validate_document_route", forbidden)
    monkeypatch.setattr(manifest_module, "build_openai_responses_payload", forbidden)
    monkeypatch.setattr(manifest_module, "cache_identity_from_request", forbidden)

    with pytest.raises(Stage4BError) as captured:
        prepare_openai_development_manifest_v0_2(
            source_routes=routes,
            parsed_documents=documents,
            partition_policy=OpenAIDevelopmentPartitionPolicyV02(),
            pricing_observation=pricing,
            pricing_review=pricing_review,
            data_controls_observation=controls,
            data_controls_review=controls_review,
            context_limit_observation=_context(),
        )

    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE
    assert documents.value_accesses == 0


def test_v0_1_and_v0_2_manifest_contracts_cannot_be_relabelled() -> None:
    v0_2 = _prepare()
    assert v0_2.manifest is not None
    with pytest.raises(ValidationError):
        OpenAIDevelopmentManifestV01.model_validate(
            v0_2.manifest.model_dump(mode="python")
        )

    v0_1_content = V0_1_MANIFEST_PATH.read_bytes()
    v0_1 = OpenAIDevelopmentManifestV01.model_validate_json(v0_1_content)
    relabelled = v0_1.model_dump(mode="python")
    relabelled["experiment_id"] = "llm-extraction-baseline-v0.2"
    with pytest.raises(ValidationError):
        OpenAIDevelopmentManifestV02.model_validate(relabelled)
    assert development_manifest_bytes(v0_1) == v0_1_content


def test_v0_2_manifest_lf_crlf_hash_and_loader_are_equivalent(
    tmp_path: Path,
) -> None:
    preparation = _prepare()
    assert preparation.manifest is not None
    lf = development_manifest_bytes_v0_2(preparation.manifest)
    crlf = lf.replace(b"\n", b"\r\n")
    assert canonical_lf_json_sha256(lf) == canonical_lf_json_sha256(crlf)

    lf_path = tmp_path / "manifest-lf.json"
    crlf_path = tmp_path / "manifest-crlf.json"
    lf_path.write_bytes(lf)
    crlf_path.write_bytes(crlf)
    assert load_development_manifest_v0_2(lf_path) == preparation.manifest
    assert load_development_manifest_v0_2(crlf_path) == preparation.manifest


def test_generated_v0_2_manifest_round_trips_when_present() -> None:
    if not V0_2_MANIFEST_PATH.exists():
        pytest.skip("real v0.2 manifest is generated only after offline gates pass")
    loaded = load_development_manifest_v0_2(V0_2_MANIFEST_PATH)
    assert development_manifest_bytes_v0_2(loaded) == canonical_lf_json_bytes(
        V0_2_MANIFEST_PATH.read_bytes()
    )
